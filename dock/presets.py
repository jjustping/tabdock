"""Ready-made sets of «Свои кнопки» for creative programs. Adding a set copies its buttons into the user's own list,
each marked with the programs it belongs to: with «по активной программе» on, the widget shows only the buttons of
the program in front. «mod» is ⌘ on a Mac and Ctrl on Windows and Linux. Default shortcuts of each program."""


def _b(title, value, icon="star"):
    return {"title": title, "kind": "hotkey", "value": value, "icon": icon}


PRESETS = [
    {"id": "photoshop", "name": "Photoshop · Photon Studio · Affinity", "apps": ["Photoshop", "Photon Studio", "Affinity"],
     "buttons": [_b("Отменить", "mod+z", "reset"), _b("Повторить", "mod+shift+z", "reset"), _b("Кисть", "b", "pencil"),
                 _b("Ластик", "e", "pencil"), _b("Кисть −", "[", "pencil"), _b("Кисть +", "]", "pencil"),
                 _b("Пипетка", "i", "drop"), _b("Рука", "h", "frame"), _b("Трансформация", "mod+t", "frame"),
                 _b("Новый слой", "mod+shift+n", "plus"), _b("Объединить", "mod+e", "archive"),
                 _b("Уровни", "mod+l", "sun"), _b("Кривые", "mod+m", "sun"), _b("По экрану", "mod+0", "expand"),
                 _b("Цвета ⇄", "x", "drop"), _b("Снять выделение", "mod+d", "check"), _b("Сохранить", "mod+s", "check")]},
    {"id": "lightroom", "name": "Lightroom Classic", "apps": ["Lightroom"],
     "buttons": [_b("Отметить", "p", "check"), _b("Отклонить", "x", "reset"), _b("Снять флажок", "u", "reset"),
                 _b("★0", "0", "star"), _b("★1", "1", "star"), _b("★2", "2", "star"), _b("★3", "3", "star"),
                 _b("★4", "4", "star"), _b("★5", "5", "star"), _b("Красный", "6", "drop"), _b("Жёлтый", "7", "drop"),
                 _b("Зелёный", "8", "drop"), _b("Синий", "9", "drop"), _b("Назад", "left", "prev"),
                 _b("Вперёд", "right", "next"), _b("Библиотека", "g", "frame"), _b("Обработка", "d", "sun"),
                 _b("До / после", "\\", "display"), _b("Экспорт", "mod+shift+e", "archive"), _b("Отменить", "mod+z", "reset")]},
    {"id": "captureone", "name": "Capture One", "apps": ["Capture One"],
     "buttons": [_b("★0", "0", "star"), _b("★1", "1", "star"), _b("★2", "2", "star"), _b("★3", "3", "star"),
                 _b("★4", "4", "star"), _b("★5", "5", "star"), _b("Назад", "left", "prev"), _b("Вперёд", "right", "next"),
                 _b("Отменить", "mod+z", "reset"), _b("Повторить", "mod+shift+z", "reset")]},
    {"id": "krita", "name": "Krita", "apps": ["Krita"],
     "buttons": [_b("Кисть", "b", "pencil"), _b("Ластик", "e", "pencil"), _b("Кисть −", "[", "pencil"),
                 _b("Кисть +", "]", "pencil"), _b("Отменить", "mod+z", "reset"), _b("Повторить", "mod+shift+z", "reset"),
                 _b("Отразить холст", "m", "frame"), _b("Повернуть ↺", "4", "reset"), _b("Повернуть ↻", "6", "reset"),
                 _b("Сбросить поворот", "5", "frame"), _b("100 %", "1", "expand"), _b("По экрану", "2", "expand")]},
    {"id": "clipstudio", "name": "Clip Studio Paint", "apps": ["Clip Studio"],
     "buttons": [_b("Кисть", "b", "pencil"), _b("Ластик", "e", "pencil"), _b("Кисть −", "[", "pencil"),
                 _b("Кисть +", "]", "pencil"), _b("Пипетка", "i", "drop"), _b("Отменить", "mod+z", "reset"),
                 _b("Повторить", "mod+y", "reset"), _b("Новый слой", "mod+shift+n", "plus"), _b("По экрану", "mod+0", "expand")]},
    {"id": "darktable", "name": "darktable", "apps": ["darktable"],
     "buttons": [_b("★0", "0", "star"), _b("★1", "1", "star"), _b("★2", "2", "star"), _b("★3", "3", "star"),
                 _b("★4", "4", "star"), _b("★5", "5", "star"), _b("Отклонить", "r", "reset"), _b("Красный", "f1", "drop"),
                 _b("Жёлтый", "f2", "drop"), _b("Зелёный", "f3", "drop"), _b("Синий", "f4", "drop"),
                 _b("Назад", "backspace", "prev"), _b("Вперёд", "space", "next"), _b("Световой стол", "l", "frame"),
                 _b("Тёмная комната", "d", "sun"), _b("Экспорт", "mod+e", "archive")]},
]


def listing():
    return [{"id": p["id"], "name": p["name"], "apps": p["apps"], "count": len(p["buttons"])} for p in PRESETS]


def buttons_for(pid, make_id):
    """The preset's buttons, ready to be added to the user's list (each with its programs)."""
    p = next((x for x in PRESETS if x["id"] == pid), None)
    if not p:
        return []
    return [dict(b, id=make_id(), apps=list(p["apps"])) for b in p["buttons"]]


def matches(button, app):
    """A button without programs is always shown; otherwise only while one of its programs is in front."""
    apps = button.get("apps") or []
    if not apps:
        return True
    a = (app or "").lower()
    return bool(a) and any(x.lower() in a for x in apps)
