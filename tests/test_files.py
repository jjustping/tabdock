import io
import os

import pytest

from dock import inbox, outbox


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "INBOX", str(tmp_path / "in"))
    return tmp_path / "in"


@pytest.mark.parametrize("bad,good", [("../../etc/passwd", "passwd"), ("a/b.txt", "b.txt"), ('x:y*z?.jpg', "x_y_z_.jpg"),
                                      (".hidden", "hidden"), ("..\\..\\win.ini", ".._.._win.ini".lstrip("."))])
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
