"""Weather from Open-Meteo (free, no API key). Cached for 15 minutes."""
import json
import threading
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "tabdock/0.1"}

# WMO weather codes -> (emoji, Russian, English)
CODES = {
    0: ("☀️", "Ясно", "Clear"), 1: ("🌤", "Малооблачно", "Mainly clear"),
    2: ("⛅️", "Облачно", "Partly cloudy"), 3: ("☁️", "Пасмурно", "Overcast"),
    45: ("🌫", "Туман", "Fog"), 48: ("🌫", "Изморозь", "Rime fog"),
    51: ("🌦", "Морось", "Drizzle"), 53: ("🌦", "Морось", "Drizzle"), 55: ("🌧", "Сильная морось", "Dense drizzle"),
    56: ("🌧", "Ледяная морось", "Freezing drizzle"), 57: ("🌧", "Ледяная морось", "Freezing drizzle"),
    61: ("🌦", "Небольшой дождь", "Light rain"), 63: ("🌧", "Дождь", "Rain"), 65: ("🌧", "Ливень", "Heavy rain"),
    66: ("🌧", "Ледяной дождь", "Freezing rain"), 67: ("🌧", "Ледяной дождь", "Freezing rain"),
    71: ("🌨", "Небольшой снег", "Light snow"), 73: ("🌨", "Снег", "Snow"), 75: ("❄️", "Сильный снег", "Heavy snow"),
    77: ("🌨", "Снежная крупа", "Snow grains"), 80: ("🌦", "Ливень", "Showers"), 81: ("🌧", "Ливни", "Showers"),
    82: ("⛈", "Сильные ливни", "Violent showers"), 85: ("🌨", "Снегопад", "Snow showers"),
    86: ("🌨", "Снегопад", "Snow showers"), 95: ("⛈", "Гроза", "Thunderstorm"),
    96: ("⛈", "Гроза с градом", "Thunderstorm, hail"), 99: ("⛈", "Гроза с градом", "Thunderstorm, hail"),
}


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def geocode(name, lang="ru"):
    q = urllib.parse.urlencode({"name": name, "count": 6, "language": lang, "format": "json"})
    data = _get("https://geocoding-api.open-meteo.com/v1/search?" + q)
    out = []
    for r in data.get("results", []) or []:
        out.append({"name": r.get("name"), "country": r.get("country"), "admin": r.get("admin1"),
                    "lat": r.get("latitude"), "lon": r.get("longitude"), "tz": r.get("timezone")})
    return out


def describe(code):
    e, ru, en = CODES.get(int(code or 0), ("🌡", "—", "—"))
    if not e.endswith("\ufe0f"):
        e += "\ufe0f"  # force colour emoji presentation
    return {"code": int(code or 0), "icon": e, "text": ru, "text_en": en}


class Weather:
    def __init__(self):
        self._cache = None
        self._at = 0
        self._key = None
        self._lock = threading.Lock()

    def get(self, place):
        if not place or place.get("lat") is None:
            return {"configured": False}
        key = (place["lat"], place["lon"])
        with self._lock:
            if self._cache and self._key == key and time.time() - self._at < 900:
                return self._cache
        q = urllib.parse.urlencode({
            "latitude": place["lat"], "longitude": place["lon"], "timezone": "auto",
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m,is_day",
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
            "forecast_days": 4, "wind_speed_unit": "ms",
        })
        try:
            d = _get("https://api.open-meteo.com/v1/forecast?" + q)
        except Exception as e:
            with self._lock:
                if self._cache:
                    c = dict(self._cache)
                    c["stale"] = True
                    return c
            return {"configured": True, "error": str(e)}
        cur = d.get("current", {})
        res = {"configured": True, "place": place.get("name"),
               "temp": cur.get("temperature_2m"), "feels": cur.get("apparent_temperature"),
               "wind": cur.get("wind_speed_10m"), "humidity": cur.get("relative_humidity_2m"),
               **describe(cur.get("weather_code"))}
        days = []
        dd = d.get("daily", {})
        for i, day in enumerate(dd.get("time", [])):
            days.append({"date": day, "max": dd["temperature_2m_max"][i], "min": dd["temperature_2m_min"][i],
                         "rain": (dd.get("precipitation_probability_max") or [None] * 9)[i],
                         "sunrise": dd["sunrise"][i][-5:], "sunset": dd["sunset"][i][-5:],
                         **describe(dd["weather_code"][i])})
        res["days"] = days
        hh = d.get("hourly", {})
        now = cur.get("time", "")[:13]
        hours = []
        times = hh.get("time", [])
        start = next((i for i, t in enumerate(times) if t[:13] >= now), 0)
        for i in range(start, min(start + 12, len(times))):
            hours.append({"t": times[i][-5:], "temp": hh["temperature_2m"][i],
                          "rain": hh["precipitation_probability"][i], **describe(hh["weather_code"][i])})
        res["hours"] = hours
        with self._lock:
            self._cache, self._at, self._key = res, time.time(), key
        return res
