"""Culling from the tablet: list the frames of a Capture One album, serve thumbnails/previews,
and write stars / colour tags back **through Capture One's own AppleScript** (never into the catalog DB).

Capture One must be running with that catalog open; otherwise the client is told so.
Changes are also kept in a small overlay until Capture One has saved them to its database.
"""
import hashlib
import os
import sqlite3
import struct
import subprocess
import threading
import time

from . import captureone

IMAGES_SQL = """
SELECT i.Z_PK AS pk, i.ZIMAGEFILENAME AS fn, i.ZEXP_DATE AS shot, p.ZISRELATIVE AS rel, p.ZRELATIVEPATH AS rp,
       p.ZMACROOT AS root,
       (SELECT v.ZVARIANTUUID FROM ZVARIANT v WHERE v.ZIMAGE = i.Z_PK ORDER BY v.ZINDEX, v.Z_PK LIMIT 1) AS vid,
       (SELECT v.Z_PK FROM ZVARIANT v WHERE v.ZIMAGE = i.Z_PK ORDER BY v.ZINDEX, v.Z_PK LIMIT 1) AS vpk,
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
-- albums can sit at any depth, and Capture One's scripting id is not always the UUID stored in the catalog:
-- look by id everywhere first, then by name (a name counts only when exactly one collection has it)
on findById(parentRef, collId)
  tell application "Capture One"
    repeat with c in (get collections of parentRef)
      set c to contents of c
      try
        if (id of c as text) is collId then return c
      end try
      set r to my findById(c, collId)
      if r is not missing value then return r
    end repeat
  end tell
  return missing value
end findById

on findByName(parentRef, collName)
  set found to {}
  tell application "Capture One"
    repeat with c in (get collections of parentRef)
      set c to contents of c
      try
        if (name of c as text) is collName then set end of found to c
      end try
      set found to found & my findByName(c, collName)
    end repeat
  end tell
  return found
end findByName

on run argv
  set collId to item 1 of argv
  set collName to item 2 of argv
  set catName to item 3 of argv
  set changes to items 4 thru -1 of argv
  -- never start Capture One ourselves: only talk to it when the user already has it open
  if application "Capture One" is not running then return "nodoc"
  tell application "Capture One"
    if (count of documents) is 0 then return "nodoc"
    set doc to current document
    if name of doc does not contain catName then return "otherdoc:" & (name of doc)
    set coll to my findById(doc, collId)
    if coll is missing value then
      set same to my findByName(doc, collName)
      if (count of same) is 1 then set coll to item 1 of same
      if (count of same) > 1 then return "manycoll"
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
        """Path of the original file (inside the catalog for referenced-in images, else at its own root)."""
        rp = (r["rp"] or "").strip("/")
        return os.path.join(catalog if r["rel"] else (r["root"] or "/"), rp, r["fn"])

    def thumb(self, catalog, uuid, pk):
        """Small JPEG for the grid: Capture One's own thumbnail (named by the *variant* id), else made from its preview.
        (.cof files next to the previews are focus maps, not pictures.)"""
        r = self._row(catalog, uuid, pk)
        if not r:
            return None
        if r.get("vpk"):
            cot = os.path.join(catalog, "Cache", "Thumbnails", "%08d.cot" % r["vpk"])
            if os.path.exists(cot):
                return cot
        return self._picture(self._paths(catalog, r), catalog, pk, 480, "s")

    def preview(self, catalog, uuid, pk, hi=False):
        """Large JPEG for the viewer; hi=True is the sharper one fetched only when the photo is zoomed in."""
        r = self._row(catalog, uuid, pk)
        if not r:
            return None
        return self._picture(self._paths(catalog, r), catalog, pk, *((4000, "x") if hi else (1800, "l")))

    # Capture One's own previews (.cop) are an internal JPEG XL proxy, not a display picture, and the .cof next
    # to them is a focus map. So the big picture comes from the camera JPEG embedded in the RAW (instant for Fuji
    # RAF), else macOS decodes the RAW / image itself. It shows the shot as the camera saw it, not the edit.
    def _picture(self, original, catalog, pk, size, tag):
        if not original or not os.path.exists(original):
            return None
        h = hashlib.sha1(catalog.encode()).hexdigest()[:10]
        out = os.path.join(self.cache_dir, "%s_%d_%s2.jpg" % (h, pk, tag))   # "2": made from the RAW, not the .cop proxy
        if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(original):
            return out
        src, tmp = original, None
        emb = embedded_jpeg(original)
        if emb:
            tmp = out + ".src.jpg"
            with open(tmp, "wb") as f:
                f.write(emb)
            src = tmp
        cmd = ["/usr/bin/sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", str(size)]
        rot = {3: 180, 6: 90, 8: 270}.get(jpeg_orientation(emb) if emb else 1)
        if rot:
            cmd += ["-r", str(rot)]
        try:
            subprocess.run(cmd + [src, "--out", out], capture_output=True, timeout=90)
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        if rot and os.path.exists(out):
            with open(out, "r+b") as f:
                buf = bytearray(f.read())
                if jpeg_orientation(buf, reset=True) != 1:
                    f.seek(0); f.write(buf)
        return out if os.path.exists(out) else None

    def _album_name(self, catalog, uuid):
        db = captureone.db_path(catalog)
        con = sqlite3.connect("file:%s?mode=ro" % db.replace("?", "%3F").replace("#", "%23"), uri=True, timeout=3)
        try:
            row = con.execute("SELECT ZNAME FROM ZCOLLECTION WHERE ZUUID = ?", (uuid,)).fetchone()
        finally:
            con.close()
        return (row[0] if row else "") or ""

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
            res = subprocess.run(["/usr/bin/osascript", "-e", TAG_SCRIPT, uuid, self._album_name(catalog, uuid), cat_name] + args,
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
        if out in ("nocoll", "manycoll"):
            return False, ("Capture One не нашёл эту съёмку в открытом каталоге" if out == "nocoll"
                           else "В каталоге несколько альбомов с таким именем — переименуйте один из них")
        if "-1743" in err or "not allowed" in err.lower():
            return False, "macOS не разрешила TabDock управлять Capture One: Настройки → Конфиденциальность → Автоматизация"
        return False, "Capture One: " + (err or out or "ошибка")[:160]


def embedded_jpeg(path):
    """Full-size camera JPEG inside a Fujifilm RAF (offset/length at bytes 84..92 of the header)."""
    if not path.lower().endswith(".raf"):
        return None
    try:
        with open(path, "rb") as f:
            head = f.read(100)
            if not head.startswith(b"FUJIFILMCCD-RAW"):
                return None
            off, ln = struct.unpack(">II", head[84:92])
            f.seek(off)
            data = f.read(ln)
        return data if data[:3] == b"\xff\xd8\xff" else None
    except (OSError, struct.error):
        return None


def jpeg_orientation(data, reset=False):
    """EXIF orientation (1..8) of a JPEG, 1 if absent. reset=True (data a bytearray) sets it to 1 in place,
    for pictures that were already turned upright."""
    try:
        i = 2
        while i < min(len(data), 65536):
            if data[i] != 0xFF:
                return 1
            marker, ln = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker == 0xE1 and data[i + 4:i + 10] == b"Exif\0\0":
                t = i + 10
                end = ">" if data[t:t + 2] == b"MM" else "<"
                ifd = t + struct.unpack(end + "I", data[t + 4:t + 8])[0]
                for k in range(struct.unpack(end + "H", data[ifd:ifd + 2])[0]):
                    e = ifd + 2 + 12 * k
                    if struct.unpack(end + "H", data[e:e + 2])[0] == 0x0112:
                        o = struct.unpack(end + "H", data[e + 8:e + 10])[0]
                        if reset:
                            data[e + 8:e + 10] = struct.pack(end + "H", 1)
                        return o
                return 1
            if marker == 0xDA:
                return 1
            i += 2 + ln
    except (IndexError, struct.error):
        pass
    return 1
