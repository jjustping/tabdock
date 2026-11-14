"""For admins and developers: hosts on the network (with Wake-on-LAN), backups, disk health (SMART),
Docker containers, GitHub Actions and local git repositories.

Everything is checked here in the background; requests only read the last result. Every list comes from the user's
own settings, and the only things that can be changed from a device are the ones listed there.
"""
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

MAC = sys.platform == "darwin"
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-:\[\]]{0,252}$")      # host name / IPv4 / IPv6; never starts with "-"
MAC_RE = re.compile(r"^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$")
GH_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
CONTAINER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _id(x):
    v = re.sub(r"[^a-z0-9]", "", str(x.get("id") or ""))[:16]
    return v or uuid.uuid4().hex[:8]


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as e:
        return 126, "", str(e)


# ---------------- settings sent by a device: checked and bounded ----------------
def clean_hosts(lst):
    out = []
    for h in (lst or [])[:24]:
        if not isinstance(h, dict):
            continue
        kind = h.get("kind") if h.get("kind") in ("ping", "http", "tcp") else "ping"
        target = str(h.get("target") or "").strip()[:300]
        if kind == "http":
            if not re.match(r"^https?://[^\s]+$", target, re.I):
                continue
        elif kind == "tcp":
            host, _, port = target.rpartition(":")
            if not HOST_RE.match(host or "x-") or not port.isdigit() or not 0 < int(port) < 65536:
                continue
        elif not HOST_RE.match(target):
            continue
        mac = str(h.get("mac") or "").strip()
        out.append({"id": _id(h), "name": str(h.get("name") or target)[:40], "kind": kind, "target": target,
                    "mac": mac.lower().replace("-", ":") if MAC_RE.match(mac) else ""})
    return out


def clean_backups(lst):
    out = []
    for b in (lst or [])[:12]:
        if not isinstance(b, dict):
            continue
        kind = "timemachine" if b.get("kind") == "timemachine" else "path"
        path = str(b.get("path") or "").strip()[:500]
        if kind == "path" and not path:
            continue
        try:
            hours = max(1, min(24 * 90, int(b.get("hours") or 26)))
        except (TypeError, ValueError):
            hours = 26
        out.append({"id": _id(b), "name": str(b.get("name") or ("Time Machine" if kind == "timemachine" else path))[:40],
                    "kind": kind, "path": path if kind == "path" else "", "hours": hours})
    return out


def clean_repos(lst):
    out = []
    for r in (lst or [])[:20]:
        if isinstance(r, dict) and str(r.get("path") or "").strip():
            p = str(r["path"]).strip()[:500]
            out.append({"id": _id(r), "name": str(r.get("name") or os.path.basename(p.rstrip("/")) or p)[:40], "path": p})
    return out


def clean_gh(lst):
    return [str(x).strip() for x in (lst or [])[:8] if GH_RE.match(str(x).strip())]


# ---------------- hosts ----------------
def parse_ping(out):
    """Round-trip time in ms from ping's output (macOS and Linux), None if no reply."""
    m = re.search(r"= [\d.]+/([\d.]+)/", out) or re.search(r"time[=<]([\d.]+) ?ms", out)
    return float(m.group(1)) if m else None


def check_host(h):
    """{"up", "ms", "err"} for one host."""
    t = time.time()
    try:
        if h["kind"] == "ping":
            if MAC:
                cmd = ["/sbin/ping6", "-c", "1", h["target"]] if ":" in h["target"] else ["/sbin/ping", "-c", "1", "-t", "3", h["target"]]
            else:
                cmd = ["ping", "-c", "1", "-W", "3", h["target"]]
            code, out, _ = _run(cmd, 6)
            ms = parse_ping(out)
            return {"up": code == 0 and ms is not None, "ms": ms, "err": None if code == 0 else "не отвечает"}
        if h["kind"] == "tcp":
            host, _, port = h["target"].rpartition(":")
            socket.create_connection((host.strip("[]"), int(port)), 4).close()
            return {"up": True, "ms": round((time.time() - t) * 1000), "err": None}
        # http: any answer below 500 counts as up (a login page answers 401/403); home services often have their own
        # certificates, and nothing secret is sent, so the certificate is not checked
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(h["target"], method="GET", headers={"User-Agent": "TabDock"})
        try:
            with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        return {"up": code < 500, "ms": round((time.time() - t) * 1000), "err": None if code < 500 else "HTTP %d" % code,
                "code": code}
    except (OSError, ValueError) as e:
        return {"up": False, "ms": None, "err": str(getattr(e, "reason", e))[:80] or "не отвечает"}


