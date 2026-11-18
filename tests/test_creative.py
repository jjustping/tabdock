"""0.17: programs for photographers and artists (synthetic catalogs: the real programs are not on the test machines)."""
import sqlite3

from dock import buttons, captureone, frontapp, lightroom, presets


def make_lrcat(path, photos_dir):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE AgLibraryRootFolder (id_local INTEGER PRIMARY KEY, absolutePath TEXT);
    CREATE TABLE AgLibraryFolder (id_local INTEGER PRIMARY KEY, pathFromRoot TEXT, rootFolder INTEGER);
    CREATE TABLE AgLibraryFile (id_local INTEGER PRIMARY KEY, baseName TEXT, extension TEXT, folder INTEGER);
    CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY, rootFile INTEGER, rating REAL, pick REAL, colorLabels TEXT, captureTime TEXT);
    CREATE TABLE AgLibraryCollection (id_local INTEGER PRIMARY KEY, name TEXT, creationId TEXT, parent INTEGER);
    CREATE TABLE AgLibraryCollectionImage (id_local INTEGER PRIMARY KEY, collection INTEGER, image INTEGER);
    """)
    con.execute("INSERT INTO AgLibraryRootFolder VALUES (1, ?)", (str(photos_dir) + "/",))
    con.execute("INSERT INTO AgLibraryFolder VALUES (1, 'wedding/', 1)")
    rows = [(1, 5, 1, "Green", "2026-11-01T12:00:00"), (2, 4, 1, "", "2026-11-01T13:00:00"),
            (3, 0, -1, "Red", "2026-11-01T14:00:00"), (4, 5, 0, "Green", "2026-11-02T10:00:00")]
    for i, rating, pick, label, t in rows:
        con.execute("INSERT INTO AgLibraryFile VALUES (?, ?, 'jpg', 1)", (i, "IMG_%d" % i))
        con.execute("INSERT INTO Adobe_images VALUES (?, ?, ?, ?, ?, ?)", (i, i, rating, pick, label, t))
    con.execute("INSERT INTO AgLibraryCollection VALUES (10, 'Свадьба', 'com.adobe.ag.library.collection', NULL)")
    con.execute("INSERT INTO AgLibraryCollection VALUES (11, 'Умная', 'com.adobe.ag.library.smart_collection', NULL)")
    for n, img in enumerate([1, 2, 3, 4]):
        con.execute("INSERT INTO AgLibraryCollectionImage VALUES (?, 10, ?)", (n + 1, img))
    con.commit()
    con.close()


def test_lightroom_collections(tmp_path):
    photos = tmp_path / "Photos"
    (photos / "wedding").mkdir(parents=True)
    (photos / "wedding" / "IMG_1.jpg").write_bytes(b"x")
    cat = tmp_path / "Lightroom Catalog.lrcat"
    make_lrcat(str(cat), photos)
    shoots = lightroom.read_catalog(str(cat))
    assert [s["name"] for s in shoots] == ["Свадьба"]           # smart collections are not shoots
    s = shoots[0]
    assert s["total"] == 4 and s["picked"] == 2 and s["rejected"] == 1
    assert s["colors"] == {"4": 2, "1": 1} and s["ratings"] == {"5": 2, "4": 1}
    assert s["cover_file"].endswith("IMG_1.jpg") and s["source"] == "lr"
    d = captureone.derive(s, {}, {"type": "color", "color": 4})
    assert d["done"] == 2 and d["target"] == 2                 # target = picks, done = green labels


def test_catalog_is_never_written(tmp_path):
    cat = tmp_path / "c.lrcat"
    make_lrcat(str(cat), tmp_path)
    before = cat.read_bytes()
    lightroom.read_catalog(str(cat))
    assert cat.read_bytes() == before


def test_presets_use_the_systems_main_modifier():
    ps = {p["id"]: p for p in presets.PRESETS}
    assert any(b["value"] == "mod+z" for b in ps["photoshop"]["buttons"])
    mods, key = buttons.parse_combo("mod+shift+z")
    assert key == "z" and mods[0] in ("cmd", "ctrl") and mods[1] == "shift"
    added = presets.buttons_for("photoshop", lambda: "x")
    assert added and all(b["apps"] == ["Photoshop", "Photon Studio", "Affinity"] for b in added)
    assert len(buttons.clean(added)) == len(added)              # every ready-made button passes the checks


def test_buttons_follow_the_program_in_front():
    b = {"apps": ["Photoshop", "Photon Studio"]}
    assert presets.matches(b, "Adobe Photoshop 2026") and presets.matches(b, "Photon Studio")
    assert not presets.matches(b, "Firefox") and not presets.matches(b, None)
    assert presets.matches({"apps": []}, "Firefox")             # own buttons without programs are always there


def test_friendly_program_names():
    assert frontapp.friendly("Photoshop.exe") == "Adobe Photoshop"
    assert frontapp.friendly("krita") == "Krita"
    assert frontapp.friendly("CLIPStudioPaint.exe") == "Clip Studio Paint"
    assert frontapp.friendly("Notepad.exe") == "Notepad"


def test_add_a_program_set_through_the_api(remote, device_key, app):
    st, d, _ = remote.get("/api/all", key=device_key)
    assert st == 200 and any(p["id"] == "krita" for p in d["presets"])
    assert "front_app" in d["state"]
    st, d, _ = remote.post("/api/config", {"add_preset": "krita"}, key=device_key)
    mine = [b for b in d["config"]["buttons"] if b.get("apps") == ["Krita"]]
    assert st == 200 and len(mine) == len(presets.PRESETS[3]["buttons"])
    st, d, _ = remote.post("/api/config", {"add_preset": "nope"}, key=device_key)
    assert st == 200 and len([b for b in d["config"]["buttons"] if b.get("apps") == ["Krita"]]) == len(mine)
    app.store.update("config", dict, lambda c: c.pop("buttons", None))


def test_recent_works(tmp_path, monkeypatch):
    from dock import recent
    monkeypatch.setattr(recent.sys, "platform", "linux")
    monkeypatch.setattr(recent, "_home", lambda: str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    work = tmp_path / "Работы"
    work.mkdir()
    for n in ("портрет.psd", "скетч.kra", "отчёт.pdf", "фото.tif"):
        (work / n).write_bytes(b"x")
    ps = tmp_path / ".config" / "Photon Studio"
    ps.mkdir(parents=True)
    import json
    (ps / "preferences.json").write_text(json.dumps({"recentFiles": [str(work / "фото.tif"), str(work / "нет-такого.psd")]}),
                                         encoding="utf-8")
    xbel = tmp_path / ".local" / "share"
    xbel.mkdir(parents=True)
    (xbel / "recently-used.xbel").write_text(
        '<?xml version="1.0"?><xbel version="1.0" xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks">'
        + "".join('<bookmark href="%s" visited="2026-11-1%dT10:00:00Z"><info><metadata><bookmark:applications>'
                  '<bookmark:application name="%s"/></bookmark:applications></metadata></info></bookmark>'
                  % ((work / n).as_uri(), i, a) for i, (n, a) in enumerate([("портрет.psd", "GIMP"), ("скетч.kra", "Krita"),
                                                                               ("отчёт.pdf", "Evince")]))
        + "</xbel>", encoding="utf-8")
    items = recent.collect()
    names = [i["name"] for i in items]
    assert "отчёт.pdf" not in names and "нет-такого.psd" not in names     # only work files that still exist
    assert names[0] == "фото.tif" and items[0]["app"] == "Photon Studio"    # Photon's list was written just now
    assert names[1:] == ["скетч.kra", "портрет.psd"] and items[1]["app"] == "Krita" and items[1]["folder"] == "Работы"
    r = recent.Recent(enabled=lambda: False)
    r.items = items
    assert r.allowed(items[0]["path"]) and not r.allowed("/etc/passwd")


def test_open_recent_only_from_the_list(remote, device_key, app):
    st, d, _ = remote.post("/api/action", {"action": "open_recent", "arg": "/etc/passwd"}, key=device_key)
    assert d["ok"] is False


def test_reference_board(tmp_path):
    from dock import refs
    root = tmp_path / "Референсы"
    (root / "Позы").mkdir(parents=True)
    (root / "Позы" / "поза1.jpg").write_bytes(b"x")
    (root / "свет.png").write_bytes(b"x")
    (root / "заметки.txt").write_text("не картинка", encoding="utf-8")
    (tmp_path / "секрет.jpg").write_bytes(b"x")
    d = refs.listing(str(root))
    assert sorted(i["rel"] for i in d["items"]) == ["Позы/поза1.jpg", "свет.png"]
    assert d["boards"] == [{"name": "Позы", "count": 1}]
    assert refs.resolve(str(root), "Позы/поза1.jpg")
    for bad in ("../секрет.jpg", "заметки.txt", "/etc/passwd", "", "Позы/../../секрет.jpg"):
        assert refs.resolve(str(root), bad) is None
    assert refs.listing(str(tmp_path / "нет"))["exists"] is False


def test_copy_color_checks_the_value(remote, device_key):
    st, d, _ = remote.post("/api/action", {"action": "copy_color", "arg": "; rm -rf /"}, key=device_key)
    assert d["ok"] is False


def make_darktable(cfg, photos):
    lib = cfg / "library.db"
    con = sqlite3.connect(str(lib))
    con.executescript("""
    CREATE TABLE film_rolls (id INTEGER PRIMARY KEY, access_timestamp INTEGER, folder VARCHAR(1024));
    CREATE TABLE images (id INTEGER PRIMARY KEY, film_id INTEGER, filename VARCHAR, flags INTEGER, datetime_taken INTEGER);
    CREATE TABLE color_labels (imgid INTEGER, color INTEGER);
    CREATE TABLE tagged_images (imgid INTEGER, tagid INTEGER, position INTEGER);
    """)
    con.execute("INSERT INTO film_rolls VALUES (1, 0, ?)", (str(photos),))
    t = (1793836800 + 62135596800) * 10 ** 6            # 2026-11-05 as darktable stores it
    for i, flags in enumerate([5, 4 | 0, 1 | 8, 6, 1], start=1):   # ★5, ★4, rejected (new flag), rejected (old ★6), ★1
        con.execute("INSERT INTO images VALUES (?, 1, ?, ?, ?)", (i, "DSC_%d.NEF" % i, flags, t + i * 10 ** 6))
    con.executemany("INSERT INTO color_labels VALUES (?, ?)", [(1, 2), (2, 2), (3, 0)])
    con.executemany("INSERT INTO tagged_images VALUES (?, 7, 0)", [(1,), (2,), (5,)])
    con.commit()
    con.close()
    data = sqlite3.connect(str(cfg / "data.db"))
    data.executescript("CREATE TABLE tags (id INTEGER PRIMARY KEY, name VARCHAR); INSERT INTO tags VALUES (7, 'darktable|exported');")
    data.commit()
    data.close()
    return lib


def test_darktable_film_rolls(tmp_path):
    from dock import darktable
    photos = tmp_path / "2026-11-05 Прогулка"
    photos.mkdir()
    (photos / "DSC_1.NEF").write_bytes(b"x")
    lib = make_darktable(tmp_path, photos)
    before = lib.read_bytes()
    [s] = darktable.read_library(str(lib))
    assert lib.read_bytes() == before                                   # never written
    assert s["name"] == "2026-11-05 Прогулка" and s["source"] == "dt"
    assert s["total"] == 5 and s["rejected"] == 2 and s["picked"] == 3
    assert s["ratings"] == {"5": 1, "4": 1, "1": 1} and s["colors"] == {"4": 2, "1": 1} and s["exported"] == 3
    assert s["cover_file"].endswith("DSC_1.NEF") and abs(s["shot_from"] - 1793836801) < 2
    assert captureone.derive(s, {}, {"type": "color", "color": 4})["done"] == 2
    assert captureone.derive(dict(s), {}, {"type": "export"})["done"] == 3
