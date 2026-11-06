"""Folder-based shoots for editors without a catalog (Photon Studio, Photoshop, …).

A configured root folder contains one sub-folder per shoot:

    Shoots/
      2026-11-01 Improv/
        DSCF0001.RAF …            <- originals (RAW, or JPEG/HEIF if there is no RAW)
        Improv.photon / *.psd     <- work files (counted as "в работе")
        Export/  (or Экспорт, Готово, Final, Output …)
          DSCF0001.jpg …          <- finished files

progress = finished files / originals (or a manual target). Scanned in the background every 60 s.
"""
import hashlib
import unicodedata
import os
import subprocess
import threading
import time

RAW = {"raf", "dng", "cr2", "cr3", "nef", "nrw", "arw", "srf", "sr2", "orf", "rw2", "pef", "rwl", "3fr", "fff",
       "iiq", "erf", "mos", "mrw", "x3f", "srw", "kdc", "dcr"}
IMAGES = {"jpg", "jpeg", "tif", "tiff", "png", "heic", "heif", "hif", "webp", "avif", "jxl"}
WORK = {"photon", "psd", "psb", "afphoto", "xcf"}
DEFAULT_EXPORT_DIRS = ["export", "exports", "экспорт", "output", "готово", "final", "finals", "ready", "jpg", "done"]


def _ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def key_for(path):
    return "dir:" + hashlib.sha1(path.encode()).hexdigest()[:12]


def scan_shoot(path, export_dirs):
    raws, imgs, work, exported = [], [], 0, []
    nfc = lambda x: unicodedata.normalize("NFC", x).lower()   # macOS stores names decomposed (й, ё)
    export_dirs = {nfc(d) for d in export_dirs}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel = os.path.relpath(root, path)
        top = nfc(rel.split(os.sep)[0]) if rel != "." else ""
        in_export = top in export_dirs
        for f in files:
            if f.startswith("."):
                continue
            e = _ext(f)
            full = os.path.join(root, f)
            if in_export:
                if e in IMAGES:
                    exported.append(full)
            elif e in RAW:
                raws.append(full)
            elif e in IMAGES:
                imgs.append(full)
            elif e in WORK:
                work += 1
        if root.count(os.sep) - path.count(os.sep) > 3:   # don't wander too deep
            dirs[:] = []
    originals = raws or imgs
    mt = lambda lst: [os.path.getmtime(x) for x in lst]
    o_times, e_times = mt(originals), mt(exported)
    cover = sorted(exported)[0] if exported else (sorted(imgs)[0] if imgs else None)
    return {
        "total": len(originals), "picked": 0, "exported": len(exported), "work_files": work,
        "shot_from": min(o_times) if o_times else os.path.getmtime(path),
        "shot_to": max(o_times) if o_times else None,
        "last_export": max(e_times) if e_times else None,
        "created": os.path.getmtime(path), "cover_file": cover,
    }


class FolderShoots:
    def __init__(self, roots_fn, cache_dir):
        self.roots_fn = roots_fn          # -> [{"path", "app"}], export dir names
        self.cache_dir = cache_dir
        self.items, self.errors = [], []
        self._paths = {}
        self._kick = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def kick(self):
        self._kick.set()

    def _loop(self):
        while True:
            try:
                self.refresh()
            except Exception as e:
                self.errors = [{"catalog": "папки", "error": str(e)}]
            self._kick.wait(60)
            self._kick.clear()

    def refresh(self):
        roots, export_dirs = self.roots_fn()
        items, errors, paths = [], [], {}
        for r in roots:
            root = os.path.expanduser(r.get("path", ""))
            app = r.get("app") or "Папки"
            try:
                subs = sorted((e for e in os.scandir(root) if e.is_dir() and not e.name.startswith(".")), key=lambda e: e.name)
            except PermissionError:
                errors.append({"catalog": root, "error": "macOS не даёт доступ к папке — разрешите python3 доступ "
                                                         "(Конфиденциальность → Файлы и папки / Полный доступ к диску)"})
                continue
            except FileNotFoundError:
                errors.append({"catalog": root, "error": "папка не найдена (диск не подключён?)"})
                continue
            for e in subs:
                s = scan_shoot(e.path, export_dirs)
                k = key_for(e.path)
                s.update({"uuid": k[4:], "key": k, "name": e.name, "source": "folder", "catalog": root,
                          "catalog_name": app, "camera": None, "group": None, "path": e.path})
                paths[k] = e.path
                items.append(s)
        self.items, self.errors, self._paths = items, errors, paths

    def path(self, key):
        return self._paths.get(key)

    def thumb(self, key):
        """Small JPEG of the cover, made once with sips and cached."""
        src = next((s.get("cover_file") for s in self.items if s["key"] == key), None)
        if not src:
            return None
        out = os.path.join(self.cache_dir, "thumbs", hashlib.sha1(src.encode()).hexdigest()[:16] + ".jpg")
        if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg", "-Z", "480", src, "--out", out],
                           capture_output=True, timeout=30)
        return out if os.path.exists(out) else None
