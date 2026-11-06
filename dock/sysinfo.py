"""Mac status: CPU load, memory, disks, temperature, uptime, network."""
import ctypes
import os
import re
import socket
import subprocess
import threading
import time

from . import temps

_libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
_libc.mach_host_self.restype = ctypes.c_uint32
_libc.host_statistics.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]

HOST_CPU_LOAD_INFO = 3


def _cpu_ticks():
    buf = (ctypes.c_uint32 * 4)()
    cnt = ctypes.c_uint32(4)
    _libc.host_statistics(_libc.mach_host_self(), HOST_CPU_LOAD_INFO, buf, ctypes.byref(cnt))
    user, system, idle, nice = buf
    return user + system + nice, user + system + idle + nice


def run(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def sysctl(name):
    return run(["/usr/sbin/sysctl", "-n", name]).strip()


class Sampler:
    """Background sampler so HTTP requests never block on slow calls."""

    def __init__(self):
        self.data = {}
        self.history = []  # last 60 CPU samples for the sparkline
        self._prev = _cpu_ticks()
        self._slow_at = 0
        self._static = {
            "model": sysctl("hw.model"),
            "chip": sysctl("machdep.cpu.brand_string"),
            "cores": int(sysctl("hw.ncpu") or 0),
            "mem_total": int(sysctl("hw.memsize") or 0),
            "hostname": socket.gethostname().replace(".local", ""),
        }
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                self._sample()
            except Exception as e:  # never die
                self.data["error"] = str(e)
            time.sleep(2)

    def _sample(self):
        busy, total = _cpu_ticks()
        pb, pt = self._prev
        self._prev = (busy, total)
        cpu = round(100.0 * (busy - pb) / (total - pt), 1) if total > pt else 0.0
        self.history = (self.history + [cpu])[-60:]
        d = dict(self.data)
        d.update(self._static)
        d["cpu"] = cpu
        d["cpu_history"] = self.history
        d["load"] = [round(x, 2) for x in os.getloadavg()]
        d["mem"] = memory()
        d["temp"] = temps.summary()
        now = time.time()
        if now - self._slow_at > 15:
            self._slow_at = now
            d["disks"] = disks()
            d["uptime"] = uptime()
            d["ip"] = lan_ip()
            d["thermal"] = thermal_pressure()
        self.data = d


def memory():
    out = run(["/usr/bin/vm_stat"])
    page = 16384
    m = re.search(r"page size of (\d+)", out)
    if m:
        page = int(m.group(1))
    vals = {}
    for line in out.splitlines()[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            try:
                vals[k.strip().strip('"')] = int(v.strip().rstrip("."))
            except ValueError:
                pass
    total = int(sysctl("hw.memsize") or 1)
    anon = vals.get("Anonymous pages", 0)
    purg = vals.get("Pages purgeable", 0)
    wired = vals.get("Pages wired down", 0)
    comp = vals.get("Pages occupied by compressor", 0)
    used = (max(anon - purg, 0) + wired + comp) * page
    swap = run(["/usr/sbin/sysctl", "-n", "vm.swapusage"])
    sm = re.search(r"used = ([\d.]+)M", swap)
    return {
        "total": total,
        "used": min(used, total),
        "pct": round(100.0 * min(used, total) / total, 1),
        "swap_mb": float(sm.group(1)) if sm else 0.0,
    }


_dinfo = {}  # mount -> (time, info)
SKIP_VOLUMES = {"Recovery", "Preboot", "VM", "Update", "xarts", "iSCPreboot", "Hardware"}


def disk_info(mount):
    """Model, bus (USB/Thunderbolt), file system, SMART for a volume; cached for 10 minutes."""
    import plistlib
    now = time.time()
    c = _dinfo.get(mount)
    if c and now - c[0] < 600:
        return c[1]
    info = {}
    try:
        out = subprocess.run(["/usr/sbin/diskutil", "info", "-plist", mount], capture_output=True, timeout=8).stdout
        d = plistlib.loads(out) if out else {}
        info = {
            "model": (d.get("MediaName") or d.get("IORegistryEntryName") or "").strip(),
            "bus": d.get("BusProtocol") or "",
            "fs": d.get("FilesystemUserVisibleName") or d.get("FilesystemName") or "",
            "smart": d.get("SMARTStatus") or "",
            "ssd": d.get("SolidState"),
            "ejectable": bool(d.get("Ejectable")),
            "device": d.get("DeviceIdentifier") or "",
        }
    except Exception:
        pass
    _dinfo[mount] = (now, info)
    return info


def disks():
    res = []
    out = run(["/bin/df", "-k"])
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9 or not parts[0].startswith("/dev/disk"):
            continue
        mount = " ".join(parts[8:])
        if mount == "/System/Volumes/Data":
            name, ext = "Macintosh HD", False
        elif mount.startswith("/Volumes/"):
            name, ext = mount[len("/Volumes/"):], True
            if name in SKIP_VOLUMES:
                continue
        else:
            continue
        total, used, avail = int(parts[1]) * 1024, int(parts[2]) * 1024, int(parts[3]) * 1024
        # APFS: "used" excludes other volumes in the container -> use total-avail
        used = total - avail
        item = {"name": name, "mount": mount, "total": total, "used": used,
                "free": avail, "pct": round(100.0 * used / total, 1) if total else 0,
                "external": ext}
        if ext:
            item.update(disk_info(mount))
        res.append(item)
    res.sort(key=lambda d: (d["external"], d["name"]))
    return res


def uptime():
    m = re.search(r"sec = (\d+)", sysctl("kern.boottime"))
    return int(time.time() - int(m.group(1))) if m else 0


def thermal_pressure():
    # "pmset -g therm" prints warning levels; nominal on a healthy Mac
    out = run(["/usr/bin/pmset", "-g", "therm"])
    if "CPU_Speed_Limit" in out:
        m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", out)
        if m and int(m.group(1)) < 100:
            return "throttled"
    return "nominal"


def lan_ip():
    """Primary LAN IPv4 (interface of the default route)."""
    out = run(["/sbin/route", "-n", "get", "default"])
    m = re.search(r"interface:\s*(\S+)", out)
    ifaces = [m.group(1)] if m else []
    ifaces += ["en0", "en1"]
    for i in ifaces:
        ip = run(["/usr/sbin/ipconfig", "getifaddr", i]).strip()
        if ip:
            return ip
    return "127.0.0.1"
