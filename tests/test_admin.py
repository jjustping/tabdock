import os
import subprocess
import time

import pytest

from dock import admin

MAC_PING = """PING 192.168.1.1 (192.168.1.1): 56 data bytes
64 bytes from 192.168.1.1: icmp_seq=0 ttl=64 time=3.104 ms

--- 192.168.1.1 ping statistics ---
1 packets transmitted, 1 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 3.104/3.104/3.104/0.000 ms"""
LINUX_PING = "64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=0.412 ms\n1 packets transmitted, 1 received\nrtt min/avg/max/mdev = 0.412/0.412/0.412/0.000 ms"


def test_ping_output():
    assert admin.parse_ping(MAC_PING) == 3.104
    assert admin.parse_ping(LINUX_PING) == 0.412
    assert admin.parse_ping("Request timeout for icmp_seq 0") is None


def test_hosts_are_checked():
    out = admin.clean_hosts([
        {"name": "NAS", "kind": "ping", "target": "192.168.1.10", "mac": "AA-BB-CC-DD-EE-FF"},
        {"kind": "ping", "target": "-oProxyCommand=evil"},          # would be an option, not a host
        {"kind": "ping", "target": "a b"},
        {"kind": "http", "target": "javascript:alert(1)"},
        {"kind": "http", "target": "https://nas.local:5001"},
        {"kind": "tcp", "target": "nas.local:22"},
        {"kind": "tcp", "target": "nas.local:99999"},
        {"kind": "weird", "target": "router"},
    ])
    assert [(h["kind"], h["target"]) for h in out] == [("ping", "192.168.1.10"), ("http", "https://nas.local:5001"),
                                                       ("tcp", "nas.local:22"), ("ping", "router")]
    assert out[0]["mac"] == "aa:bb:cc:dd:ee:ff" and out[0]["id"]


def test_bad_mac_is_dropped():
    assert admin.clean_hosts([{"target": "pc", "mac": "zz:zz"}])[0]["mac"] == ""


def test_wol_packet():
    p = admin.wol_packet("aa:bb:cc:dd:ee:ff")
    assert len(p) == 102 and p[:6] == b"\xff" * 6 and p[6:12] == bytes.fromhex("aabbccddeeff")
    with pytest.raises(ValueError):
        admin.wol_packet("aa:bb")


def test_tcp_check_against_a_local_port(servers):
    port = servers[0].server_address[1]
    assert admin.check_host({"kind": "tcp", "target": "127.0.0.1:%d" % port})["up"]


def test_http_check_counts_login_pages_as_up(servers):
    port = servers[0].server_address[1]
    r = admin.check_host({"kind": "http", "target": "http://127.0.0.1:%d/no-such-page" % port})
    assert r["up"] and r["code"] == 404


def test_down_host():
    assert not admin.check_host({"kind": "tcp", "target": "127.0.0.1:1"})["up"]


def test_time_machine_date():
    t = admin.parse_tm_date("/Volumes/.timemachine/x/2026-11-09-123456.backup/2026-11-09-123456.backup")
    assert time.localtime(t)[:6] == (2026, 11, 9, 12, 34, 56)
    assert admin.parse_tm_date("") is None


def test_backup_marker(tmp_path):
    f = tmp_path / "last-run"
    f.write_text("ok")
    b = admin.clean_backups([{"name": "rsync", "path": str(f), "hours": 2}])[0]
    assert admin.check_backup(b)["ok"]
    old = time.time() - 5 * 3600
    os.utime(str(f), (old, old))
    assert not admin.check_backup(b)["ok"]
    assert admin.check_backup(dict(b, path=str(tmp_path / "missing")))["err"] == "Нет файла или папки"


def test_backup_folder_uses_the_newest_file(tmp_path):
    (tmp_path / "a").write_text("1")
    old = time.time() - 50 * 3600
    os.utime(str(tmp_path), (old, old))
    b = admin.clean_backups([{"path": str(tmp_path), "hours": 1}])[0]
    assert admin.check_backup(b)["ok"]


def test_diskutil():
    phys = "/dev/disk0 (internal, physical):\n   #: TYPE\n/dev/disk4 (external, physical):\n/dev/disk3 (synthesized):"
    assert admin.parse_diskutil_physical(phys) == ["/dev/disk0", "/dev/disk4"]
    d = admin.parse_diskutil_info("   Device / Media Name:      APPLE SSD AP0512Q\n   SMART Status:             Verified\n")
    assert d == {"name": "APPLE SSD AP0512Q", "status": "ok", "raw": "Verified"}
    assert admin.parse_diskutil_info("   SMART Status:             Failing\n")["status"] == "failing"
    assert admin.parse_diskutil_info("   SMART Status:             Not Supported\n")["status"] == "unknown"


