"""Built-in and user-defined apps registry."""

from __future__ import annotations

import shlex
from typing import Any

from deckpip.settings import SettingsStore

DEFAULT_APPS: list[dict[str, Any]] = [
    {
        "id": "discord_flatpak",
        "label": "Discord (Flatpak)",
        "command": ["flatpak", "run", "com.discordapp.Discord"],
    },
    {
        "id": "telegram_flatpak",
        "label": "Telegram (Flatpak)",
        "command": ["flatpak", "run", "org.telegram.desktop"],
    },
]

LABEL_MAX = 256
COMMAND_MAX = 1024
ID_MAX = 64


def _custom_apps(store: SettingsStore) -> list[dict[str, Any]]:
    raw = store.get("custom_apps", []) or []
    if not isinstance(raw, list):
        return []
    return [c for c in raw if isinstance(c, dict) and "id" in c and "command" in c]


def all_apps(store: SettingsStore) -> list[dict[str, Any]]:
    return DEFAULT_APPS + _custom_apps(store)


def add_custom_app(store: SettingsStore, app_id: str, label: str, command: str) -> dict:
    if not app_id or len(app_id) > ID_MAX:
        return {"ok": False, "error": "invalid_id"}
    if len(label) > LABEL_MAX:
        return {"ok": False, "error": "label_too_long"}
    if len(command) > COMMAND_MAX:
        return {"ok": False, "error": "command_too_long"}
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return {"ok": False, "error": f"parse_error:{exc}"}
    if not argv:
        return {"ok": False, "error": "empty_command"}
    apps = _custom_apps(store)
    apps = [a for a in apps if a.get("id") != app_id]
    apps.append({"id": app_id, "label": label, "command": argv})
    store.set("custom_apps", apps)
    return {"ok": True}


def remove_custom_app(store: SettingsStore, app_id: str) -> dict:
    apps = [a for a in _custom_apps(store) if a.get("id") != app_id]
    store.set("custom_apps", apps)
    return {"ok": True}
