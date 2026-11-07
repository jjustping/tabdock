"""Linux computer status: CPU, memory, disks, temperatures, uptime, LAN address (from /proc and /sys)."""
import glob
import ipaddress
import os
import re
import socket
import threading
import time

from . import run

TUNNEL = re.compile(r"^(tun|tap|wg|tailscale|zt|docker|br-|veth|virbr|lxc|lo|ppp|vmnet|cni|flannel)")


def _cpu_ticks():
    with open("/proc/stat") as f:
        p = [int(x) for x in f.readline().split()[1:]]
    idle = p[3] + (p[4] if len(p) > 4 else 0)
    total = sum(p[:8])
    return total - idle, total


def _read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _cpu_name():
    m = re.search(r"^model name\s*:\s*(.+)$", _read("/proc/cpuinfo"), re.M)
    if m and m.group(1).strip() not in ("", "-"):
        return m.group(1).strip()
    out = run(["lscpu"])
    model = re.search(r"Model name:\s*(.+)", out)
    vendor = re.search(r"Vendor ID:\s*(.+)", out)
    model = model.group(1).strip() if model else ""
    if model and model != "-":
        return model
    # ARM (Raspberry Pi, Apple silicon VMs…): lscpu often has no model name
    import platform
    return ((vendor.group(1).strip() + " ") if vendor else "") + platform.machine()


def _model():
    for p in ("/sys/devices/virtual/dmi/id/product_name", "/proc/device-tree/model"):
        v = _read(p).replace("\x00", "")
        if v and v.lower() not in ("to be filled by o.e.m.", "system product name", "default string"):
            return v
    return "Linux"


class Sampler:
    """Background sampler so HTTP requests never block on slow calls."""

    def __init__(self):
        self.data = {}
        self.history = []
        self._prev = _cpu_ticks()
        self._slow_at = 0
        self._static = {
            "model": _model(),
            "chip": _cpu_name(),
            "cores": os.cpu_count() or 0,
            "mem_total": memory()["total"],
            "hostname": socket.gethostname().split(".")[0],
            "os": _os_name(),
        }
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                self._sample()
            except Exception as e:
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
        d["temp"] = temps()
        now = time.time()
        if now - self._slow_at > 15:
            self._slow_at = now
            d["disks"] = disks()
            d["uptime"] = uptime()
            d["ip"] = lan_ip()
            d["thermal"] = "nominal"
        self.data = d


def _os_name():
    m = re.search(r'^PRETTY_NAME="?([^"\n]+)', _read("/etc/os-release"), re.M)
    return m.group(1) if m else "Linux"


def memory():
    vals = {}
    for line in _read("/proc/meminfo").splitlines():
        k, _, v = line.partition(":")
        try:
            vals[k] = int(v.split()[0]) * 1024
        except (ValueError, IndexError):
            pass
    total = vals.get("MemTotal", 1)
    used = total - vals.get("MemAvailable", vals.get("MemFree", 0))
    swap = vals.get("SwapTotal", 0) - vals.get("SwapFree", 0)
    return {"total": total, "used": max(0, used), "pct": round(100.0 * used / total, 1), "swap_mb": round(swap / 1048576, 1)}


def temps():
    """CPU and SSD temperatures from hwmon (coretemp / k10temp / cpu_thermal / nvme…)."""
    cpu, ssd, n = [], [], 0
    for hw in glob.glob("/sys/class/hwmon/hwmon*"):
        name = _read(os.path.join(hw, "name")).lower()
        for t in glob.glob(os.path.join(hw, "temp*_input")):
            try:
                v = int(_read(t, "0")) / 1000.0
            except ValueError:
                continue
            if not 0 < v < 130:
                continue
            n += 1
            if name in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "soc_thermal", "acpitz", "cpu-thermal") or "cpu" in name:
                cpu.append(v)
            elif name in ("nvme", "drivetemp"):
                ssd.append(v)
    if not cpu:   # fall back to thermal zones (ARM boards, some laptops)
        for z in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            try:
                v = int(_read(z, "0")) / 1000.0
            except ValueError:
                continue
            if 0 < v < 130:
                cpu.append(v); n += 1
    return {"cpu": round(max(cpu), 1) if cpu else None, "cpu_avg": round(sum(cpu) / len(cpu), 1) if cpu else None,
            "ssd": round(max(ssd), 1) if ssd else None, "sensors": n}


