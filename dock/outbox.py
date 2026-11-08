"""Computer → phone/tablet: files dropped into the «Передача файлов» window wait here until the app picks them up.

Each file is addressed to one device (by its name, as the app reports it) or to all devices. The app downloads it,
saves it to Downloads/TabDock on the phone and says «готово»; a file addressed to all devices stays until every
device that was connected when it was sent has taken it. Files are kept for 24 hours at most.
"""
import json
import os
import shutil
import threading
import time
import uuid

from .inbox import safe_name

KEEP = 24 * 3600
MAX_FILE = 4 * 1024 ** 3     # 4 GB


class Outbox:
    def __init__(self, data_dir):
        self.dir = os.path.join(data_dir, "outbox")
        os.makedirs(self.dir, exist_ok=True)
        self._meta = os.path.join(self.dir, "index.json")
        self._lock = threading.Lock()
        try:
            with open(self._meta) as f:
                self.items = json.load(f)
        except (OSError, ValueError):
            self.items = []
        self.cleanup()

    def _save(self):
        tmp = self._meta + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.items, f, ensure_ascii=False)
        os.replace(tmp, self._meta)

    def cleanup(self):
        now = time.time()
        with self._lock:
            keep = []
            for it in self.items:
                if now - it["at"] > KEEP or it.get("removed"):
                    shutil.rmtree(os.path.join(self.dir, it["id"]), ignore_errors=True)
                else:
                    keep.append(it)
            self.items = keep
            self._save()

    def add(self, rfile, length, name, to, expected):
        """Store an uploaded file. `to` = device name or "" for all; `expected` = devices that should take it."""
        if length <= 0:
            return False, "Пустой файл", None
        if length > MAX_FILE:
            return False, "Файл больше 4 ГБ", None
        fid = uuid.uuid4().hex[:12]
        d = os.path.join(self.dir, fid)
        os.makedirs(d)
        name = safe_name(name)
        path = os.path.join(d, name)
        left = length
        try:
            with open(path, "wb") as f:
                while left > 0:
                    chunk = rfile.read(min(1024 * 1024, left))
                    if not chunk:
                        raise IOError("соединение прервалось")
                    f.write(chunk)
                    left -= len(chunk)
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            return False, "Не получилось принять файл: %s" % str(e)[:100], None
        item = {"id": fid, "name": name, "size": length, "at": time.time(), "to": to or "",
                "expected": sorted(set([to] if to else expected)), "got": []}
        with self._lock:
            self.items.append(item)
            self._save()
        return True, "Файл ждёт телефон" if to else "Файл ждёт устройства", item

    def for_device(self, device):
        """Files this device has not taken yet."""
        now = time.time()
        with self._lock:
            return [{"id": it["id"], "name": it["name"], "size": it["size"], "at": it["at"]}
                    for it in self.items
                    if now - it["at"] < KEEP and not it.get("delivered") and device not in it["got"]
                    and (not it["to"] or it["to"] == device)]

    def path(self, fid):
        it = next((x for x in self.items if x["id"] == fid), None)
        return os.path.join(self.dir, fid, it["name"]) if it else None

    def done(self, fid, device):
        with self._lock:
            for it in self.items:
                if it["id"] == fid and device not in it["got"]:
                    it["got"].append(device)
                    # addressed to one device, or everyone expected has it → delete the copy
                    if it["to"] or (it["expected"] and set(it["expected"]) <= set(it["got"])):
                        it["delivered"] = True      # keep the line for the window, drop the copy
                        shutil.rmtree(os.path.join(self.dir, it["id"]), ignore_errors=True)
            self._save()

    def remove(self, fid):
        with self._lock:
            for it in self.items:
                if it["id"] == fid:
                    it["removed"] = True
            self._save()
        self.cleanup()

    def listing(self):
        """For the transfer window: what is waiting and who already took it."""
        with self._lock:
            return [dict(it) for it in self.items if not it.get("removed")]
