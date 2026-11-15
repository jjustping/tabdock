"""Windows computer status: CPU, memory, disks, uptime, LAN address (ctypes + one PowerShell call for the names).
Temperatures: Windows has no standard way for ordinary programs to read them, so they are shown as «—»."""
import ctypes
import ipaddress
import json
import os
import re
import socket
import threading
import time
from ctypes import wintypes

from . import ps

k32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None
TUNNEL = re.compile(r"(vpn|wireguard|wintun|tap|tun|tailscale|zerotier|hyper-v|vethernet|wsl|loopback|bluetooth|virtual)", re.I)


class FILETIME(ctypes.Structure):
    _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]


def _ft(f):
    return (f.hi << 32) | f.lo


def _cpu_times():
    idle, kern, user = FILETIME(), FILETIME(), FILETIME()
    k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    total = _ft(kern) + _ft(user)          # kernel time includes idle time
    return total - _ft(idle), total


class MEMSTAT(ctypes.Structure):
    _fields_ = [("len", wintypes.DWORD), ("load", wintypes.DWORD), ("total", ctypes.c_uint64), ("avail", ctypes.c_uint64),
                ("ptotal", ctypes.c_uint64), ("pavail", ctypes.c_uint64), ("vtotal", ctypes.c_uint64),
                ("vavail", ctypes.c_uint64), ("evavail", ctypes.c_uint64)]


def memory():
    m = MEMSTAT()
    m.len = ctypes.sizeof(MEMSTAT)
    k32.GlobalMemoryStatusEx(ctypes.byref(m))
    used = m.total - m.avail
    swap = max(0, (m.ptotal - m.pavail) - used)
    return {"total": m.total, "used": used, "pct": round(100.0 * used / m.total, 1) if m.total else 0,
            "swap_mb": round(swap / 1048576, 1)}


def temps():
    return {"cpu": None, "cpu_avg": None, "ssd": None, "sensors": 0}


def uptime():
    k32.GetTickCount64.restype = ctypes.c_uint64
    return int(k32.GetTickCount64() // 1000)


DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3


def disks():
    res = []
    mask = k32.GetLogicalDrives()
    for i in range(26):
        if not mask & (1 << i):
            continue
        root = "%s:\\" % chr(65 + i)
        kind = k32.GetDriveTypeW(root)
        if kind not in (DRIVE_REMOVABLE, DRIVE_FIXED):
            continue
        free, total, tfree = ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_uint64()
        if not k32.GetDiskFreeSpaceExW(root, ctypes.byref(free), ctypes.byref(total), ctypes.byref(tfree)) or not total.value:
            continue
        label, fs = ctypes.create_unicode_buffer(261), ctypes.create_unicode_buffer(261)
        flags = wintypes.DWORD()
        k32.GetVolumeInformationW(root, label, 261, None, None, ctypes.byref(flags), fs, 261)
        system = os.environ.get("SystemDrive", "C:").upper() == root[:2]
        ext = kind == DRIVE_REMOVABLE
        name = label.value or ("Системный диск" if system else "Диск %s" % root[:2])
        used = total.value - free.value
        res.append({"name": "%s (%s)" % (name, root[:2]), "mount": root, "total": total.value, "used": used,
                    "free": free.value, "pct": round(100.0 * used / total.value, 1), "external": ext, "fs": fs.value,
                    "readonly": bool(flags.value & 0x80000), "ejectable": ext, "bus": "USB" if ext else "", "model": ""})
    res.sort(key=lambda d: (d["external"], not d["mount"].upper().startswith(os.environ.get("SystemDrive", "C:").upper()), d["mount"]))
    return res


def _statics():
    out = ps("$c=Get-CimInstance Win32_ComputerSystem;$p=Get-CimInstance Win32_Processor|Select -First 1;"
             "$o=Get-CimInstance Win32_OperatingSystem;"
             "@{model=$c.Model;maker=$c.Manufacturer;chip=$p.Name;cores=$p.NumberOfLogicalProcessors;os=$o.Caption}|ConvertTo-Json")
    try:
        j = json.loads(out)
    except ValueError:
        j = {}
    model = (j.get("model") or "").strip()
    if model.lower() in ("", "system product name", "to be filled by o.e.m."):
        model = "Windows PC"
    return {"model": model, "chip": (j.get("chip") or "").strip() or os.environ.get("PROCESSOR_IDENTIFIER", ""),
            "cores": j.get("cores") or os.cpu_count() or 0, "os": (j.get("os") or "Windows").replace("Microsoft ", "")}


def lan_interfaces():
    """[(iface, ip, network)]: real adapters with a private IPv4 address (no VPN / virtual switches)."""
    out = ps("Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred|"
             "Select InterfaceAlias,IPAddress,PrefixLength|ConvertTo-Json -Compress")
    try:
        rows = json.loads(out or "[]")
    except ValueError:
        return []
    rows = rows if isinstance(rows, list) else [rows]
    res = []
    for r in rows:
        ip, name = r.get("IPAddress", ""), r.get("InterfaceAlias", "")
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_private and not addr.is_loopback and not ip.startswith("169.254.") and not TUNNEL.search(name):
            res.append((name, ip, ipaddress.ip_network("%s/%s" % (ip, r.get("PrefixLength", 24)), strict=False)))
    return res


def lan_ip():
    lan = lan_interfaces()
    # prefer the adapter that has the default route
    out = ps("(Get-NetRoute -DestinationPrefix 0.0.0.0/0 -ErrorAction SilentlyContinue|Sort RouteMetric|Select -First 1).InterfaceAlias")
    for name, ip, _ in lan:
        if name == out.strip():
            return ip
    if lan:
        return lan[0][1]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.0.1", 9))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def thermal_pressure():
    return "nominal"


class Sampler:
    """Background sampler so HTTP requests never block on slow calls."""

    def __init__(self):
        self.data = {}
        self.history = []
        self._prev = _cpu_times()
        self._slow_at = 0
        self._static = {"hostname": socket.gethostname().split(".")[0], "mem_total": memory()["total"],
                        "model": "Windows PC", "chip": "", "cores": os.cpu_count() or 0, "os": "Windows"}
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        try:
            self._sample()                       # numbers first; the slow names (PowerShell) right after
            self._static.update(_statics())
        except Exception:
            pass
        while True:
            try:
                self._sample()
            except Exception as e:
                self.data["error"] = str(e)
            time.sleep(2)

    def _sample(self):
        busy, total = _cpu_times()
        pb, pt = self._prev
        self._prev = (busy, total)
        cpu = round(100.0 * (busy - pb) / (total - pt), 1) if total > pt else 0.0
        cpu = max(0.0, min(100.0, cpu))
        self.history = (self.history + [cpu])[-60:]
        d = dict(self.data)
        d.update(self._static)
        d.update(cpu=cpu, cpu_history=self.history, load=[], mem=memory(), temp=temps())
        now = time.time()
        if now - self._slow_at > 15:
            self._slow_at = now
            d.update(disks=disks(), uptime=uptime(), ip=lan_ip(), thermal="nominal")
        self.data = d
