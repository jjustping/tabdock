"""Ready-made cheat sheets for the «Справка» tab, grouped by usage scenario.

The first-run setup adds the sets that fit the chosen scenarios (photo, work, fun, admin); any set can also
be added later from the notes screen. Notes are plain Markdown the clients already render:
`- **keys** — what it does`, `code`, `- [ ] checklist`.
"""
import sys
import time
import uuid

MAC = sys.platform == "darwin"


def _n(title, tag, color, body, links=None, pinned=False):
    return {"title": title, "tag": tag, "color": color, "pinned": pinned, "body": body.strip(), "links": links or []}


SETS = {
    "macos": {
        "name": "macOS: горячие клавиши", "for": ["photo", "work", "fun", "admin"], "os": "darwin",
        "notes": [
            _n("Горячие клавиши macOS", "Mac", "blue", """
- **⇧⌘3** — снимок всего экрана, **⇧⌘4** — области, **⇧⌘5** — панель снимков и записи
- **⌘Tab** — переключить программу, **⌘ + клавиша над Tab** — окна одной программы
- **⌥⌘Esc** — принудительно завершить программу
- **⌃⌘Q** — заблокировать экран
- **⌘Пробел** — Spotlight, **⌃⌘Пробел** — эмодзи и символы
- **⌘⌥D** — показать/скрыть Dock, **⌃⌘F** — полный экран
- Finder: **⇧⌘.** — скрытые файлы, **⇧⌘G** — перейти к папке, **⌘⌥V** — переместить (после ⌘C)
""", pinned=True),
        ],
    },
    "linux": {
        "name": "Linux (Ubuntu/GNOME) и терминал", "for": ["work", "admin"], "os": "linux",
        "notes": [
            _n("Горячие клавиши Ubuntu (GNOME)", "Linux", "blue", """
- **Super** — обзор окон, **Super+A** — все приложения
- **Ctrl+Alt+T** — терминал, **Alt+F2** — выполнить команду
- **Super+L** — заблокировать экран
- **PrtSc** — снимок экрана (область, окно, весь экран, запись)
- **Super+←/→** — окно на половину экрана, **Super+↑** — развернуть
- **Super+PageUp/PageDown** — соседний рабочий стол
- **Alt+Tab** — программы, **Alt + клавиша над Tab** — окна одной программы
""", pinned=True),
            _n("Терминал: быстрее руками", "Linux", "teal", """
- **Ctrl+R** — поиск по истории команд
- **Ctrl+A / Ctrl+E** — в начало / в конец строки
- **Ctrl+U / Ctrl+K** — стереть до начала / до конца строки
- **Ctrl+W** — стереть слово, **Ctrl+L** — очистить экран
- **Ctrl+Shift+C / Ctrl+Shift+V** — копировать / вставить
- `sudo !!` — повторить прошлую команду с sudo
- `cd -` — вернуться в прошлую папку
- `!$` — последний аргумент прошлой команды
"""),
        ],
    },
    "photoshop": {
        "name": "Photoshop", "for": ["photo"],
        "notes": [
            _n("Photoshop: горячие клавиши", "Фото", "violet", """
- **B** — кисть, **[ / ]** — размер, **⇧[ / ⇧]** — жёсткость
- **J** — восстанавливающая кисть, **S** — штамп, **E** — ластик
- **⌘J** — дублировать слой, **⇧⌘N** — новый слой, **⌘G** — группа
- **⇧⌥⌘E** — «штамп»: видимое в новый слой
- **⌘T** — свободное трансформирование
- **⌘L** — уровни, **⌘M** — кривые, **⌘U** — цветовой тон/насыщенность
- **Q** — быстрая маска, **⌘D** — снять выделение, **⇧⌘I** — инвертировать выделение
- **D** — цвета по умолчанию, **X** — поменять местами
- **⌘0** — по размеру экрана, **⌘1** — 100%, **Пробел** — рука
- **Tab** — скрыть панели, **F** — режимы экрана
На Windows вместо ⌘ — Ctrl, вместо ⌥ — Alt.
"""),
        ],
    },
    "captureone": {
        "name": "Capture One", "for": ["photo"],
        "notes": [
            _n("Capture One: отбор и обработка", "Фото", "amber", """
- **0–5** — рейтинг звёздами
- **−** — красная метка, **+** — зелёная, ***** — жёлтая
- **⇧⌘C / ⇧⌘V** — скопировать / применить настройки
- **⌘D** — обработать (вывести) выбранные кадры
- **⌘Z** — отменить
Это клавиши по умолчанию; свои — Capture One → Edit Keyboard Shortcuts.
С планшета: «Съёмки» → съёмка → «Отбор и метки».
"""),
            _n("Чек-лист перед съёмкой", "Фото", "green", """
- [ ] Аккумуляторы заряжены
- [ ] Карты отформатированы
- [ ] Чистая матрица и объективы
- [ ] Свет и стойки
- [ ] Договор с клиентом
- [ ] Плейлист на съёмку
"""),
        ],
    },
    "lightroom": {
        "name": "Lightroom Classic", "for": ["photo"],
        "notes": [
            _n("Lightroom Classic: отбор", "Фото", "amber", """
- **P** — флажок «выбран», **X** — «отклонён», **U** — снять флажок
- **0–5** — звёзды, **6–9** — цвет: красный, жёлтый, зелёный, синий
- **Caps Lock** — после оценки сразу следующий кадр
- **G** — сетка, **E** — лупа, **D** — «Обработка», **R** — кадрирование
- **\\** — до/после, **Y** — сравнить до/после рядом
- **⇧⌘C / ⇧⌘V** — скопировать / вставить настройки
- **⇧⌘E** — экспорт
"""),
        ],
    },
    "sysadmin": {
        "name": "Сисадмину", "for": ["admin"],
        "notes": [
            _n("Сеть и порты", "Админ", "teal", """
- `ip -br a` — адреса интерфейсов (macOS: `ifconfig | grep inet`)
- `ss -tulpn` — кто слушает порты (macOS: `sudo lsof -i -P | grep LISTEN`)
- `lsof -i :8787` — кто занял порт
- `dig +short example.com` — во что резолвится имя
- `mtr 1.1.1.1` — где теряются пакеты
- `curl -I https://example.com` — заголовки ответа
- `nc -zv host 22` — открыт ли порт
""", pinned=True),
            _n("Службы, логи, диски", "Админ", "blue", """
- `systemctl status nginx` / `restart` / `enable --now`
- `journalctl -u nginx -f` — логи службы в реальном времени
- `journalctl -p err -b` — ошибки с последней загрузки
- `df -h` — место на дисках, `du -sh * | sort -h` — что занимает папку
- `ncdu /` — то же, но удобно
- `htop` — процессы, `iotop` — кто нагружает диск
- macOS: `log stream --predicate 'process == "TabDock"'`, `pmset -g assertions` — кто не даёт спать
"""),
            _n("Удалённая работа", "Админ", "violet", """
- `ssh-copy-id user@host` — вход по ключу без пароля
- `ssh -L 8080:localhost:80 user@host` — проброс порта к себе
- `rsync -avh --progress src/ user@host:dst/` — копирование с докачкой
- `tmux new -s work` — сессия, которая не умрёт при обрыве; `tmux a` — вернуться
- `scp file user@host:~/` — быстро закинуть файл
"""),
        ],
    },
    "dev": {
        "name": "Программисту: git и VS Code", "for": ["work"],
        "notes": [
            _n("git: на каждый день", "Код", "amber", """
- `git switch -c feature` — новая ветка и сразу на неё
- `git stash -u` / `git stash pop` — спрятать / вернуть правки
- `git log --oneline --graph -20` — история веткой
- `git commit --amend --no-edit` — дописать в прошлый коммит
- `git restore --staged file` — убрать из индекса
- `git diff --staged` — что уйдёт в коммит
- `git reflog` — спасательный круг: всё, что было, даже «потерянное»
""", pinned=True),
            _n("VS Code: горячие клавиши (Mac)", "Код", "blue", """
- **⌘P** — открыть файл по имени, **⇧⌘P** — палитра команд
- **⌘D** — выделить следующее совпадение (мультикурсор)
- **⌥↑ / ⌥↓** — переместить строку, **⇧⌥↓** — дублировать
- **⌘/** — закомментировать, **F2** — переименовать символ
- **F12** — к определению, **⌃-** — назад
- **⌃ + клавиша над Tab** — терминал, **⌘B** — боковая панель
- **⌘K Z** — дзен-режим
На Linux/Windows вместо ⌘ — Ctrl, вместо ⌥ — Alt.
"""),
        ],
    },
    "fun": {
        "name": "Рофлы для терминала", "for": ["fun", "work", "admin"],
        "notes": [
            _n("Терминал для души", "Фан", "red", """
- `sl` — паровоз за опечатку в `ls` (`brew install sl` / `sudo apt install sl`)
- `fortune | cowsay` — корова с мудростью (`cowsay`, `fortune`)
- `cmatrix` — «Матрица» в терминале
- `figlet TabDock` — большие буквы
- `asciiquarium` — аквариум
- `curl wttr.in` — погода прямо в терминале
- `curl parrot.live` — танцующий попугай (выход — Ctrl+C)
- macOS: `say "Сборка готова"` — пусть Mac скажет вслух
- `yes "я молодец"` — поддержка без остановки (Ctrl+C)
VS Code: расширения **vscode-pets** (питомец в редакторе) и **Power Mode** (искры при наборе).
"""),
        ],
    },
}

