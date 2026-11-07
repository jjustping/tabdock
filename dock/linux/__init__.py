"""Linux implementations of the platform modules (same interfaces as the macOS ones in dock/).

server.py picks them when sys.platform is not "darwin": sysinfo, media, actions, bonjour, calendar.
Tested on Ubuntu (GNOME, PipeWire). Everything degrades quietly when a tool is missing.
"""
import shutil
import subprocess


def run(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def have(tool):
    return shutil.which(tool) is not None
