"""«Недавние работы»: files of creative programs opened lately, to reopen them from the tablet with one tap.

Sources: Photon Studio's own list (preferences.json → recentFiles), and the system's recent documents —
Spotlight on a Mac, ~/.local/share/recently-used.xbel on Linux, the Recent folder on Windows. Only work files
(photos, layered files, drawings) are kept, so the list is not flooded with PDFs and text files.
"""
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

WORK = {".psd", ".psb", ".tif", ".tiff", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".kra", ".clip", ".xcf",
        ".afphoto", ".afdesign", ".procreate", ".dng", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".orf", ".rw2",
        ".lrcat", ".cocatalog", ".blend", ".svg", ".ora", ".photon"}
LIMIT = 30


def _home():
    return os.path.expanduser("~")


def photon_files():
    """Photon Studio keeps its recent list as plain paths."""
    if sys.platform == "darwin":
        base = os.path.join(_home(), "Library", "Application Support", "Photon Studio")
    elif sys.platform == "win32":
        base = os.path.join(os.environ.get("APPDATA", _home()), "Photon Studio")
    else:
        base = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(_home(), ".config"), "Photon Studio")
    prefs = os.path.join(base, "preferences.json")
    try:
        with open(prefs, encoding="utf-8") as f:
            items = json.load(f).get("recentFiles") or []
    except (OSError, ValueError, AttributeError):
        return []
    # the list is newest first and has no dates: the newest file was opened about when the list was last written
    at = _mtime(prefs)
    out = []
    for i, x in enumerate(items):
        p = x if isinstance(x, str) else (x.get("path") if isinstance(x, dict) else None)
        if p:
            out.append({"path": p, "app": "Photon Studio", "at": at - i})
    return out


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0


def _mac_spotlight(days=14):
    exts = " || ".join('kMDItemFSName == "*%s"c' % e for e in sorted(WORK))
    q = "kMDItemLastUsedDate >= $time.today(-%d) && (%s)" % (days, exts)
    try:
        out = subprocess.run(["mdfind", "-onlyin", _home(), q], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    paths = [p for p in out.splitlines() if p and "/Library/" not in p and "/." not in p]
    return [{"path": p, "app": "", "at": _used_at(p)} for p in paths[:200]]


def _used_at(p):
    # Spotlight's «last used» is what matters; mtime is a fair stand-in and needs no extra call per file
    return _mtime(p)


def _linux_xbel():
    path = os.path.join(_home(), ".local", "share", "recently-used.xbel")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    out = []
    for b in root.iter("bookmark"):
        href = b.get("href", "")
        if not href.startswith("file://"):
            continue
        p = urllib.parse.unquote(urllib.parse.urlparse(href).path)
        if re.match(r"^/[A-Za-z]:", p):          # file:///C:/… on Windows
            p = p[1:]
        at = b.get("visited") or b.get("modified") or ""
        try:
            t = time.mktime(time.strptime(at[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            t = _mtime(p)
        app = ""
        for a in b.iter():
            if a.tag.endswith("application") and a.get("name"):
                app = a.get("name")
        out.append({"path": p, "app": app, "at": t})
    return out


def _windows_recent():
    """Shortcuts in the Recent folder; opening the shortcut opens the file in its program."""
    base = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
    out = []
    for lnk in glob.glob(os.path.join(base, "*.lnk")):
        name = os.path.basename(lnk)[:-4]
        if os.path.splitext(name)[1].lower() in WORK:
            out.append({"path": lnk, "name": name, "app": "", "at": _mtime(lnk)})
    return out


def collect():
    items = photon_files()
    if sys.platform == "darwin":
        items += _mac_spotlight()
    elif sys.platform == "win32":
        items += _windows_recent()
    else:
        items += _linux_xbel()
    seen, out = set(), []
    for it in sorted(items, key=lambda x: -(x.get("at") or 0)):
        p = it["path"]
        name = it.get("name") or os.path.basename(p.rstrip("/\\"))
        ext = os.path.splitext(name)[1].lower()
        if ext not in WORK or p in seen or not os.path.exists(p):
            continue
        seen.add(p)
        out.append({"path": p, "name": name, "ext": ext.lstrip("."), "app": it.get("app") or "",
                    "folder": os.path.basename(os.path.dirname(p)) if not p.lower().endswith(".lnk") else "",
                    "at": it.get("at") or 0})
        if len(out) >= LIMIT:
            break
    return out


class Recent:
    """Gathered in the background every minute (Spotlight can take a moment); requests read the last list."""

    def __init__(self, enabled=lambda: True, interval=60):
        self.items = []
        self.enabled = enabled
        self.interval = interval
        self._kick = threading.Event()
        threading.Thread(target=self._loop, name="recent", daemon=True).start()

    def _loop(self):
        while True:
            if self.enabled():
                try:
                    self.items = collect()
                except Exception:
                    pass
            self._kick.wait(self.interval)
            self._kick.clear()

    def refresh(self):
        self._kick.set()

    def allowed(self, path):
        """Only a file that is in the list right now can be opened from the tablet."""
        return any(i["path"] == path for i in self.items)