def wol_packet(mac):
    raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(raw) != 6:
        raise ValueError("bad MAC")
    return b"\xff" * 6 + raw * 16


def wake(mac):
    """Wake-on-LAN: the magic packet to the whole home network (port 9, and 7 for older cards)."""
    pkt = wol_packet(mac)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for port in (9, 7):
            s.sendto(pkt, ("255.255.255.255", port))
    finally:
        s.close()


# ---------------- backups ----------------
def parse_tm_date(text):
    """Time of the newest Time Machine backup from `tmutil latestbackup` (…/2026-11-09-123456.backup)."""
    m = re.findall(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})", text or "")
    if not m:
        return None
    return time.mktime(tuple(int(x) for x in m[-1]) + (0, 0, -1))


def last_change(path):
    """When a backup last ran: the file's time, or the newest item at the top of a folder."""
    p = os.path.expanduser(path)
    st = os.stat(p)
    newest = st.st_mtime
    if os.path.isdir(p):
        with os.scandir(p) as it:
            for i, e in enumerate(it):
                if i > 2000:
                    break
                try:
                    newest = max(newest, e.stat(follow_symlinks=False).st_mtime)
                except OSError:
                    pass
    return newest


def check_backup(b, now=None):
    now = now or time.time()
    try:
        if b["kind"] == "timemachine":
            if not MAC:
                return {"ok": False, "at": None, "err": "Time Machine есть только на Mac"}
            code, out, err = _run(["/usr/bin/tmutil", "latestbackup"], 20)
            at = parse_tm_date(out)
            if not at:
                return {"ok": False, "at": None, "err": "Нет копий или нет доступа (TabDock нужен «Полный доступ к диску»)"
                        if code else "Копий пока нет"}
        else:
            at = last_change(b["path"])
        return {"ok": now - at <= b["hours"] * 3600, "at": at, "err": None}
    except OSError as e:
        return {"ok": False, "at": None, "err": "Нет файла или папки" if isinstance(e, FileNotFoundError) else str(e)[:80]}


# ---------------- disk health ----------------
def parse_diskutil_physical(out):
    return re.findall(r"^(/dev/disk\d+) \((?:internal|external)[^)]*physical\)", out, re.M)


def parse_diskutil_info(out):
    name = re.search(r"Device / Media Name:\s*(.+)", out)
    smart = re.search(r"SMART Status:\s*(.+)", out)
    s = (smart.group(1).strip() if smart else "")
    return {"name": name.group(1).strip() if name else "Диск",
            "status": "ok" if s == "Verified" else "failing" if s.lower().startswith("fail") else "unknown", "raw": s or "нет данных"}


