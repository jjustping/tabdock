"""Upcoming events from macOS Calendar.

1) bin/dock-calendar (EventKit, expands recurring events) – preferred
2) AppleScript fallback via Calendar.app (slower, recurring events not expanded)
Refreshed in the background every 5 minutes.
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(HERE, "bin", "dock-calendar")

OSA = r'''
set d0 to current date
set time of d0 to 0
set d1 to d0 + (2 * days)
set out to ""
tell application "Calendar"
  repeat with c in calendars
    set cn to name of c
    repeat with e in (every event of c whose start date ≥ d0 and start date < d1)
      set s to start date of e
      set f to end date of e
      set out to out & (summary of e) & (ASCII character 31) & cn & (ASCII character 31) & (allday event of e) & (ASCII character 31) & ((s - d0) as integer) & (ASCII character 31) & ((f - d0) as integer) & linefeed
    end repeat
  end repeat
end tell
return out
'''


class CalendarFeed:
    def __init__(self, enabled_fn):
        self.enabled_fn = enabled_fn
        self.data = {"ok": False, "events": [], "error": "loading"}
        self._kick = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def refresh_soon(self):
        self._kick.set()

    def _loop(self):
        while True:
            if self.enabled_fn():
                try:
                    self.data = self._read()
                except Exception as e:
                    self.data = {"ok": False, "events": [], "error": str(e)}
            else:
                self.data = {"ok": False, "events": [], "error": "disabled"}
            self._kick.wait(300)
            self._kick.clear()

    def _read(self):
        if os.path.exists(HELPER):
            try:
                r = subprocess.run([HELPER, "2"], capture_output=True, text=True, timeout=30)
                d = json.loads(r.stdout or "{}")
                if d.get("ok"):
                    d["source"] = "eventkit"
                    d["at"] = time.time()
                    return d
            except Exception:
                pass
        return self._osa()

    def _osa(self):
        try:
            r = subprocess.run(["/usr/bin/osascript", "-e", OSA], capture_output=True, text=True, timeout=40)
        except subprocess.TimeoutExpired:
            return {"ok": False, "events": [], "error": "timeout"}
        if r.returncode != 0:
            return {"ok": False, "events": [], "error": "no_access", "detail": r.stderr.strip()[:200]}
        d0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ev = []
        for line in r.stdout.splitlines():
            p = line.split("\x1f")
            if len(p) < 5:
                continue
            s = d0 + timedelta(seconds=int(p[3]))
            e = d0 + timedelta(seconds=int(p[4]))
            ev.append({"title": p[0], "calendar": p[1], "allDay": p[2] == "true",
                       "start": s.astimezone().isoformat(), "end": e.astimezone().isoformat(),
                       "color": "#8e8e93", "location": ""})
        ev.sort(key=lambda x: x["start"])
        return {"ok": True, "events": ev, "source": "applescript", "at": time.time()}
