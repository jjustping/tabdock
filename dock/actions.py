"""Quick actions: launch apps, sleep, screenshot, keep-awake, eject disks."""
import hashlib
import os
import plistlib
import subprocess
import time

APP_DIRS = ["/Applications", "/System/Applications", "/System/Applications/Utilities",
            "/Applications/Utilities", "/System/Library/CoreServices", os.path.expanduser("~/Applications")]


def find_app(name):
    for d in APP_DIRS:
        p = os.path.join(d, name + ".app")
        if os.path.isdir(p):
            return p
    return None


def installed_apps():
    names = {"Finder"}
    for d in APP_DIRS[:-2] + APP_DIRS[-1:]:
        try:
            for n in os.listdir(d):
                if n.endswith(".app") and not n.startswith("."):
                    names.add(n[:-4])
        except OSError:
            pass
    return sorted(names, key=str.lower)


def app_icon(name, cache_dir):
    """PNG icon for an app (from its .icns) cached on disk; None if unavailable."""
    path = find_app(name)
    if not path:
        return None
    out = os.path.join(cache_dir, "icons", hashlib.md5(path.encode()).hexdigest() + ".png")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        with open(os.path.join(path, "Contents", "Info.plist"), "rb") as f:
            info = plistlib.load(f)
        icon = info.get("CFBundleIconFile") or info.get("CFBundleIconName") or ""
        if icon and not icon.endswith(".icns"):
            icon += ".icns"
        src = os.path.join(path, "Contents", "Resources", icon)
        if not os.path.exists(src):
            return None
        subprocess.run(["/usr/bin/sips", "-s", "format", "png", "-Z", "160", src, "--out", out],
                       capture_output=True, timeout=10)
        return out if os.path.exists(out) else None
    except Exception:
        return None


class Actions:
    def __init__(self):
        self._caff = None

    @property
    def awake(self):
        return self._caff is not None and self._caff.poll() is None

    def run(self, action, arg=None):
        if action == "open_app":
            if not arg or not find_app(arg):
                return False, "Приложение не найдено"
            subprocess.Popen(["/usr/bin/open", "-a", arg])
            return True, "Открываю %s" % arg
        if action == "open_path":
            subprocess.Popen(["/usr/bin/open", os.path.expanduser(arg or "~")])
            return True, "Открыто"
        if action == "sleep":
            subprocess.Popen(["/usr/bin/pmset", "sleepnow"])
            return True, "Mac засыпает"
        if action == "display_sleep":
            subprocess.Popen(["/usr/bin/pmset", "displaysleepnow"])
            return True, "Экран выключен"
        if action == "screenshot":
            d = os.path.expanduser("~/Desktop")
            fn = os.path.join(d, time.strftime("Снимок экрана %Y-%m-%d в %H.%M.%S.png"))
            r = subprocess.run(["/usr/sbin/screencapture", "-x", fn], capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.exists(fn):
                return True, "Скриншот на Рабочем столе"
            return False, "Нет доступа к записи экрана (см. README)"
        if action == "awake":
            if self.awake:
                self._caff.terminate()
                self._caff = None
                return True, "Mac снова может засыпать"
            self._caff = subprocess.Popen(["/usr/bin/caffeinate", "-dims"])
            return True, "Mac не будет засыпать"
        if action == "eject":
            r = subprocess.run(["/usr/sbin/diskutil", "eject", arg], capture_output=True, text=True, timeout=30)
            ok = r.returncode == 0
            return ok, ("Диск извлечён" if ok else (r.stderr or r.stdout).strip()[:200])
        return False, "Неизвестное действие"
