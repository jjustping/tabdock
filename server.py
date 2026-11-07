#!/usr/bin/env python3
"""TabDock — local touch dashboard for a Mac, served to a tablet over the home LAN.

Run:  .venv/bin/python server.py [--port 8787] [--data DIR]
Open: http://localhost:8787 on the Mac, then scan the QR code with the tablet.
"""
import argparse
import hashlib
import hmac
import ipaddress
import secrets
import io
import json
import mimetypes
import re
import socket
import subprocess
import os
import sys
import threading
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dock import auth, captureone, culling, demo, folders, lanbind, netcheck, notesets, updates, weather, wfolio  # noqa: E402
if sys.platform == "darwin":
    from dock import actions as act_mod, bonjour, sysinfo   # noqa: E402
    from dock.calendar_mac import CalendarFeed               # noqa: E402
    from dock.media import Media                             # noqa: E402
else:   # Linux: same interfaces, see dock/linux/
    from dock.linux import actions as act_mod, bonjour, sysinfo   # noqa: E402
    from dock.linux.calendar import CalendarFeed                   # noqa: E402
    from dock.linux.media import Media                             # noqa: E402
from dock.store import Store, default_config, default_notes, new_id  # noqa: E402

VERSION = "0.11.0-beta"
WEB = os.path.join(HERE, "web")