def parse_udisks(dump):
    """Drive health from `udisksctl dump` (no root needed): ATA SmartFailing / NVMe critical warnings."""
    drives, cur, iface = [], None, None
    for line in dump.splitlines():
        if re.match(r"^/org/freedesktop/UDisks2/drives/\S+:$", line):
            cur = {"name": "Диск", "status": "unknown", "raw": "нет данных"}
            drives.append(cur)
            iface = None
            continue
        if cur is None:
            continue
        if re.match(r"^/", line):
            cur = None
            continue
        m = re.match(r"^  (org\.freedesktop\.\S+):$", line)
        if m:
            iface = m.group(1)
            continue
        m = re.match(r"^\s{4}(\w+):\s*(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if iface == "org.freedesktop.UDisks2.Drive" and k == "Model" and v:
            cur["name"] = v
        elif iface == "org.freedesktop.UDisks2.Drive.Ata":
            if k == "SmartFailing":
                cur["status"], cur["raw"] = ("failing", "диск сообщает о сбое") if v == "true" else ("ok", "в порядке")
            elif k == "SmartTemperature" and v not in ("0", "0.0"):
                cur["temp"] = round(float(v) - 273.15)
        elif iface == "org.freedesktop.UDisks2.NVMe.Controller":
            if k == "SmartCriticalWarning":
                warn = v.strip("[]").strip()
                cur["status"], cur["raw"] = ("failing", "предупреждение: " + warn) if warn else ("ok", "в порядке")
            elif k == "SmartTemperature" and v not in ("0", "0.0"):
                cur["temp"] = round(float(v) - 273.15)
    return [d for d in drives if d["raw"] != "нет данных" or d["name"] != "Диск"]


def smart():
    if MAC:
        _, out, _ = _run(["/usr/sbin/diskutil", "list", "physical"], 15)
        res = []
        for dev in parse_diskutil_physical(out)[:8]:
            _, info, _ = _run(["/usr/sbin/diskutil", "info", dev], 15)
            d = parse_diskutil_info(info)
            if "Disk Image" not in info:
                res.append(d)
        return res
    code, out, _ = _run(["udisksctl", "dump"], 15)
    return parse_udisks(out) if code == 0 else []


# ---------------- Docker ----------------
def docker_bin():
    for p in [shutil.which("docker"), "/usr/local/bin/docker", "/opt/homebrew/bin/docker",
              "/Applications/Docker.app/Contents/Resources/bin/docker", "/usr/bin/docker"]:
        if p and os.path.exists(p):
            return p
    return None


def parse_docker_ps(out):
    res = []
    for line in out.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        res.append({"name": j.get("Names", "").split(",")[0], "image": j.get("Image", ""), "state": j.get("State", ""),
                    "status": j.get("Status", "")})
    return sorted(res, key=lambda c: (c["state"] != "running", c["name"]))


def docker_error(err):
    e = err.lower()
    if "permission denied" in e:
        return "Нет доступа к Docker: добавьте пользователя в группу docker и перезайдите"
    if "cannot connect" in e or "is the docker daemon running" in e or "no such file" in e:
        return "Docker не запущен"
    return err.strip()[:120] or "Docker не ответил"


def docker_list():
    b = docker_bin()
    if not b:
        return {"installed": False, "containers": []}
    code, out, err = _run([b, "ps", "-a", "--format", "{{json .}}"], 10)
    if code != 0:
        return {"installed": True, "containers": [], "error": docker_error(err)}
    return {"installed": True, "containers": parse_docker_ps(out)}


# ---------------- GitHub Actions ----------------
def gh_token():
    tok = os.environ.get("TABDOCK_GITHUB_TOKEN")
    if tok:
        return tok.strip()
    try:
        with open(os.path.expanduser("~/.config/tabdock/github-token")) as f:
            return f.read().strip() or None
    except OSError:
        return None


def parse_gh_runs(j):
    runs = (j or {}).get("workflow_runs") or []
    if not runs:
        return {"state": "none"}
    r = runs[0]
    state = r.get("conclusion") or r.get("status") or "unknown"     # success / failure / cancelled / in_progress / queued
    return {"state": state, "workflow": r.get("name", ""), "title": (r.get("display_title") or "")[:120],
            "branch": r.get("head_branch", ""), "url": r.get("html_url", ""), "at": r.get("updated_at", "")}


# ---------------- git ----------------
def parse_git_status(out):
    st = {"branch": "", "upstream": "", "ahead": 0, "behind": 0, "changes": 0}
    for line in out.splitlines():
        if line.startswith("# branch.head "):
            st["branch"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.upstream "):
            st["upstream"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            m = re.match(r"# branch\.ab \+(\d+) -(\d+)", line)
            if m:
                st["ahead"], st["behind"] = int(m.group(1)), int(m.group(2))
        elif line and not line.startswith("#"):
            st["changes"] += 1
    return st


def git(path, *args, timeout=15):
    # core.fsmonitor and hooks from a repository's own config must not run commands for us
    return _run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-C", os.path.expanduser(path)]
                + list(args), timeout)


def repo_state(path):
    if not os.path.isdir(os.path.join(os.path.expanduser(path), ".git")) and not os.path.isfile(os.path.join(os.path.expanduser(path), ".git")):
        return {"error": "Не git-репозиторий"}
    code, out, err = git(path, "status", "--porcelain=v2", "--branch")
    if code != 0:
        return {"error": (err.strip() or "git не ответил")[:120]}
    st = parse_git_status(out)
    code, out, _ = git(path, "log", "-1", "--format=%s%x1f%ct")
    if code == 0 and "\x1f" in out:
        subj, ts = out.strip().split("\x1f", 1)
        st.update(last=subj[:120], last_at=int(ts) if ts.isdigit() else None)
    return st


# ---------------- the background checker ----------------
class Admin:
    def __init__(self, config, add_event):
        self.config = config            # () -> current config
        self.add_event = add_event      # (**event) -> None
        self.data = {"hosts": {}, "backups": {}, "smart": [], "docker": {"installed": False, "containers": []},
                     "ci": {}, "repos": {}}
        self._etag = {}
        self._kick = threading.Event()
        self._lock = threading.Lock()
        threading.Thread(target=self._loop, name="admin", daemon=True).start()

    def kick(self):
        self._kick.set()

    def _loop(self):
        tick = 0
        while True:
            cfg = self.config()
            for name, every, fn in (("hosts", 1, self._hosts), ("repos", 1, self._repos), ("docker", 1, self._docker),
                                    ("backups", 10, self._backups), ("ci", 10, self._ci), ("smart", 30, self._smart)):
                if tick % every == 0 or self._kick.is_set():
                    try:
                        fn(cfg)
                    except Exception as e:      # one broken check must not stop the others
                        print("admin %s: %s" % (name, e), flush=True)
            self._kick.clear()
            tick += 1
            self._kick.wait(60)

    def _hosts(self, cfg):
        hosts = cfg.get("hosts", [])
        res, threads = {}, []
        for h in hosts:
            def one(h=h):
                res[h["id"]] = check_host(h)
            t = threading.Thread(target=one, daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(10)
        old, now = self.data["hosts"], time.time()
        out = {}
        for h in hosts:
            r = res.get(h["id"]) or {"up": False, "ms": None, "err": "нет ответа"}
            prev = old.get(h["id"])
            r["since"] = prev["since"] if prev and prev["up"] == r["up"] else now
            if prev and prev["up"] != r["up"]:
                self.add_event(type="host_up" if r["up"] else "host_down", name=h["name"])
            out[h["id"]] = r
        self.data["hosts"] = out

    def _backups(self, cfg):
        self.data["backups"] = {b["id"]: check_backup(b) for b in cfg.get("backups", [])}

    def _smart(self, cfg):
        self.data["smart"] = smart()

    def _docker(self, cfg):
        self.data["docker"] = docker_list()

    def _repos(self, cfg):
        self.data["repos"] = {r["id"]: repo_state(r["path"]) for r in cfg.get("repos", [])}

    def _ci(self, cfg):
        tok, out = gh_token(), {}
        for repo in cfg.get("gh_repos", []):
            headers = {"User-Agent": "TabDock", "Accept": "application/vnd.github+json"}
            if tok:
                headers["Authorization"] = "Bearer " + tok
            if repo in self._etag:                      # unchanged answers do not count against GitHub's limit
                headers["If-None-Match"] = self._etag[repo][0]
            req = urllib.request.Request("https://api.github.com/repos/%s/actions/runs?per_page=1" % repo, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    j = json.loads(r.read())
                    self._etag[repo] = (r.headers.get("ETag", ""), parse_gh_runs(j))
                out[repo] = self._etag[repo][1]
            except urllib.error.HTTPError as e:
                if e.code == 304 and repo in self._etag:
                    out[repo] = self._etag[repo][1]
                else:
                    out[repo] = {"state": "error", "err": "репозиторий не найден или закрыт (нужен токен)"
                                 if e.code in (401, 403, 404) else "GitHub: HTTP %d" % e.code}
            except (OSError, ValueError):
                out[repo] = {"state": "error", "err": "нет связи с GitHub"}
        self.data["ci"] = out

    # ---------------- actions from a device: only for what the settings list ----------------
    def wake(self, host_id):
        h = next((x for x in self.config().get("hosts", []) if x["id"] == host_id), None)
        if not h or not h.get("mac"):
            return False, "Для этого устройства не указан MAC-адрес"
        try:
            wake(h["mac"])
        except (OSError, ValueError) as e:
            return False, "Не получилось: %s" % e
        self.kick()
        return True, "Отправил сигнал «проснись» для «%s»" % h["name"]

    def docker(self, name, op):
        if op not in ("start", "stop", "restart"):
            return False, "Неизвестное действие"
        names = {c["name"] for c in self.data["docker"].get("containers", [])}
        if name not in names or not CONTAINER_RE.match(name):
            return False, "Контейнер не найден"
        code, _, err = _run([docker_bin(), op, name], 60)
        self._docker(None)
        return (True, {"start": "Запущен", "stop": "Остановлен", "restart": "Перезапущен"}[op] + ": " + name) if code == 0 \
            else (False, docker_error(err))

    def docker_logs(self, name, lines=80):
        names = {c["name"] for c in self.data["docker"].get("containers", [])}
        if name not in names or not CONTAINER_RE.match(name):
            return None
        code, out, err = _run([docker_bin(), "logs", "--tail", str(max(10, min(500, lines))), name], 15)
        return ANSI.sub("", (out + err) if code == 0 else docker_error(err))[-30000:]

    def git_op(self, repo_id, op):
        r = next((x for x in self.config().get("repos", []) if x["id"] == repo_id), None)
        if not r:
            return False, "Репозиторий не найден"
        if op not in ("fetch", "pull"):
            return False, "Неизвестное действие"
        code, out, err = git(r["path"], *(["fetch", "--quiet"] if op == "fetch" else ["pull", "--ff-only", "--quiet"]), timeout=90)
        self.data["repos"][r["id"]] = repo_state(r["path"])
        if code == 0:
            return True, ("Обновлено с сервера: " if op == "fetch" else "Подтянуто: ") + r["name"]
        return False, (err.strip().splitlines() or ["git не ответил"])[-1][:160]
