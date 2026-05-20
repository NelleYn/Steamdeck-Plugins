import asyncio
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

DISPLAY = ":42"
GEOMETRY = "1280x800"
DEPTH = "24"

VNC_BIND = "127.0.0.1"
VNC_RFB_PORT = 5942      # raw VNC, Xvnc listens here
VNC_WEB_PORT = 6901      # websockify + noVNC frontend, this is what the iframe loads

NOVNC_CANDIDATES = [
    "/usr/share/novnc",
    "/usr/share/webapps/novnc",
    "/usr/lib/novnc",
]

PACMAN_PACKAGES = [
    "tigervnc",
    "python-websockify",
    "novnc",
    "xterm",
    "wmctrl",
]


def _which(binary: str) -> Optional[str]:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(d) / binary
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _novnc_dir() -> Optional[str]:
    for path in NOVNC_CANDIDATES:
        if Path(path, "vnc.html").exists():
            return path
    return None


class PipSession:
    """Owns the Xvnc + target app + websockify process group for one PiP session."""

    def __init__(self, app: dict, token: str, audio_only: bool) -> None:
        self.app = app
        self.token = token
        self.audio_only = audio_only
        self.xvnc: Optional[subprocess.Popen] = None
        self.guest: Optional[subprocess.Popen] = None
        self.websockify: Optional[subprocess.Popen] = None

    async def start(self) -> None:
        passwd_path = self._write_vnc_passwd()

        self.xvnc = subprocess.Popen(
            [
                "Xvnc", DISPLAY,
                "-geometry", GEOMETRY,
                "-depth", DEPTH,
                "-SecurityTypes", "VncAuth",
                "-PasswordFile", passwd_path,
                "-localhost", "yes",
                "-rfbport", str(VNC_RFB_PORT),
                "-AlwaysShared",
            ],
            preexec_fn=os.setsid,
        )
        await asyncio.sleep(0.6)

        env = {**os.environ, "DISPLAY": DISPLAY}
        self.guest = subprocess.Popen(
            self.app["command"],
            env=env,
            preexec_fn=os.setsid,
        )

        if self.audio_only:
            # No iframe will be opened; we still keep Xvnc running so the app has
            # an X server to draw to, but we don't need the websocket bridge.
            return

        novnc = _novnc_dir()
        if novnc is None:
            self.stop()
            raise FileNotFoundError("novnc")

        self.websockify = subprocess.Popen(
            [
                "websockify",
                "--web", novnc,
                f"{VNC_BIND}:{VNC_WEB_PORT}",
                f"127.0.0.1:{VNC_RFB_PORT}",
            ],
            preexec_fn=os.setsid,
        )

    def _write_vnc_passwd(self) -> str:
        path = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "vncpasswd"
        # TigerVNC password is limited to 8 chars; loopback-only so the token
        # length is not a security boundary, just a handshake.
        proc = subprocess.run(
            ["vncpasswd", "-f"],
            input=self.token[:8].encode(),
            capture_output=True,
            check=True,
        )
        path.write_bytes(proc.stdout)
        path.chmod(0o600)
        return str(path)

    def url(self) -> Optional[str]:
        if self.audio_only:
            return None
        return (
            f"http://{VNC_BIND}:{VNC_WEB_PORT}/vnc.html"
            f"?host={VNC_BIND}&port={VNC_WEB_PORT}"
            f"&password={self.token[:8]}"
            f"&autoconnect=1&resize=remote&reconnect=1"
        )

    def stop(self) -> None:
        for proc in (self.websockify, self.guest, self.xvnc):
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

    async def check_dependencies(self) -> dict:
        """Report which runtime dependencies are present on this system."""
        return {
            "Xvnc": _which("Xvnc") is not None,
            "vncpasswd": _which("vncpasswd") is not None,
            "websockify": _which("websockify") is not None,
            "novnc": _novnc_dir() is not None,
            "xterm": _which("xterm") is not None,
            "wmctrl": _which("wmctrl") is not None,
        }

    async def install_dependencies(self) -> dict:
        """Install missing packages via pacman, toggling SteamOS read-only off
        and back on around it. Plugin runs as root (_root flag), so no sudo."""
        script = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "install.sh"
        if not script.exists():
            return {"ok": False, "error": "install.sh not found"}
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }

    async def start_pip(self, app_id: str, audio_only: bool = False) -> dict:
        if self.session is not None:
            return {"ok": False, "error": "already_running"}

        app = next((a for a in DEFAULT_APPS if a["id"] == app_id), None)
        if app is None:
            return {"ok": False, "error": "unknown_app"}

        if _which("Xvnc") is None:
            return {"ok": False, "error": "missing_dependency:Xvnc"}

        token = secrets.token_hex(8)
        session = PipSession(app, token, audio_only=audio_only)
        try:
            await session.start()
        except FileNotFoundError as exc:
            decky.logger.error("dependency missing: %s", exc)
            session.stop()
            return {"ok": False, "error": f"missing_dependency:{exc.args[0]}"}
        except Exception as exc:
            decky.logger.exception("start_pip failed")
            session.stop()
            return {"ok": False, "error": str(exc)}

        self.session = session
        return {
            "ok": True,
            "audio_only": audio_only,
            "url": session.url(),
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
