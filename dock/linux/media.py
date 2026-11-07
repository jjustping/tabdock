"""Now playing + volume on Linux: any MPRIS player (Spotify, Rhythmbox, VLC, browsers…) via `playerctl`,
system volume via PipeWire (`wpctl`) or PulseAudio (`pactl`)."""
import hashlib
import os
import re
import shutil
import threading
import time
import urllib.parse

from . import have, run


def _volume():
    if have("wpctl"):
        out = run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])          # "Volume: 0.45 [MUTED]"
        m = re.search(r"Volume:\s*([\d.]+)", out)
        if m:
            return round(float(m.group(1)) * 100), "MUTED" in out
    if have("pactl"):
        v = re.search(r"(\d+)%", run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"]))
        mu = "yes" in run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"])
        if v:
            return int(v.group(1)), mu
    return None, False


def _set_volume(v):
    if have("wpctl"):
        run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "%d%%" % v])
    elif have("pactl"):
        run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "%d%%" % v])


def _toggle_mute():
    if have("wpctl"):
        run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
    elif have("pactl"):
        run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])


FMT = "{{playerName}}\x1f{{status}}\x1f{{title}}\x1f{{artist}}\x1f{{album}}\x1f{{mpris:length}}\x1f{{position}}\x1f{{mpris:artUrl}}"


class Media:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.data = {"volume": None, "muted": False, "player": None}
        self._art_src = None
        self._lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                self.refresh()
            except Exception as e:
                self.data = dict(self.data, error=str(e)[:120])
            time.sleep(3)

    def refresh(self):
        vol, muted = _volume()
        d = {"volume": vol, "muted": muted, "player": None, "error": None if have("playerctl") else "playerctl не установлен"}
        players = []
        if have("playerctl"):
            out = run(["playerctl", "-a", "metadata", "--format", FMT], timeout=4)
            for line in out.splitlines():
                p = line.split("\x1f")
                if len(p) < 8 or p[1].lower() == "stopped" or not p[2]:
                    continue
                players.append({"app": p[0].capitalize(), "state": p[1].lower(), "title": p[2], "artist": p[3], "album": p[4],
                                "duration": (int(p[5]) / 1e6) if p[5].isdigit() else None,
                                "position": (int(p[6]) / 1e6) if p[6].isdigit() else None, "art_src": p[7], "name": p[0]})
        players.sort(key=lambda x: x["state"] != "playing")
        if players:
            pl = players[0]
            pl["art"] = self._art(pl.pop("art_src"))
            self._player = pl.pop("name")
            d["player"] = pl
        else:
            self._player = None
        d["at"] = time.time()
        with self._lock:
            self.data = d
        return d

    def _art(self, src):
        if not src:
            return None
        if src.startswith(("http://", "https://")):
            return src
        if src.startswith("file://"):
            path = urllib.parse.unquote(src[7:])
            dst = os.path.join(self.cache_dir, "cover.jpg")
            if src != self._art_src:
                self._art_src = src
                try:
                    shutil.copyfile(path, dst)
                except OSError:
                    return None
            return "/api/media/cover?k=%s" % hashlib.md5(src.encode()).hexdigest()[:10]
        return None

    def command(self, cmd, value=None):
        pl = getattr(self, "_player", None)
        target = ["-p", pl] if pl else []
        if cmd == "volume" and value is not None:
            _set_volume(max(0, min(100, int(value))))
        elif cmd == "mute":
            _toggle_mute()
        elif cmd in ("playpause", "next", "previous") and have("playerctl"):
            run(["playerctl"] + target + [{"playpause": "play-pause", "next": "next", "previous": "previous"}[cmd]])
        else:
            return False
        time.sleep(0.25)
        self.refresh()
        return True
