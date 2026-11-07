"""Culling from the tablet: list the frames of a Capture One album, serve thumbnails/previews,
and write stars / colour tags back **through Capture One's own AppleScript** (never into the catalog DB).

Capture One must be running with that catalog open; otherwise the client is told so.
Changes are also kept in a small overlay until Capture One has saved them to its database.
"""
import hashlib
import os
import sqlite3
import subprocess
import threading
import time

from . import captureone

IMAGES_SQL = """
SELECT i.Z_PK AS pk, i.ZIMAGEFILENAME AS fn, i.ZEXP_DATE AS shot, p.ZISRELATIVE AS rel, p.ZRELATIVEPATH AS rp,
       p.ZMACROOT AS root,
       (SELECT v.ZVARIANTUUID FROM ZVARIANT v WHERE v.ZIMAGE = i.Z_PK ORDER BY v.ZINDEX, v.Z_PK LIMIT 1) AS vid,
       (SELECT MAX(COALESCE(m.ZBASIC_RATING, 0)) FROM ZVARIANT v JOIN ZVARIANTLAYER l ON l.ZVARIANT = v.Z_PK
          JOIN ZVARIANTMETADATA m ON m.ZLAYER = l.Z_PK WHERE v.ZIMAGE = i.Z_PK) AS rating,
       (SELECT MAX(COALESCE(m.ZCOLOR_TAG_INDEX, 0)) FROM ZVARIANT v JOIN ZVARIANTLAYER l ON l.ZVARIANT = v.Z_PK
          JOIN ZVARIANTMETADATA m ON m.ZLAYER = l.Z_PK WHERE v.ZIMAGE = i.Z_PK) AS color,
       EXISTS (SELECT 1 FROM ZPROCESSHISTORY h JOIN ZVARIANT v2 ON v2.Z_PK = h.ZVARIANT WHERE v2.ZIMAGE = i.Z_PK) AS exported
FROM ZIMAGEINCOLLECTION ic
JOIN ZIMAGE i ON i.Z_PK = ic.ZIMAGE AND COALESCE(i.ZISTRASHED, 0) = 0
JOIN ZPATHLOCATION p ON p.Z_PK = i.ZIMAGELOCATION
WHERE ic.ZCOLLECTION = (SELECT Z_PK FROM ZCOLLECTION WHERE ZUUID = ?)
ORDER BY i.ZEXP_DATE, i.ZIMAGEFILENAME
"""

TAG_SCRIPT = r'''
on run argv
  set collId to item 1 of argv
  set catName to item 2 of argv
  set changes to items 3 thru -1 of argv
  tell application "Capture One"
    if (count of documents) is 0 then return "nodoc"
    set doc to current document
    if name of doc does not contain catName then return "otherdoc:" & (name of doc)
    set coll to missing value
    try
      set coll to first collection of doc whose id is collId
    end try
    if coll is missing value then
      repeat with c in (collections of doc)
        try
          set coll to first collection of c whose id is collId
          exit repeat
        end try
      end repeat
    end if
    if coll is missing value then return "nocoll"
    set n to 0
    set AppleScript's text item delimiters to "|"
    repeat with ch in changes
      set parts to text items of (ch as text)
      set v to missing value
      try
        set v to first variant of coll whose id is (item 1 of parts)
      end try
      if v is missing value then
        try
          set v to first variant of coll whose name is (item 2 of parts)
        end try
      end if
      if v is not missing value then
        if item 3 of parts is not "-" then set rating of v to ((item 3 of parts) as integer)
        if item 4 of parts is not "-" then set color tag of v to ((item 4 of parts) as integer)
        set n to n + 1
      end if
    end repeat
    return "ok " & n
  end tell
end run
'''


