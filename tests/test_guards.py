from types import SimpleNamespace

import pytest

from dock.httpd import Handler


@pytest.mark.parametrize("ip,ok", [("192.168.1.5", True), ("10.0.0.2", True), ("172.16.3.1", True), ("127.0.0.1", True),
                                   ("169.254.1.1", True), ("::ffff:192.168.1.5", True), ("8.8.8.8", False),
                                   ("1.1.1.1", False), ("::ffff:8.8.8.8", False), ("garbage", False)])
def test_only_private_networks(ip, ok):
    assert Handler._client_allowed(SimpleNamespace(client_address=(ip, 1))) is ok


def test_plain_http_from_a_device_goes_to_https(plain_remote):
    st, _, r = plain_remote.get("/api/state")
    assert st == 301 and r.getheader("Location").startswith("https://")
    st, _, _ = plain_remote.post("/api/action", {"action": "x"})
    assert st == 403


def test_this_computer_may_use_plain_http(local):
    assert local.get("/api/tray")[0] == 200


def test_hello_is_open_and_shows_the_certificate(remote, app):
    st, d, _ = remote.get("/api/hello?nonce=abc")
    assert st == 200 and d["app"] == "tabdock" and d["fp"] == app.cert_fp and d["proof"]
    assert "token" not in d


def test_bad_host_is_refused(remote):
    assert remote.get("/api/hello", Host="evil.example.com")[0] == 421


@pytest.mark.parametrize("path", ["/api/all", "/api/state", "/api/shoots", "/api/pin", "/api/update"])
def test_no_key_no_data(remote, path):
    assert remote.get(path)[0] == 401


def test_wrong_key(remote):
    assert remote.get("/api/all", key="nope")[0] == 401


def test_pairing_code_is_not_an_access_key(remote, code):
    assert remote.get("/api/all", key=code)[0] == 401
    assert remote.get("/api/all?k=" + code)[0] == 401


def test_cross_site_post_is_blocked(remote, device_key):
    st, _, _ = remote.post("/api/action", {"action": "x"}, key=device_key, Origin="https://evil.example.com")
    assert st == 403


def test_post_must_be_json(remote, device_key):
    st, _, _ = remote.request("POST", "/api/action", "a=b", {"X-Dock-Key": device_key, "Content-Type": "text/plain"})
    assert st == 403


@pytest.mark.parametrize("path", ["/api/tray", "/api/devices", "/api/transfer", "/transfer"])
def test_computer_only_pages(remote, device_key, path):
    assert remote.get(path, key=device_key)[0] == 403


def test_device_cannot_send_to_outbox(remote, device_key):
    st, _, _ = remote.request("PUT", "/api/outbox/file?name=a.txt", "x", {"X-Dock-Key": device_key})
    assert st == 403


def test_device_cannot_change_password_or_devices(remote, device_key):
    assert remote.post("/api/password", {"password": "abcd"}, key=device_key)[0] == 403
    assert remote.post("/api/devices", {"op": "allow", "id": "x"}, key=device_key)[0] == 403
    assert remote.post("/api/config", {"new_token": True}, key=device_key)[0] == 403


def test_secrets_never_leave(remote, device_key):
    st, d, _ = remote.get("/api/all", key=device_key)
    assert st == 200
    for k in ("token", "identity_key", "password_hash"):
        assert k not in d["config"]
