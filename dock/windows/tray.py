"""TabDock icon in the Windows notification area (pystray): the same menu as the macOS menu-bar icon and the Linux tray.
Started by dock/windows/run.py."""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# run as a script, Python puts this folder first on the path; its module names must not hide the standard library's
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(os.path.abspath(__file__))]
sys.path.insert(0, HERE)
import pystray                                      # noqa: E402
from PIL import Image, ImageDraw                    # noqa: E402

from dock.windows import NO_WINDOW, appdata, follow_runner, kill_tree  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
LOCAL = "http://localhost:%d" % PORT


def fetch():
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/tray" % PORT, timeout=1.5) as r:
            return json.loads(r.read())
    except Exception:
        return None


def image(ok):
    """A tablet in landscape, white on transparent; a red dot when the server does not answer."""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 14, 58, 50), radius=7, outline=(255, 255, 255, 255), width=5)
    d.ellipse((49, 29, 53, 35), fill=(255, 255, 255, 255))
    if not ok:
        d.ellipse((40, 2, 62, 24), fill=(232, 72, 72, 255))
    return im


def schtasks(*args):
    return subprocess.run(["schtasks.exe"] + list(args), capture_output=True, text=True, creationflags=NO_WINDOW)


def autostart_on():
    r = schtasks("/Query", "/TN", "TabDock", "/XML")
    return r.returncode == 0 and "<Enabled>false</Enabled>" not in r.stdout.split("<Triggers>")[0]


def pids():
    try:
        with open(appdata("run.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ago(s):
    return "сейчас" if s < 10 else ("%d с назад" % s if s < 60 else "%d мин назад" % (s // 60))


class Tray:
    def __init__(self):
        self.t = None
        self.icon = pystray.Icon("TabDock", image(True), "TabDock", menu=pystray.Menu(lambda: self.items()))

    def items(self):
        t, I, S = self.t, pystray.MenuItem, pystray.Menu.SEPARATOR
        out = []
        if t:
            url = (t.get("url") or LOCAL).split("/?")[0]
            out += [I("TabDock %s — работает" % t.get("version", ""), None, enabled=False),
                    I("Адрес: %s  (скопировать)" % url, lambda: self.copy(url))]
            if t.get("update"):
                out.append(I("Доступна версия %s — обновить…" % t["update"], lambda: webbrowser.open(LOCAL + "/")))
            for p in t.get("pending", []):
                out.append(I("Новое устройство: %s — разрешить…" % p.get("name", ""), lambda: webbrowser.open(LOCAL + "/")))
            out.append(S)
            cl = t.get("clients", [])
            out.append(I("Подключено устройств: %d" % len(cl) if cl else "Подключённых устройств нет", None, enabled=False))
            for c in cl:
                kind = "" if c.get("kind") == "app" else " (браузер)"
                out.append(I("    %s%s · %s · %s" % (c["name"], kind, c["ip"], ago(c.get("ago", 0))), None, enabled=False))
        else:
            out.append(I("TabDock не отвечает — перезапустите", None, enabled=False))
        out += [S,
                I("Передача файлов…", lambda: webbrowser.open(LOCAL + "/transfer")),
                I("Показать QR-код для подключения…", lambda: webbrowser.open(LOCAL + "/"), default=True),
                I("Открыть панель TabDock", lambda: webbrowser.open(LOCAL + "/")),
                S,
                I("Запускать при входе", self.toggle_autostart, checked=lambda _: autostart_on()),
                I("Перезапустить", self.restart),
                I("Открыть журнал", lambda: os.startfile(appdata("logs", "tabdock.log"))),
                S,
                I("Остановить TabDock", self.stop)]
        return out

    def copy(self, text):
        from dock.buttons import set_clipboard
        set_clipboard(text)

    def toggle_autostart(self):
        schtasks("/Change", "/TN", "TabDock", "/DISABLE" if autostart_on() else "/ENABLE")

    def restart(self):
        p = pids().get("server")
        if p:      # run.py starts it again
            kill_tree(p)

    def stop(self):
        p = pids()
        for k in ("runner", "server"):
            if p.get(k):
                kill_tree(p[k])
        self.icon.stop()

    def poll(self):
        while True:
            self.t = fetch()
            self.icon.icon = image(self.t is not None)
            self.icon.title = "TabDock работает" if self.t else "TabDock не отвечает"
            self.icon.update_menu()
            time.sleep(5)

    def run(self):
        threading.Thread(target=self.poll, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    follow_runner()
    Tray().run()
