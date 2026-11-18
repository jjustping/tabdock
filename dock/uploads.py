"""Phone → computer for big files and whole folders: uploads in parts that survive a broken connection.

The app asks to start (name, size, and for a folder: the folder's name and the file's path inside it), then sends the
file in parts of up to 64 MB, each with its SHA-256. A part is written only at the exact place the server expects, so
after a dropped Wi-Fi the app asks where to continue and sends the rest. The file grows next to the inbox (same disk)
and is moved into place when the last byte arrives; a folder is recreated with its sub-folders.
"""
import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid

from . import inbox

MAX_PART = 64 * 1024 * 1024
KEEP_PARTS = 72 * 3600          # unfinished uploads are dropped after three days
RESERVE = 512 * 1024 * 1024     # always leave this much free on the disk


def safe_rel(rel):
    """'a/b/../c\\d.jpg' -> ['a', 'b', 'c'] (directories only; never leaves the folder)."""
    parts = [p for p in re.split(r"[\\/]+", str(rel or "")) if p and p not in (".", "..")]
    return [inbox.safe_name(p) for p in parts][:20]


class Uploads:
    def __init__(self):
        self._lock = threading.Lock()

    @property
    def dir(self):
        return os.path.join(inbox.INBOX, ".tabdock-incoming")

    def _meta(self, uid):
        return os.path.join(self.dir, uid + ".json")

    def _part(self, uid):
        return os.path.join(self.dir, uid + ".part")

    def _load(self, uid):
        if not re.match(r"^[0-9a-f]{16}$", uid or ""):
            return None
        try:
            with open(self._meta(uid), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _save(self, m):
        tmp = self._meta(m["id"]) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False)
        os.replace(tmp, self._meta(m["id"]))

    def received(self, uid):
        try:
            return os.path.getsize(self._part(uid))
        except OSError:
            return 0

    def start(self, device, name, size, folder="", rel="", batch=""):
        """(ok, message, {"id", "offset"}). The same file from the same device continues where it stopped."""
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = -1
        if size < 0:
            return False, "Неизвестный размер файла", None
        name, folder = inbox.safe_name(name), (inbox.safe_name(folder) if folder else "")
        rel = "/".join(safe_rel(rel))
        batch = re.sub(r"[^A-Za-z0-9_-]", "", str(batch or ""))[:40]
        os.makedirs(self.dir, exist_ok=True)
        self.cleanup()
        with self._lock:
            for f in os.listdir(self.dir):
                if f.endswith(".json"):
                    m = self._load(f[:-5])
                    if m and (m["device"], m["name"], m["size"], m["folder"], m["rel"], m["batch"]) == \
                            (device, name, size, folder, rel, batch):
                        return True, "Продолжаю", {"id": m["id"], "offset": self.received(m["id"])}
            free = shutil.disk_usage(self.dir).free
            if size + RESERVE > free:
                return False, "На компьютере мало места: нужно %.1f ГБ, свободно %.1f ГБ" % (
                    (size + RESERVE) / 1e9, free / 1e9), None
            m = {"id": uuid.uuid4().hex[:16], "device": device, "name": name, "size": size, "folder": folder,
                 "rel": rel, "batch": batch, "at": time.time()}
            open(self._part(m["id"]), "wb").close()
            self._save(m)
        if size == 0:                                # an empty file is done at once
            ok, msg, _ = self._finish(m)
            return ok, msg, {"id": m["id"], "offset": 0, "done": ok}
        return True, "Начинаю", {"id": m["id"], "offset": 0}

    def put(self, uid, offset, rfile, length, sha=None):
        """(http status, body). Append one part at `offset`; 409 tells the app where to continue."""
        def skip():      # read the refused part anyway: the app then gets a clean answer instead of a reset connection
            left = length if 0 < length <= MAX_PART else 0
            while left > 0:
                chunk = rfile.read(min(1024 * 1024, left))
                if not chunk:
                    break
                left -= len(chunk)
        m = self._load(uid)
        if not m:
            skip()
            return 404, {"ok": False, "message": "Передача не найдена — начните заново"}
        have = self.received(uid)
        if offset != have:
            skip()
            return 409, {"ok": False, "offset": have}
        if length <= 0 or length > MAX_PART or have + length > m["size"]:
            return 400, {"ok": False, "message": "Неверный размер части", "offset": have}
        data = rfile.read(length)
        if len(data) != length:
            return 400, {"ok": False, "message": "Соединение прервалось", "offset": have}
        if sha and hashlib.sha256(data).hexdigest() != sha.lower():
            return 422, {"ok": False, "message": "Часть пришла с ошибкой — отправьте её снова", "offset": have}
        with self._lock:
            if self.received(uid) != have:          # a retry of the same part arrived first
                return 409, {"ok": False, "offset": self.received(uid)}
            with open(self._part(uid), "ab") as f:
                f.write(data)
        have += length
        if have < m["size"]:
            return 200, {"ok": True, "offset": have}
        ok, msg, path = self._finish(m)
        return (200 if ok else 500), {"ok": ok, "offset": have, "done": ok, "message": msg,
                                       "name": os.path.relpath(path, inbox.INBOX) if path else None}

    def _target_dir(self, m):
        """Where the file goes: the inbox, or this batch's own copy of the folder («Фото», «Фото (2)» …).
        The choice is kept on disk, so a restart of the server in the middle of a folder changes nothing."""
        if not m["folder"]:
            return inbox.INBOX
        with self._lock:
            batches = os.path.join(self.dir, "batches.json")
            try:
                with open(batches, encoding="utf-8") as f:
                    known = json.load(f)
            except (OSError, ValueError):
                known = {}
            base = known.get(m["batch"]) if m["batch"] else None
            if not base or not base.startswith(inbox.INBOX):
                base, i = os.path.join(inbox.INBOX, m["folder"]), 2
                if m["batch"]:
                    while os.path.exists(base):
                        base = os.path.join(inbox.INBOX, "%s (%d)" % (m["folder"], i))
                        i += 1
                    os.makedirs(base, exist_ok=True)
                    known = {k: v for k, v in known.items() if os.path.exists(v)}
                    known[m["batch"]] = base
                    with open(batches, "w", encoding="utf-8") as f:
                        json.dump(known, f, ensure_ascii=False)
            return os.path.join(base, *m["rel"].split("/")) if m["rel"] else base

    def _finish(self, m):
        d = self._target_dir(m)
        os.makedirs(d, exist_ok=True)
        base, ext = os.path.splitext(m["name"])
        path, i = os.path.join(d, m["name"]), 2
        while os.path.exists(path):
            path = os.path.join(d, "%s (%d)%s" % (base, i, ext))
            i += 1
        try:
            os.replace(self._part(m["id"]), path)
        except OSError as e:
            return False, "Не получилось сохранить: %s" % str(e)[:120], None
        try:
            os.remove(self._meta(m["id"]))
        except OSError:
            pass
        return True, "Сохранено в «Загрузки → TabDock»", path

    def active(self):
        """Files arriving right now (for the transfer window)."""
        out = []
        try:
            names = os.listdir(self.dir)
        except OSError:
            return out
        for f in names:
            if f.endswith(".json") and f != "batches.json":
                m = self._load(f[:-5])
                if m:
                    p = self._part(m["id"])
                    try:
                        mt = os.path.getmtime(p)
                    except OSError:
                        continue
                    out.append({"name": m["name"], "folder": m["folder"], "size": m["size"], "received": self.received(m["id"]),
                                "device": m["device"], "moving": time.time() - mt < 30})
        return sorted(out, key=lambda x: (not x["moving"], x["name"]))

    def status(self, uid):
        m = self._load(uid)
        return {"ok": bool(m), "offset": self.received(uid) if m else 0, "size": m["size"] if m else 0}

    def cleanup(self):
        now = time.time()
        try:
            names = os.listdir(self.dir)
        except OSError:
            return
        for f in names:
            p = os.path.join(self.dir, f)
            try:
                if now - os.path.getmtime(p) > KEEP_PARTS:
                    os.remove(p)
            except OSError:
                pass
