"""Tiny JSON file store with atomic writes."""
import copy
import json
import os
import secrets
import sys
import threading
import time
import uuid

_lock = threading.RLock()


def new_id():
    return uuid.uuid4().hex[:10]


class Store:
    def __init__(self, data_dir):
        self.dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._mem = {}

    def path(self, name):
        return os.path.join(self.dir, name + ".json")

    def load(self, name, default):
        with _lock:
            if name in self._mem:
                return copy.deepcopy(self._mem[name])
            try:
                with open(self.path(name), encoding="utf-8") as f:
                    val = json.load(f)
            except (OSError, ValueError):
                val = copy.deepcopy(default)
                if callable(val):
                    val = val()
                self._write(name, val)
            self._mem[name] = val
            return copy.deepcopy(val)

    def save(self, name, val):
        with _lock:
            self._mem[name] = copy.deepcopy(val)
            self._write(name, val)

    def _write(self, name, val):
        tmp = self.path(name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(val, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path(name))

    def update(self, name, default, fn):
        """Atomically load -> fn(value) -> save. fn may return a result."""
        with _lock:
            val = self.load(name, default)
            res = fn(val)
            self.save(name, val)
            return res


DEFAULT_APPS = ["Capture One", "Serato DJ Pro", "Finder", "Safari", "Music", "Telegram",
                "Photos", "System Settings", "Activity Monitor", "Terminal"]
if sys.platform != "darwin":   # Linux: names as the .desktop files show them (only installed ones appear)
    DEFAULT_APPS = ["Files", "Firefox", "Terminal", "Settings", "Text Editor", "Resources", "darktable", "GIMP",
                    "digiKam", "Visual Studio Code", "Telegram", "Spotify",
                    "Файлы", "Терминал", "Параметры", "Текстовый редактор"]


def default_config():
    return {
        "token": secrets.token_urlsafe(12),
        "place": None,
        "apps": DEFAULT_APPS,
        "folders": [
            {"title": "Загрузки", "path": "~/Downloads"},
            {"title": "Изображения", "path": "~/Pictures"},
            {"title": "Рабочий стол", "path": "~/Desktop"},
        ],
        "c1_catalogs": [],      # empty = auto-discover
        "calendar": True,
        "created": time.time(),
    }


def default_notes():
    # ready-made cheat sheets live in notesets.py (by scenario); a fresh install gets the system's shortcuts
    from .notesets import default_notes as _d
    return _d()
