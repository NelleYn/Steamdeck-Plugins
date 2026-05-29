from pathlib import Path

from deckpip.bookmarks import add_bookmark, list_bookmarks, remove_bookmark
from deckpip.settings import SettingsStore


def test_empty_initially(tmp_path: Path) -> None:
    assert list_bookmarks(SettingsStore(tmp_path)) == []


def test_add_round_trip(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    res = add_bookmark(s, "wiki", "Wiki", "https://wiki.gg")
    assert res == {"ok": True}
    items = list_bookmarks(s)
    assert len(items) == 1
    assert items[0]["url"] == "https://wiki.gg"


def test_replace_by_id(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    add_bookmark(s, "x", "Old", "https://a")
    add_bookmark(s, "x", "New", "https://b")
    items = list_bookmarks(s)
    assert len(items) == 1
    assert items[0]["label"] == "New"


def test_remove(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    add_bookmark(s, "a", "A", "https://a")
    add_bookmark(s, "b", "B", "https://b")
    remove_bookmark(s, "a")
    ids = [b["id"] for b in list_bookmarks(s)]
    assert ids == ["b"]


def test_rejects_non_http(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    res = add_bookmark(s, "x", "L", "javascript:alert(1)")
    assert res == {"ok": False, "error": "invalid_url"}


def test_rejects_too_long(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    res = add_bookmark(s, "x", "L", "https://" + ("x" * 4000))
    assert res == {"ok": False, "error": "invalid_url"}


def test_rejects_empty_label(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    res = add_bookmark(s, "x", "", "https://ok")
    assert res == {"ok": False, "error": "invalid_label"}


def test_rejects_empty_id(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    res = add_bookmark(s, "", "L", "https://ok")
    assert res == {"ok": False, "error": "invalid_id"}


def test_corrupted_storage_treated_as_empty(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    s.set("bookmarks", "not a list")
    assert list_bookmarks(s) == []
    add_bookmark(s, "a", "L", "https://x")
    assert len(list_bookmarks(s)) == 1
