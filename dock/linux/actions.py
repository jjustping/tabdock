"""Quick actions on Linux: launch apps (.desktop), open folders, suspend, blank the screen, screenshot,
keep awake (systemd-inhibit), eject disks (udisksctl)."""
import glob
import hashlib
import os
import shutil
import subprocess
import time

from . import have, run

DESKTOP_DIRS = ["/usr/share/applications", "/usr/local/share/applications", os.path.expanduser("~/.local/share/applications"),
                "/var/lib/snapd/desktop/applications", "/var/lib/flatpak/exports/share/applications",
                os.path.expanduser("~/.local/share/flatpak/exports/share/applications")]
_cache = {"at": 0, "apps": {}}


def _parse(path):
    """Name (Russian if there is one), Icon, NoDisplay of a .desktop file."""
    d = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            in_entry = False
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    in_entry = line == "[Desktop Entry]"
                    continue
                if in_entry and "=" in line:
                    k, v = line.split("=", 1)
                    d.setdefault(k, v)
    except OSError:
        return None
    if d.get("Type", "Application") != "Application" or d.get("NoDisplay") == "true" or d.get("Hidden") == "true":
        return None
    return {"name": d.get("Name[ru]") or d.get("Name") or "", "icon": d.get("Icon", ""), "path": path}


def _apps():
    if time.time() - _cache["at"] > 120:
        apps = {}
        for d in DESKTOP_DIRS:
            for f in glob.glob(os.path.join(d, "*.desktop")):
                a = _parse(f)
                if a and a["name"] and a["name"] not in apps:
                    apps[a["name"]] = a
        _cache.update(at=time.time(), apps=apps)
    return _cache["apps"]


def find_app(name):
    a = _apps().get(name)
    return a["path"] if a else None


def installed_apps():
    return sorted(_apps(), key=str.lower)


def _icon_file(icon):
    if not icon:
        return None
    if os.path.isabs(icon) and os.path.exists(icon):
        return icon
    for size in ("256x256", "128x128", "512x512", "96x96", "64x64", "48x48", "scalable"):
        for theme in ("hicolor", "Yaru", "Adwaita"):
            for ext in ("png", "svg"):
                p = "/usr/share/icons/%s/%s/apps/%s.%s" % (theme, size, icon, ext)
                if os.path.exists(p):
                    return p
    for p in glob.glob("/usr/share/pixmaps/%s.*" % icon) + glob.glob("/var/lib/snapd/desktop/icons/*%s*.png" % icon):
        return p
    return None


def app_icon(name, cache_dir):
    """PNG icon for an app, cached on disk (SVG icons are rendered with rsvg-convert if it is installed)."""
    a = _apps().get(name)
    src = _icon_file(a["icon"]) if a else None
    if not src:
        return None
    out = os.path.join(cache_dir, "icons", hashlib.md5(src.encode()).hexdigest() + ".png")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if src.endswith(".png"):
        shutil.copyfile(src, out)
    elif src.endswith(".svg") and have("rsvg-convert"):
        run(["rsvg-convert", "-w", "160", "-h", "160", "-o", out, src], timeout=10)
    return out if os.path.exists(out) else None


def _spawn(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


class Actions:
    def __init__(self):
        self._inhibit = None

    @property
    def awake(self):
        return self._inhibit is not None and self._inhibit.poll() is None

    def run(self, action, arg=None):
        if action == "open_app":
            path = find_app(arg or "")
            if not path:
                return False, "Приложение не найдено"
            if have("gio"):
                _spawn(["gio", "launch", path])
            else:
                _spawn(["gtk-launch", os.path.basename(path)[:-8]])
            return True, "Открываю %s" % arg
        if action == "open_path":
            _spawn(["xdg-open", os.path.expanduser(arg or "~")])
            return True, "Открыто"
        if action == "sleep":
            _spawn(["systemctl", "suspend"])
            return True, "Компьютер засыпает"
        if action == "display_sleep":
            # GNOME/KDE: activate the screensaver (blanks and locks); X11 fallback: DPMS off
            r = subprocess.run(["dbus-send", "--session", "--dest=org.freedesktop.ScreenSaver", "--type=method_call",
                                "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver.SetActive", "boolean:true"],
                               capture_output=True, timeout=5) if have("dbus-send") else None
            if (r is None or r.returncode != 0) and have("xset"):
                run(["xset", "dpms", "force", "off"])
            return True, "Экран выключен"
        if action == "screenshot":
            d = os.path.expanduser("~/Pictures/Screenshots")
            os.makedirs(d, exist_ok=True)
            fn = os.path.join(d, time.strftime("Снимок экрана %Y-%m-%d %H-%M-%S.png"))
            if os.environ.get("WAYLAND_DISPLAY") and os.path.exists("/usr/bin/python3"):
                # Wayland: only the desktop portal may grab the screen; the first time it asks «Allow?» on screen
                _spawn(["/usr/bin/python3", os.path.join(os.path.dirname(__file__), "shot.py"), fn])
                return True, "Делаю скриншот в «Изображения → Screenshots». В первый раз подтвердите на экране компьютера"
            for cmd in (["gnome-screenshot", "-f", fn], ["spectacle", "-b", "-n", "-o", fn], ["grim", fn], ["scrot", fn]):
                if have(cmd[0]):
                    try:
                        subprocess.run(cmd, capture_output=True, timeout=15)
                    except subprocess.TimeoutExpired:
                        continue
                    if os.path.exists(fn):
                        return True, "Скриншот в «Изображения → Screenshots»"
            return False, "Не получилось сделать скриншот (sudo apt install gnome-screenshot)"
        if action == "awake":
            if self.awake:
                self._inhibit.terminate()
                self._inhibit = None
                return True, "Компьютер снова может засыпать"
            self._inhibit = subprocess.Popen(["systemd-inhibit", "--what=idle:sleep", "--who=TabDock",
                                              "--why=Не спать (кнопка на планшете)", "sleep", "infinity"],
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, "Компьютер не будет засыпать"
        if action == "eject":
            dev = run(["findmnt", "-no", "SOURCE", arg or ""]).strip()
            if not dev:
                return False, "Диск не найден"
            r = subprocess.run(["udisksctl", "unmount", "-b", dev], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                parent = run(["lsblk", "-no", "PKNAME", dev]).strip()
                if parent:
                    run(["udisksctl", "power-off", "-b", "/dev/" + parent], timeout=15)
                return True, "Диск извлечён"
            return False, (r.stderr or r.stdout).strip()[:200]
        return False, "Неизвестное действие"