FS_OK = {"ext4", "ext3", "ext2", "xfs", "btrfs", "vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "f2fs", "zfs", "apfs", "hfsplus"}
_dinfo = {}


def disk_info(dev):
    """Model and bus of the physical disk behind a partition (lsblk), cached for 10 minutes."""
    now = time.time()
    c = _dinfo.get(dev)
    if c and now - c[0] < 600:
        return c[1]
    info = {"model": "", "bus": "", "ssd": None}
    parent = run(["lsblk", "-no", "PKNAME", dev]).strip().splitlines()
    whole = "/dev/" + parent[0] if parent and parent[0] else dev
    out = run(["lsblk", "-dno", "MODEL,TRAN,ROTA", whole]).strip()
    if out:
        parts = out.rsplit(None, 2)
        if len(parts) == 3:
            info = {"model": parts[0].strip(), "bus": parts[1].upper(), "ssd": parts[2] == "0"}
        elif len(parts) == 2 and parts[1] in ("0", "1"):
            info = {"model": parts[0].strip(), "bus": "", "ssd": parts[1] == "0"}
    _dinfo[dev] = (now, info)
    return info


def disks():
    res = []
    ro = {}
    for line in _read("/proc/mounts").splitlines():
        p = line.split()
        if len(p) >= 4:
            ro[p[1].replace("\\040", " ")] = "ro" in p[3].split(",")
    out = run(["df", "-kPT"])
    seen = set()
    for line in out.splitlines()[1:]:
        p = line.split()
        if len(p) < 7 or p[1] not in FS_OK or not p[0].startswith("/dev/"):
            continue
        mount = " ".join(p[6:])
        if mount.startswith(("/boot", "/snap", "/var/snap", "/run/snapd")) or p[0] in seen:
            continue
        seen.add(p[0])
        ext = mount.startswith(("/media/", "/run/media/", "/mnt/"))
        name = "Системный диск" if mount == "/" else ("Домашняя папка" if mount == "/home" else os.path.basename(mount))
        total, used, avail = int(p[2]) * 1024, int(p[3]) * 1024, int(p[4]) * 1024
        item = {"name": name, "mount": mount, "total": total, "used": total - avail, "free": avail,
                "pct": round(100.0 * (total - avail) / total, 1) if total else 0, "external": ext,
                "fs": p[1], "device": p[0], "readonly": ro.get(mount, False), "ejectable": ext}
        item.update(disk_info(p[0]))
        res.append(item)
    res.sort(key=lambda d: (d["external"], d["mount"] != "/", d["name"]))
    return res


def uptime():
    try:
        return int(float(_read("/proc/uptime", "0").split()[0]))
    except (ValueError, IndexError):
        return 0


def thermal_pressure():
    return "nominal"


def lan_interfaces():
    """[(iface, ip, network)] for real interfaces with a private IPv4 address (no VPN / docker / bridges)."""
    res = []
    for line in run(["ip", "-4", "-o", "addr", "show", "scope", "global"]).splitlines():
        m = re.match(r"\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", line)
        if not m or TUNNEL.match(m.group(1)):
            continue
        ip = m.group(2)
        if ipaddress.ip_address(ip).is_private:
            res.append((m.group(1), ip, ipaddress.ip_network("%s/%s" % (ip, m.group(3)), strict=False)))
    return res


def lan_ip():
    dev = re.search(r"\bdev (\S+)", run(["ip", "-4", "route", "show", "default"]))
    lan = lan_interfaces()
    for i, ip, _ in lan:
        if dev and i == dev.group(1):
            return ip
    return lan[0][1] if lan else "127.0.0.1"
