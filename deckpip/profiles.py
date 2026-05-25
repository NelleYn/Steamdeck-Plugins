"""Per-game launch profiles keyed by Steam appid.

Maps an appid -> {
    "app_id":      str,            # which DeckPiP app to launch (xterm, discord_flatpak, custom_...)
    "audio_only":  bool,
    "auto_launch": bool,           # start automatically when this Steam app starts
    "geom":        {x,y,w,h}|None, # overlay geometry override; if None, use global default
    "opacity":     int|None,
}
"""

from __future__ import annotations

from typing import Any

from deckpip.settings import SettingsStore

PROFILES_KEY = "game_profiles"


def _all(store: SettingsStore) -> dict[str, Any]:
    raw = store.get(PROFILES_KEY, {}) or {}
    return raw if isinstance(raw, dict) else {}


def list_profiles(store: SettingsStore) -> dict[str, Any]:
    return _all(store)


def get_profile(store: SettingsStore, appid: str | int) -> dict[str, Any] | None:
    return _all(store).get(str(appid))


def set_profile(store: SettingsStore, appid: str | int, profile: dict[str, Any]) -> dict:
    if not isinstance(profile, dict):
        return {"ok": False, "error": "invalid_profile"}
    profiles = _all(store)
    profiles[str(appid)] = profile
    store.set(PROFILES_KEY, profiles)
    return {"ok": True}


def remove_profile(store: SettingsStore, appid: str | int) -> dict:
    profiles = _all(store)
    profiles.pop(str(appid), None)
    store.set(PROFILES_KEY, profiles)
    return {"ok": True}