# which sets go with each first-run scenario
FOR_USAGE = {"photo": ["photoshop", "captureone", "lightroom"], "work": ["dev", "fun"], "fun": ["fun"], "admin": ["sysadmin", "linux"]}


def base_set():
    return "macos" if MAC else "linux"


def listing(notes):
    """Sets with how many of their notes are already present (matched by title)."""
    have = {n.get("title") for n in notes}
    out = []
    for sid, s in SETS.items():
        if sid == "macos" and not MAC:
            continue
        titles = [n["title"] for n in s["notes"]]
        out.append({"id": sid, "name": s["name"], "count": len(titles), "added": all(t in have for t in titles),
                    "titles": titles})
    return out


def materialize(sid):
    now = time.time()
    return [dict(n, id=uuid.uuid4().hex[:12], updated=now) for n in SETS[sid]["notes"]]


def add_sets(notes, ids):
    """Append the notes of these sets that are not there yet. Returns how many were added."""
    have = {n.get("title") for n in notes}
    added = 0
    for sid in ids:
        if sid not in SETS:
            continue
        for n in materialize(sid):
            if n["title"] not in have:
                notes.append(n)
                have.add(n["title"])
                added += 1
    return added


def for_usage(usage):
    ids = [base_set()]
    for u in usage or []:
        ids += [i for i in FOR_USAGE.get(u, []) if i not in ids]
    return ids


def default_notes():
    """A fresh install: the system's shortcuts, a links note and a how-to."""
    now = time.time()
    notes = materialize(base_set())
    notes.append({"id": uuid.uuid4().hex[:12], "title": "Полезные ссылки", "tag": "Ссылки", "color": "green", "pinned": False,
                  "body": "Свои ссылки добавляются кнопкой ✎ → «Ссылка».",
                  "links": [{"title": "Capture One — поддержка", "url": "https://support.captureone.com"},
                            {"title": "Справка Photoshop", "url": "https://helpx.adobe.com/photoshop/user-guide.html"}],
                  "updated": now})
    notes.append({"id": uuid.uuid4().hex[:12], "title": "Как пользоваться справкой", "tag": "Справка", "color": "amber",
                  "pinned": False, "updated": now, "links": [],
                  "body": "Здесь хранятся шпаргалки: горячие клавиши, команды, рецепты экспорта, чек-листы.\n\n"
                          "Формат: `- пункт`, **жирный**, `код`, `- [ ] задача` — отмечается касанием.\n\n"
                          "Готовые наборы для Photoshop, Capture One, Lightroom, Linux, сисадминов и программистов — "
                          "кнопка «Шпаргалки»."})
    return notes
