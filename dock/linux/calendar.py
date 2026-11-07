"""Today's and tomorrow's events on Linux, from iCalendar (.ics) files:
GNOME/Evolution local calendars and any .ics put into ~/.config/tabdock/calendars/
(e.g. an exported Google/Nextcloud calendar). Simple events only; repeating events are not expanded yet."""
import glob
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone

SOURCES = [os.path.expanduser("~/.local/share/evolution/calendar/*/calendar.ics"),
           os.path.expanduser("~/.config/tabdock/calendars/*.ics")]


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def _dt(value, params):
    v = value.strip()
    try:
        if "VALUE=DATE" in params or len(v) == 8:
            return datetime.strptime(v[:8], "%Y%m%d").astimezone(), True
        if v.endswith("Z"):
            return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(), False
        return datetime.strptime(v[:15], "%Y%m%dT%H%M%S").astimezone(), False
    except ValueError:
        return None, False


def read_events(days=2):
    now = datetime.now().astimezone()
    d0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d1 = d0 + timedelta(days=days)
    ev = []
    files = [f for pat in SOURCES for f in glob.glob(pat)]
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                text = _unfold(fh.read())
        except OSError:
            continue
        cal = os.path.basename(os.path.dirname(f)) if f.endswith("calendar.ics") else os.path.splitext(os.path.basename(f))[0]
        for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
            props = {}
            for line in block.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                name, _, params = k.partition(";")
                props.setdefault(name.upper(), (v, params))
            if "DTSTART" not in props or "RRULE" in props:
                continue
            s, all_day = _dt(*props["DTSTART"])
            e = _dt(*props["DTEND"])[0] if "DTEND" in props else None
            if not s:
                continue
            e = e or (s + (timedelta(days=1) if all_day else timedelta(hours=1)))
            if e <= d0 or s >= d1:
                continue
            title = props.get("SUMMARY", ("(без названия)", ""))[0].replace("\\,", ",").replace("\\n", " ")
            ev.append({"title": title, "calendar": cal, "allDay": all_day, "start": s.isoformat(), "end": e.isoformat(),
                       "color": "#8e8e93", "location": props.get("LOCATION", ("", ""))[0].replace("\\,", ",")})
    ev.sort(key=lambda x: x["start"])
    return {"ok": True, "events": ev, "source": "ics", "files": len(files), "at": time.time()}


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
                    self.data = read_events()
                except Exception as e:
                    self.data = {"ok": False, "events": [], "error": str(e)}
            else:
                self.data = {"ok": False, "events": [], "error": "disabled"}
            self._kick.wait(300)
            self._kick.clear()
