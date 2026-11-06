"""Read Capture One catalogs (read-only) and derive per-shoot progress.

A "shoot" is a user album in the catalog (import batches under
"Recent Imports" are skipped because they duplicate albums). For every shoot:
  total     – images in the album
  picked    – images with a star rating >= 1 or any colour tag
  exported  – images that have at least one entry in the process history
  last_*    – dates of capture / last export
The database is opened with mode=ro so Capture One is never disturbed.
"""
import glob
import os
import sqlite3
import subprocess
import time

# Core Data entity ids differ between versions; detect them by name/shape.
ALBUM_SQL = """
SELECT c.Z_PK, c.Z_ENT, c.ZUUID, c.ZNAME, c.ZPARENT, c.ZDATECREATED,
       p.Z_ENT AS PARENT_ENT, p.ZNAME AS PARENT_NAME
FROM ZCOLLECTION c LEFT JOIN ZCOLLECTION p ON p.Z_PK = c.ZPARENT
"""

STATS_SQL = """
SELECT ic.ZCOLLECTION AS cid,
       COUNT(DISTINCT ic.ZIMAGE) AS total,
       COUNT(DISTINCT CASE WHEN m.ZBASIC_RATING >= 1 OR m.ZCOLOR_TAG_INDEX > 0 THEN ic.ZIMAGE END) AS picked,
       COUNT(DISTINCT ph.img) AS exported,
       MIN(i.ZEXP_DATE) AS shot_from, MAX(i.ZEXP_DATE) AS shot_to,
       MAX(ph.last) AS last_export,
       MIN(ic.ZIMAGE) AS first_img
FROM ZIMAGEINCOLLECTION ic
JOIN ZIMAGE i ON i.Z_PK = ic.ZIMAGE AND COALESCE(i.ZISTRASHED, 0) = 0
LEFT JOIN ZVARIANT v ON v.ZIMAGE = i.Z_PK
LEFT JOIN ZVARIANTLAYER l ON l.ZVARIANT = v.Z_PK
LEFT JOIN ZVARIANTMETADATA m ON m.ZLAYER = l.Z_PK
LEFT JOIN (SELECT v2.ZIMAGE AS img, MAX(h.ZDATE) AS last
           FROM ZPROCESSHISTORY h JOIN ZVARIANT v2 ON v2.Z_PK = h.ZVARIANT
           GROUP BY v2.ZIMAGE) ph ON ph.img = i.Z_PK
GROUP BY ic.ZCOLLECTION
"""

CAMERA_SQL = """
SELECT ic.ZCOLLECTION, i.ZCAMERA_MODEL, COUNT(*) FROM ZIMAGEINCOLLECTION ic
JOIN ZIMAGE i ON i.Z_PK = ic.ZIMAGE GROUP BY 1, 2
"""


def discover():
    """Find Capture One catalogs on this Mac (Spotlight + ~/Pictures)."""
    found = set(glob.glob(os.path.expanduser("~/Pictures/*.cocatalog")))
    try:
        out = subprocess.run(["/usr/bin/mdfind", "kMDItemFSName == '*.cocatalog'"],
                             capture_output=True, text=True, timeout=8).stdout
        for line in out.splitlines():
            if line.endswith(".cocatalog") and "/Backups/" not in line and "/.Trash" not in line:
                found.add(line)
    except Exception:
        pass
    return sorted(found)


def db_path(catalog):
    if catalog.endswith(".cocatalogdb"):
        return catalog
    dbs = glob.glob(os.path.join(catalog, "*.cocatalogdb"))
    return dbs[0] if dbs else None


def _ts(v):
    # Capture One 16 stores unix seconds; older Core Data stores used 2001 epoch.
    if v is None:
        return None
    v = float(v)
    return v + 978307200 if v < 1_000_000_000 else v


