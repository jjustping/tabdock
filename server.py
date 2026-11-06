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
import os
import sys
import threading
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dock import actions as act_mod          # noqa: E402
from dock import auth, bonjour, captureone, demo, sysinfo, weather, wfolio  # noqa: E402
from dock.calendar_mac import CalendarFeed    # noqa: E402
from dock.media import Media                  # noqa: E402
from dock.store import Store, default_config, default_notes, new_id  # noqa: E402

VERSION = "0.4.0"
WEB = os.path.join(HERE, "web")


class App:
    def __init__(self, data_dir, port, demo_mode=False):
        self.port = port
        self.demo = demo_mode
        self.store = Store(data_dir)
        self.cache_dir = os.path.join(data_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cfg = self.store.load("config", default_config)
        self.store.load("reminders", [])
        self.store.load("notes", default_notes)
        self.store.load("shoots", {"manual": {}, "custom": []})
        self.store.load("wfolio", [])
        self.wfolio = wfolio.Checker(self.store)
        self.sys = sysinfo.Sampler()
        self.media = Media(self.cache_dir)
        self.actions = act_mod.Actions()
        self.c1 = captureone.CaptureOne()
        self.weather = weather.Weather()
        self.calendar = CalendarFeed(lambda: not self.demo and self.config().get("calendar", True))
        self._catalogs = None
        self._catalogs_at = 0
        self.version_ts = time.time()

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
        if self._catalogs is None or time.time() - self._catalogs_at > 600:
            self._catalogs = captureone.discover()
            self._catalogs_at = time.time()
        return self._catalogs

    def shoots(self):
        data = self.store.load("shoots", {"manual": {}, "custom": []})
        items, errors = (demo.shoots(), []) if self.demo else self.c1.shoots(self.catalogs())
        for c in data.get("custom", []):
            s = dict(c)
            s.update({"source": "manual", "key": "m:" + c["id"], "total": c.get("target", 0),
                      "picked": 0, "exported": 0})
            items.append(s)
        out = []
        for s in items:
            s.setdefault("source", "c1")
            s = captureone.derive(s, data["manual"].get(s["key"]))
            s["cover"] = s.pop("demo_cover", None) or (
                ("/api/shoots/cover?key=" + urllib.parse.quote(s["key"])) if s.get("cover_file") else None)
            s.pop("cover_file", None)
            out.append(s)
        order = {"editing": 0, "selecting": 1, "new": 2, "delivered": 4, "done": 3}
        out.sort(key=lambda s: (s["hidden"], order.get(s["status"], 5),
                                s.get("deadline") or "9999", -(s.get("shot_from") or s.get("created") or 0)))
        return {"items": out, "errors": errors, "catalogs": self.catalogs()}

    def cover_file(self, key):
        if self.demo:
            return None
        items, _ = self.c1.shoots(self.catalogs())
        for s in items:
            if s["key"] == key:
                return s.get("cover_file")
        return None

    def state(self):
        return {"sys": self.sysdata(), "media": self.media.data, "awake": self.actions.awake,
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
            "auth": {"password": bool(cfg.get("password_hash"))},
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

    def hello(self, nonce=None):
        s = self.sysdata()
        return {"app": "tabdock", "version": VERSION, "name": s.get("hostname") or "Mac",
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
        if "c1_catalogs" in body and isinstance(body["c1_catalogs"], list):
            cfg["c1_catalogs"] = [c for c in body["c1_catalogs"] if isinstance(c, str)]
        if body.get("new_token"):
            import secrets
            cfg["token"] = secrets.token_urlsafe(12)
        return True
    r = app.store.update("config", default_config, fn)
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
    if a == "open_shoot":
        cat = body.get("catalog")
        if cat not in app.catalogs():
            return False, "Каталог не найден"
        captureone.open_in_c1(cat)
        return True, "Открываю Capture One"
    if a == "calendar_access":
        app.calendar.refresh_soon()
        return True, "Запрос доступа отправлен — подтвердите на Mac"
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
        if qs.get("k", [""])[0] == tok or self.headers.get("X-Dock-Key") == tok:
            return True
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "dock_k" in c and c["dock_k"].value == tok

    def _is_local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _login(self, body):
        ip = self.client_address[0]
        cfg = self.app.config()
        if not cfg.get("password_hash"):
            return self._send(200, {"ok": False, "message": "Пароль не задан — подключитесь по QR-коду с Mac"})
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
            if p == "/api/password":
                if not self._is_local():
                    return self._send(403, {"ok": False, "message": "Пароль меняется только на самом Mac"})
                pw = body.get("password") or ""
                if body.get("remove"):
                    app.store.update("config", default_config, lambda c: c.pop("password_hash", None))
                    return self._send(200, {"ok": True, "message": "Пароль удалён — вход только по QR"})
                if len(pw) < 4:
                    return self._send(200, {"ok": False, "message": "Минимум 4 символа"})
                h = auth.hash_password(pw)
                app.store.update("config", default_config, lambda c: c.__setitem__("password_hash", h))
                return self._send(200, {"ok": True, "message": "Пароль сохранён"})
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
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    srv.daemon_threads = True
    if not os.environ.get("DOCK_NO_BONJOUR"):
        bonjour.advertise(a.port, VERSION)
    print("TabDock %s on http://localhost:%d  (tablet: %s)" % (VERSION, a.port, app.url()), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
