"""Windows: keeps TabDock running in the user's session. Started by Task Scheduler at log on (install-windows.ps1).

Starts the server and the tray icon, restarts the server after an update (exit code 3) or a crash, stops on exit
code 0. Only one copy runs at a time.
"""
import ctypes
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# run as a script, Python puts this folder first on the path; its module names must not hide the standard library's
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(os.path.abspath(__file__))]
sys.path.insert(0, HERE)
from dock.windows import NO_WINDOW, appdata, kill_tree  # noqa: E402


def main():
    if ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\TabDockRunner") and ctypes.GetLastError() == 183:
        return                                       # ERROR_ALREADY_EXISTS: TabDock is already running
    args = sys.argv[1:]
    port = args[args.index("--port") + 1] if "--port" in args else "8787"
    py = sys.executable                              # pythonw.exe from the venv: no console windows
    os.makedirs(appdata("logs"), exist_ok=True)
    log = open(appdata("logs", "tabdock.log"), "a", buffering=1, encoding="utf-8")
    tray, delay = None, 2
    env = dict(os.environ, TABDOCK_RUNNER=str(os.getpid()))   # server and tray quit when this process is gone
    while True:
        if tray is None or tray.poll() is not None:
            tray = subprocess.Popen([py, os.path.join(HERE, "dock", "windows", "tray.py"), port], cwd=HERE,
                                    stdout=log, stderr=log, creationflags=NO_WINDOW, env=env)
        started = time.time()
        srv = subprocess.Popen([py, os.path.join(HERE, "server.py")] + args, cwd=HERE, stdout=log, stderr=log,
                               creationflags=NO_WINDOW, env=env)
        with open(appdata("run.json"), "w") as f:
            json.dump({"runner": os.getpid(), "server": srv.pid, "tray": tray.pid, "port": port}, f)
        code = srv.wait()
        log.write("TabDock: server exited with code %s\n" % code)
        if code == 0:                                # stopped on purpose
            break
        if code == 3 and tray.poll() is None:        # updated: the tray may have new code too
            kill_tree(tray.pid)
            tray = None
        delay = 2 if time.time() - started > 60 else min(delay * 2, 60)     # back off if it keeps crashing
        time.sleep(delay)
    if tray and tray.poll() is None:
        kill_tree(tray.pid)


if __name__ == "__main__":
    main()
