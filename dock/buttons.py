"""Custom buttons («Свои кнопки»), Stream-Deck style: each button does one thing on the computer.

Kinds:
  hotkey  — press a key combination, e.g. "cmd+shift+4", "ctrl+alt+t", "space", "f5"
  text    — type / paste a piece of text into the active window (via the clipboard + paste)
  url     — open a web address in the default browser (http/https only)
  folder  — open a folder (must exist)
  app     — open an installed app
  command — run a «Команда»: an Apple Shortcut on the Mac, or a script from ~/.config/tabdock/commands on Linux

Arbitrary shell commands are deliberately not possible: the buttons are edited from the tablet, and anyone with the
access key must not be able to run code on the computer. Scripts have to be put into the commands folder by hand.
"""
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

MAC = sys.platform == "darwin"
KINDS = ("hotkey", "text", "url", "folder", "app", "command")
ICONS = ("frame", "link", "folder", "app", "star", "play", "note", "computer", "display", "cup", "moon", "check",
         "calendar", "book", "gear", "volume", "qr", "reset", "drive", "pencil")


def clean(lst):
    """Validate the list of buttons sent by a client."""
    out = []
    for b in (lst or [])[:48]:
        if not isinstance(b, dict) or b.get("kind") not in KINDS:
            continue
        value = str(b.get("value") or "")[:2000]
        if b["kind"] == "url" and not re.match(r"^https?://", value, re.I):
            continue
        out.append({"id": str(b.get("id") or uuid.uuid4().hex[:8])[:16], "title": str(b.get("title") or "Кнопка")[:40],
                    "icon": b.get("icon") if b.get("icon") in ICONS else "star", "kind": b["kind"], "value": value,
                    "color": str(b.get("color") or "")[:9] if re.match(r"^#[0-9a-fA-F]{6}$", str(b.get("color") or "")) else ""})
    return out


# ---------------- keys ----------------
MAC_CODES = {"enter": 36, "return": 36, "tab": 48, "space": 49, "delete": 51, "backspace": 51, "esc": 53, "escape": 53,
             "left": 123, "right": 124, "down": 125, "up": 126, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
             "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109,
             "f11": 103, "f12": 111}
MAC_MODS = {"cmd": "command down", "command": "command down", "⌘": "command down", "shift": "shift down", "⇧": "shift down",
            "alt": "option down", "option": "option down", "opt": "option down", "⌥": "option down",
            "ctrl": "control down", "control": "control down", "⌃": "control down"}


# Linux input event codes (linux/input-event-codes.h) for ydotool 1.x, which takes "code:1 code:0" pairs
EV = {"ctrl": 29, "control": 29, "shift": 42, "alt": 56, "option": 56, "super": 125, "cmd": 125, "command": 125, "win": 125,
      "esc": 1, "escape": 1, "backspace": 14, "delete": 111, "tab": 15, "enter": 28, "return": 28, "space": 57,
      "home": 102, "end": 107, "pageup": 104, "pagedown": 109, "up": 103, "down": 108, "left": 105, "right": 106,
      "minus": 12, "-": 12, "equal": 13, "=": 13, "[": 26, "]": 27, ";": 39, "'": 40, "`": 41, "\\": 43, ",": 51, ".": 52, "/": 53,
      "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64, "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88}
EV.update({str(d): c for d, c in zip("1234567890", range(2, 12))})
EV.update({ch: c for row, start in (("qwertyuiop", 16), ("asdfghjkl", 30), ("zxcvbnm", 44)) for ch, c in zip(row, range(start, start + len(row)))})


def ydotool_codes(mods, key):
    codes = [EV[m] for m in mods if m in EV]
    if key not in EV:
        return None
    seq = codes + [EV[key]]
    return ["%d:1" % c for c in seq] + ["%d:0" % c for c in reversed(seq)]


def parse_combo(s):
    """'cmd+shift+4' -> (['cmd','shift'], '4')"""
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", s.strip()) if p.strip()]
    if not parts:
        return [], ""
    return parts[:-1], parts[-1]


def _osa(script):
    r = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "1002" in err or "not allowed" in err.lower() or "assistive" in err.lower():
            return False, ("macOS не разрешила TabDock нажимать клавиши: Настройки → Конфиденциальность и безопасность → "
                           "Универсальный доступ → включите TabDock")
        return False, err[:200] or "Не получилось"
    return True, ""


