import io
import os

import pytest

from dock import inbox, outbox


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "INBOX", str(tmp_path / "in"))
    return tmp_path / "in"


@pytest.mark.parametrize("bad,good", [("../../etc/passwd", "passwd"), ("a/b.txt", "b.txt"), ('x:y*z?.jpg', "x_y_z_.jpg"),
                                      (".hidden", "hidden"), ("..\\..\\win.ini", "win.ini")])
def test_safe_name(bad, good):
    assert inbox.safe_name(bad) == good


def test_safe_name_is_never_empty():
    assert inbox.safe_name("") and inbox.safe_name("...") and inbox.safe_name(None)


def test_long_names_are_cut():
    assert len(inbox.safe_name("я" * 500 + ".jpg")) <= 180


def test_receive_file(box):
    ok, _, path = inbox.receive_file(io.BytesIO(b"hello"), 5, "кот.txt")
    assert ok and open(path, "rb").read() == b"hello" and os.path.dirname(path) == str(box)


def test_same_name_gets_a_number(box):
    inbox.receive_file(io.BytesIO(b"1"), 1, "a.txt")
    _, _, p = inbox.receive_file(io.BytesIO(b"2"), 1, "a.txt")
    assert p.endswith("a (2).txt")


def test_interrupted_upload_leaves_nothing(box):
    ok, _, _ = inbox.receive_file(io.BytesIO(b"ab"), 10, "x.bin")
    assert not ok and os.listdir(str(box)) == []


def test_size_limits(box):
    assert not inbox.receive_file(io.BytesIO(b""), 0, "x")[0]
    assert not inbox.receive_file(io.BytesIO(b""), inbox.MAX_FILE + 1, "x")[0]


def test_outbox_delivery(tmp_path):
    o = outbox.Outbox(str(tmp_path))
    ok, _, it = o.add(io.BytesIO(b"data"), 4, "a.txt", "", ["Tablet", "Phone"])
    assert ok
    assert [x["id"] for x in o.for_device("Tablet")] == [it["id"]]
    o.done(it["id"], "Tablet")
    assert o.for_device("Tablet") == []
    assert [x["id"] for x in o.for_device("Phone")] == [it["id"]]


def test_outbox_addressed_to_one_device(tmp_path):
    o = outbox.Outbox(str(tmp_path))
    o.add(io.BytesIO(b"x"), 1, "a.txt", "Tablet", ["Tablet", "Phone"])
    assert o.for_device("Phone") == [] and len(o.for_device("Tablet")) == 1


def test_upload_over_https(remote, device_key, box):
    st, r, _ = remote.request("PUT", "/api/send/file?name=t.bin", b"x" * 100000, {"X-Dock-Key": device_key})
    assert st == 200 and r["ok"] and os.path.getsize(str(box / "t.bin")) == 100000


def test_upload_needs_the_header_not_a_cookie(remote, device_key, box):
    st, _, _ = remote.request("PUT", "/api/send/file?name=t.bin", b"x", {"Cookie": "dock_k=" + device_key})
    assert st == 401


# ---------------- big files in parts, folders, resumed downloads (0.16) ----------------
import hashlib
import json


def start(remote, key, **body):
    return remote.post("/api/upload/start", body, key=key, **{"X-Dock-Device": "Tab"})[1]


def chunk(remote, key, uid, offset, data, sha=True):
    h = {"X-Dock-Key": key, "X-Dock-Device": "Tab"}
    if sha:
        h["X-Chunk-Sha256"] = hashlib.sha256(data).hexdigest()
    return remote.request("PUT", "/api/upload/chunk?id=%s&offset=%d" % (uid, offset), data, h)


def test_upload_in_parts_and_resume(remote, device_key, box):
    data = os.urandom(300000)
    r = start(remote, device_key, name="big.bin", size=len(data))
    assert r["ok"] and r["offset"] == 0
    st, b, _ = chunk(remote, device_key, r["id"], 0, data[:100000])
    assert st == 200 and b["offset"] == 100000
    # the connection «dropped»: the app asks again and continues where the server stopped
    r2 = start(remote, device_key, name="big.bin", size=len(data))
    assert r2["id"] == r["id"] and r2["offset"] == 100000
    st, b, _ = chunk(remote, device_key, r["id"], 0, data[:100000])          # a stale retry is refused
    assert st == 409 and b["offset"] == 100000
    st, b, _ = chunk(remote, device_key, r["id"], 100000, data[100000:])
    assert st == 200 and b["done"]
    assert open(str(box / "big.bin"), "rb").read() == data
    assert not [f for f in os.listdir(str(box / ".tabdock-incoming")) if f.endswith(".part")]


