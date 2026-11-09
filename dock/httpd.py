"""HTTP layer: request guards, authentication and the routes of the API."""
import hmac
import ipaddress
import json
import mimetypes
import os
import re

import shutil
import socket
import ssl
import sys
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import auth, inbox, lanbind, netcheck, notesets, updates, weather
from .core import (act_mod, op_action, op_config, op_notes, op_reminders, op_shoots, op_wfolio, qr_svg)
from .store import default_config, default_notes
from .version import VERSION

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


class Handler(BaseHTTPRequestHandler):
    server_version = "TabDock/" + VERSION
    app = None  # type: App

    def log_message(self, fmt, *args):
        if os.environ.get("DOCK_DEBUG"):
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    LOCAL = ("127.0.0.1", "::1")

    # --- auth: localhost is trusted; every other device has its own key (see dock/devices.py)
    def _is_local(self):
        return self.client_address[0] in self.LOCAL

    def _is_tls(self):
        return isinstance(self.connection, ssl.SSLSocket)

    def _key(self):
        key = self.headers.get("X-Dock-Key")
        if key:
            return key
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return c["dock_k"].value if "dock_k" in c else None

    def _token_ok(self, qs=None):
        if self._is_local():
            return True
        d = self.app.devices.allowed(self._key(), self.client_address[0])
        if d:      # remember who is connected (shown in the menu-bar icon / tray)
            self.app.seen(self.client_address[0], d["name"] if d["kind"] == "app" else None, self.headers.get("User-Agent"))
        return bool(d)

    def _cookie(self, key):
        return "dock_k=%s; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax; Secure" % key

    def _browser_name(self):
        ua = self.headers.get("User-Agent") or ""
        m = re.search(r"Android [\d.]+; ([^;)]+?)(?: Build|\))", ua)
        return "Браузер · " + (m.group(1) if m else "iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else "Mac" if "Macintosh" in ua
                               else "Linux" if "Linux" in ua else "Windows" if "Windows" in ua else "устройство")

    def _pairing_ok(self, code=None, password=None):
        """(ok, message): the code from the QR or the password, with brute-force protection for both."""
        ip, cfg = self.client_address[0], self.app.config()
        if not auth.allowed(ip):
            return False, "Слишком много попыток, подождите 5 минут"
        if code is not None and hmac.compare_digest(str(code).encode(), cfg["token"].encode()):
            return True, ""
        if password is not None and cfg.get("password_hash") and auth.check_password(str(password), cfg["password_hash"]):
            return True, ""
        auth.failed(ip)
        if password is not None and not cfg.get("password_hash"):
            return False, "Пароль не задан — подключитесь по QR-коду с компьютера"
        return False, "Неверный пароль" if password is not None else "Неверный код подключения"

    def _new_device(self, name, kind):
        """The device gets its key at once; it starts working when the computer allows it."""
        d, key = self.app.devices.request(name, self.client_address[0], kind)
        if not d:
            self._send(200, {"ok": False, "message": "Слишком много устройств: удалите лишние в панели на компьютере"})
            return None
        return d, key

    def _login(self, body):
        ok, msg = self._pairing_ok(password=body.get("password") or "")
        if not ok:
            return self._send(429 if "попыток" in msg else 200, {"ok": False, "message": msg})
        made = self._new_device(self._browser_name(), "browser")
        if made:
            d, key = made
            self._send(200, {"ok": True, "status": d["status"]}, extra={"Set-Cookie": self._cookie(key)})

    def _request_device(self, body):
        """The app asks for its own key, with the QR code's pairing code or the password."""
        ok, msg = self._pairing_ok(body.get("k"), None if "k" in body else body.get("password") or "")
        if not ok:
            return self._send(429 if "попыток" in msg else 200, {"ok": False, "message": msg})
        made = self._new_device(body.get("name"), "app")
        if made:
            d, key = made
            self._send(200, {"ok": True, "key": key, "id": d["id"], "status": d["status"]})

    def _pair_browser(self, qs):
        """A browser opened the link from the QR code."""
        known = self.app.devices.check(self._key())
        if known:
            return self._send(302, "", "text/plain", {"Location": "/"})
        ok, _ = self._pairing_ok(qs["k"][0])
        if not ok:
            return self._file(os.path.join(WEB, "login.html"))
        made = self._new_device(self._browser_name(), "browser")
        if made:
            return self._send(302, "", "text/plain", {"Location": "/", "Set-Cookie": self._cookie(made[1])})

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if code >= 300 and self.command in ("POST", "PUT") and not getattr(self, "body_read", False):
            # refused before reading the body: without this the client gets a connection reset instead of the answer
            self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 65536))
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

    def _stream(self, path, name):
        """Send a (possibly big) file in chunks, as a download."""
        try:
            size = os.path.getsize(path)
            f = open(path, "rb")
        except OSError:
            return self._send(404, {"error": "not found"})
        with f:
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(name))
            self.end_headers()
            shutil.copyfileobj(f, self.wfile, 1024 * 1024)

    def _device(self):
        return (self.headers.get("X-Dock-Device") or "").strip()[:60]

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

    def do_PUT(self):
        """Phone → computer file upload: PUT /api/send/file?name=… with the X-Dock-Key header (no cookie: a web page on
        another site cannot send this header without a CORS preflight, which the server never allows)."""
        if not self._guard():
            return
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path == "/api/outbox/file":   # computer → phone: only from the computer itself (the transfer window)
            if not self._is_local():
                return self._send(403, {"error": "local only"})
            n = int(self.headers.get("Content-Length") or 0)
            to = qs.get("to", [""])[0][:60]
            expected = [c["name"] for c in self.app.clients(600) if c.get("kind") == "app"]
            ok, msg, item = self.app.outbox.add(self.rfile, n, qs.get("name", [""])[0], to, expected)
            return self._send(200, {"ok": ok, "message": msg, "item": item})
        if u.path != "/api/send/file":
            return self._send(404, {"error": "not found"})
        # the key must be in the header, not a cookie: a page on another site cannot set it without a preflight
        if not self.headers.get("X-Dock-Key") and not self._is_local():
            return self._send(401, {"error": "unauthorized"})
        if not self._token_ok():
            return self._send(401, {"error": "unauthorized"})
        n = int(self.headers.get("Content-Length") or 0)
        ok, msg, path = inbox.receive_file(self.rfile, n, qs.get("name", [""])[0])
        if ok:
            self.app.add_event(type="received", name=os.path.basename(path))
        return self._send(200, {"ok": ok, "message": msg, "name": os.path.basename(path) if path else None})

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
        if not self._is_local() and not self._is_tls():      # only this computer itself may talk plain HTTP
            if not self.app.tls_context:
                self._send(503, {"error": "HTTPS не настроен: на компьютере нужна команда openssl"})
            elif self.command in ("GET", "HEAD"):
                self._send(301, "", "text/plain", {"Location": "https://%s%s" % (self.headers.get("Host"), self.path)})
            else:
                self._send(403, {"error": "HTTPS required"})
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
            if "k" in qs:       # the link from the QR code: never keep the code in the address bar
                if self._is_local():
                    return self._send(302, "", "text/plain", {"Location": "/"})
                return self._pair_browser(qs)
            if not self._token_ok():
                waiting = app.devices.check(self._key())
                return self._file(os.path.join(WEB, "wait.html" if waiting else "login.html"))
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
        if p == "/api/devices/me":      # a device waiting for its «allow» on the computer
            if self._is_local():
                return self._send(200, {"status": "ok"})
            d = app.devices.check(self._key())
            return self._send(200 if d else 401, {"status": d["status"] if d else "unknown"})
        if p == "/manifest.webmanifest":
            return self._file(os.path.join(WEB, "manifest.webmanifest"), "application/manifest+json")
        if not self._token_ok(qs):
            return self._send(401, {"error": "unauthorized"})
        if p == "/api/state":
            d = app.state()
            if self._device():      # the app: files waiting for this device (computer → phone)
                d = dict(d, outbox=app.outbox.for_device(self._device()))
            return self._send(200, d)
        if p == "/api/outbox/file":
            fid = qs.get("id", [""])[0]
            f = app.outbox.path(fid)
            if not f:
                return self._send(404, {"error": "not found"})
            return self._stream(f, os.path.basename(f))
        if p == "/api/transfer":     # the «Передача файлов» window, on the computer itself
            if not self._is_local():
                return self._send(403, {"error": "local only"})
            return self._send(200, {"outbox": app.outbox.listing(), "inbox": inbox.recent(),
                                    "devices": [c for c in app.clients(600) if c.get("kind") == "app"]})
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
            f = None
            if cat:
                f = app.cull.thumb(cat, uuid, pk) if p.endswith("thumb") else app.cull.preview(cat, uuid, pk, hi="hi" in qs)
            return self._file(f, "image/jpeg", cache=True) if f else self._send(404, {})
        if p == "/api/pin":   # native client: identity to pin after sign-in (never the access key itself)
            return self._send(200, {"id": app.server_id(), "key": app.proof_key(), "name": app.sysdata().get("hostname")})
        if p == "/api/catalogs":
            app._discover_kick.set()
            return self._send(200, {"found": app.discovered,
                                    "active": app.catalogs(), "manual": app.config().get("c1_catalogs", [])})
        if p == "/api/update":
            return self._send(200, app.updates.info())
        if p in ("/transfer", "/transfer.html"):
            if not self._is_local():
                return self._send(403, {"error": "local only"})
            return self._file(os.path.join(WEB, "transfer.html"))
        if p == "/api/devices":         # the list in the control panel, on the computer itself
            if not self._is_local():
                return self._send(403, {"error": "local only"})
            return self._send(200, {"devices": app.devices.listing()})
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
            self.body_read = True
        except ValueError:
            self.body_read = True
            return self._send(400, {"error": "bad json"})
        app, p = self.app, u.path
        if p == "/api/login":
            return self._login(body)
        if p == "/api/devices/request":
            return self._request_device(body)
        if not self._token_ok(qs):
            return self._send(401, {"error": "unauthorized"})
        try:
            if p == "/api/reminders":
                return self._send(200, {"ok": op_reminders(app, body), "reminders": app.store.load("reminders", [])})
            if p == "/api/notes":
                return self._send(200, {"ok": op_notes(app, body), "notes": app.store.load("notes", [])})
            if p == "/api/shoots":
                return self._send(200, {"ok": op_shoots(app, body), "shoots": app.shoots()})
            if p == "/api/devices":
                if not self._is_local():
                    return self._send(403, {"ok": False, "message": "Устройствами управляют только на самом компьютере"})
                op, did = body.get("op"), str(body.get("id", ""))
                ok = app.devices.allow(did) if op == "allow" else app.devices.remove(did) if op == "remove" else False
                return self._send(200, {"ok": bool(ok), "devices": app.devices.listing()})
            if p == "/api/config":
                if body.get("new_token"):
                    if not self._is_local():
                        return self._send(403, {"error": "local only"})
                    app.devices.clear()
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
            if p == "/api/outbox":     # the app took a file / the window removes one
                if body.get("op") == "done" and self._device():
                    app.outbox.done(str(body.get("id", "")), self._device())
                    return self._send(200, {"ok": True})
                if body.get("op") == "remove" and self._is_local():
                    app.outbox.remove(str(body.get("id", "")))
                    return self._send(200, {"ok": True})
                if body.get("op") == "reveal" and self._is_local():
                    inbox.reveal_dir()
                    return self._send(200, {"ok": True})
                return self._send(400, {"ok": False})
            if p == "/api/send":       # phone → computer: a link or a piece of text
                ok, msg = inbox.receive(body.get("kind"), body.get("value"))
                return self._send(200, {"ok": ok, "message": msg})
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