class App:
    def __init__(self, data_dir, port, demo_mode=False):
        self.port = port
        self.demo = demo_mode
        self._clients, self._clients_lock = {}, threading.Lock()
        self.store = Store(data_dir)
        self.cache_dir = os.path.join(data_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cfg = self.store.load("config", default_config)
        self.store.load("reminders", [])
        self.store.load("notes", default_notes)
        self.store.load("shoots", {"manual": {}, "custom": []})
        self.store.load("wfolio", [])
        self.wfolio = wfolio.Checker(self.store)
        self.folders = folders.FolderShoots(
            lambda: ([] if self.demo else self.config().get("folder_roots", []),
                     self.config().get("export_dirs") or folders.DEFAULT_EXPORT_DIRS), self.cache_dir)
        self.sys = sysinfo.Sampler()
        self.media = Media(self.cache_dir)
        self.net = netcheck.NetCheck()
        self.cull = culling.Culling(self.cache_dir)
        self.actions = act_mod.Actions()
        self.c1 = captureone.CaptureOne()
        self.weather = weather.Weather()
        self.updates = updates.Updates(VERSION)
        self.calendar = CalendarFeed(lambda: not self.demo and self.config().get("calendar", True))
        self._catalogs = None
        self._catalogs_at = 0
        self.discovered = []
        self._discover_kick = threading.Event()
        self._discover_done = threading.Event()
        threading.Thread(target=self._discover_loop, daemon=True).start()
        self.version_ts = time.time()
        self.events = []          # [{id, type, at, ...}] newest last, for toasts on the tablet
        self._event_id = 0
        self._exports = {}        # shoot key -> {"count", "start", "changed"}
        threading.Thread(target=self._watch_exports, daemon=True).start()

    def add_event(self, **ev):
        self._event_id += 1
        ev.update({"id": self._event_id, "at": time.time()})
        self.events = (self.events + [ev])[-20:]

    def _watch_exports(self):
        """Capture One export runs -> one "export finished" event per shoot, 40 s after the last new file."""
        first = True
        while True:
            try:
                items = self.shoots()["items"]
                now = time.time()
                for sh in items:
                    if sh.get("source") not in ("c1", "folder"):
                        continue
                    cnt, st = sh.get("exported", 0), self._exports.get(sh["key"])
                    if st is None or first:
                        self._exports[sh["key"]] = {"count": cnt, "start": cnt, "changed": 0}
                        continue
                    if cnt != st["count"]:
                        if not st["changed"]:
                            st["start"] = st["count"]
                        st["count"], st["changed"] = cnt, now
                    elif st["changed"] and now - st["changed"] > 40:
                        added = st["count"] - st["start"]
                        if added > 0:
                            self.add_event(type="export_done", name=sh["name"], added=added,
                                           done=sh.get("done"), target=sh.get("target"))
                        st["changed"] = 0
                first = False
            except Exception:
                pass
            time.sleep(10)

    def config(self):
        return self.store.load("config", default_config)

    def sysdata(self):
        return demo.sysinfo(self.sys.data) if self.demo else self.sys.data

    def url(self):
        return "http://%s:%d/?k=%s" % (self.sysdata().get("ip") or sysinfo.lan_ip(), self.port, self.config()["token"])

    # ---------- shoots ----------
    def catalogs(self):
        cfg = self.config()
        if self.demo:
            return ["~/Pictures/Demo.cocatalog"]
        if cfg.get("c1_catalogs"):
            return cfg["c1_catalogs"]
        if self._catalogs is None:
            self._discover_kick.set()
            self._discover_done.wait(5)      # first call: give discovery a moment, never block longer
        return self._catalogs or []

    def _discover_loop(self):
        """Catalog discovery touches other apps' prefs and external disks; macOS may hold such calls
        while a permission dialog is open, so it runs here and requests only read the cached result."""
        while True:
            try:
                if not self.demo:
                    found = captureone.discover_detailed()
                    self.discovered = found
                    cur = [e["path"] for e in found if e["current"] and e["exists"]]
                    self._catalogs = cur or [e["path"] for e in found if e["exists"] and e["kind"] == "catalog"]
            except Exception:
                pass
            self._discover_done.set()
            self._discover_kick.wait(600)
            self._discover_kick.clear()

    def shoots(self):
        data = self.store.load("shoots", {"manual": {}, "custom": []})
        items, errors = (demo.shoots(), []) if self.demo else self.c1.shoots(self.catalogs())
        items = items + [dict(x) for x in self.folders.items]
        errors = errors + list(self.folders.errors)
        for c in data.get("custom", []):
            s = dict(c)
            s.update({"source": "manual", "key": "m:" + c["id"], "total": c.get("target", 0),
                      "picked": 0, "exported": 0})
            items.append(s)
        out = []
        for s in items:
            s.setdefault("source", "c1")
            s = captureone.derive(s, data["manual"].get(s["key"]), self.config().get("done_rule"))
            s["cover"] = s.pop("demo_cover", None) or (
                ("/api/shoots/cover?key=" + urllib.parse.quote(s["key"])) if s.get("cover_file") else None)
            s.pop("cover_file", None)
            out.append(s)
        order = {"editing": 0, "selecting": 1, "new": 2, "delivered": 4, "done": 3}
        out.sort(key=lambda s: (s["hidden"], order.get(s["status"], 5),
                                s.get("deadline") or "9999", -(s.get("shot_from") or s.get("created") or 0)))
        cats = self.catalogs()
        backups = [] if self.demo else [captureone.backup_info(c) for c in cats if os.path.isdir(c)]
        vols = []
        for c in cats:
            v = captureone.catalog_volume(c)
            if v:
                vols.append({"catalog": c, "mount": v, "name": v.split("/")[-1], "connected": os.path.isdir(v)})
        return {"items": out, "errors": errors, "catalogs": cats, "backups": backups, "volumes": vols}

    def c1_shoot(self, key):
        """(catalog, album uuid) for a Capture One shoot key, only for catalogs we serve."""
        if not key.startswith("c1:") or self.demo:
            return None, None
        uuid = key[3:]
        items, _ = self.c1.shoots(self.catalogs())
        for s in items:
            if s["key"] == key:
                return s["catalog"], uuid
        return None, None

    def cover_file(self, key):
        if self.demo:
            return None
        if key.startswith("dir:"):
            return self.folders.thumb(key)
        items, _ = self.c1.shoots(self.catalogs())
        for s in items:
            if s["key"] == key:
                return s.get("cover_file")
        return None

    def state(self):
        return {"events": self.events, "net": self.net.data, "sys": self.sysdata(), "media": self.media.data, "awake": self.actions.awake, "vpn": lanbind.VPN,
                "now": time.time(), "version": VERSION}

    def everything(self):
        cfg = self.config()
        return {
            "state": self.state(),
            "reminders": self.store.load("reminders", []),
            "notes": self.store.load("notes", default_notes),
            "shoots": self.shoots(),
            "weather": self.weather.get(cfg.get("place")),
            "calendar": demo.calendar() if self.demo else self.calendar.data,
            "config": {k: v for k, v in cfg.items() if k != "token"},
            "apps": [{"name": a, "installed": bool(act_mod.find_app(a))} for a in cfg.get("apps", [])],
            "url": self.url(),
            "qr": qr_svg(self.url()),
            "wfolio": self.galleries(),
            "export_dirs_default": folders.DEFAULT_EXPORT_DIRS,
            "auth": {"password": bool(cfg.get("password_hash"))},
            "platform": sys.platform,
        }

    def galleries(self):
        from datetime import date
        out = []
        for g in self.store.load("wfolio", []):
            g = dict(g)
            g["days_left"] = None
            if g.get("expires"):
                try:
                    g["days_left"] = (date.fromisoformat(g["expires"]) - date.today()).days
                except ValueError:
                    pass
            out.append(g)
        out.sort(key=lambda g: (g["days_left"] is None, g["days_left"] if g["days_left"] is not None else 0))
        return out

    def server_id(self):
        cfg = self.config()
        if not cfg.get("server_id"):
            sid = secrets.token_hex(8)
            self.store.update("config", default_config, lambda c: c.setdefault("server_id", sid))
            cfg = self.config()
        return cfg["server_id"]

    def proof_key(self):
        """Derived from the access token: lets a paired tablet check it talks to *this* Mac
        (challenge-response) without the token itself ever being sent by the server."""
        return hmac.new(self.config()["token"].encode(), b"tabdock-proof-v1", hashlib.sha256).hexdigest()

    def proof(self, nonce):
        msg = ("%s|%s" % (nonce, self.server_id())).encode()
        return hmac.new(self.proof_key().encode(), msg, hashlib.sha256).hexdigest()

    # ---------------- connected devices (for the menu-bar icon) ----------------
    def seen(self, ip, device, ua):
        name = (device or "").strip()[:60]
        kind = "app" if name else "browser"
        if not name:
            ua = ua or ""
            m = re.search(r"Android [\d.]+; ([^;)]+?)(?: Build|\))", ua)
            name = ("Браузер · " + m.group(1)) if m else "Браузер · " + (
                "iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else "Mac" if "Macintosh" in ua else
                "Linux" if "Linux" in ua else "Windows" if "Windows" in ua else "устройство")
        with self._clients_lock:
            self._clients[(ip, name)] = {"ip": ip, "name": name, "kind": kind, "at": time.time()}

    def clients(self, window=90):
        now = time.time()
        with self._clients_lock:
            for k in [k for k, v in self._clients.items() if now - v["at"] > 3600]:
                del self._clients[k]
            out = [dict(v, ago=int(now - v["at"])) for v in self._clients.values() if now - v["at"] <= window]
        return sorted(out, key=lambda c: c["ago"])

    def tray(self):
        """Everything the menu-bar icon / tray shows (localhost only)."""
        u = self.updates.info()
        return {"ok": True, "version": VERSION, "url": self.url(), "port": self.port, "clients": self.clients(),
                "vpn": lanbind.VPN, "name": socket.gethostname().split(".")[0],
                "update": (u["latest"] or {}).get("version") if u["newer"] else None, "can_self_update": u["can_self_update"]}

    def hello(self, nonce=None):
        s = self.sysdata()
        return {"app": "tabdock", "version": VERSION, "name": s.get("hostname") or "Компьютер",
                "model": s.get("chip") or s.get("model"), "ip": s.get("ip"), "port": self.port,
                "password": bool(self.config().get("password_hash")), "id": self.server_id(),
                **({"nonce": nonce, "proof": self.proof(nonce)} if nonce else {})}


# ---------------- API ops ----------------

def op_reminders(app, body):
    op = body.get("op")

    def fn(items):
        if op == "add":
            text = (body.get("text") or "").strip()
            if not text:
                return False
            items.insert(0, {"id": new_id(), "text": text[:500], "done": False, "due": body.get("due") or None,
                             "important": bool(body.get("important")), "list": body.get("list") or "",
                             "created": time.time(), "done_at": None})
            return True
        for it in items:
            if it["id"] == body.get("id"):
                if op == "toggle":
                    it["done"] = not it["done"]
                    it["done_at"] = time.time() if it["done"] else None
                elif op == "edit":
                    for k in ("text", "due", "important", "list"):
                        if k in body:
                            it[k] = body[k]
                elif op == "delete":
                    items.remove(it)
                return True
        if op == "clear_done":
            items[:] = [i for i in items if not i["done"]]
            return True
        return False
    return app.store.update("reminders", [], fn)


SAFE_LINK = re.compile(r"^(https?://|mailto:|tel:)", re.I)


def op_notes(app, body):
    op = body.get("op")
    if isinstance(body.get("links"), list):   # never store javascript:/data: links
        body["links"] = [{"title": str(l.get("title", ""))[:200], "url": str(l.get("url", ""))[:2000]}
                         for l in body["links"] if isinstance(l, dict) and SAFE_LINK.match(str(l.get("url", "")))]

    def fn(notes):
        if op == "add_sets":   # ready-made cheat sheets (dock/notesets.py)
            return notesets.add_sets(notes, [str(i) for i in body.get("sets", [])][:20])
        if op == "add":
            n = {"id": new_id(), "title": (body.get("title") or "Новая заметка")[:200], "tag": body.get("tag", ""),
                 "color": body.get("color", "blue"), "pinned": False, "body": body.get("body", ""),
                 "links": body.get("links", []), "updated": time.time()}
            notes.insert(0, n)
            return n["id"]
        for n in notes:
            if n["id"] == body.get("id"):
                if op == "edit":
                    for k in ("title", "tag", "color", "pinned", "body", "links"):
                        if k in body:
                            n[k] = body[k]
                    n["updated"] = time.time()
                elif op == "delete":
                    notes.remove(n)
                return True
        return False
    return app.store.update("notes", default_notes, fn)


def op_shoots(app, body):
    op = body.get("op")

    def fn(data):
        data.setdefault("manual", {})
        data.setdefault("custom", [])
        if op == "set":
            m = data["manual"].setdefault(body["key"], {})
            for k in ("status", "deadline", "note", "client", "target", "hidden", "done"):
                if k in body:
                    v = body[k]
                    if v in (None, "", 0) and k != "done":
                        m.pop(k, None)
                    else:
                        m[k] = v
            return True
        if op == "add":
            sid = new_id()
            data["custom"].append({"id": sid, "name": (body.get("name") or "Съёмка")[:200],
                                   "created": time.time(), "shot_from": body.get("shot_from")})
            data["manual"]["m:" + sid] = {"target": int(body.get("target") or 0), "done": 0,
                                          "deadline": body.get("deadline")}
            return sid
        if op == "delete":
            key = body.get("key", "")
            if key.startswith("m:"):
                data["custom"] = [c for c in data["custom"] if c["id"] != key[2:]]
            data["manual"].pop(key, None)
            return True
        return False
    return app.store.update("shoots", {"manual": {}, "custom": []}, fn)


def op_wfolio(app, body):
    op = body.get("op")

    def clean_url(u):
        u = (u or "").strip()
        if u and not re.match(r"^https?://", u, re.I):
            u = "https://" + u
        return u if re.match(r"^https?://[^\s/:?#]+\.[^\s/:?#]{2,}(:\d+)?([/?#]\S*)?$", u) else ""

    def fn(items):
        if op == "add":
            url = clean_url(body.get("url"))
            if not url:
                return False
            items.append({"id": new_id(), "url": url, "title": (body.get("title") or "").strip()[:200],
                          "expires": body.get("expires") or None, "client": (body.get("client") or "").strip()[:200],
                          "shoot_key": body.get("shoot_key") or None, "created": time.time(), "check": None})
            return True
        for g in items:
            if g["id"] == body.get("id"):
                if op == "edit":
                    for k in ("title", "expires", "client", "shoot_key"):
                        if k in body:
                            g[k] = body[k] or (None if k in ("expires", "shoot_key") else "")
                    if "url" in body and clean_url(body["url"]):
                        if clean_url(body["url"]) != g["url"]:
                            g["check"] = None
                        g["url"] = clean_url(body["url"])
                elif op == "delete":
                    items.remove(g)
                elif op == "check":
                    g["check"] = None
                return True
        return False
    r = app.store.update("wfolio", [], fn)
    app.wfolio.kick()
    return r


WIDGET_TYPES = {"reminders", "shoots", "calendar", "player", "quick", "clock", "weather", "deadlines", "events",
                "macstat", "disks", "note", "focus", "network", "shortcuts", "wfolio"}
USAGES = {"photo", "work", "fun", "admin"}
TABS = {"shoots", "notes", "mac", "connect", "settings"}


def clean_spaces(spaces):
    """Validate the space/widget layout sent by the client (it is user data, keep it bounded)."""
    out = []
    for sp in spaces[:8]:
        if not isinstance(sp, dict):
            continue
        widgets = []
        for w in (sp.get("widgets") or [])[:40]:
            if not isinstance(w, dict) or w.get("type") not in WIDGET_TYPES:
                continue
            opts = w.get("opts") if isinstance(w.get("opts"), dict) else {}
            opts = {str(k)[:30]: (v if isinstance(v, (int, float, bool)) else str(v)[:200] if not isinstance(v, list)
                                  else [str(x)[:120] for x in v[:20]]) for k, v in list(opts.items())[:10]}
            widgets.append({"id": re.sub(r"[^a-z0-9]", "", str(w.get("id", "")))[:16] or new_id(), "type": w["type"],
                            "w": max(2, min(12, int(w.get("w") or 4))), "h": max(1, min(8, int(w.get("h") or 2))),
                            "opts": opts})
        out.append({"id": re.sub(r"[^a-z0-9]", "", str(sp.get("id", "")))[:16] or new_id(),
                    "name": str(sp.get("name") or "Пространство")[:40], "icon": str(sp.get("icon") or "home")[:20],
                    "widgets": widgets})
    return out


def op_config(app, body):
    def fn(cfg):
        if "place" in body:
            cfg["place"] = body["place"]
        if "apps" in body and isinstance(body["apps"], list):
            cfg["apps"] = [str(a) for a in body["apps"]][:24]
        if "folders" in body and isinstance(body["folders"], list):
            cfg["folders"] = body["folders"][:12]
        if "calendar" in body:
            cfg["calendar"] = bool(body["calendar"])
        if isinstance(body.get("spaces"), list):
            cfg["spaces"] = clean_spaces(body["spaces"])
        if "setup_done" in body:
            cfg["setup_done"] = bool(body["setup_done"])
        if isinstance(body.get("usage"), list):
            cfg["usage"] = [u for u in body["usage"] if u in USAGES]
        if isinstance(body.get("tabs"), list):
            cfg["tabs"] = [t for t in body["tabs"] if t in TABS]
        if isinstance(body.get("done_rule"), dict):
            r = body["done_rule"]
            kind = r.get("type") if r.get("type") in ("export", "color", "color_or_export", "rating") else "export"
            cfg["done_rule"] = {"type": kind, "color": max(1, min(7, int(r.get("color") or 4))),
                                "rating": max(1, min(5, int(r.get("rating") or 5)))}
        if "skin" in body:
            cfg["skin"] = re.sub(r"[^a-z0-9-]", "", str(body["skin"]))[:30]
        if "folder_roots" in body and isinstance(body["folder_roots"], list):
            cfg["folder_roots"] = [{"path": str(r.get("path", ""))[:500], "app": str(r.get("app", ""))[:60]}
                                   for r in body["folder_roots"] if isinstance(r, dict) and r.get("path")][:12]
        if "export_dirs" in body and isinstance(body["export_dirs"], list):
            cfg["export_dirs"] = [str(x).strip().lower()[:40] for x in body["export_dirs"] if str(x).strip()][:20]
        if "c1_catalogs" in body and isinstance(body["c1_catalogs"], list):
            cfg["c1_catalogs"] = [os.path.expanduser(c.strip()).rstrip("/") for c in body["c1_catalogs"]
                                  if isinstance(c, str) and c.strip()][:12]
        if body.get("new_token"):
            import secrets
            cfg["token"] = secrets.token_urlsafe(12)
        return True
    r = app.store.update("config", default_config, fn)
    # first-run setup picked scenarios → add the matching cheat sheets once
    if isinstance(body.get("usage"), list) and body.get("setup_done"):
        app.store.update("notes", default_notes, lambda notes: notesets.add_sets(notes, notesets.for_usage(body["usage"])))
    if "c1_catalogs" in body:
        app._discover_kick.set()
    if "folder_roots" in body or "export_dirs" in body:
        app.folders.refresh()
    if "calendar" in body:
        app.calendar.refresh_soon()
    return r


def op_action(app, body):
    a, arg = body.get("action"), body.get("arg")
    if a == "eject":
        ext = [d["mount"] for d in sysinfo.disks() if d["external"]]
        if arg not in ext:
            return False, "Диск не найден"
    if a == "open_app" and arg not in app.config().get("apps", []):
        return False, "Приложение не в списке"
    if a == "open_path":
        allowed = [f["path"] for f in app.config().get("folders", [])]
        if arg not in allowed:
            return False, "Папка не в списке"
    if a == "open_folder":
        path = app.folders.path(body.get("key", ""))
        if not path:
            return False, "Папка не найдена"
        subprocess.Popen(["/usr/bin/open", path])
        return True, "Открываю папку в Finder"
    if a == "open_shoot":
        cat = body.get("catalog")
        if cat not in app.catalogs():
            return False, "Каталог не найден"
        captureone.open_in_c1(cat)
        return True, "Открываю Capture One"
    if a == "shortcut":
        return netcheck.run_shortcut(str(arg or ""))
    if a == "calendar_access":
        app.calendar.refresh_soon()
        return True, "Запрос доступа отправлен — подтвердите на компьютере"
    return app.actions.run(a, arg)


# ---------------- HTTP ----------------

class Handler(BaseHTTPRequestHandler):
    server_version = "TabDock/" + VERSION
    app = None  # type: App

    def log_message(self, fmt, *args):
        if os.environ.get("DOCK_DEBUG"):
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # --- auth: localhost is trusted, LAN clients need the token (cookie after first QR scan)
    def _token_ok(self, qs):
        if self.client_address[0] in ("127.0.0.1", "::1"):
            return True
        tok = self.app.config()["token"]
        ok = qs.get("k", [""])[0] == tok or self.headers.get("X-Dock-Key") == tok
        if not ok:
            c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            ok = "dock_k" in c and c["dock_k"].value == tok
        if ok:   # remember who is connected (shown in the menu-bar icon / tray)
            self.app.seen(self.client_address[0], self.headers.get("X-Dock-Device"), self.headers.get("User-Agent"))
        return ok

    def _is_local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _login(self, body):
        ip = self.client_address[0]
        cfg = self.app.config()
        if not cfg.get("password_hash"):
            return self._send(200, {"ok": False, "message": "Пароль не задан — подключитесь по QR-коду с компьютера"})
        if not auth.allowed(ip):
            return self._send(429, {"ok": False, "message": "Слишком много попыток, подождите 5 минут"})
        if not auth.check_password(body.get("password") or "", cfg["password_hash"]):
            auth.failed(ip)
            return self._send(200, {"ok": False, "message": "Неверный пароль"})
        return self._send(200, {"ok": True}, extra={
            "Set-Cookie": "dock_k=%s; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax" % cfg["token"]})

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, default=str).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _file(self, path, ctype=None, cache=False):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            return self._send(404, {"error": "not found"})
        ctype = ctype or mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _panel(self):
        """On the computer itself: a control panel (connect devices, password, updates) instead of a copy of the dock."""
        return self._file(os.path.join(WEB, "panel.html"))

    def _index(self, qs):
        """index.html with the initial state inlined -> instant first paint."""
        with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
            html = f.read()
        d = self.app.everything()
        d["is_local"] = self._is_local()
        d["pin"] = {"id": self.app.server_id(), "key": self.app.proof_key()}
        init = json.dumps(d, ensure_ascii=False, default=str).replace("</", "<\\/")
        tab = qs.get("tab", [""])[0]
        boot = "<script>window.__INIT__=%s;window.__TAB__=%s;</script>" % (init, json.dumps(tab))
        skin = re.sub(r"[^a-z0-9-]", "", str(self.app.config().get("skin") or ""))
        html = html.replace("<head>", '<head><script>window.__SKIN__="%s";</script>' % skin, 1)
        return self._send(200, html.replace("<script src=", boot + "\n<script src=", 1), "text/html; charset=utf-8")

    def do_HEAD(self):
        self.do_GET()

    # --- network guards: private networks only, no DNS rebinding, no cross-site POSTs
    def _client_allowed(self):
        if os.environ.get("DOCK_ALLOW_PUBLIC"):
            return True
        try:
            ip = ipaddress.ip_address(self.client_address[0].split("%")[0])
        except ValueError:
            return False
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        return ip.is_loopback or ip.is_private or ip.is_link_local

    def _host_allowed(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        if not host or host == "localhost" or host.endswith(".local"):
            return True
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return host == socket.gethostname().lower().replace(".local", "")

    def _guard(self):
        if not self._client_allowed():
            self._send(403, {"error": "TabDock answers only on private networks"})
            return False
        if not self._host_allowed():
            self._send(421, {"error": "unexpected Host header"})
            return False
        return True

    def _same_origin_post(self):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":      # forces a CORS preflight for cross-site callers
            return False
        origin = self.headers.get("Origin")
        if origin and origin != "null":
            o = urllib.parse.urlparse(origin)
            if o.netloc.lower() != (self.headers.get("Host") or "").lower():
                return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        p = u.path
        app = self.app
        if p in ("/", "/index.html"):
            if not self._token_ok(qs):
                return self._file(os.path.join(WEB, "login.html"))
            if "k" in qs:  # remember the tablet, then drop the token from the address bar
                return self._send(302, "", "text/plain", {
                    "Location": "/",
                    "Set-Cookie": "dock_k=%s; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax" % qs["k"][0]})
            if self._is_local() and "dock" not in qs and "tab" not in qs and "space" not in qs and "wz" not in qs:
                return self._panel()
            return self._index(qs)
        if p.startswith("/static/"):
            f = os.path.normpath(os.path.join(WEB, p[len("/static/"):]))
            if not f.startswith(WEB + os.sep):
                return self._send(403, {"error": "forbidden"})
            return self._file(f)
        if p == "/api/hello":
            nonce = qs.get("nonce", [""])[0][:64] or None
            return self._send(200, app.hello(nonce), extra={"Access-Control-Allow-Origin": "*"})
        if p == "/manifest.webmanifest":
            return self._file(os.path.join(WEB, "manifest.webmanifest"), "application/manifest+json")
        if not self._token_ok(qs):
            return self._send(401, {"error": "unauthorized"})
        if p == "/api/state":
            return self._send(200, app.state())
        if p == "/api/all":
            d = app.everything()
            d["is_local"] = self._is_local()
            return self._send(200, d)
        if p == "/api/shoots":
            return self._send(200, app.shoots())
        if p == "/api/shoots/cover":
            f = app.cover_file(qs.get("key", [""])[0])
            return self._file(f, "image/jpeg", cache=True) if f else self._send(404, {})
        if p == "/api/media/cover":
            return self._file(os.path.join(app.cache_dir, "cover.jpg"), "image/jpeg", cache=True)
        if p == "/api/app_icon":
            f = act_mod.app_icon(qs.get("name", [""])[0], app.cache_dir)
            return self._file(f, "image/png", cache=True) if f else self._send(404, {})
        if p == "/api/cull/images":
            cat, uuid = app.c1_shoot(qs.get("key", [""])[0])
            if not cat:
                return self._send(404, {"error": "Отбор пока работает только для съёмок из Capture One"})
            return self._send(200, {"images": app.cull.images(cat, uuid)})
        if p in ("/api/cull/thumb", "/api/cull/preview"):
            cat, uuid = app.c1_shoot(qs.get("key", [""])[0])
            try:
                pk = int(qs.get("img", ["0"])[0])
            except ValueError:
                pk = 0
            f = (app.cull.thumb if p.endswith("thumb") else app.cull.preview)(cat, uuid, pk) if cat else None
            return self._file(f, "image/jpeg", cache=True) if f else self._send(404, {})
        if p == "/api/pin":   # native client: identity to pin after sign-in (never the access key itself)
            return self._send(200, {"id": app.server_id(), "key": app.proof_key(), "name": app.sysdata().get("hostname")})
        if p == "/api/catalogs":
            app._discover_kick.set()
            return self._send(200, {"found": app.discovered,
                                    "active": app.catalogs(), "manual": app.config().get("c1_catalogs", [])})
        if p == "/api/update":
            return self._send(200, app.updates.info())
        if p == "/api/tray":   # menu-bar icon / tray on this computer only
            if not self._is_local():
                return self._send(403, {"error": "local only"})
            return self._send(200, app.tray())
        if p == "/api/notesets":
            return self._send(200, notesets.listing(app.store.load("notes", default_notes)))
        if p == "/api/shortcuts":
            return self._send(200, netcheck.shortcuts_list())
        if p == "/api/apps_installed":
            return self._send(200, act_mod.installed_apps())
        if p == "/api/weather":
            return self._send(200, app.weather.get(app.config().get("place")))
        if p == "/api/geocode":
            try:
                return self._send(200, weather.geocode(qs.get("q", [""])[0]))
            except Exception as e:
                return self._send(502, {"error": str(e)})
        if p == "/api/qr.svg":
            return self._send(200, qr_svg(app.url()), "image/svg+xml")
        if p == "/api/pair":
            return self._send(200, {"url": app.url()})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._guard():
            return
        if not self._same_origin_post():
            return self._send(403, {"error": "cross-site request blocked"})
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            return self._send(413, {"error": "too large"})
        try:
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            return self._send(400, {"error": "bad json"})
        app, p = self.app, u.path
        if p == "/api/login":
            return self._login(body)
        if not self._token_ok(qs):
            return self._send(401, {"error": "unauthorized"})
        try:
            if p == "/api/reminders":
                return self._send(200, {"ok": op_reminders(app, body), "reminders": app.store.load("reminders", [])})
            if p == "/api/notes":
                return self._send(200, {"ok": op_notes(app, body), "notes": app.store.load("notes", [])})
            if p == "/api/shoots":
                return self._send(200, {"ok": op_shoots(app, body), "shoots": app.shoots()})
            if p == "/api/config":
                op_config(app, body)
                d = app.everything()
                d["is_local"] = self._is_local()
                return self._send(200, d)
            if p == "/api/media":
                ok = app.media.command(body.get("cmd"), body.get("value"))
                return self._send(200, {"ok": ok, "media": app.media.data})
            if p == "/api/update":     # check now / update the server (on the computer itself only)
                if not self._is_local():
                    return self._send(403, {"ok": False, "message": "Обновление запускается только на самом компьютере"})
                if body.get("op") == "apply":
                    ok, msg = updates.apply()
                    if ok and "перезапускается" in msg:
                        updates.restart_later()
                    return self._send(200, {"ok": ok, "message": msg})
                app.updates.check()
                return self._send(200, dict(app.updates.info(), ok=True))
            if p == "/api/password":
                if not self._is_local():
                    return self._send(403, {"ok": False, "message": "Пароль меняется только на самом компьютере"})
                pw = body.get("password") or ""
                if body.get("remove"):
                    app.store.update("config", default_config, lambda c: c.pop("password_hash", None))
                    return self._send(200, {"ok": True, "message": "Пароль удалён — вход только по QR"})
                if len(pw) < 4:
                    return self._send(200, {"ok": False, "message": "Минимум 4 символа"})
                h = auth.hash_password(pw)
                app.store.update("config", default_config, lambda c: c.__setitem__("password_hash", h))
                return self._send(200, {"ok": True, "message": "Пароль сохранён"})
            if p == "/api/cull/tag":
                cat, uuid = app.c1_shoot(str(body.get("key", "")))
                if not cat:
                    return self._send(200, {"ok": False, "message": "Съёмка не найдена"})
                ok, msg = app.cull.tag(cat, uuid, body.get("changes") or [])
                return self._send(200, {"ok": ok, "message": msg})
            if p == "/api/wfolio":
                return self._send(200, {"ok": op_wfolio(app, body), "wfolio": app.galleries()})
            if p == "/api/action":
                ok, msg = op_action(app, body)
                return self._send(200, {"ok": ok, "message": msg, "awake": app.actions.awake})
        except Exception as e:
            return self._send(500, {"error": str(e)})
        return self._send(404, {"error": "not found"})


def qr_svg(text):
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="60"><text x="0" y="30" '
                'fill="#fff" font-size="12">pip install qrcode</text></svg>')
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathFillImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


