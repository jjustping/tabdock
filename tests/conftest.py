"""Two real servers on one demo App: `local` is seen as this computer, `remote` as a device on the home network."""
import http.client
import json
import os
import ssl
import sys
import threading

import pytest

os.environ.update(DOCK_NO_LANBIND="1", DOCK_NO_BONJOUR="1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dock import auth                                # noqa: E402
from dock.core import App                            # noqa: E402
from dock.httpd import DockServer, Handler           # noqa: E402


class RemoteHandler(Handler):
    LOCAL = ()          # nobody counts as "this computer"


class Client:
    def __init__(self, port, tls):
        self.port, self.tls = port, tls
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def request(self, method, path, body=None, headers=None):
        conn = (http.client.HTTPSConnection("localhost", self.port, context=self.ctx, timeout=20) if self.tls
                else http.client.HTTPConnection("localhost", self.port, timeout=20))
        h = dict(headers or {})
        if isinstance(body, dict):
            body = json.dumps(body)
            h.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        try:
            data = json.loads(raw)
        except ValueError:
            data = raw.decode("utf-8", "replace")
        return r.status, data, r

    def get(self, path, key=None, **kw):
        return self.request("GET", path, headers=dict({"X-Dock-Key": key} if key else {}, **kw))

    def post(self, path, body, key=None, **kw):
        return self.request("POST", path, body, dict({"X-Dock-Key": key} if key else {}, **kw))


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    a = App(str(tmp_path_factory.mktemp("data")), 0, demo_mode=True)
    a.devices.announce = lambda *_: None
    assert a.tls_context, "openssl is needed for the tests"
    return a


@pytest.fixture(scope="session")
def servers(app):
    Handler.app = app
    DockServer.tls_context = app.tls_context
    made = []
    for handler in (Handler, RemoteHandler):
        s = DockServer(("127.0.0.1", 0), handler)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        made.append(s)
    yield made
    for s in made:
        s.shutdown()


@pytest.fixture
def local(servers):
    return Client(servers[0].server_address[1], tls=False)


@pytest.fixture
def remote(servers):
    return Client(servers[1].server_address[1], tls=True)


@pytest.fixture
def plain_remote(servers):
    return Client(servers[1].server_address[1], tls=False)


@pytest.fixture(autouse=True)
def clean_state(app):
    auth._fail.clear()
    app.devices.clear()
    yield


@pytest.fixture
def code(app):
    return app.config()["token"]


@pytest.fixture
def device_key(app, remote, code):
    """A key of a device already allowed on the computer."""
    _, r, _ = remote.post("/api/devices/request", {"k": code, "name": "Test tablet"})
    assert app.devices.allow(r["id"])
    return r["key"]

