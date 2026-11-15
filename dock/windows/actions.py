"""Quick actions on Windows: launch programs (Start-menu shortcuts), open folders, sleep, turn the screen off,
screenshot, keep awake, eject drives."""
import ctypes
import glob
import hashlib
import os
import threading
import time

from . import ps

START_DIRS = [os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
              os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")]
# system tools that have no Start-menu shortcut of their own, named in the language of Windows
BUILTIN_RU = {"Проводник": "explorer.exe", "Параметры": "ms-settings:", "Диспетчер задач": "taskmgr.exe", "Терминал": "wt.exe",
              "Блокнот": "notepad.exe", "Калькулятор": "calc.exe"}
BUILTIN_EN = {"File Explorer": "explorer.exe", "Settings": "ms-settings:", "Task Manager": "taskmgr.exe", "Terminal": "wt.exe",
              "Notepad": "notepad.exe", "Calculator": "calc.exe"}


def _builtin():
    try:
        russian = (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x19
    except (AttributeError, OSError):
        russian = False
    return BUILTIN_RU if russian else BUILTIN_EN
_cache = {"at": 0, "apps": {}}
SKIP = ("uninstall", "удал", "readme", "help", "справка", "documentation", "website", "release notes")


def _apps():
    if time.time() - _cache["at"] > 120:
        apps = {}
        for d in START_DIRS:
            for f in glob.glob(os.path.join(d, "**", "*.lnk"), recursive=True):
                name = os.path.splitext(os.path.basename(f))[0]
                # «… (Mac)»: Parallels puts the Mac's own apps into the Start menu
                if name and name not in apps and not any(s in name.lower() for s in SKIP) and not name.endswith(" (Mac)"):
                    apps[name] = f
        for name, target in _builtin().items():
            apps.setdefault(name, target)
        _cache.update(at=time.time(), apps=apps)
    return _cache["apps"]


def find_app(name):
    return _apps().get(name)


def installed_apps():
    return sorted(_apps(), key=str.lower)


def app_icon(name, cache_dir):
    """PNG icon from the program the shortcut points to (System.Drawing in PowerShell), cached on disk."""
    src = find_app(name)
    if not src:
        return None
    out = os.path.join(cache_dir, "icons", hashlib.md5(src.encode()).hexdigest() + ".png")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    target = src
    if src.lower().endswith(".lnk"):
        target = ps("(New-Object -ComObject WScript.Shell).CreateShortcut('%s').TargetPath" % src.replace("'", "''")).strip() or src
    elif not os.path.isabs(src):
        target = ps("(Get-Command '%s' -ErrorAction SilentlyContinue).Source" % src.replace("'", "''")).strip()
    if not target or not os.path.exists(target):
        return None
    ps("Add-Type -AssemblyName System.Drawing;$i=[Drawing.Icon]::ExtractAssociatedIcon('%s');"
       "$b=$i.ToBitmap();$b.Save('%s',[Drawing.Imaging.ImageFormat]::Png)" % (target.replace("'", "''"), out.replace("'", "''")))
    return out if os.path.exists(out) else None


SHOT = r"""Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class TdDpi { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[TdDpi]::SetProcessDPIAware() | Out-Null
$b=[Windows.Forms.SystemInformation]::VirtualScreen
$bmp=New-Object Drawing.Bitmap $b.Width,$b.Height
$g=[Drawing.Graphics]::FromImage($bmp);$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size)
$bmp.Save('%s',[Drawing.Imaging.ImageFormat]::Png)"""

EJECT = "(New-Object -ComObject Shell.Application).Namespace(17).ParseName('%s').InvokeVerb('Eject')"


def bring_forward():
    """Windows lets only the process that got the last input bring a window to the front. TabDock runs in the
    background, so before opening something it sends a key nobody uses (F24): the new window then opens on top."""
    u = ctypes.windll.user32
    u.keybd_event(0x87, 0, 0, 0)
    u.keybd_event(0x87, 0, 2, 0)
    u.AllowSetForegroundWindow(-1)        # ASFW_ANY: the program we start may take the front


def start(target):
    bring_forward()
    os.startfile(target)


class Actions:
    ES_CONTINUOUS, ES_SYSTEM, ES_DISPLAY = 0x80000000, 0x1, 0x2

    def __init__(self):
        self._awake = None          # Event that keeps the «stay awake» thread alive

    @property
    def awake(self):
        return self._awake is not None

    def _keep_awake(self, stop):
        # the request belongs to the thread that made it, so a thread holds it until «stop» is set
        k32 = ctypes.windll.kernel32
        k32.SetThreadExecutionState(self.ES_CONTINUOUS | self.ES_SYSTEM | self.ES_DISPLAY)
        stop.wait()
        k32.SetThreadExecutionState(self.ES_CONTINUOUS)

    def run(self, action, arg=None):
        if action == "open_app":
            target = find_app(arg or "")
            if not target:
                return False, "Программа не найдена"
            start(target)
            return True, "Открываю %s" % arg
        if action == "open_path":
            start(os.path.expanduser(arg or "~"))
            return True, "Открыто"
        if action == "sleep":
            # SetSuspendState(hibernate=False, force=False, wakeup=False); with hibernation turned on Windows may hibernate
            threading.Timer(1.0, lambda: ctypes.windll.powrprof.SetSuspendState(0, 0, 0)).start()
            return True, "Компьютер засыпает"
        if action == "display_sleep":
            # WM_SYSCOMMAND / SC_MONITORPOWER / 2 = off, posted so a hung window cannot block the request
            ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)
            return True, "Экран выключен"
        if action == "screenshot":
            d = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
            os.makedirs(d, exist_ok=True)
            fn = os.path.join(d, time.strftime("Снимок экрана %Y-%m-%d %H-%M-%S.png"))
            ps(SHOT % fn.replace("'", "''"), timeout=30)
            if os.path.exists(fn):
                return True, "Скриншот в «Изображения → Screenshots»"
            return False, "Не получилось сделать скриншот (сервер должен работать в вашем сеансе Windows)"
        if action == "awake":
            if self._awake:
                self._awake.set()
                self._awake = None
                return True, "Компьютер снова может засыпать"
            self._awake = threading.Event()
            threading.Thread(target=self._keep_awake, args=(self._awake,), daemon=True).start()
            return True, "Компьютер не будет засыпать"
        if action == "eject":
            root = (arg or "")[:3]
            if len(root) < 2 or root[1] != ":":
                return False, "Диск не найден"
            ps(EJECT % root[:2], timeout=30)
            time.sleep(1.5)
            if not os.path.exists(root):
                return True, "Диск извлечён"
            return False, "Windows не дала извлечь диск: возможно, он занят"
        return False, "Неизвестное действие"
