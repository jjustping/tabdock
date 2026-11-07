"""Home-network health for the "Сеть" widget: gateway, DNS, internet. Refreshed in the background."""
import re
import socket
import subprocess
import threading
import time


def _run(cmd, timeout=6):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def _gateway():
    out = _run(["/sbin/route", "-n", "get", "default"])
    gw = re.search(r"gateway:\s*(\S+)", out)
    iface = re.search(r"interface:\s*(\S+)", out)
    return (gw.group(1) if gw else None), (iface.group(1) if iface else None)


def _ping(host):
    out = _run(["/sbin/ping", "-c", "2", "-t", "3", host], timeout=6)
    m = re.search(r"= [\d.]+/([\d.]+)/", out)
    loss = re.search(r"([\d.]+)% packet loss", out)
    return (float(m.group(1)) if m else None), (float(loss.group(1)) if loss else 100.0)


def _timed(fn, timeout):
    res = {}

    def run():
        t = time.time()
        try:
            fn()
            res["ms"] = round((time.time() - t) * 1000)
        except Exception as e:
            res["err"] = str(e)[:80]
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        res["err"] = "нет ответа за %d с" % timeout
    return res


class NetCheck:
    def __init__(self, interval=30):
        self.data = {"at": 0}
        self.interval = interval
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                self.data = self.check()
            except Exception as e:
                self.data = {"at": time.time(), "error": str(e)}
            time.sleep(self.interval)

    def check(self):
        gw, iface = _gateway()
        gw_ms, gw_loss = _ping(gw) if gw else (None, 100.0)
        dns = _timed(lambda: socket.getaddrinfo("apple.com", 443), 4)
        net = _timed(lambda: socket.create_connection(("1.1.1.1", 443), 3).close(), 4)
        return {
            "at": time.time(), "iface": iface, "gateway": gw, "gw_ms": gw_ms, "gw_loss": gw_loss,
            "dns_ok": "ms" in dns, "dns_ms": dns.get("ms"), "dns_err": dns.get("err"),
            "inet_ok": "ms" in net, "inet_ms": net.get("ms"), "inet_err": net.get("err"),
        }


_sc_cache = {"at": 0, "list": []}


def shortcuts_list():
    """Apple Shortcuts available on this Mac (cached for 5 minutes)."""
    if time.time() - _sc_cache["at"] > 300:
        out = _run(["/usr/bin/shortcuts", "list"], timeout=10)
        _sc_cache.update(at=time.time(), list=[l.strip() for l in out.splitlines() if l.strip()][:200])
    return _sc_cache["list"]


def run_shortcut(name):
    if name not in shortcuts_list():
        return False, "Такой команды нет в «Командах» на Mac"
    subprocess.Popen(["/usr/bin/shortcuts", "run", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True, "Запускаю «%s»" % name
