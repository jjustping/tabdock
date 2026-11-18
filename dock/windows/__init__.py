"""Windows implementations of the platform modules (same interfaces as the macOS ones in dock/ and dock/linux/):
sysinfo, media, actions, bonjour, calendar. Built on ctypes and the PowerShell that comes with Windows, so the server
needs no extra programs. Tested on Windows 11 (ARM64).

Everything that touches the desktop (keys, screenshots, the tray) works only when the server runs in the user's own
session — that is how install-windows.ps1 starts it (Task Scheduler, «at log on»).
"""
import ctypes
import os
import struct
import subprocess
import sys

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0     # CREATE_NO_WINDOW: no console flashes under pythonw


def run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW,
                              encoding="utf-8", errors="replace").stdout
    except Exception:
        return ""


def ps(script, timeout=20):
    """Run a PowerShell snippet and return its output (UTF-8)."""
    pre = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;$ProgressPreference='SilentlyContinue';"
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", pre + script],
               timeout)


def spawn(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)


# ---------------- ping without ping.exe: IcmpSendEcho (no admin rights, no localized output to parse) ----------------
def icmp_ping(host, timeout_ms=3000):
    """Round-trip time in ms, or None when there is no reply."""
    import socket
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        return None
    iphlp = ctypes.WinDLL("iphlpapi")
    iphlp.IcmpCreateFile.restype = ctypes.c_void_p
    iphlp.IcmpSendEcho.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint16, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    iphlp.IcmpCloseHandle.argtypes = [ctypes.c_void_p]
    h = iphlp.IcmpCreateFile()
    try:
        data = b"TabDock-ping"
        reply = ctypes.create_string_buffer(64 + len(data) + 8)
        addr = struct.unpack("<I", socket.inet_aton(ip))[0]
        n = iphlp.IcmpSendEcho(h, addr, data, len(data), None, reply, len(reply), timeout_ms)
        if n <= 0:
            return None
        status, rtt = struct.unpack_from("<II", reply.raw, 4)   # ICMP_ECHO_REPLY: Address, Status, RoundTripTime
        return float(rtt) if status == 0 else None
    finally:
        iphlp.IcmpCloseHandle(h)


def kill_tree(pid):
    """End a process with everything it started: the venv's pythonw.exe is only a launcher of the real Python."""
    subprocess.run(["taskkill.exe", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)


def alive(pid):
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    h = k.OpenProcess(0x1000, False, int(pid))                 # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
        return code.value == 259                               # STILL_ACTIVE
    finally:
        k.CloseHandle(ctypes.c_void_p(h))


def follow_runner():
    """Server and tray quit by themselves when run.py is gone (the task was stopped, the runner was killed):
    otherwise an orphaned server keeps the port and an orphaned tray leaves a second icon."""
    pid = os.environ.get("TABDOCK_RUNNER")
    if not pid or not pid.isdigit():
        return
    import threading
    import time

    def watch():
        while alive(pid):
            time.sleep(3)
        os._exit(0)
    threading.Thread(target=watch, name="follow-runner", daemon=True).start()


def appdata(*parts):
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "TabDock", *parts)
