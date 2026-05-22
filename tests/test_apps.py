from pathlib import Path

from deckpip.apps import DEFAULT_APPS, add_custom_app, all_apps, remove_custom_app
from deckpip.settings import SettingsStore


def test_default_apps_only(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    apps = all_apps(store)
    assert [a["id"] for a in apps] == [a["id"] for a in DEFAULT_APPS]


def test_add_custom_appends(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    res = add_custom_app(store, "x1", "Hello", "echo hi")
    assert res == {"ok": True}
    apps = all_apps(store)
    assert apps[-1] == {"id": "x1", "label": "Hello", "command": ["echo", "hi"]}


def test_add_with_quoting(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    add_custom_app(store, "x1", "Quoted", 'echo "hello world"')
    assert all_apps(store)[-1]["command"] == ["echo", "hello world"]


def test_add_replaces_existing_id(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    add_custom_app(store, "x1", "First", "true")
    add_custom_app(store, "x1", "Second", "false")
    custom = [a for a in all_apps(store) if a["id"] == "x1"]
    assert len(custom) == 1
    assert custom[0]["label"] == "Second"
    assert custom[0]["command"] == ["false"]


def test_empty_command_rejected(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    res = add_custom_app(store, "x1", "Empty", "   ")
    assert res == {"ok": False, "error": "empty_command"}
    assert all(a["id"] != "x1" for a in all_apps(store))


def test_unterminated_quote_returns_parse_error(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    res = add_custom_app(store, "x1", "Broken", 'echo "no end')
    assert not res["ok"]
    assert res["error"].startswith("parse_error:")


def test_remove(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    add_custom_app(store, "x1", "A", "true")
    add_custom_app(store, "x2", "B", "true")
    remove_custom_app(store, "x1")
    ids = [a["id"] for a in all_apps(store)]
    assert "x1" not in ids
    assert "x2" in ids


def test_remove_missing_is_noop(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    assert remove_custom_app(store, "never_added") == {"ok": True}


def test_corrupt_custom_entries_filtered(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set(
        "custom_apps",
        [
            {"id": "good", "command": ["x"]},
            {"junk": True},
            "not even a dict",
            {"id": "no_command"},
        ],
    )
    ids = [a["id"] for a in all_apps(store) if a["id"] not in {d["id"] for d in DEFAULT_APPS}]
    assert ids == ["good"]


def test_non_list_custom_apps_ignored(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set("custom_apps", "garbage")
    assert [a["id"] for a in all_apps(store)] == [a["id"] for a in DEFAULT_APPS]


def test_label_length_limit(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    res = add_custom_app(store, "x1", "A" * 1024, "true")
    assert res == {"ok": False, "error": "label_too_long"}


def test_command_length_limit(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    res = add_custom_app(store, "x1", "ok", "true " * 1000)
    assert res == {"ok": False, "error": "command_too_long"}


def test_empty_id_rejected(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    res = add_custom_app(store, "", "ok", "true")
    assert res == {"ok": False, "error": "invalid_id"}
