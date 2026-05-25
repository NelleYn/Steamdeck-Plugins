"""DeckPiP Decky plugin entrypoint.

Decky Loader imports this file and instantiates ``Plugin``. All
non-trivial behaviour lives in the ``deckpip`` package alongside this
file so it can be unit-tested without the Decky runtime.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import shutil
from pathlib import Path
from typing import Any

import decky

from deckpip.apps import add_custom_app, all_apps, remove_custom_app
from deckpip.audio import set_guest_volume as _set_guest_volume
from deckpip.battery import read_state as _battery_read
from deckpip.bookmarks import (
    add_bookmark as _add_bookmark,
)
from deckpip.bookmarks import (
    list_bookmarks as _list_bookmarks,
)
from deckpip.bookmarks import (
    remove_bookmark as _remove_bookmark,
)
from deckpip.diagnostics import collect as _diagnostics_collect
from deckpip.ludusavi import (
    backup as _ludusavi_backup,
)
from deckpip.ludusavi import (
    find_games as _ludusavi_find,
)
from deckpip.ludusavi import (
    install as _ludusavi_install,
)
from deckpip.ludusavi import (
    parse_backup_summary as _ludusavi_summary,
)
from deckpip.ludusavi import (
    resolve_binary as _ludusavi_resolve,
)
from deckpip.ludusavi import (
    restore as _ludusavi_restore,
)
from deckpip.mirror import start_mirror_window
from deckpip.mpris import list_players as _mpris_list
from deckpip.mpris import player_action as _mpris_action
from deckpip.notifications import NotificationMirror
from deckpip.profiles import (
    get_profile as _get_profile,
)
from deckpip.profiles import (
    list_profiles as _list_profiles,
)
from deckpip.profiles import (
    remove_profile as _remove_profile,
)
from deckpip.profiles import (
    set_profile as _set_profile,
)
from deckpip.ptt import send_key as _ptt_send_key
from deckpip.session import PipSession, novnc_dir, terminate, websockify_argv
from deckpip.settings import SettingsStore
from deckpip.trackpad import (
    mouse_button as _mouse_button,
)
from deckpip.trackpad import (
    mouse_move as _mouse_move,
)
from deckpip.trackpad import (
    mouse_scroll as _mouse_scroll,
)
from deckpip.updater import check_release as _check_release
from deckpip.updater import run_setup as _run_setup
from deckpip.vendoring import install_all as _vendor_install
from deckpip.vendoring import status as _vendor_status


class Plugin:
    session: PipSession | None = None
    _lock: asyncio.Lock | None = None
    _settings: SettingsStore | None = None
    _notif_mirror: NotificationMirror | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _get_settings(self) -> SettingsStore:
        if self._settings is None:
            self._settings = SettingsStore(Path(decky.DECKY_PLUGIN_SETTINGS_DIR))
        return self._settings

    # ----- frontend callables ----------------------------------------------

    async def list_apps(self) -> list:
        return all_apps(self._get_settings())

    async def add_custom_app(self, app_id: str, label: str, command: str) -> dict:
        return add_custom_app(self._get_settings(), app_id, label, command)

    async def remove_custom_app(self, app_id: str) -> dict:
        return remove_custom_app(self._get_settings(), app_id)

    async def settings_get(self, key: str, default: Any = None) -> Any:
        return self._get_settings().get(key, default)

    async def settings_set(self, key: str, value: Any) -> dict:
        self._get_settings().set(key, value)
        return {"ok": True}

    async def check_dependencies(self) -> dict:
        rt = Path(decky.DECKY_PLUGIN_RUNTIME_DIR)
        return {
            # Required for any PiP session
            "Xvnc": shutil.which("Xvnc") is not None,
            "vncpasswd": shutil.which("vncpasswd") is not None,
            "websockify": websockify_argv(rt) is not None,
            "novnc": novnc_dir(rt) is not None,
            "pactl": shutil.which("pactl") is not None,
            # Optional, for GameMirror only — surface separately so the panel
            # doesn't scream "missing" for a feature the user may not need.
            "_optional_wmctrl": shutil.which("wmctrl") is not None,
            "_optional_gst": shutil.which("gst-launch-1.0") is not None,
            "_optional_pw-cli": shutil.which("pw-cli") is not None,
        }

    async def vendor_status(self) -> dict:
        return _vendor_status(Path(decky.DECKY_PLUGIN_RUNTIME_DIR))

    async def install_vendored(self, force: bool = False) -> dict:
        return await _vendor_install(
            Path(decky.DECKY_PLUGIN_RUNTIME_DIR), force=force,
        )

    # ----- D-Bus notification mirror ---------------------------------------

    async def start_notification_mirror(self) -> dict:
        if self._notif_mirror is not None:
            return {"ok": False, "error": "already_running"}

        async def _emit(payload: dict) -> None:
            await decky.emit("deckpip_notification", payload)

        self._notif_mirror = NotificationMirror(_emit)
        res = await self._notif_mirror.start()
        if not res["ok"]:
            self._notif_mirror = None
        return res

    async def stop_notification_mirror(self) -> dict:
        if self._notif_mirror is None:
            return {"ok": True}
        await self._notif_mirror.stop()
        self._notif_mirror = None
        return {"ok": True}

    # ----- pointer forwarding (trackpad-as-mouse in PiP) -------------------

    async def mouse_move(self, x_pct: float, y_pct: float) -> dict:
        return await _mouse_move(x_pct, y_pct)

    async def mouse_button(self, button: int, action: str) -> dict:
        return await _mouse_button(button, action)

    async def mouse_scroll(self, direction: str) -> dict:
        return await _mouse_scroll(direction)

    # ----- MPRIS media controls --------------------------------------------

    async def mpris_list(self) -> list:
        return await _mpris_list()

    async def mpris_action(self, bus_name: str, action: str) -> dict:
        return await _mpris_action(bus_name, action)

    # ----- Ludusavi save sync ---------------------------------------------

    async def ludusavi_status(self) -> dict:
        rt = Path(decky.DECKY_PLUGIN_RUNTIME_DIR)
        return {
            "installed": _ludusavi_resolve(rt) is not None,
            "path": _ludusavi_resolve(rt) or "",
        }

    async def ludusavi_install(self, force: bool = False) -> dict:
        return await _ludusavi_install(
            Path(decky.DECKY_PLUGIN_RUNTIME_DIR), force=force,
        )

    async def ludusavi_backup(self, game: str | None = None) -> dict:
        res = await _ludusavi_backup(
            Path(decky.DECKY_PLUGIN_RUNTIME_DIR), game=game,
        )
        if res.get("ok") and isinstance(res.get("payload"), dict):
            res["summary"] = _ludusavi_summary(res["payload"])
        return res

    async def ludusavi_restore(self, game: str | None = None) -> dict:
        return await _ludusavi_restore(
            Path(decky.DECKY_PLUGIN_RUNTIME_DIR), game=game,
        )

    async def ludusavi_find(self, query: str | None = None) -> dict:
        return await _ludusavi_find(
            Path(decky.DECKY_PLUGIN_RUNTIME_DIR), query=query,
        )

    async def install_dependencies(self) -> dict:
        script = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "install.sh"
        if not script.exists():
            return {"ok": False, "error": "install.sh not found"}
        proc = await asyncio.create_subprocess_exec(
            "bash", str(script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        except TimeoutError:
            proc.kill()
            return {"ok": False, "error": "timeout"}
        return {
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "stdout": stdout.decode(errors="replace")[-2000:],
            "stderr": stderr.decode(errors="replace")[-2000:],
        }

    async def start_pip(self, app_id: str, audio_only: bool = False) -> dict:
        async with self._get_lock():
            if self.session is not None:
                return {"ok": False, "error": "already_running"}

            app = next(
                (a for a in all_apps(self._get_settings()) if a["id"] == app_id),
                None,
            )
            if app is None:
                return {"ok": False, "error": "unknown_app"}

            if shutil.which("Xvnc") is None:
                return {"ok": False, "error": "missing_dependency:Xvnc"}

            token = secrets.token_hex(8)
            session = PipSession(
                app, token, audio_only=audio_only,
                runtime_dir=Path(decky.DECKY_PLUGIN_RUNTIME_DIR),
            )
            try:
                await session.start()
            except FileNotFoundError as exc:
                decky.logger.error("dependency missing: %s", exc)
                await session.stop()
                return {"ok": False, "error": f"missing_dependency:{exc.args[0]}"}
            except Exception as exc:
                decky.logger.exception("start_pip failed")
                await session.stop()
                return {"ok": False, "error": str(exc)}

            self.session = session
            return {
                "ok": True,
                "audio_only": audio_only,
                "url": session.url(),
            }

    async def stop_pip(self) -> dict:
        async with self._get_lock():
            if self.session is None:
                return {"ok": True}
            await self.session.stop()
            self.session = None
            with contextlib.suppress(Exception):
                (Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "vncpasswd").unlink(
                    missing_ok=True
                )
            return {"ok": True}

    async def start_game_mirror(self) -> dict:
        async with self._get_lock():
            if self.session is None:
                return {"ok": False, "error": "no_session"}
            if self.session.mirror is not None:
                return {"ok": False, "error": "already_mirroring"}
            try:
                self.session.mirror = await start_mirror_window()
            except FileNotFoundError as exc:
                return {"ok": False, "error": f"missing_dependency:{exc.args[0]}"}
            except RuntimeError as exc:
                return {"ok": False, "error": str(exc)}
            return {"ok": True}

    async def stop_game_mirror(self) -> dict:
        async with self._get_lock():
            if self.session is None or self.session.mirror is None:
                return {"ok": True}
            await terminate(self.session.mirror)
            self.session.mirror = None
            return {"ok": True}

    async def pause_session(self) -> dict:
        async with self._get_lock():
            if self.session is None:
                return {"ok": False, "error": "no_session"}
            self.session.pause()
            return {"ok": True, "paused": True}

    async def resume_session(self) -> dict:
        async with self._get_lock():
            if self.session is None:
                return {"ok": False, "error": "no_session"}
            self.session.resume()
            return {"ok": True, "paused": False}

    async def set_guest_volume(self, percent: int) -> dict:
        if self.session is None or self.session.guest is None:
            return {"ok": False, "error": "no_session"}
        return await _set_guest_volume(self.session.guest.pid, percent)

    async def battery_state(self) -> dict:
        return _battery_read()

    async def export_settings(self) -> dict:
        data = self._get_settings()._load()  # noqa: SLF001 -- intentional snapshot
        return {"ok": True, "data": data}

    async def import_settings(self, payload: dict, merge: bool = True) -> dict:
        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_payload"}
        store = self._get_settings()
        if merge:
            current = store._load()  # noqa: SLF001
            current.update(payload)
            store._save(current)  # noqa: SLF001
        else:
            store._save(payload)  # noqa: SLF001
        return {"ok": True}

    # ----- per-game profiles -----------------------------------------------

    async def list_profiles(self) -> dict:
        return _list_profiles(self._get_settings())

    async def get_profile(self, appid: str) -> dict | None:
        return _get_profile(self._get_settings(), appid)

    async def set_profile(self, appid: str, profile: dict) -> dict:
        return _set_profile(self._get_settings(), appid, profile)

    async def remove_profile(self, appid: str) -> dict:
        return _remove_profile(self._get_settings(), appid)

    # ----- bookmarks --------------------------------------------------------

    async def list_bookmarks(self) -> list:
        return _list_bookmarks(self._get_settings())

    async def add_bookmark(self, bm_id: str, label: str, url: str) -> dict:
        return _add_bookmark(self._get_settings(), bm_id, label, url)

    async def remove_bookmark(self, bm_id: str) -> dict:
        return _remove_bookmark(self._get_settings(), bm_id)

    # ----- diagnostics ------------------------------------------------------

    async def diagnostics(self) -> dict:
        return await _diagnostics_collect(Path(decky.DECKY_PLUGIN_RUNTIME_DIR))

    # ----- push-to-talk -----------------------------------------------------

    async def ptt(self, _key_combo: str, action: str) -> dict:
        """PTT is now PulseAudio mute/unmute; key_combo arg kept for API
        compatibility with older frontends."""
        return await _ptt_send_key(_key_combo, action)

    # ----- one-click update -------------------------------------------------

    async def check_update(self) -> dict:
        return await _check_release(self._get_settings())

    async def run_update(self) -> dict:
        return await _run_setup(Path(decky.DECKY_PLUGIN_DIR))

    # ----- lifecycle -------------------------------------------------------

    async def _main(self) -> None:
        self._lock = asyncio.Lock()
        decky.logger.info("DeckPiP loaded")

    async def _unload(self) -> None:
        if self._notif_mirror is not None:
            await self._notif_mirror.stop()
            self._notif_mirror = None
        await self.stop_pip()
        decky.logger.info("DeckPiP unloaded")

    async def _uninstall(self) -> None:
        await self.stop_pip()
