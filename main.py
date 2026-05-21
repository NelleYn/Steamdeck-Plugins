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
from deckpip.mirror import start_mirror_window
from deckpip.session import PipSession, novnc_dir, terminate
from deckpip.settings import SettingsStore


class Plugin:
    session: PipSession | None = None
    _lock: asyncio.Lock | None = None
    _settings: SettingsStore | None = None

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
        return {
            "Xvnc": shutil.which("Xvnc") is not None,
            "vncpasswd": shutil.which("vncpasswd") is not None,
            "websockify": shutil.which("websockify") is not None,
            "novnc": novnc_dir() is not None,
            "xterm": shutil.which("xterm") is not None,
            "wmctrl": shutil.which("wmctrl") is not None,
        }

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

    # ----- lifecycle -------------------------------------------------------

    async def _main(self) -> None:
        self._lock = asyncio.Lock()
        decky.logger.info("DeckPiP loaded")

    async def _unload(self) -> None:
        await self.stop_pip()
        decky.logger.info("DeckPiP unloaded")

    async def _uninstall(self) -> None:
        await self.stop_pip()
