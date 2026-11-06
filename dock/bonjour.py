"""Advertise the dock on the LAN as _tabdock._tcp (Bonjour) via the built-in dns-sd tool.

Browsers cannot browse Bonjour, so the tablet UI finds servers by probing /api/hello;
this announcement is for native clients and for `dns-sd -B _tabdock._tcp`.
"""
import atexit
import socket
import subprocess

_proc = None


def advertise(port, version):
    global _proc
    name = "TabDock (%s)" % socket.gethostname().replace(".local", "")
    try:
        _proc = subprocess.Popen(["/usr/bin/dns-sd", "-R", name, "_tabdock._tcp", "local", str(port),
                                  "path=/", "version=%s" % version],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atexit.register(stop)
    except OSError:
        _proc = None


def stop():
    if _proc and _proc.poll() is None:
        _proc.terminate()