UDISKS = """/org/freedesktop/UDisks2/block_devices/sda:
  org.freedesktop.UDisks2.Block:
    Device:                     /dev/sda
/org/freedesktop/UDisks2/drives/Samsung_SSD:
  org.freedesktop.UDisks2.Drive:
    Model:                      Samsung SSD 870
  org.freedesktop.UDisks2.Drive.Ata:
    SmartEnabled:               true
    SmartFailing:               false
    SmartTemperature:           308.15
/org/freedesktop/UDisks2/drives/WD_NVMe:
  org.freedesktop.UDisks2.Drive:
    Model:                      WD Black
  org.freedesktop.UDisks2.NVMe.Controller:
    SmartCriticalWarning:       [spare]
    SmartTemperature:           320
/org/freedesktop/UDisks2/drives/USB_Stick:
  org.freedesktop.UDisks2.Drive:
    Model:                      Flash
"""


def test_udisks():
    d = admin.parse_udisks(UDISKS)
    assert [(x["name"], x["status"]) for x in d] == [("Samsung SSD 870", "ok"), ("WD Black", "failing"), ("Flash", "unknown")]
    assert d[0]["temp"] == 35


def test_docker_ps():
    out = ('{"Names":"web","Image":"nginx","State":"exited","Status":"Exited (0) 2 hours ago"}\n'
           '{"Names":"db","Image":"postgres:16","State":"running","Status":"Up 3 days"}\nnot json\n')
    assert [c["name"] for c in admin.parse_docker_ps(out)] == ["db", "web"]
    assert "группу docker" in admin.docker_error("permission denied while trying to connect")
    assert admin.docker_error("Cannot connect to the Docker daemon") == "Docker не запущен"


def test_github_runs():
    j = {"workflow_runs": [{"name": "CI", "status": "completed", "conclusion": "failure", "head_branch": "main",
                            "html_url": "https://github.com/a/b/actions/runs/1", "updated_at": "2026-11-14T10:00:00Z",
                            "display_title": "Fix"}]}
    assert admin.parse_gh_runs(j)["state"] == "failure"
    assert admin.parse_gh_runs({"workflow_runs": [{"status": "in_progress", "conclusion": None}]})["state"] == "in_progress"
    assert admin.parse_gh_runs({})["state"] == "none"
    assert admin.clean_gh(["jjustping/tabdock", "../../etc", "a/b/c", "x"]) == ["jjustping/tabdock"]


def test_git_status_parse():
    out = "# branch.oid abc\n# branch.head main\n# branch.upstream origin/main\n# branch.ab +2 -1\n1 .M N... a.py\n? new.txt\n"
    assert admin.parse_git_status(out) == {"branch": "main", "upstream": "origin/main", "ahead": 2, "behind": 1, "changes": 2}


def test_real_repo(tmp_path):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, env=env)
    (tmp_path / "a.txt").write_text("1")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "first"], check=True, env=env)
    (tmp_path / "b.txt").write_text("2")
    st = admin.repo_state(str(tmp_path))
    assert st["branch"] == "main" and st["changes"] == 1 and st["last"] == "first"
    assert admin.repo_state(str(tmp_path / "nope"))["error"]


def test_actions_only_for_configured_things(app):
    assert app.admin.wake("nope")[0] is False
    assert app.admin.docker("anything", "stop")[0] is False
    assert app.admin.docker("x", "rm")[0] is False
    assert app.admin.git_op("nope", "pull")[0] is False
    assert app.admin.docker_logs("not-listed") is None


def test_settings_through_the_api(remote, device_key, app):
    st, d, _ = remote.post("/api/config", {"hosts": [{"name": "Router", "target": "127.0.0.1"}], "gh_repos": ["a/b", "bad"]},
                           key=device_key)
    assert st == 200 and d["config"]["hosts"][0]["name"] == "Router" and d["config"]["gh_repos"] == ["a/b"]
    st, d, _ = remote.get("/api/state", key=device_key)
    assert st == 200 and "admin" in d
    app.store.update("config", dict, lambda c: [c.pop(k, None) for k in ("hosts", "gh_repos")])
