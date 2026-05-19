import asyncio
import json
import os
import secrets
import signal
import subprocess
from pathlib import Path
from typing import Optional

import decky


DEFAULT_APPS = [
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
    {
        "id": "xterm",
        "label": "xterm (debug)",
        "command": ["xterm"],
    },
]

XVFB_DISPLAY = ":42"
XVFB_RESOLUTION = "1280x800x24"
VNC_BIND = "127.0.0.1"
VNC_PORT = 6901


class PipSession:
    """Owns the Xvfb + target app + KasmVNC process group for one PiP session."""

    def __init__(self, app: dict, token: str) -> None:
        self.app = app
        self.token = token
        self.xvfb: Optional[subprocess.Popen] = None
        self.guest: Optional[subprocess.Popen] = None
        self.vnc: Optional[subprocess.Popen] = None

    async def start(self) -> None:
        env = {**os.environ, "DISPLAY": XVFB_DISPLAY}
        self.xvfb = subprocess.Popen(
            ["Xvfb", XVFB_DISPLAY, "-screen", "0", XVFB_RESOLUTION],
            preexec_fn=os.setsid,
        )
        # Give Xvfb a moment to bind the X socket.
        await asyncio.sleep(0.5)

        self.guest = subprocess.Popen(
            self.app["command"],
            env=env,
            preexec_fn=os.setsid,
        )

        # KasmVNC reads the password from stdin via `vncpasswd -f`-style;
        # for the PoC we shell out to kasmvncserver with a static config.
        # TODO: replace with portable KasmVNC bundled under runtime_dir.
        self.vnc = subprocess.Popen(
            [
                "kasmvncserver",
                "-localhost",
                "-rfbport",
                str(VNC_PORT),
                "-PasswordFile",
                self._write_passwd(),
                XVFB_DISPLAY,
            ],
            env=env,
            preexec_fn=os.setsid,
        )

    def _write_passwd(self) -> str:
        path = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "vncpasswd"
        path.write_text(self.token)
        path.chmod(0o600)
        return str(path)

    def stop(self) -> None:
        for proc in (self.vnc, self.guest, self.xvfb):
            if proc is None or proc.poll() is not None:
                continue
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass


class Plugin:
    session: Optional[PipSession] = None

    async def list_apps(self) -> list:
        return DEFAULT_APPS

    async def start_pip(self, app_id: str) -> dict:
        if self.session is not None:
            return {"ok": False, "error": "already_running"}

        app = next((a for a in DEFAULT_APPS if a["id"] == app_id), None)
        if app is None:
            return {"ok": False, "error": "unknown_app"}

        token = secrets.token_hex(16)
        session = PipSession(app, token)
        try:
            await session.start()
        except FileNotFoundError as exc:
            decky.logger.error("dependency missing: %s", exc)
            session.stop()
            return {"ok": False, "error": f"missing:{exc.filename}"}

        self.session = session
        return {
            "ok": True,
            "url": f"http://{VNC_BIND}:{VNC_PORT}/?password={token}&autoconnect=1",
        }

    async def stop_pip(self) -> dict:
        if self.session is None:
            return {"ok": True}
        self.session.stop()
        self.session = None
        return {"ok": True}

    async def _main(self) -> None:
        decky.logger.info("DeckPiP loaded")

    async def _unload(self) -> None:
        await self.stop_pip()
        decky.logger.info("DeckPiP unloaded")

    async def _uninstall(self) -> None:
        await self.stop_pip()
