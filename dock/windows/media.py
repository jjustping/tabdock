"""Now playing + volume on Windows.

* Any player that shows up in the Windows media overlay (Spotify, browsers, Apple Music, VLC…) through
  Global System Media Transport Controls (the `winrt` packages, installed by install-windows.ps1).
* System volume and mute through Core Audio (IAudioEndpointVolume), called with ctypes.
* Without `winrt`, play/pause/next still work as media keys.
"""
import asyncio
import ctypes
import hashlib
import os
import threading
import time
import uuid
from ctypes import POINTER, byref, c_float, c_int, c_uint, c_void_p

# ---------------- Core Audio ----------------
CLSID_ENUM = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_ENUM = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_VOLUME = "{5CDF2C82-841E-4546-9722-0CF74078229A}"


class GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]


def _guid(s):
    return GUID.from_buffer_copy(uuid.UUID(s).bytes_le)


def _method(obj, index, *argtypes):
    vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)(vtbl[index])


def _release(obj):
    if obj:
        vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
        ctypes.WINFUNCTYPE(c_uint, c_void_p)(vtbl[2])(obj)


_com = threading.local()


def _endpoint_volume():
    if not getattr(_com, "ready", False):
        ctypes.oledll.ole32.CoInitializeEx(None, 0)       # multithreaded apartment, once per thread
        _com.ready = True
    enum, dev, vol = c_void_p(), c_void_p(), c_void_p()
    ctypes.oledll.ole32.CoCreateInstance(byref(_guid(CLSID_ENUM)), None, 23, byref(_guid(IID_ENUM)), byref(enum))
    try:
        _method(enum, 4, c_int, c_int, POINTER(c_void_p))(enum, 0, 1, byref(dev))        # eRender, eMultimedia
        _method(dev, 3, POINTER(GUID), c_uint, c_void_p, POINTER(c_void_p))(dev, byref(_guid(IID_VOLUME)), 23, None, byref(vol))
    finally:
        _release(dev)
        _release(enum)
    return vol


def get_volume():
    vol = _endpoint_volume()
    try:
        level, mute = c_float(), ctypes.c_int()
        _method(vol, 9, POINTER(c_float))(vol, byref(level))
        _method(vol, 15, POINTER(ctypes.c_int))(vol, byref(mute))
        return round(level.value * 100), bool(mute.value)
    finally:
        _release(vol)


def set_volume(v):
    vol = _endpoint_volume()
    try:
        _method(vol, 7, c_float, c_void_p)(vol, max(0, min(100, v)) / 100.0, None)
    finally:
        _release(vol)


def toggle_mute():
    _, muted = get_volume()
    vol = _endpoint_volume()
    try:
        _method(vol, 14, ctypes.c_int, c_void_p)(vol, 0 if muted else 1, None)
    finally:
        _release(vol)


VK = {"playpause": 0xB3, "next": 0xB0, "previous": 0xB1}


def media_key(name):
    u = ctypes.windll.user32
    u.keybd_event(VK[name], 0, 1, 0)          # KEYEVENTF_EXTENDEDKEY
    u.keybd_event(VK[name], 0, 3, 0)          # … | KEYEVENTF_KEYUP


# ---------------- Global System Media Transport Controls ----------------
try:
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as _Manager
except Exception:          # the winrt packages are optional
    _Manager = None

APP_NAMES = {"spotify": "Spotify", "chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox", "applemusic": "Apple Music",
             "vlc": "VLC", "zunemusic": "Медиаплеер", "music.ui": "Медиаплеер"}


def _app_name(aumid):
    a = (aumid or "").lower()
    for k, v in APP_NAMES.items():
        if k in a:
            return v
    return (aumid or "Плеер").split("!")[-1].split(".")[0][:24] or "Плеер"


async def _session():
    mgr = await _Manager.request_async()
    return mgr.get_current_session()


async def _now_playing(cache_dir):
    s = await _session()
    if s is None:
        return None
    props = await s.try_get_media_properties_async()
    info = s.get_playback_info()
    status = int(info.playback_status) if info else 0          # 4 = playing, 5 = paused
    if not props or not props.title or status not in (4, 5):
        return None
    tl = s.get_timeline_properties()
    pl = {"app": _app_name(s.source_app_user_model_id), "state": "playing" if status == 4 else "paused", "title": props.title,
          "artist": props.artist or props.album_artist or "", "album": props.album_title or "",
          "duration": tl.end_time.total_seconds() if tl and tl.end_time else None,
          "position": tl.position.total_seconds() if tl and tl.position else None, "art": None}
    try:
        key = hashlib.md5(("%s|%s|%s" % (pl["app"], pl["title"], pl["artist"])).encode()).hexdigest()[:10]
        dst = os.path.join(cache_dir, "cover.jpg")
        if props.thumbnail and getattr(_now_playing, "last_art", None) != key:
            from winrt.windows.storage.streams import Buffer, InputStreamOptions
            stream = await props.thumbnail.open_read_async()
            buf = Buffer(min(int(stream.size), 8 * 1024 * 1024))
            await stream.read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD)
            with open(dst, "wb") as f:
                f.write(bytes(buf))
            _now_playing.last_art = key
        if getattr(_now_playing, "last_art", None) == key:
            pl["art"] = "/api/media/cover?k=" + key
    except Exception:
        pass
    return pl


async def _command(cmd):
    s = await _session()
    if s is None:
        return False
    fn = {"playpause": s.try_toggle_play_pause_async, "next": s.try_skip_next_async,
          "previous": s.try_skip_previous_async}[cmd]
    return bool(await fn())


class Media:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.data = {"volume": None, "muted": False, "player": None}
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
        try:
            vol, muted = get_volume()
        except OSError:
            vol, muted = None, False
        d = {"volume": vol, "muted": muted, "player": None, "at": time.time(),
             "error": None if _Manager else "Нет пакета winrt: «сейчас играет» недоступно (кнопки работают)"}
        if _Manager:
            try:
                d["player"] = asyncio.run(_now_playing(self.cache_dir))
            except Exception as e:
                d["error"] = str(e)[:120]
        with self._lock:
            self.data = d
        return d

    def command(self, cmd, value=None):
        if cmd == "volume" and value is not None:
            set_volume(int(value))
        elif cmd == "mute":
            toggle_mute()
        elif cmd in VK:
            ok = False
            if _Manager:
                try:
                    ok = asyncio.run(_command(cmd))
                except Exception:
                    ok = False
            if not ok:
                media_key(cmd)
        else:
            return False
        time.sleep(0.3)
        self.refresh()
        return True
