#!/usr/bin/env python3
"""TabDock — local touch dashboard for a computer, served to a tablet or phone over the home network.

Run:  .venv/bin/python server.py [--port 8787] [--data DIR]
Open: http://localhost:8787 on the computer, then scan the QR code with the tablet.

The code lives in dock/: core.py (the application), httpd.py (HTTP layer), the rest are features.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dock import auth, lanbind                        # noqa: E402
from dock.core import App, bonjour                    # noqa: E402
from dock.httpd import DockServer, Handler            # noqa: E402
from dock.store import Store, default_config          # noqa: E402
from dock.version import VERSION                      # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="TabDock server")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DOCK_PORT", 8787)))
    ap.add_argument("--data", default=os.environ.get("DOCK_DATA", os.path.join(HERE, "data")))
    ap.add_argument("--print-url", action="store_true", help="print the tablet URL and exit")
    ap.add_argument("--demo", action="store_true", help="synthetic shoots/calendar for screenshots (no real catalog)")
    ap.add_argument("--set-password", action="store_true", help="set the tablet login password and exit")
    a = ap.parse_args()
    if a.set_password:
        import getpass
        st = Store(os.path.abspath(a.data))
        pw = getpass.getpass("Новый пароль для планшета: ")
        if len(pw) < 4 or pw != getpass.getpass("Ещё раз: "):
            sys.exit("Пароли не совпадают или короче 4 символов")
        h = auth.hash_password(pw)
        st.update("config", default_config, lambda c: c.__setitem__("password_hash", h))
        print("Пароль сохранён. Перезапустите службу, если она работает.")
        return
    app = App(os.path.abspath(a.data), a.port, demo_mode=a.demo)
    if a.print_url:
        print(app.url())
        return
    Handler.app = app
    DockServer.tls_context = app.tls_context
    srv = DockServer(("0.0.0.0", a.port), Handler)
    # replies to the tablet/phone go straight through Wi-Fi/Ethernet even when a VPN is on
    if not os.environ.get("DOCK_NO_LANBIND"):
        lanbind.LanBinder(lambda ip, port, idx: DockServer((ip, port), Handler, idx), a.port).start()
    if not os.environ.get("DOCK_NO_BONJOUR"):
        bonjour.advertise(a.port, VERSION)
    print("TabDock %s on http://localhost:%d  (devices: https, port %d)" % (VERSION, a.port, a.port), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
