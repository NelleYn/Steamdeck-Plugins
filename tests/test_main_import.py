"""Verify main.py is importable (catches Decky runtime import errors).

Decky Loader imports main.py at startup; if any module-level statement
raises, the plugin disappears from the UI with the traceback in
``journalctl -u plugin_loader``. That class of bug is hard to debug
through Decky's logging, so we catch it in CI by stubbing the
``decky`` module and importing main.py.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path


def _install_decky_stub() -> None:
    if "decky" in sys.modules:
        return
    fake = types.ModuleType("decky")
    fake.DECKY_PLUGIN_SETTINGS_DIR = "/tmp/deckpip-test-settings"  # type: ignore[attr-defined]
    fake.DECKY_PLUGIN_RUNTIME_DIR = "/tmp/deckpip-test-runtime"  # type: ignore[attr-defined]
    fake.DECKY_PLUGIN_DIR = str(Path(__file__).parent.parent)  # type: ignore[attr-defined]

    class _Logger:
        def __getattr__(self, _name: str):  # pragma: no cover
            return lambda *_a, **_kw: None

    fake.logger = _Logger()  # type: ignore[attr-defined]
    sys.modules["decky"] = fake


def test_main_module_imports_cleanly() -> None:
    _install_decky_stub()
    import importlib

    import main as decky_main

    importlib.reload(decky_main)
    assert hasattr(decky_main, "Plugin")


def test_plugin_class_has_required_methods() -> None:
    _install_decky_stub()
    import main as decky_main

    plugin = decky_main.Plugin
    # Spot-check the callables the frontend binds to.
    for name in [
        "list_apps", "start_pip", "stop_pip",
        "settings_get", "settings_set",
        "add_custom_app", "remove_custom_app",
        "check_dependencies", "install_dependencies",
        "start_game_mirror", "stop_game_mirror",
        "list_profiles", "get_profile", "set_profile", "remove_profile",
        "list_bookmarks", "add_bookmark", "remove_bookmark",
        "diagnostics", "ptt",
        "check_update", "run_update",
        "pause_session", "resume_session",
        "set_guest_volume", "battery_state",
        "export_settings", "import_settings",
        "vendor_status", "install_vendored",
        "_main", "_unload", "_uninstall",
    ]:
        assert callable(getattr(plugin, name)), f"missing: {name}"
