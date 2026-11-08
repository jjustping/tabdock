"""Update check: the server looks at the project's GitHub releases twice a day and tells the apps (and the menu-bar /
tray icon) when a newer version is out, with its list of changes. Only the computer needs internet for this.

A git checkout can update itself: `git pull --ff-only`, refresh the Python packages, then restart.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

REPO = "jjustping/tabdock"
API = "https://api.github.com/repos/%s/releases?per_page=10" % REPO
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(v):
    """'v0.10.0-beta' -> (0, 10, 0, 0); a release without a suffix sorts after its betas."""
    m = re.match(r"v?(\d+)\.(\d+)(?:\.(\d+))?(-[\w.]+)?", (v or "").strip())
    if not m:
        return (0, 0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), 0 if m.group(4) else 1)


def newer(a, b):
    """True if version a is newer than b."""
    return parse(a) > parse(b)


class Updates:
    def __init__(self, current, interval=12 * 3600):
        self.current = current
        self.interval = interval
        self.latest = None          # {"version", "name", "notes", "url", "apk", "published"}
        self.checked = 0
        self.error = None
        self._kick = threading.Event()
        threading.Thread(target=self._loop, name="updates", daemon=True).start()

    def _loop(self):
        time.sleep(20)              # let the server start first
        while True:
            self.check()
            self._kick.wait(self.interval)
            self._kick.clear()

    def check_soon(self):
        self._kick.set()

    def check(self):
        try:
            req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "TabDock/%s" % self.current})
            with urllib.request.urlopen(req, timeout=15) as r:
                rels = json.loads(r.read())
            rels = [x for x in rels if not x.get("draft")]
            rels.sort(key=lambda x: parse(x.get("tag_name")), reverse=True)
            if rels:
                x = rels[0]
                apk = next((a["browser_download_url"] for a in x.get("assets", []) if a.get("name", "").endswith(".apk")), None)
                self.latest = {"version": x.get("tag_name", "").lstrip("v"), "name": x.get("name") or x.get("tag_name"),
                               "notes": _short_notes(x.get("body") or ""), "url": x.get("html_url"), "apk": apk,
                               "published": x.get("published_at")}
            self.error = None
        except Exception as e:
            self.error = str(e)[:160]
        self.checked = time.time()

    def info(self):
        lv = (self.latest or {}).get("version")
        return {"current": self.current, "latest": self.latest, "newer": bool(lv and newer(lv, self.current)),
                "checked": self.checked, "error": self.error, "can_self_update": can_self_update()}


def _short_notes(body):
    """The Russian part of the release notes (before the '---' line), without the images; at most ~3000 chars."""
    text = body.split("\n---", 1)[0]
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)\s*", "", text)
    return text.strip()[:3000]


def can_self_update():
    return os.path.isdir(os.path.join(HERE, ".git")) and subprocess.run(
        ["git", "--version"], capture_output=True).returncode == 0


def apply():
    """git pull + pip install. Returns (ok, message). The caller restarts the server afterwards."""
    if not can_self_update():
        return False, "Сервер установлен не через git — скачайте новую версию со страницы релизов"
    r = subprocess.run(["git", "-C", HERE, "pull", "--ff-only"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return False, "git pull не прошёл: " + (r.stderr or r.stdout).strip()[:200]
    pip = os.path.join(HERE, ".venv", "bin", "pip")
    if os.path.exists(pip):
        subprocess.run([pip, "install", "-q", "--disable-pip-version-check", "-r", os.path.join(HERE, "requirements.txt")],
                       capture_output=True, timeout=300)
    if "Already up to date" in r.stdout or "Уже актуально" in r.stdout:
        return True, "Уже последняя версия"
    changed = subprocess.run(["git", "-C", HERE, "diff", "--name-only", "HEAD@{1}", "HEAD"], capture_output=True, text=True).stdout
    if sys.platform == "darwin" and "helper/" in changed and os.path.exists(os.path.join(HERE, "helper", "build.sh")):
        # the menu-bar app changed: rebuild it (macOS may ask for its permissions again once)
        subprocess.run([os.path.join(HERE, "helper", "build.sh")], capture_output=True, timeout=600)
    if sys.platform != "darwin":
        subprocess.run(["systemctl", "--user", "restart", "tabdock-tray.service"], capture_output=True, timeout=30)
    return True, "Обновлено — сервер перезапускается"


def restart_later(delay=1.5):
    """Exit with a non-zero code: launchd (KeepAlive) / systemd (Restart=on-failure) start the new version."""
    def go():
        time.sleep(delay)
        os._exit(3)
    threading.Thread(target=go, daemon=True).start()
