#!/usr/bin/env python3
"""TabDock icon in the Linux tray (AppIndicator: Ubuntu/GNOME, KDE, XFCE…).

Same menu as the macOS menu-bar icon: status, address, connected devices, autostart at login, QR code,
open, restart, log, stop. Runs with the *system* python3 (it needs PyGObject):
    sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1
Started by the user service tabdock-tray.service (see install-linux.sh).
"""
import json
import os
import subprocess
import sys
import urllib.request

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AI
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AI
from gi.repository import GLib, Gdk, Gtk  # noqa: E402

PORT = int(os.environ.get("DOCK_PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8787))
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_OK = os.path.join(HERE, "tray-ok.svg")
ICON_BAD = os.path.join(HERE, "tray-bad.svg")


def fetch():
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/tray" % PORT, timeout=1.5) as r:
            return json.loads(r.read())
    except Exception:
        return None


def sysd(*args):
    return subprocess.run(["systemctl", "--user"] + list(args), capture_output=True, text=True)


def autostart_on():
    return sysd("is-enabled", "tabdock.service").stdout.strip() == "enabled"


def ago(s):
    return "сейчас" if s < 10 else ("%d с назад" % s if s < 60 else "%d мин назад" % (s // 60))


class Tray:
    def __init__(self):
        self.ind = AI.Indicator.new("tabdock", ICON_OK, AI.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_status(AI.IndicatorStatus.ACTIVE)
        self.ind.set_title("TabDock")
        self.url = "http://localhost:%d" % PORT
        self._sig = None
        self.rebuild()
        GLib.timeout_add_seconds(5, self.rebuild)   # AppIndicator menus have no "about to open" signal

    def _item(self, menu, label, cb=None, sensitive=True):
        it = Gtk.MenuItem(label=label)
        it.set_sensitive(sensitive and cb is not None)
        if cb:
            it.connect("activate", lambda *_: cb())
        menu.append(it)
        return it

    def rebuild(self):
        t = fetch()
        sig = json.dumps(t and {k: t.get(k) for k in ("version", "url", "vpn", "update")}) + json.dumps(
            [(c["name"], c["ip"], c["ago"] // 30) for c in (t or {}).get("clients", [])]) + str(autostart_on())
        self.ind.set_icon_full(ICON_OK if t else ICON_BAD, "TabDock")
        if sig == self._sig:
            return True
        self._sig = sig
        m = Gtk.Menu()
        if t:
            self.url = (t.get("url") or self.url).split("/?")[0]
            self._item(m, "TabDock %s — работает" % t.get("version", ""))
            self._item(m, "Адрес: %s  (скопировать)" % self.url, self.copy)
            if t.get("update"):
                self._item(m, "Доступна версия %s — обновить…" % t["update"], lambda: self.open("/"))
            m.append(Gtk.SeparatorMenuItem())
            cl = t.get("clients", [])
            self._item(m, "Подключено устройств: %d" % len(cl) if cl else "Подключённых устройств нет")
            for c in cl:
                kind = "" if c.get("kind") == "app" else " (браузер)"
                self._item(m, "    %s%s · %s · %s" % (c["name"], kind, c["ip"], ago(c.get("ago", 0))))
        else:
            self._item(m, "TabDock не отвечает — перезапустите службу")
        m.append(Gtk.SeparatorMenuItem())
        self._item(m, "Показать QR-код для подключения…", lambda: self.open("/"))
        self._item(m, "Открыть панель TabDock", lambda: self.open("/"))
        m.append(Gtk.SeparatorMenuItem())
        auto = Gtk.CheckMenuItem(label="Запускать при входе")
        auto.set_active(autostart_on())
        auto.connect("toggled", lambda w: sysd("enable" if w.get_active() else "disable", "tabdock.service"))
        m.append(auto)
        self._item(m, "Перезапустить службу", lambda: sysd("restart", "tabdock.service"))
        self._item(m, "Открыть журнал", self.log)
        m.append(Gtk.SeparatorMenuItem())
        self._item(m, "Остановить TabDock", self.stop)
        m.show_all()
        self.ind.set_menu(m)
        return True

    def copy(self):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self.url, -1)

    def open(self, path):
        subprocess.Popen(["xdg-open", "http://localhost:%d%s" % (PORT, path)])

    def log(self):
        f = os.path.join(GLib.get_user_cache_dir(), "tabdock-journal.txt")
        with open(f, "w") as fh:
            subprocess.run(["journalctl", "--user", "-u", "tabdock", "-n", "300", "--no-pager"], stdout=fh)
        subprocess.Popen(["xdg-open", f])

    def stop(self):
        d = Gtk.MessageDialog(message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
                              text="Остановить TabDock?")
        d.format_secondary_text("Планшеты и телефоны перестанут получать данные. " +
                                ("TabDock снова запустится при следующем входе." if autostart_on() else "Автозапуск выключен."))
        ok = d.run() == Gtk.ResponseType.OK
        d.destroy()
        if ok:
            sysd("stop", "tabdock.service")
            self._sig = None
            self.rebuild()


if __name__ == "__main__":
    Tray()
    Gtk.main()