class DockServer(ThreadingHTTPServer):
    """HTTP server whose port can be shared with the interface-pinned LAN listeners (see dock/lanbind.py)."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler, bound_if=None):
        self.bound_if = bound_if
        super().__init__(addr, handler)

    def server_bind(self):
        if hasattr(socket, "SO_REUSEPORT"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        if self.bound_if:
            self.socket.setsockopt(socket.IPPROTO_IP, lanbind.IP_BOUND_IF, self.bound_if)
        super().server_bind()


def main():
    ap = argparse.ArgumentParser(description="TabDock server")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DOCK_PORT", 8787)))
    ap.add_argument("--data", default=os.environ.get("DOCK_DATA", os.path.join(HERE, "data")))
    ap.add_argument("--print-url", action="store_true", help="print the tablet URL and exit")
    ap.add_argument("--demo", action="store_true", help="synthetic shoots/calendar for screenshots (no real catalog)")
    ap.add_argument("--set-password", action="store_true", help="set the tablet login password and exit")
    a = ap.parse_args()
    if a.set_password:
        import getpass
        st = Store(os.path.abspath(a.data))
        pw = getpass.getpass("Новый пароль для планшета: ")
        if len(pw) < 4 or pw != getpass.getpass("Ещё раз: "):
            sys.exit("Пароли не совпадают или короче 4 символов")
        h = auth.hash_password(pw)
        st.update("config", default_config, lambda c: c.__setitem__("password_hash", h))
        print("Пароль сохранён. Перезапустите службу, если она работает.")
        return
    app = App(os.path.abspath(a.data), a.port, demo_mode=a.demo)
    if a.print_url:
        print(app.url())
        return
    Handler.app = app
    srv = DockServer(("0.0.0.0", a.port), Handler)
    # replies to the tablet/phone go straight through Wi-Fi/Ethernet even when a VPN is on
    if not os.environ.get("DOCK_NO_LANBIND"):
        lanbind.LanBinder(lambda ip, port, idx: DockServer((ip, port), Handler, idx), a.port).start()
    if not os.environ.get("DOCK_NO_BONJOUR"):
        bonjour.advertise(a.port, VERSION)
    print("TabDock %s on http://localhost:%d  (tablet: %s)" % (VERSION, a.port, app.url()), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
