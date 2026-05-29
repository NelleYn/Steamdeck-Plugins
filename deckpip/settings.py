"""JSON-backed settings store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class SettingsStore:
    def __init__(self, settings_dir: Path) -> None:
        self.path = Path(settings_dir) / "settings.json"

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: tmp + rename so a crash mid-write doesn't truncate.
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, self.path)

    def get(self, key: str, default: Any = None) -> Any:
        return self._load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = value
        self._save(data)
