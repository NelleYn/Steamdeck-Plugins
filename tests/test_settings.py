from pathlib import Path

from deckpip.settings import SettingsStore


def test_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    assert store.get("anything") is None
    store.set("foo", 42)
    assert store.get("foo") == 42


def test_default_returned_for_missing_key(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    assert store.get("missing", "fallback") == "fallback"


def test_overwrite(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set("k", 1)
    store.set("k", 2)
    assert store.get("k") == 2


def test_persists_across_instances(tmp_path: Path) -> None:
    SettingsStore(tmp_path).set("k", "v")
    assert SettingsStore(tmp_path).get("k") == "v"


def test_corrupted_json_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text("not json {")
    store = SettingsStore(tmp_path)
    assert store.get("anything") is None
    # And setting still works (file is rewritten).
    store.set("k", "v")
    assert store.get("k") == "v"


def test_non_dict_json_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text('["not", "a", "dict"]')
    store = SettingsStore(tmp_path)
    assert store.get("anything") is None


def test_creates_parent_dir(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    store = SettingsStore(deep)
    store.set("k", 1)
    assert (deep / "settings.json").exists()
