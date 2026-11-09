import pytest

from dock import buttons, captureone, demo


def shoot(**kw):
    return dict({"source": "c1", "total": 100, "picked": 40, "exported": 10, "colors": {"4": 25}, "ratings": {"5": 5}}, **kw)


def test_progress_from_exports():
    s = captureone.derive(shoot(), {}, {"type": "export"})
    assert s["target"] == 40 and s["done"] == 10 and s["progress"] == 0.25 and s["status"] == "editing"


def test_green_tag_counts_as_delivered():
    s = captureone.derive(shoot(), {}, {"type": "color", "color": 4})
    assert s["done"] == 25


def test_rating_rule():
    s = captureone.derive(shoot(), {}, {"type": "rating", "rating": 5})
    assert s["done"] == 5


def test_finished_shoot():
    s = captureone.derive(shoot(exported=40), {}, {"type": "export"})
    assert s["status"] == "done" and s["progress"] == 1.0


def test_manual_status_wins():
    s = captureone.derive(shoot(), {"status": "delivered", "deadline": "2030-01-01"}, {"type": "export"})
    assert s["status"] == "delivered" and s["deadline"] == "2030-01-01" and s["status_auto"] == "editing"


def test_empty_shoot():
    s = captureone.derive(shoot(total=0, picked=0, exported=0, colors={}, ratings={}), {}, None)
    assert s["progress"] == 0 and s["status"] == "new"


def test_demo_shoots_all_derive():
    for s in demo.shoots():
        d = captureone.derive(dict(s, source="c1"), {}, None)
        assert 0 <= d["progress"] <= 1


def test_buttons_only_known_kinds():
    out = buttons.clean([{"kind": "shell", "value": "rm -rf /"}, {"kind": "url", "value": "javascript:alert(1)"},
                         {"kind": "url", "value": "https://example.com", "title": "ok"}, "junk"])
    assert [b["kind"] for b in out] == ["url"]


def test_pressing_only_saved_buttons(remote, device_key):
    _, r, _ = remote.post("/api/action", {"action": "button", "arg": "not-saved"}, key=device_key)
    assert r["ok"] is False


@pytest.mark.parametrize("spec", [{"kind": "url", "value": "x" * 5000}])
def test_values_are_bounded(spec):
    assert buttons.clean([dict(spec, value="https://" + spec["value"])])[0]["value"].__len__() <= 2000
