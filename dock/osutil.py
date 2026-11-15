"""Small things every platform does its own way: open a file / folder / link, show a file in its folder,
a notification on this computer."""
import os
import subprocess
import sys
import threading

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
NO_WINDOW = 0x08000000 if WIN else 0


def open_path(target):
    """Open a file, folder or link with the default program."""
    if WIN:
        from .windows.actions import start
        start(target)
    else:
        subprocess.Popen(["/usr/bin/open" if MAC else "xdg-open", target], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def open_with(app, target):
    """Open target in a given program (macOS: by name; elsewhere the default program)."""
    if MAC:
        subprocess.Popen(["/usr/bin/open", "-a", app, target])
    else:
        open_path(target)


def reveal(path):
    """Show a file selected in its folder."""
    if MAC:
        subprocess.Popen(["/usr/bin/open", "-R", path])
    elif WIN:
        subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(path)])
    else:
        open_path(os.path.dirname(path))


NOTIFY_MAC = 'on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run'
NOTIFY_WIN = r"""$t=$env:TD_TITLE;$m=$env:TD_TEXT
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null
$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$n=$x.GetElementsByTagName('text');$n.Item(0).AppendChild($x.CreateTextNode($t))|Out-Null;$n.Item(1).AppendChild($x.CreateTextNode($m))|Out-Null
$app='{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($x))"""


def notify(title, text):
    """Best effort, never blocks a request."""
    def run():
        try:
            if MAC:
                subprocess.run(["/usr/bin/osascript", "-e", NOTIFY_MAC, title, text], capture_output=True, timeout=10)
            elif WIN:
                subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", NOTIFY_WIN],
                               env=dict(os.environ, TD_TITLE=title, TD_TEXT=text),
                               capture_output=True, timeout=20, creationflags=NO_WINDOW)
            else:
                subprocess.run(["notify-send", "-a", "TabDock", title, text], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
    threading.Thread(target=run, daemon=True).start()


def make_jpeg(src, out, size, rotate=0):
    """Resized JPEG copy: sips on macOS, Pillow elsewhere. rotate: degrees clockwise. True if out was written."""
    if MAC:
        cmd = ["/usr/bin/sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", str(size)]
        if rotate:
            cmd += ["-r", str(rotate)]
        subprocess.run(cmd + [src, "--out", out], capture_output=True, timeout=90)
        return os.path.exists(out)
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return False
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im) if not rotate else im.rotate(-rotate, expand=True)
            im.thumbnail((size, size))
            im.convert("RGB").save(out, "JPEG", quality=82)
        return True
    except (OSError, ValueError):
        return False
