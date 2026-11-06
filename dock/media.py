"""Music / Spotify now playing + system volume via AppleScript."""
import os
import subprocess
import threading
import time

SEP = "\x1f"

STATUS_TMPL = r'''
set out to ""
set vs to get volume settings
set vol to output volume of vs
set mut to output muted of vs
set out to "VOL" & (ASCII character 31) & vol & (ASCII character 31) & mut
%APPS%
return out
'''

MUSIC_BLOCK = r'''
if application "Music" is running then
  try
    tell application "Music"
      set pState to player state as text
      if pState is not "stopped" then
        set t to current track
        set out to out & linefeed & "TRK" & (ASCII character 31) & "Music" & (ASCII character 31) & pState & (ASCII character 31) & (name of t) & (ASCII character 31) & (artist of t) & (ASCII character 31) & (album of t) & (ASCII character 31) & (duration of t) & (ASCII character 31) & player position & (ASCII character 31) & (persistent ID of t)
      end if
    end tell
  end try
end if
'''
SPOTIFY_BLOCK = r'''
if application "Spotify" is running then
  try
    tell application "Spotify"
      set pState to player state as text
      if pState is not "stopped" then
        set t to current track
        set out to out & linefeed & "TRK" & (ASCII character 31) & "Spotify" & (ASCII character 31) & pState & (ASCII character 31) & (name of t) & (ASCII character 31) & (artist of t) & (ASCII character 31) & (album of t) & (ASCII character 31) & ((duration of t) / 1000) & (ASCII character 31) & player position & (ASCII character 31) & (artwork url of t)
      end if
    end tell
  end try
end if
'''


def _status_script():
    blocks = [MUSIC_BLOCK]
    if any(os.path.isdir(p) for p in ("/Applications/Spotify.app", os.path.expanduser("~/Applications/Spotify.app"))):
        blocks.insert(0, SPOTIFY_BLOCK)
    return STATUS_TMPL.replace("%APPS%", "\n".join(blocks))


ART_SCRIPT = r'''
on run argv
  tell application "Music"
    try
      set d to raw data of artwork 1 of current track
    on error
      return "none"
    end try
  end tell
  set f to open for access (POSIX file (item 1 of argv)) with write permission
  set eof f to 0
  write d to f
  close access f
  return "ok"
end run
'''


def osa(script, *args, timeout=6):
    try:
        r = subprocess.run(["/usr/bin/osascript", "-e", script] + list(args),
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "timeout"


def _num(s):
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None


class Media:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.data = {"volume": None, "muted": False, "player": None}
        self._art_id = None
        self._script = _status_script()
        self._lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            self.refresh()
            time.sleep(3)

    def refresh(self):
        out, err = osa(self._script)
        d = {"volume": None, "muted": False, "player": None, "error": err or None}
        players = []
        for line in out.splitlines():
            p = line.split(SEP)
            if p[0] == "VOL" and len(p) >= 3:
                d["volume"] = None if p[1] == "missing value" else int(_num(p[1]) or 0)
                d["muted"] = p[2] == "true"
            elif p[0] == "TRK" and len(p) >= 9:
                players.append({
                    "app": p[1], "state": p[2], "title": p[3], "artist": p[4], "album": p[5],
                    "duration": _num(p[6]), "position": _num(p[7]), "art_key": p[8],
                })
        # prefer the one that is playing
        players.sort(key=lambda x: x["state"] != "playing")
        if players:
            pl = players[0]
            pl["art"] = self._art(pl)
            pl.pop("art_key", None)
            d["player"] = pl
        d["at"] = time.time()
        with self._lock:
            self.data = d
        return d

    def _art(self, pl):
        if pl["app"] == "Spotify":
            return pl["art_key"] or None
        key = pl["art_key"]
        path = os.path.join(self.cache_dir, "cover.jpg")
        if key != self._art_id:
            self._art_id = key
            res, _ = osa(ART_SCRIPT, path)
            if res != "ok" and os.path.exists(path):
                os.remove(path)
        return "/api/media/cover?k=%s" % key if os.path.exists(path) else None

    def command(self, cmd, value=None):
        pl = (self.data.get("player") or {}).get("app") or ("Music" if cmd in ("playpause", "next", "previous") else None)
        if cmd == "volume" and value is not None:
            v = max(0, min(100, int(value)))
            osa("set volume output volume %d" % v)
        elif cmd == "mute":
            osa("set volume output muted (not (output muted of (get volume settings)))")
        elif cmd in ("playpause", "next", "previous") and pl:
            verb = {"playpause": "playpause", "next": "next track", "previous": "previous track"}[cmd]
            osa('tell application "%s" to %s' % (pl, verb))
        else:
            return False
        time.sleep(0.25)
        self.refresh()
        return True
