"""User-saved http(s) URLs for the Web-PiP mode."""

from __future__ import annotations

import re
from typing import Any

from deckpip.settings import SettingsStore

BOOKMARKS_KEY = "bookmarks"
LABEL_MAX = 64
URL_MAX = 2048
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _all(store: SettingsStore) -> list[dict[str, str]]:
    raw = store.get(BOOKMARKS_KEY, []) or []
    if not isinstance(raw, list):
        return []
    return [b for b in raw if isinstance(b, dict) and "id" in b and "url" in b and "label" in b]


def list_bookmarks(store: SettingsStore) -> list[dict[str, str]]:
    return _all(store)


def add_bookmark(store: SettingsStore, bm_id: str, label: str, url: str) -> dict[str, Any]:
    if not bm_id or len(bm_id) > 64:
        return {"ok": False, "error": "invalid_id"}
    if not label or len(label) > LABEL_MAX:
        return {"ok": False, "error": "invalid_label"}
    if not url or len(url) > URL_MAX or not _URL_RE.match(url):
        return {"ok": False, "error": "invalid_url"}
    items = [b for b in _all(store) if b["id"] != bm_id]
    items.append({"id": bm_id, "label": label, "url": url})
    store.set(BOOKMARKS_KEY, items)
    return {"ok": True}


def remove_bookmark(store: SettingsStore, bm_id: str) -> dict[str, Any]:
    items = [b for b in _all(store) if b["id"] != bm_id]
    store.set(BOOKMARKS_KEY, items)
    return {"ok": True}