def press(combo):
    mods, key = parse_combo(combo)
    if not key:
        return False, "Пустое сочетание клавиш"
    if MAC:
        m = [MAC_MODS[x] for x in mods if x in MAC_MODS]
        using = (" using {%s}" % ", ".join(m)) if m else ""
        if key in MAC_CODES:
            action = "key code %d%s" % (MAC_CODES[key], using)
        elif len(key) == 1:
            action = 'keystroke "%s"%s' % (key.replace("\\", "\\\\").replace('"', '\\"'), using)
        else:
            return False, "Неизвестная клавиша «%s»" % key
        ok, msg = _osa('tell application "System Events" to ' + action)
        return ok, msg or "Нажато: " + combo
    # Linux: X11 → xdotool; Wayland → ydotool (needs its daemon) or wtype (wlroots desktops)
    xmods = {"cmd": "super", "command": "super", "super": "super", "win": "super", "ctrl": "ctrl", "control": "ctrl",
             "alt": "alt", "option": "alt", "shift": "shift"}
    xkey = {"enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape", "space": "space", "tab": "Tab",
            "delete": "Delete", "backspace": "BackSpace", "left": "Left", "right": "Right", "up": "Up", "down": "Down",
            "home": "Home", "end": "End", "pageup": "Prior", "pagedown": "Next"}.get(key, key.upper() if re.match(r"^f\d+$", key) else key)
    combo_x = "+".join([xmods.get(m, m) for m in mods] + [xkey])
    if os.environ.get("WAYLAND_DISPLAY"):
        if shutil.which("wtype"):
            args = ["wtype"]
            for m in mods:
                args += ["-M", xmods.get(m, m)]
            args += ["-k", xkey] if len(xkey) > 1 else [xkey]
            for m in reversed(mods):
                args += ["-m", xmods.get(m, m)]
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
            return (r.returncode == 0), ("Нажато: " + combo if r.returncode == 0 else r.stderr.strip()[:160])
        if shutil.which("ydotool"):
            codes = ydotool_codes(mods, key)
            if codes is None:
                return False, "Неизвестная клавиша «%s»" % key
            r = subprocess.run(["ydotool", "key"] + codes, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "failed" not in (r.stderr or "").lower():
                return True, "Нажато: " + combo
            return False, "Нажатия клавиш не включены: запустите ./install-linux.sh --keys (один раз)"
        return False, "Нажатия клавиш не включены: запустите ./install-linux.sh --keys (один раз)"
    if shutil.which("xdotool"):
        r = subprocess.run(["xdotool", "key", combo_x], capture_output=True, text=True, timeout=10)
        return (r.returncode == 0), ("Нажато: " + combo if r.returncode == 0 else r.stderr.strip()[:160])
    return False, "Нужна программа xdotool: sudo apt install xdotool"


def set_clipboard(text):
    if MAC:
        subprocess.run(["/usr/bin/pbcopy"], input=text, text=True, timeout=5)
        return True
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        if shutil.which(cmd[0]) and (cmd[0] != "wl-copy" or os.environ.get("WAYLAND_DISPLAY")):
            subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True).communicate(text.encode(), timeout=5)
            return True
    return False


def type_text(text):
    """Put the text into the clipboard and press paste in the active window."""
    if not set_clipboard(text):
        return False, "Нет программы для буфера обмена (sudo apt install wl-clipboard)"
    time.sleep(0.15)
    ok, msg = press("cmd+v" if MAC else "ctrl+v")
    return (True, "Текст вставлен") if ok else (False, msg)


def open_target(target):
    subprocess.Popen(["/usr/bin/open" if MAC else "xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def run(button, actions_mod, netcheck_mod):
    """Do what the button says. Returns (ok, message)."""
    k, v = button.get("kind"), button.get("value") or ""
    if k == "hotkey":
        return press(v)
    if k == "text":
        return type_text(v)
    if k == "url":
        if not re.match(r"^https?://", v, re.I):
            return False, "Адрес должен начинаться с http:// или https://"
        open_target(v)
        return True, "Открываю в браузере"
    if k == "folder":
        p = os.path.expanduser(v)
        if not os.path.isdir(p):
            return False, "Папки нет: %s" % v
        open_target(p)
        return True, "Открываю папку"
    if k == "app":
        if not actions_mod.find_app(v):
            return False, "Приложение «%s» не найдено" % v
        return actions_mod.Actions().run("open_app", v)
    if k == "command":
        return netcheck_mod.run_shortcut(v)
    return False, "Неизвестный тип кнопки"