NO_ACCESS = ("macOS не даёт TabDock доступ к этому диску. На Mac: Системные настройки → Конфиденциальность "
             "и безопасность → Файлы и папки → python3 → «Съёмные тома» (или «Полный доступ к диску» для python3)")


def read_catalog(catalog):
    try:
        os.listdir(catalog)
    except PermissionError:
        raise PermissionError(NO_ACCESS)
    except FileNotFoundError:
        raise FileNotFoundError("каталог не найден (диск не подключён?): %s" % catalog)
    db = db_path(catalog)
    if not db:
        raise FileNotFoundError("нет базы в %s" % catalog)
    uri = "file:%s?mode=ro" % db.replace("?", "%3F").replace("#", "%23")
    con = sqlite3.connect(uri, uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(ALBUM_SQL).fetchall()
        stats = {r["cid"]: r for r in con.execute(STATS_SQL)}
        cams = {}
        for cid, model, n in con.execute(CAMERA_SQL):
            if model and n > cams.get(cid, ("", 0))[1]:
                cams[cid] = (model, n)
        # Capture One only caches thumbnails for images it has shown: pick the first image that has one
        thumbs_dir = os.path.join(catalog, "Cache", "Thumbnails")
        try:
            have = {int(f[:8]) for f in os.listdir(thumbs_dir) if f.endswith(".cot") and f[:8].isdigit()}
        except OSError:
            have = set()
        covers = {}
        for cid, img in con.execute("SELECT ZCOLLECTION, ZIMAGE FROM ZIMAGEINCOLLECTION ORDER BY ZCOLLECTION, ZIMAGE"):
            if cid not in covers and img in have:
                covers[cid] = img
    finally:
        con.close()

    # Entity of import batches = entity of the children of "Recent imports" style groups:
    # they are albums whose parent is a smart/group collection that is *not* root/user group.
    by_pk = {r["Z_PK"]: r for r in rows}
    root = [r["Z_PK"] for r in rows if r["ZPARENT"] is None]
    album_ent = None
    ent_count = {}
    for r in rows:
        if r["Z_PK"] in stats and r["ZPARENT"] is not None:
            ent_count[r["Z_ENT"]] = ent_count.get(r["Z_ENT"], 0) + 1
    if ent_count:
        album_ent = max(ent_count, key=ent_count.get)
    import_parents = set()
    for r in rows:
        if r["Z_ENT"] != album_ent and r["ZPARENT"] in root and any(
                c["ZPARENT"] == r["Z_PK"] and c["Z_ENT"] == album_ent for c in rows):
            import_parents.add(r["Z_PK"])

    thumbs = os.path.join(catalog, "Cache", "Thumbnails")
    shoots = []
    for r in rows:
        if r["Z_ENT"] != album_ent or r["Z_PK"] not in stats:
            continue
        if r["ZPARENT"] in import_parents:
            continue
        s = stats[r["Z_PK"]]
        cover = None
        img = covers.get(r["Z_PK"], s["first_img"])
        thumb = os.path.join(thumbs, "%08d.cot" % img) if img else None
        if thumb and os.path.exists(thumb):
            cover = thumb
        parent = by_pk.get(r["ZPARENT"])
        shoots.append({
            "uuid": r["ZUUID"],
            "name": r["ZNAME"] or "Без названия",
            "group": parent["ZNAME"] if parent is not None and parent["ZPARENT"] is not None else None,
            "total": s["total"],
            "picked": s["picked"],
            "exported": s["exported"],
            "shot_from": _ts(s["shot_from"]),
            "shot_to": _ts(s["shot_to"]),
            "created": _ts(r["ZDATECREATED"]),
            "last_export": _ts(s["last_export"]),
            "camera": cams.get(r["Z_PK"], (None,))[0],
            "cover_file": cover,
        })
    # Fallback: catalog without albums -> use import batches as shoots
    if not shoots:
        for r in rows:
            if r["ZPARENT"] in import_parents and r["Z_PK"] in stats:
                s = stats[r["Z_PK"]]
                shoots.append({"uuid": r["ZUUID"], "name": r["ZNAME"], "group": "Импорт",
                               "total": s["total"], "picked": s["picked"], "exported": s["exported"],
                               "shot_from": _ts(s["shot_from"]), "shot_to": _ts(s["shot_to"]),
                               "created": _ts(r["ZDATECREATED"]), "last_export": _ts(s["last_export"]),
                               "camera": None, "cover_file": None})
    return shoots


class CaptureOne:
    def __init__(self):
        self._cache = {}  # catalog -> (mtime, shoots)

    def shoots(self, catalogs):
        res, errors = [], []
        for cat in catalogs:
            db = db_path(cat)
            try:
                mt = os.path.getmtime(db) if db else 0
                cached = self._cache.get(cat)
                if not cached or cached[0] != mt:
                    cached = (mt, read_catalog(cat))
                    self._cache[cat] = cached
                for s in cached[1]:
                    s = dict(s)
                    s["catalog"] = cat
                    s["catalog_name"] = os.path.splitext(os.path.basename(cat))[0]
                    s["key"] = "c1:" + s["uuid"]
                    res.append(s)
            except Exception as e:
                errors.append({"catalog": cat, "error": str(e)})
        return res, errors


def backup_info(catalog):
    """Newest Capture One catalog backup: `*.cocatalogdb.backup N` next to the base and
    ~/Library/Application Support/Capture One/Backups/<catalog>/<date>/ (both layouts exist)."""
    stamps = []
    try:
        for f in os.listdir(catalog):
            if ".cocatalogdb.backup" in f and not f.startswith("._"):
                stamps.append(os.path.getmtime(os.path.join(catalog, f)))
    except OSError:
        pass
    name = os.path.splitext(os.path.basename(catalog))[0]
    bdir = os.path.expanduser(os.path.join("~/Library/Application Support/Capture One/Backups", name))
    try:
        for f in os.listdir(bdir):
            p = os.path.join(bdir, f)
            if os.path.isdir(p):
                stamps.append(os.path.getmtime(p))
    except OSError:
        pass
    return {"catalog": catalog, "name": name, "last": max(stamps) if stamps else None, "count": len(stamps)}


def catalog_volume(catalog):
    """Mount point of the disk that holds the catalog (None for the system disk)."""
    parts = catalog.split("/")
    if len(parts) > 2 and parts[1] == "Volumes":
        return "/" + "/".join(parts[1:3])
    return None


def derive(shoot, manual):
    """Merge catalog stats with manual overrides -> progress + status."""
    m = manual or {}
    total, picked, exported = shoot.get("total", 0), shoot.get("picked", 0), shoot.get("exported", 0)
    target = m.get("target") or (picked if picked else total) or 0
    if shoot.get("source") == "manual":
        done = m.get("done", 0)
        target = m.get("target") or 0
    else:
        done = exported
    progress = min(1.0, done / target) if target else 0.0
    auto = "new" if done == 0 and not picked else ("selecting" if done == 0 else ("done" if progress >= 1 else "editing"))
    status = m.get("status") or auto
    if status == "done" and m.get("status"):
        progress = max(progress, 1.0 if not target else progress)
    shoot.update({"target": target, "done": done, "progress": round(progress, 3),
                  "status": status, "status_auto": auto, "status_manual": bool(m.get("status")),
                  "deadline": m.get("deadline"), "note": m.get("note", ""), "client": m.get("client", ""),
                  "hidden": bool(m.get("hidden")), "target_manual": bool(m.get("target"))})
    return shoot


def open_in_c1(catalog):
    subprocess.Popen(["/usr/bin/open", "-a", "Capture One", catalog])


if __name__ == "__main__":
    import json
    for c in discover():
        print(c)
        for s in read_catalog(c):
            print(json.dumps(derive(s, {}), ensure_ascii=False, default=str))
