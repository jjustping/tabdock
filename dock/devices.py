"""Every tablet, phone or browser has its own key, can be switched off on its own, and has to be allowed on the
computer first. Only a hash of each key is stored."""
import hashlib
import re
import secrets
import subprocess
import sys
import threading
import time

MAX_PENDING = 5
MAX_DEVICES = 64
NOTIFY_MAC = 'on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run'


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def clean_name(name):
    return re.sub(r"[\x00-\x1f\x7f]", "", str(name or "")).strip()[:60] or "Устройство"


def notify(title, text):
    """Best effort, never blocks a request."""
    def run():
        try:
            if sys.platform == "darwin":
                subprocess.run(["/usr/bin/osascript", "-e", NOTIFY_MAC, title, text], capture_output=True, timeout=10)
            else:
                subprocess.run(["notify-send", "-a", "TabDock", title, text], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
    threading.Thread(target=run, daemon=True).start()


class Devices:
    def __init__(self, store, announce=notify):
        self.store = store
        self.announce = announce
        self._last = {}          # id -> (time, ip): not written to disk on every request

    def _all(self):
        return self.store.load("devices", [])

    def request(self, name, ip, kind):
        """A new device asks for access: returns (entry, key). The key works only after allow()."""
        key = secrets.token_urlsafe(32)
        d = {"id": secrets.token_hex(6), "name": clean_name(name), "kind": "app" if kind == "app" else "browser",
             "hash": _hash(key), "status": "pending", "ip": str(ip)[:45], "at": time.time()}

        def add(lst):
            pending = [x for x in lst if x["status"] == "pending"]
            for old in pending[:max(0, len(pending) - MAX_PENDING + 1)]:
                lst.remove(old)
            if len(lst) >= MAX_DEVICES:      # refuse rather than push out a device that is already allowed
                return False
            lst.append(d)
            return True
        if not self.store.update("devices", [], add):
            return None, None
        self.announce("TabDock: новое устройство", "%s просит доступ. Разрешите его в панели TabDock." % d["name"])
        return d, key

    def check(self, key):
        """The device this key belongs to (allowed or still waiting), or None."""
        if not key:
            return None
        h = _hash(key)
        return next((d for d in self._all() if d["hash"] == h), None)

    def allowed(self, key, ip=None):
        d = self.check(key)
        if not d or d["status"] != "ok":
            return None
        self._last[d["id"]] = (time.time(), ip or d.get("ip"))
        return d

    def _set(self, fn):
        def run(lst):
            return fn(lst)
        return self.store.update("devices", [], run)

    def allow(self, did):
        def fn(lst):
            for d in lst:
                if d["id"] == did and d["status"] == "pending":
                    d["status"] = "ok"
                    return True
            return False
        return self._set(fn)

    def remove(self, did):
        def fn(lst):
            n = len(lst)
            lst[:] = [d for d in lst if d["id"] != did]
            return len(lst) != n
        return self._set(fn)

    def clear(self):
        self._set(lambda lst: lst.clear())

    def listing(self):
        """Without the key hashes, for the panel on the computer."""
        out = []
        for d in self._all():
            x = {k: v for k, v in d.items() if k != "hash"}
            last = self._last.get(d["id"])
            if last:
                x.update(last_seen=last[0], ip=last[1])
            out.append(x)
        return sorted(out, key=lambda d: (d["status"] != "pending", -(d.get("last_seen") or d["at"])))

    def pending(self):
        return [d for d in self.listing() if d["status"] == "pending"]
