"""Announce the dock on the LAN as _tabdock._tcp through Avahi (avahi-publish), so the Android app finds it."""
import atexit
import socket
import subprocess

from . import have

_proc = None


def advertise(port, version):
    global _proc
    if not have("avahi-publish"):
        return
    name = "TabDock (%s)" % socket.gethostname().split(".")[0]
    try:
        _proc = subprocess.Popen(["avahi-publish", "-s", name, "_tabdock._tcp", str(port), "path=/", "version=%s" % version],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atexit.register(stop)
    except OSError:
        _proc = None


def stop():
    if _proc and _proc.poll() is None:
        _proc.terminate()
