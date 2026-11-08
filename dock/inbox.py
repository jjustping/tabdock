"""Phone → computer: files and photos land in ~/Downloads/TabDock, links open in the browser, text goes to the clipboard."""
import os
import re
import subprocess
import sys
import time

from . import buttons

MAX_FILE = 2 * 1024 ** 3        # 2 GB per file
INBOX = os.path.expanduser("~/Downloads/TabDock")


def safe_name(name):
    name = os.path.basename(str(name or "")).strip().replace("\x00", "")
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)[:180].lstrip(".") or time.strftime("файл %Y-%m-%d %H-%M-%S")
    return name


def unique_path(name):
    os.makedirs(INBOX, exist_ok=True)
    base, ext = os.path.splitext(name)
    p, i = os.path.join(INBOX, name), 2
    while os.path.exists(p):
        p = os.path.join(INBOX, "%s (%d)%s" % (base, i, ext))
        i += 1
    return p


def receive_file(rfile, length, name):
    """Stream the request body into the inbox. Returns (ok, message, path)."""
    if length <= 0:
        return False, "Пустой файл", None
    if length > MAX_FILE:
        return False, "Файл больше 2 ГБ", None
    path = unique_path(safe_name(name))
    tmp = path + ".part"
    left = length
    try:
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = rfile.read(min(1024 * 1024, left))
                if not chunk:
                    raise IOError("соединение прервалось")
                f.write(chunk)
                left -= len(chunk)
        os.replace(tmp, path)
    except Exception as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False, "Не получилось сохранить: %s" % str(e)[:120], None
    return True, "Сохранено в «Загрузки → TabDock»", path


def receive(kind, value):
    """Links and text (JSON). Returns (ok, message)."""
    value = str(value or "")[:100000]
    if kind == "link":
        m = re.search(r"https?://\S+", value)
        if not m:
            return False, "В сообщении нет ссылки"
        buttons.open_target(m.group(0))
        return True, "Ссылка открыта на компьютере"
    if kind == "text":
        if not value.strip():
            return False, "Пустой текст"
        return (True, "Текст в буфере обмена компьютера — вставьте его") if buttons.set_clipboard(value) else \
            (False, "Нет программы для буфера обмена (Linux: sudo apt install wl-clipboard)")
    return False, "Неизвестный тип"


def reveal(path):
    """Show the received file in Finder / the file manager."""
    if sys.platform == "darwin":
        subprocess.Popen(["/usr/bin/open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def recent(limit=12):
    """Latest files that arrived from phones (for the transfer window)."""
    try:
        names = [n for n in os.listdir(INBOX) if not n.startswith(".") and not n.endswith(".part")]
    except OSError:
        return []
    items = []
    for n in names:
        try:
            st = os.stat(os.path.join(INBOX, n))
        except OSError:
            continue
        items.append({"name": n, "size": st.st_size, "at": st.st_mtime})
    return sorted(items, key=lambda x: -x["at"])[:limit]


def reveal_dir():
    os.makedirs(INBOX, exist_ok=True)
    subprocess.Popen(["/usr/bin/open" if sys.platform == "darwin" else "xdg-open", INBOX],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