class Culling:
    def __init__(self, cache_dir):
        self.cache_dir = os.path.join(cache_dir, "cull")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.overlay = {}          # (catalog, pk) -> {"rating", "color", "at"}
        self._lists = {}           # (catalog, uuid) -> (mtime, rows)
        self._lock = threading.Lock()

    # ---------------- listing ----------------
    def images(self, catalog, uuid):
        db = captureone.db_path(catalog)
        mt = os.path.getmtime(db)
        key = (catalog, uuid)
        cached = self._lists.get(key)
        if not cached or cached[0] != mt:
            con = sqlite3.connect("file:%s?mode=ro" % db.replace("?", "%3F").replace("#", "%23"), uri=True, timeout=3)
            con.row_factory = sqlite3.Row
            try:
                rows = [dict(r) for r in con.execute(IMAGES_SQL, (uuid,))]
            finally:
                con.close()
            cached = (mt, rows)
            self._lists[key] = cached
        now = time.time()
        out = []
        for r in cached[1]:
            item = {"img": r["pk"], "vid": r["vid"], "name": r["fn"], "rating": r["rating"] or 0, "color": r["color"] or 0,
                    "exported": bool(r["exported"]), "shot": captureone._ts(r["shot"])}
            ov = self.overlay.get((catalog, r["pk"]))
            if ov and now - ov["at"] < 900:
                item.update({k: v for k, v in ov.items() if k in ("rating", "color")})
            out.append(item)
        return out

    def _row(self, catalog, uuid, pk):
        cached = self._lists.get((catalog, uuid))
        if not cached:
            self.images(catalog, uuid); cached = self._lists.get((catalog, uuid))
        return next((r for r in cached[1] if r["pk"] == pk), None)

    # ---------------- pictures ----------------
    def _paths(self, catalog, r):
        rp = (r["rp"] or "").strip("/")
        if r["rel"]:
            original = os.path.join(catalog, rp, r["fn"])
            sub = rp[len("Originals/"):] if rp.startswith("Originals/") else rp
        else:
            original = os.path.join(r["root"] or "/", rp, r["fn"])
            sub = rp
        prev = os.path.join(catalog, "Cache", "Previews", sub, r["fn"])
        return original, prev + ".cof", prev + ".cop"

    def thumb(self, catalog, uuid, pk):
        """Small JPEG for the grid: Capture One's own thumbnail or small preview, else made from the original."""
        r = self._row(catalog, uuid, pk)
        if not r:
            return None
        cot = os.path.join(catalog, "Cache", "Thumbnails", "%08d.cot" % pk)
        if os.path.exists(cot):
            return cot
        original, cof, cop = self._paths(catalog, r)
        if os.path.exists(cof):
            return cof
        return self._convert(cop if os.path.exists(cop) else original, catalog, pk, 480, "s")

    def preview(self, catalog, uuid, pk):
        """Large JPEG for the viewer (Capture One's big preview is JPEG XL → converted once and cached)."""
        r = self._row(catalog, uuid, pk)
        if not r:
            return None
        original, cof, cop = self._paths(catalog, r)
        src = cop if os.path.exists(cop) else original
        return self._convert(src, catalog, pk, 1800, "l") or (cof if os.path.exists(cof) else None)

    def _convert(self, src, catalog, pk, size, tag):
        if not src or not os.path.exists(src):
            return None
        h = hashlib.sha1(catalog.encode()).hexdigest()[:10]
        out = os.path.join(self.cache_dir, "%s_%d_%s.jpg" % (h, pk, tag))
        if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
            return out
        subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", str(size), src, "--out", out],
                       capture_output=True, timeout=60)
        return out if os.path.exists(out) else None

    # ---------------- writing tags via Capture One ----------------
    def tag(self, catalog, uuid, changes):
        """changes: [{"img": pk, "rating": 0..5?, "color": 0..7?}] → AppleScript to Capture One."""
        self.images(catalog, uuid)   # make sure the list is cached
        rows = {r["pk"]: r for r in self._lists[(catalog, uuid)][1]}
        args = []
        for ch in changes[:200]:
            r = rows.get(int(ch.get("img", -1)))
            if not r:
                continue
            rating = ch.get("rating"); color = ch.get("color")
            rating = "-" if rating is None else str(max(0, min(5, int(rating))))
            color = "-" if color is None else str(max(0, min(7, int(color))))
            args.append("%s|%s|%s|%s" % (r["vid"] or "", os.path.splitext(r["fn"])[0], rating, color))
        if not args:
            return False, "Нечего менять"
        cat_name = os.path.splitext(os.path.basename(catalog))[0]
        try:
            res = subprocess.run(["/usr/bin/osascript", "-e", TAG_SCRIPT, uuid, cat_name] + args,
                                 capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return False, "Capture One не ответил — возможно, на компьютере ждёт окно разрешения"
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        if out.startswith("ok"):
            now = time.time()
            for ch in changes:
                ov = self.overlay.setdefault((catalog, int(ch["img"])), {})
                for k in ("rating", "color"):
                    if ch.get(k) is not None:
                        ov[k] = int(ch[k])
                ov["at"] = now
            n = out.split()[-1]
            return True, "Записано в Capture One: %s" % n
        if out == "nodoc" or "isn’t running" in err or "not running" in err or "-600" in err:
            return False, "Откройте каталог в Capture One — метки ставятся через него"
        if out.startswith("otherdoc"):
            return False, "В Capture One открыт другой каталог (%s)" % out.split(":", 1)[-1]
        if out == "nocoll":
            return False, "Capture One не нашёл эту съёмку в открытом каталоге"
        if "-1743" in err or "not allowed" in err.lower():
            return False, "macOS не разрешила TabDock управлять Capture One: Настройки → Конфиденциальность → Автоматизация"
        return False, "Capture One: " + (err or out or "ошибка")[:160]
