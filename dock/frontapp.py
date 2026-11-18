"""Which program is in front on the computer right now — so the «Свои кнопки» widget can show that program's buttons.

macOS: lsappinfo (no permissions needed). Windows: the foreground window's process. Linux: X11 through xdotool;
Wayland does not tell other programs which window is active, so there the buttons stay as they are.
"""
import os
import re
import shutil
import subprocess
import sys
import threading
import time

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
# Windows / Linux process names → the names people know (and the presets match)
FRIENDLY = {"photoshop": "Adobe Photoshop", "photon studio": "Photon Studio", "photonstudio": "Photon Studio",
            "lightroom": "Lightroom Classic", "captureone": "Capture One", "capture one": "Capture One",
            "krita": "Krita", "clipstudiopaint": "Clip Studio Paint", "clip studio paint": "Clip Studio Paint",
            "darktable": "darktable", "digikam": "digiKam", "gimp": "GIMP", "affinity": "Affinity",
            "blender": "Blender", "obs64": "OBS Studio", "obs": "OBS Studio", "code": "Visual Studio Code"}


def friendly(name):
    n = (name or "").strip()
    low = re.sub(r"\.exe$", "", n.lower())
    for k, v in FRIENDLY.items():
        if low == k or low.startswith(k):
            return v
    return re.sub(r"\.exe$", "", n, flags=re.I)


def _run(cmd, timeout=3):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _mac():
    asn = _run(["lsappinfo", "front"]).strip()
    if not asn:
        return None
    out = _run(["lsappinfo", "info", "-only", "name", asn])
    # macOS versions print either «"LSDisplayName"="Firefox"» or «"Firefox" ASN:… (in front)»
    m = re.search(r'"LSDisplayName"="([^"]+)"', out) or re.match(r'\s*"([^"]+)"', out)
    name = m.group(1) if m else None
    return None if name in ("loginwindow", "ScreenSaverEngine") else name


def _windows():
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        if not k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return None
        return friendly(os.path.basename(buf.value))
    finally:
        k.CloseHandle(h)


def _linux():
    if os.environ.get("WAYLAND_DISPLAY") or not shutil.which("xdotool"):
        return None
    pid = _run(["xdotool", "getactivewindow", "getwindowpid"]).strip()
    if not pid.isdigit():
        return None
    try:
        with open("/proc/%s/comm" % pid, encoding="utf-8") as f:
            return friendly(f.read().strip())
    except OSError:
        return None


def front_app():
    try:
        if sys.platform == "darwin":
            return _mac()
        if sys.platform == "win32":
            return _windows()
        return _linux()
    except Exception:
        return None


class FrontApp:
    """Checked every second in the background; requests only read the last value."""

    def __init__(self, interval=1.0):
        self.name = None
        self.interval = interval
        threading.Thread(target=self._loop, name="frontapp", daemon=True).start()

    def _loop(self):
        while True:
            n = front_app()
            if n and not n.lower().startswith(("tabdock", "python", "pythonw")):   # TabDock's own windows do not count
                self.name = n
            time.sleep(self.interval)
