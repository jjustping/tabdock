"""Answer devices on the home network directly, even when a VPN is on (macOS).

A VPN on the computer usually takes over the whole routing table, so the replies to the tablet
(192.168.x.x) go into the tunnel and never arrive. Fix: besides the normal listener on 0.0.0.0, open one
more listener on the LAN address of each real network interface (Wi-Fi / Ethernet) and pin it to that
interface with IP_BOUND_IF. The kernel delivers connections to the more specific address to that socket,
and everything it sends (including the SYN-ACK) leaves through the physical interface, not the tunnel.
"""
import ipaddress
import re
import socket
import subprocess
import sys
import threading
import time

IP_BOUND_IF = 25          # <netinet/in.h> on macOS
VPN = False               # a VPN holds the default route right now (shown to the client as a hint)
TUNNEL = re.compile(r"^(utun|ipsec|ppp|tun|tap|gif|stf|awdl|llw|bridge|anpi|ap)\d*")


def lan_interfaces():
    """[(iface, ip, network)] for physical interfaces with a private IPv4 address."""
    try:
        out = subprocess.run(["/sbin/ifconfig"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return []
    res, cur = [], None
    for line in out.splitlines():
        m = re.match(r"^(\S+?):\s", line)
        if m:
            cur = m.group(1)
            continue
        m = re.search(r"\binet (\d+\.\d+\.\d+\.\d+) netmask (0x[0-9a-f]+)", line)
        if m and cur and cur != "lo0" and not TUNNEL.match(cur):
            ip = m.group(1)
            if ipaddress.ip_address(ip).is_private and not ip.startswith("169.254."):
                bits = bin(int(m.group(2), 16)).count("1")
                res.append((cur, ip, ipaddress.ip_network("%s/%d" % (ip, bits), strict=False)))
    return res


def vpn_active():
    """True when internet traffic goes into a tunnel (a VPN is on). Many VPNs (WireGuard, OpenVPN and others) keep the
    default route and add 0/1 + 128/1 instead, so ask where a public address is actually routed."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["/sbin/route", "-n", "get", "1.1.1.1"], capture_output=True, text=True, timeout=3).stdout
            m = re.search(r"interface:\s*(\S+)", out)
        else:
            out = subprocess.run(["ip", "-4", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=3).stdout
            m = re.search(r"\bdev\s+(\S+)", out)
    except Exception:
        return False
    i = m.group(1) if m else ""
    return bool(i and re.match(r"(utun|ipsec|ppp|tun|tap|wg|tailscale|zt|nordlynx|proton)", i))


class LanBinder:
    """Keeps one interface-pinned listener per LAN address; re-checks every 30 s (Wi-Fi changes, DHCP)."""

    def __init__(self, make_server, port):
        self.make_server = make_server      # (host, port) -> server with a socket not yet bound
        self.port = port
        self.servers = {}                   # (iface, ip) -> server
        self.lock = threading.Lock()

    def start(self):
        if sys.platform != "darwin":
            # Linux: replies to the home network follow the more specific LAN route even with wg-quick/OpenVPN;
            # only keep the «VPN is on» flag current for the menu and the apps
            threading.Thread(target=self._vpn_loop, name="vpnflag", daemon=True).start()
            return
        threading.Thread(target=self._loop, name="lanbind", daemon=True).start()

    def _vpn_loop(self):
        global VPN
        while True:
            VPN = vpn_active()
            time.sleep(30)

    def _loop(self):
        while True:
            try:
                self.sync()
            except Exception as e:
                print("lanbind:", e, flush=True)
            time.sleep(30)

    def sync(self):
        global VPN
        VPN = vpn_active()
        want = {(i, ip) for i, ip, _ in lan_interfaces()}
        with self.lock:
            for key in list(self.servers):
                if key not in want:
                    srv = self.servers.pop(key)
                    threading.Thread(target=srv.shutdown, daemon=True).start()
                    srv.server_close()
            for iface, ip in want - set(self.servers):
                try:
                    srv = self.make_server(ip, self.port, socket.if_nametoindex(iface))
                except OSError as e:
                    print("lanbind: %s %s: %s" % (iface, ip, e), flush=True)
                    continue
                self.servers[(iface, ip)] = srv
                threading.Thread(target=srv.serve_forever, name="lan-" + iface, daemon=True).start()
