import json
import os

from dock import auth


def req(remote, **body):
    return remote.post("/api/devices/request", dict({"name": "Tab"}, **body))[1]


def test_wrong_code(remote):
    r = req(remote, k="wrong")
    assert not r["ok"] and "key" not in r


def test_new_device_waits_for_the_computer(remote, app, code):
    r = req(remote, k=code)
    assert r["ok"] and r["status"] == "pending"
    assert remote.get("/api/all", key=r["key"])[0] == 401
    assert remote.get("/api/devices/me", key=r["key"])[1]["status"] == "pending"
    assert app.devices.allow(r["id"])
    assert remote.get("/api/devices/me", key=r["key"])[1]["status"] == "ok"
    assert remote.get("/api/all", key=r["key"])[0] == 200


def test_allow_and_remove_from_the_computer(local, remote, code):
    r = req(remote, k=code)
    assert local.post("/api/devices", {"op": "allow", "id": r["id"]})[1]["ok"]
    assert remote.get("/api/state", key=r["key"])[0] == 200
    assert local.post("/api/devices", {"op": "remove", "id": r["id"]})[1]["ok"]
    assert remote.get("/api/state", key=r["key"])[0] == 401
    assert remote.get("/api/devices/me", key=r["key"])[0] == 401


def test_each_device_has_its_own_key(remote, app, code):
    a, b = req(remote, k=code), req(remote, k=code)
    assert a["key"] != b["key"]
    app.devices.allow(a["id"]); app.devices.allow(b["id"])
    app.devices.remove(a["id"])
    assert remote.get("/api/state", key=a["key"])[0] == 401
    assert remote.get("/api/state", key=b["key"])[0] == 200


def test_keys_are_stored_only_as_hashes(remote, app, code):
    r = req(remote, k=code)
    with open(os.path.join(app.store.dir if hasattr(app.store, "dir") else os.path.dirname(app.store.path("devices")), "devices.json")) as f:
        raw = f.read()
    assert r["key"] not in raw and json.loads(raw)
    assert all("hash" not in d for d in app.devices.listing())


def test_wrong_codes_are_rate_limited(remote):
    for _ in range(5):
        assert remote.post("/api/devices/request", {"k": "bad"})[0] == 200
    assert remote.post("/api/devices/request", {"k": "bad"})[0] == 429


def test_password_also_needs_the_computer(remote, app):
    h = auth.hash_password("secret1")
    app.store.update("config", dict, lambda c: c.__setitem__("password_hash", h))
    try:
        assert not req(remote, password="wrong")["ok"]
        r = req(remote, password="secret1")
        assert r["ok"] and remote.get("/api/all", key=r["key"])[0] == 401
    finally:
        app.store.update("config", dict, lambda c: c.pop("password_hash", None))


def test_browser_from_the_qr_link(remote, app, code):
    st, _, r = remote.get("/?k=" + code)
    assert st == 302 and r.getheader("Location") == "/"
    cookie = r.getheader("Set-Cookie")
    assert "Secure" in cookie and "HttpOnly" in cookie
    head = {"Cookie": cookie.split(";")[0]}
    st, page, _ = remote.get("/", **head)
    assert st == 200 and "Подтвердите на компьютере" in page
    app.devices.allow(app.devices.pending()[0]["id"])
    st, page, _ = remote.get("/", **head)
    assert st == 200 and "Подтвердите на компьютере" not in page


def test_old_requests_are_pushed_out_not_allowed_ones(remote, app, code):
    keep = req(remote, k=code)
    app.devices.allow(keep["id"])
    for _ in range(9):
        auth._fail.clear()
        req(remote, k=code)
    assert len(app.devices.pending()) <= 5
    assert remote.get("/api/state", key=keep["key"])[0] == 200


def test_new_qr_disconnects_everyone(local, remote, app, code, device_key):
    assert local.post("/api/config", {"new_token": True})[0] == 200
    try:
        assert remote.get("/api/state", key=device_key)[0] == 401
        assert app.config()["token"] != code
    finally:
        app.store.update("config", dict, lambda c: c.__setitem__("token", code))


def test_new_qr_keeps_the_computer_identity(local, app, code):
    before = app.proof_key()
    local.post("/api/config", {"new_token": True})
    try:
        assert app.proof_key() == before
    finally:
        app.store.update("config", dict, lambda c: c.__setitem__("token", code))


def test_control_characters_in_names(remote, app, code):
    req(remote, k=code, name="A\nB\x00C" + "x" * 200)
    n = app.devices.pending()[0]["name"]
    assert "\n" not in n and "\x00" not in n and len(n) <= 60