def test_damaged_part_is_refused(remote, device_key, box):
    data = b"x" * 1000
    r = start(remote, device_key, name="d.bin", size=1000)
    h = {"X-Dock-Key": device_key, "X-Chunk-Sha256": "0" * 64}
    st, b, _ = remote.request("PUT", "/api/upload/chunk?id=%s&offset=0" % r["id"], data, h)
    assert st == 422 and b["offset"] == 0
    assert chunk(remote, device_key, r["id"], 0, data)[1]["done"]


def test_folder_is_recreated(remote, device_key, box):
    files = {"a.jpg": b"1", "sub/b.jpg": b"22", "sub/deep/c.jpg": b"333", "../../evil.txt": b"!"}
    for rel_name, data in files.items():
        rel, _, name = rel_name.rpartition("/")
        r = start(remote, device_key, name=name, size=len(data), folder="Фото", rel=rel, batch="b1")
        assert chunk(remote, device_key, r["id"], 0, data)[1]["done"]
    root = box / "Фото"
    assert (root / "a.jpg").read_bytes() == b"1"
    assert (root / "sub" / "b.jpg").read_bytes() == b"22"
    assert (root / "sub" / "deep" / "c.jpg").read_bytes() == b"333"
    assert (root / "evil.txt").read_bytes() == b"!"           # «..» never leaves the folder
    # the same folder sent again (a new batch) does not mix with the first copy
    r = start(remote, device_key, name="a.jpg", size=1, folder="Фото", rel="", batch="b2")
    chunk(remote, device_key, r["id"], 0, b"9")
    assert (box / "Фото (2)" / "a.jpg").read_bytes() == b"9"


def test_not_enough_space(remote, device_key, box):
    r = start(remote, device_key, name="huge.bin", size=10 ** 15)
    assert not r["ok"] and "места" in r["message"]


def test_parts_need_a_device_key(remote, device_key, box):
    r = start(remote, device_key, name="k.bin", size=3)
    st, _, _ = remote.request("PUT", "/api/upload/chunk?id=%s&offset=0" % r["id"], b"abc", {"Cookie": "dock_k=" + device_key})
    assert st == 401
    assert remote.post("/api/upload/start", {"name": "x", "size": 1})[0] == 401


def test_resumed_download_from_outbox(local, remote, device_key, app):
    data = os.urandom(200000)
    st, r, _ = local.request("PUT", "/api/outbox/file?name=big.bin&to=Test%20tablet&folder=%D0%90%D0%BB%D1%8C%D0%B1%D0%BE%D0%BC&rel=x/y", data)
    assert r["ok"] and r["item"]["folder"] == "Альбом" and r["item"]["rel"] == "x/y"
    fid = r["item"]["id"]
    st, part, resp = remote.request("GET", "/api/outbox/file?id=" + fid, headers={"X-Dock-Key": device_key, "Range": "bytes=150000-"})
    assert st == 206 and resp.getheader("Content-Range") == "bytes 150000-199999/200000"
    st, _, _ = remote.request("GET", "/api/outbox/file?id=" + fid, headers={"X-Dock-Key": device_key, "Range": "bytes=999999-"})
    assert st == 416
    app.outbox.remove(fid)


def test_folder_names_in_any_alphabet_on_every_system(remote, device_key, box, monkeypatch):
    """Windows writes text files in its own code page unless told otherwise: Cyrillic folder names must still work."""
    import locale
    monkeypatch.setattr(locale, "getpreferredencoding", lambda *a, **k: "cp1252")
    r = start(remote, device_key, name="файл.txt", size=3, folder="Папка ёжик", rel="Подпапка", batch="u1")
    assert r["ok"] and chunk(remote, device_key, r["id"], 0, b"abc")[1]["done"]
    assert (box / "Папка ёжик" / "Подпапка" / "файл.txt").read_bytes() == b"abc"
