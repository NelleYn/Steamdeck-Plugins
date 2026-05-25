from pathlib import Path

from deckpip.profiles import get_profile, list_profiles, remove_profile, set_profile
from deckpip.settings import SettingsStore


def test_empty_initially(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    assert list_profiles(s) == {}
    assert get_profile(s, 12345) is None


def test_set_and_get(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    set_profile(s, 12345, {"app_id": "discord_flatpak", "auto_launch": True})
    p = get_profile(s, 12345)
    assert p is not None
    assert p["auto_launch"] is True


def test_appid_coerced_to_string(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    set_profile(s, 12345, {"app_id": "x"})
    # Lookup with int and str should both work.
    assert get_profile(s, 12345) is not None
    assert get_profile(s, "12345") is not None


def test_overwrite(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    set_profile(s, 1, {"app_id": "a"})
    set_profile(s, 1, {"app_id": "b"})
    assert get_profile(s, 1)["app_id"] == "b"


def test_remove(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    set_profile(s, 1, {"app_id": "a"})
    set_profile(s, 2, {"app_id": "b"})
    remove_profile(s, 1)
    assert get_profile(s, 1) is None
    assert get_profile(s, 2) is not None


def test_remove_missing_is_noop(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    assert remove_profile(s, 999) == {"ok": True}


def test_invalid_profile_rejected(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    res = set_profile(s, 1, "not a dict")  # type: ignore[arg-type]
    assert not res["ok"]


def test_corrupted_storage_treated_as_empty(tmp_path: Path) -> None:
    s = SettingsStore(tmp_path)
    s.set("game_profiles", "not a dict")
    assert list_profiles(s) == {}
    assert get_profile(s, 1) is None
    # Setting still works (overwrites garbage).
    set_profile(s, 1, {"app_id": "x"})
    assert get_profile(s, 1)["app_id"] == "x"
