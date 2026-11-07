#!/usr/bin/env python3
"""Take a screenshot through the desktop portal (works on GNOME/KDE under Wayland, where screenshot tools
are not allowed to grab the screen directly). The first time the desktop asks «Allow?» — after that it is silent.

    /usr/bin/python3 shot.py <target.png>     (system python: needs PyGObject)
Exit code 0 and the file at <target.png> on success.
"""
import os
import shutil
import sys
import urllib.parse
import uuid

from gi.repository import Gio, GLib

target = sys.argv[1]
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
token = "tabdock" + uuid.uuid4().hex[:8]
sender = bus.get_unique_name()[1:].replace(".", "_")
path = "/org/freedesktop/portal/desktop/request/%s/%s" % (sender, token)
loop = GLib.MainLoop()
result = {"code": 2}


def on_response(_c, _s, _p, _i, _sig, params):
    code, res = params.unpack()
    uri = res.get("uri") if code == 0 else None
    if uri:
        src = urllib.parse.unquote(urllib.parse.urlparse(uri).path)
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(src, target)
            result["code"] = 0
        except OSError:
            result["code"] = 3
    else:
        result["code"] = 1          # refused / cancelled
    loop.quit()


bus.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request", "Response", path, None,
                     Gio.DBusSignalFlags.NO_MATCH_RULE, on_response)
bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Screenshot",
              "Screenshot", GLib.Variant("(sa{sv})", ("", {"handle_token": GLib.Variant("s", token),
                                                            "interactive": GLib.Variant("b", False)})),
              None, Gio.DBusCallFlags.NONE, -1, None)
GLib.timeout_add_seconds(90, loop.quit)   # time to answer the first «Allow?» dialog
loop.run()
sys.exit(result["code"])
