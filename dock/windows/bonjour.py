"""Announce the dock on the LAN as _tabdock._tcp with the zeroconf package (Windows has no dns-sd / avahi)."""
import socket

_zc = None


def advertise(port, version):
    global _zc
    try:
        from zeroconf import ServiceInfo, Zeroconf
        from . import sysinfo
        ip = sysinfo.lan_ip()
        host = socket.gethostname().split(".")[0]
        info = ServiceInfo("_tabdock._tcp.local.", "TabDock (%s)._tabdock._tcp.local." % host, port=port,
                           addresses=[socket.inet_aton(ip)], properties={"path": "/", "version": version},
                           server="%s.local." % host)
        _zc = Zeroconf()
        _zc.register_service(info)
    except Exception as e:          # the app also finds the computer by scanning the network
        print("bonjour:", e, flush=True)
