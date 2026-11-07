"""Demo mode (`server.py --demo`): synthetic shoots, calendar and Mac info for screenshots.

Nothing here comes from the real Capture One catalog, so screenshots never contain client data.
"""
import time
from datetime import datetime, timedelta

DAY = 86400


def shoots():
    now = time.time()
    base = {"catalog": "~/Pictures/Demo.cocatalog", "catalog_name": "Demo", "camera": "", "picked": 0,
            "group": None, "source": "c1"}
    items = [
        dict(base, uuid="demo-1", name="Improv", total=77, picked=40, exported=12, shot_from=now - 6 * DAY,
             created=now - 5 * DAY, last_export=now - DAY, demo_cover="/static/demo/cover1.png"),
        dict(base, uuid="demo-2", name="Lookbook — студия", total=120, picked=0, exported=0, shot_from=now - 2 * DAY,
             created=now - 2 * DAY, last_export=None, demo_cover="/static/demo/cover2.png"),
        dict(base, uuid="demo-3", name="Я красивенький", total=163, exported=163, shot_from=now - 47 * DAY,
             created=now - 47 * DAY, last_export=now - 16 * DAY, demo_cover="/static/demo/cover3.png"),
        dict(base, uuid="demo-4", name="Свадьба", total=410, picked=96, exported=0, shot_from=now - 9 * DAY,
             created=now - 9 * DAY, last_export=None, demo_cover="/static/demo/cover4.png"),
    ]
    for s in items:
        s["key"] = "c1:" + s["uuid"]
        s["cover_file"] = None
    return items


def calendar():
    d0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).astimezone()

    def ev(day, h, m, dur, title, cal, color, loc=""):
        s = d0 + timedelta(days=day, hours=h, minutes=m)
        return {"title": title, "start": s.isoformat(), "end": (s + timedelta(minutes=dur)).isoformat(),
                "allDay": False, "calendar": cal, "color": color, "location": loc}
    return {"ok": True, "source": "demo", "events": [
        ev(0, 11, 0, 60, "Созвон с клиентом по свадьбе", "Работа", "#63b3ed"),
        ev(0, 19, 30, 180, "DJ-сет", "Музыка", "#b794f4", "клуб"),
        ev(1, 14, 0, 120, "Съёмка Improv, часть 2", "Съёмки", "#f6ad55", "студия"),
    ]}


def sysinfo(real):
    d = dict(real)
    d.update({"hostname": "Мой компьютер", "chip": "Apple silicon", "model": "server", "cores": 10, "ip": "192.168.1.20"})
    g = 1000 ** 3
    d["disks"] = [
        {"name": "Macintosh HD", "mount": "/", "total": 512 * g, "used": 301 * g, "free": 211 * g, "pct": 58.8, "external": False},
        {"name": "Photo SSD", "mount": "/Volumes/Photo SSD", "total": 2000 * g, "used": 1460 * g, "free": 540 * g, "pct": 73.0, "external": True},
    ]
    if d.get("mem"):
        d["mem"] = dict(d["mem"], total=16 * g, used=int(16 * g * d["mem"]["pct"] / 100))
    return d
