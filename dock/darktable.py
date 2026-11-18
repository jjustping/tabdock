"""darktable library (library.db, SQLite), read only: every film roll (an imported folder) is a shoot with its stars,
rejects, colour labels and the «exported» count (darktable tags exported images «darktable|exported»).
Nothing is ever written; the database is opened read-only and «immutable» (darktable may be running).
"""
import hashlib
import os
import re
import sqlite3
import sys

# darktable colour labels (0 red … 4 purple) → the colour numbers of the «отдано» rule (Capture One's: green = 4)
LABELS = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}
REJECTED = 8                  # flags bit since darktable 3.0; before that a rating of 6 meant «rejected»
GTIME_UNIX = 62135596800      # seconds from 0001-01-01 (darktable's GTimeSpan) to 1970-01-01


def config_dir():
    if sys.platform == "win32":
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "darktable")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"), "darktable")


def discover():
    p = os.path.join(config_dir(), "library.db")
    return [p] if os.path.isfile(p) else []


def _connect(path):
    uri = "file:%s?mode=ro&immutable=1" % path.replace("?", "%3F").replace("#", "%23")
    con = sqlite3.connect(uri, uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    return con


def _taken(v):
    """darktable 4+: microseconds since year 1; older: «YYYY:MM:DD HH:MM:SS» text."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v / 1e6 - GTIME_UNIX if v > 1e12 else None
    import time
    try:
        return time.mktime(time.strptime(str(v)[:19], "%Y:%m:%d %H:%M:%S"))
    except ValueError:
        return None


def _exported(con, path):
    """Image ids tagged «darktable|exported» (the tag names live in data.db next to library.db)."""
    data = os.path.join(os.path.dirname(path), "data.db")
    if not os.path.isfile(data):
        return set()
    try:
        con.execute("ATTACH DATABASE ? AS d", ("file:%s?mode=ro&immutable=1" % data,))
        rows = con.execute("SELECT ti.imgid FROM tagged_images ti JOIN d.tags t ON t.id = ti.tagid "
                           "WHERE t.name = 'darktable|exported'").fetchall()
        return {r[0] for r in rows}
    except sqlite3.Error:
        return set()


def read_library(path):
    tag = hashlib.sha1(path.encode()).hexdigest()[:8]
    con = _connect(path)
    try:
        rows = con.execute("SELECT f.id AS fid, f.folder AS folder, i.id AS img, i.filename AS filename, i.flags AS flags, "
                           "i.datetime_taken AS taken FROM film_rolls f JOIN images i ON i.film_id = f.id "
                           "ORDER BY f.id, i.id").fetchall()
        labels = {}
        for r in con.execute("SELECT imgid, color FROM color_labels").fetchall():
            labels.setdefault(r[0], []).append(r[1])
        exported = _exported(con, path)
    finally:
        con.close()
    shoots = {}
    for r in rows:
        folder = r["folder"] or ""
        s = shoots.setdefault(r["fid"], {"key": "dt:%s:%s" % (tag, r["fid"]), "uuid": str(r["fid"]),
                                         "name": re.split(r"[\\/]", folder.rstrip("/\\"))[-1] or "Плёнка",
                                         "source": "dt", "catalog": path, "catalog_name": "darktable", "folder": folder,
                                         "total": 0, "picked": 0, "rejected": 0, "exported": 0, "colors": {}, "ratings": {},
                                         "shot_from": None, "shot_to": None, "cover_file": None, "camera": ""})
        s["total"] += 1
        flags = r["flags"] or 0
        rating = flags & 7
        if flags & REJECTED or rating == 6:
            s["rejected"] += 1
            rating = 0
        if rating:
            s["ratings"][str(rating)] = s["ratings"].get(str(rating), 0) + 1
        for c in labels.get(r["img"], []):
            n = LABELS.get(c)
            if n:
                s["colors"][str(n)] = s["colors"].get(str(n), 0) + 1
        if r["img"] in exported:
            s["exported"] += 1
        t = _taken(r["taken"])
        if t:
            s["shot_from"] = min(s["shot_from"] or t, t)
            s["shot_to"] = max(s["shot_to"] or t, t)
        p = os.path.join(folder, r["filename"] or "")
        if not s["cover_file"] and r["filename"] and os.path.exists(p):
            s["cover_file"] = p
    for s in shoots.values():
        # darktable has no «pick» flag: what is left after the rejects is the selection
        s["picked"] = s["total"] - s["rejected"] if s["rejected"] else 0
        s["created"] = s["shot_from"]
    return list(shoots.values())


class Darktable:
    """The library is read again only when the file changes."""

    def __init__(self):
        self._cache = {}

    def shoots(self, libraries):
        items, errors = [], []
        for c in libraries:
            try:
                mt = os.path.getmtime(c)
                hit = self._cache.get(c)
                if not hit or hit[0] != mt:
                    hit = (mt, read_library(c))
                    self._cache[c] = hit
                items += [dict(s) for s in hit[1]]
            except (OSError, sqlite3.Error) as e:
                errors.append({"catalog": c, "error": str(e)[:160]})
        return items, errors


def open_folder(folder):
    """Open the film roll in darktable (its folder as the argument); the folder itself when darktable is not found."""
    import shutil
    import subprocess
    from .osutil import open_path
    exe = shutil.which("darktable")
    if sys.platform == "win32" and not exe:
        cand = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "darktable", "bin", "darktable.exe")
        exe = cand if os.path.isfile(cand) else None
    if sys.platform == "darwin" and not exe and os.path.isdir("/Applications/darktable.app"):
        return subprocess.Popen(["open", "-a", "darktable", folder])
    if exe:
        return subprocess.Popen([exe, folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    open_path(folder)
