"""Lightroom Classic catalogs (.lrcat, SQLite), read only — like Capture One: every collection is a shoot with its
progress (picks, stars, colour labels). Nothing is ever written into the catalog; Lightroom keeps it locked while it
runs, so it is opened read-only and «immutable» (a snapshot of what is on disk).

Not tested on a real catalog yet: the table layout follows Lightroom Classic 13–15.
"""
import glob
import hashlib
import os
import sqlite3
import sys
import time

# Lightroom colour labels → the colour numbers of the «отдано» rule (the same as Capture One's: green = 4)
LABELS = {"red": 1, "yellow": 3, "green": 4, "blue": 5, "purple": 7}
COLLECTION = "com.adobe.ag.library.collection"


def discover():
    """Catalogs in the usual places: Pictures/Lightroom…/*.lrcat (two levels deep)."""
    home = os.path.expanduser("~")
    pats = [os.path.join(home, "Pictures", "Lightroom*", "*.lrcat"), os.path.join(home, "Pictures", "Lightroom*", "*", "*.lrcat"),
            os.path.join(home, "Pictures", "*.lrcat")]
    if sys.platform == "win32":
        pats.append(os.path.join(os.environ.get("USERPROFILE", home), "OneDrive", "Pictures", "Lightroom*", "*.lrcat"))
    out = []
    for pat in pats:
        for p in glob.glob(pat):
            if "Backups" not in p and p not in out:
                out.append(p)
    return out


def _connect(path):
    uri = "file:%s?mode=ro&immutable=1" % path.replace("?", "%3F").replace("#", "%23")
    con = sqlite3.connect(uri, uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    return con


def _ts(s):
    """'2026-11-18T14:05:31.12' → unix time."""
    if not s:
        return None
    try:
        return time.mktime(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None


SQL = """
SELECT c.id_local AS cid, c.name AS name,
       i.id_local AS img, i.rating AS rating, i.pick AS pick, i.colorLabels AS label, i.captureTime AS shot,
       rf.absolutePath || fo.pathFromRoot || f.baseName || '.' || f.extension AS path
FROM AgLibraryCollection c
JOIN AgLibraryCollectionImage ci ON ci.collection = c.id_local
JOIN Adobe_images i ON i.id_local = ci.image
LEFT JOIN AgLibraryFile f ON f.id_local = i.rootFile
LEFT JOIN AgLibraryFolder fo ON fo.id_local = f.folder
LEFT JOIN AgLibraryRootFolder rf ON rf.id_local = fo.rootFolder
WHERE c.creationId = ?
ORDER BY c.id_local, i.captureTime
"""


def read_catalog(path):
    """Shoots of one catalog, in the same shape as Capture One's (see captureone.derive)."""
    tag = hashlib.sha1(path.encode()).hexdigest()[:8]
    con = _connect(path)
    try:
        rows = con.execute(SQL, (COLLECTION,)).fetchall()
    finally:
        con.close()
    shoots = {}
    for r in rows:
        s = shoots.setdefault(r["cid"], {"key": "lr:%s:%s" % (tag, r["cid"]), "uuid": str(r["cid"]), "name": r["name"] or "Коллекция",
                                         "source": "lr", "catalog": path, "catalog_name": os.path.splitext(os.path.basename(path))[0],
                                         "total": 0, "picked": 0, "rejected": 0, "exported": 0, "colors": {}, "ratings": {},
                                         "shot_from": None, "shot_to": None, "cover_file": None, "camera": ""})
        s["total"] += 1
        pick = r["pick"] or 0
        if pick > 0:
            s["picked"] += 1
        elif pick < 0:
            s["rejected"] += 1
        c = LABELS.get(str(r["label"] or "").strip().lower())
        if c:
            s["colors"][str(c)] = s["colors"].get(str(c), 0) + 1
        rating = int(r["rating"] or 0)
        if rating:
            s["ratings"][str(rating)] = s["ratings"].get(str(rating), 0) + 1
        t = _ts(r["shot"])
        if t:
            s["shot_from"] = min(s["shot_from"] or t, t)
            s["shot_to"] = max(s["shot_to"] or t, t)
        if not s["cover_file"] and r["path"] and os.path.exists(r["path"]):
            s["cover_file"] = r["path"]
    for s in shoots.values():
        s["created"] = s["shot_from"]
    return list(shoots.values())


def open_catalog(path):
    from .osutil import open_path
    open_path(path)        # .lrcat opens in Lightroom Classic on Mac and Windows


class Lightroom:
    """Catalogs are read again only when the file changes."""

    def __init__(self):
        self._cache = {}

    def shoots(self, catalogs):
        items, errors = [], []
        for c in catalogs:
            try:
                mt = os.path.getmtime(c)
                hit = self._cache.get(c)
                if not hit or hit[0] != mt:
                    hit = (mt, read_catalog(c))
                    self._cache[c] = hit
                items += [dict(s) for s in hit[1]]
            except (OSError, sqlite3.Error) as e:
                errors.append({"catalog": c, "error": str(e)[:160]})
        return items, errors
