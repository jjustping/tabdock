"""wfolio client galleries.

wfolio (wfolio.ru / wfolio.pro) has no public API, webhooks or feeds (checked 2026-11-06 against
docs.wfolio.pro/llms.txt). So galleries are added by link + storage end date ("срок хранения"),
and the dock checks the public link itself every few hours:
  active   – page opens
  expired  – page says "Срок действия ссылки истёк" or returns 404/410
  error    – no internet / unexpected answer
No wfolio login or password is used or stored.
"""
import html
import re
import threading
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) tabdock/0.2"
EXPIRED_MARKERS = ("Срок действия ссылки истёк", "Срок действия ссылки истек", "link has expired")


def check(url, timeout=12):
    res = {"at": time.time(), "status": "error", "http": None, "title": None}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru,en"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res["http"] = r.status
            body = r.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        res["http"] = e.code
        if e.code in (404, 410):
            res["status"] = "expired"
        return res
    except Exception as e:
        res["error"] = str(e)[:120]
        return res
    if any(m.lower() in body.lower() for m in EXPIRED_MARKERS):
        res["status"] = "expired"
    else:
        res["status"] = "active"
        m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
        if m:
            res["title"] = html.unescape(m.group(1)).strip()[:200]
        if re.search(r'type=["\']password["\']', body, re.I):
            res["protected"] = True
    return res


class Checker:
    """Re-checks every gallery link every 6 hours (and right after it is added)."""

    def __init__(self, store):
        self.store = store
        self._kick = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def kick(self):
        self._kick.set()

    def _loop(self):
        time.sleep(5)
        while True:
            items = self.store.load("wfolio", [])
            now = time.time()
            for g in items:
                last = (g.get("check") or {}).get("at", 0)
                if g.get("url") and now - last > 6 * 3600:
                    r = check(g["url"])

                    def upd(lst, gid=g["id"], r=r):
                        for x in lst:
                            if x["id"] == gid:
                                x["check"] = r
                    self.store.update("wfolio", [], upd)
            self._kick.wait(1800)
            self._kick.clear()