class DockServer(ThreadingHTTPServer):
    """HTTP server whose port can be shared with the interface-pinned LAN listeners (see dock/lanbind.py)."""
    daemon_threads = True
    allow_reuse_address = True
    tls_context = None         # set by main(): HTTPS and plain HTTP share one port, the first byte tells them apart

    def __init__(self, addr, handler, bound_if=None):
        self.bound_if = bound_if
        super().__init__(addr, handler)

    def server_bind(self):
        if hasattr(socket, "SO_REUSEPORT"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        if self.bound_if:
            self.socket.setsockopt(socket.IPPROTO_IP, lanbind.IP_BOUND_IF, self.bound_if)
        super().server_bind()

    def finish_request(self, request, client_address):
        ctx = type(self).tls_context
        if not ctx:
            return super().finish_request(request, client_address)
        request.settimeout(15)
        try:
            is_tls = request.recv(1, socket.MSG_PEEK) == b"\x16"      # a TLS record starts with «handshake»
            if not is_tls:
                request.settimeout(None)
                return super().finish_request(request, client_address)
            conn = ctx.wrap_socket(request, server_side=True)
        except (OSError, ssl.SSLError):
            return None
        try:
            conn.settimeout(None)
            self.RequestHandlerClass(conn, client_address, self)
        finally:
            conn.close()

    def handle_error(self, request, client_address):
        """A device that goes away mid-request is normal, not an error worth a traceback."""
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError, ssl.SSLError)):
            super().handle_error(request, client_address)
