import asyncio
import contextlib
import json
import os
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
from pathlib import Path
from typing import Any, Optional

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
VNC_RFB_PORT = 5942
VNC_WEB_PORT = 6901

NOVNC_CANDIDATES = [
    "/usr/share/novnc",
    "/usr/share/webapps/novnc",
    "/usr/lib/novnc",
]


def _novnc_dir() -> Optional[str]:
    for path in NOVNC_CANDIDATES:
        if Path(path, "vnc.html").exists():
            return path
    return None


def _settings_path() -> Path:
    return Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / "settings.json"


async def _wait_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Active-wait until TCP port accepts a connection, or give up."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=0.5
            )
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
            await asyncio.sleep(0.1)
    return False


async def _terminate(proc: Optional[subprocess.Popen], grace: float = 3.0) -> None:
    """SIGTERM the process group, wait, then SIGKILL if still alive."""
    if proc is None or proc.poll() is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGTERM)
    try:
        await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=grace)
        return
    except asyncio.TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        await asyncio.to_thread(proc.wait)


class PipSession:
    """Owns the Xvnc + target app + websockify process group for one PiP session."""

    def __init__(self, app: dict, token: str, audio_only: bool) -> None:
        self.app = app
        self.token = token
        self.audio_only = audio_only
        self.xvnc: Optional[subprocess.Popen] = None
        self.guest: Optional[subprocess.Popen] = None
        self.websockify: Optional[subprocess.Popen] = None
        self.mirror: Optional[subprocess.Popen] = None

    async def start(self) -> None:
        if shutil.which(self.app["command"][0]) is None:
            raise FileNotFoundError(self.app["command"][0])

        passwd_path = await self._write_vnc_passwd()

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

        if not await _wait_port("127.0.0.1", VNC_RFB_PORT, timeout=5.0):
            raise RuntimeError(f"Xvnc did not start listening on {VNC_RFB_PORT}")

        env = {**os.environ, "DISPLAY": DISPLAY}
        self.guest = subprocess.Popen(
            self.app["command"],
            env=env,
            preexec_fn=os.setsid,
        )

        if self.audio_only:
            return

        novnc = _novnc_dir()
        if novnc is None:
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

        if not await _wait_port(VNC_BIND, VNC_WEB_PORT, timeout=5.0):
            raise RuntimeError(f"websockify did not start listening on {VNC_WEB_PORT}")

    async def _write_vnc_passwd(self) -> str:
        path = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "vncpasswd"
        proc = await asyncio.create_subprocess_exec(
            "vncpasswd", "-f",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=self.token[:8].encode())
        if proc.returncode != 0:
            raise RuntimeError(f"vncpasswd failed: {stderr.decode(errors='replace')}")
        path.write_bytes(stdout)
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

    async def stop(self) -> None:
        # Reverse start order so children die first.
        for proc in (self.mirror, self.websockify, self.guest, self.xvnc):
            await _terminate(proc)
        self.mirror = self.websockify = self.guest = self.xvnc = None


class Plugin:
    session: Optional[PipSession] = None
    _lock: Optional[asyncio.Lock] = None

    # ----- helpers ---------------------------------------------------------

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _load_settings(self) -> dict:
        path = _settings_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _save_settings(self, data: dict) -> None:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    def _all_apps(self) -> list:
        settings = self._load_settings()
        custom = settings.get("custom_apps", [])
        return DEFAULT_APPS + [c for c in custom if "id" in c and "command" in c]

    # ----- frontend callables ---------------------------------------------

    async def list_apps(self) -> list:
        return self._all_apps()

    async def add_custom_app(self, app_id: str, label: str, command: str) -> dict:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return {"ok": False, "error": f"parse_error:{exc}"}
        if not argv:
            return {"ok": False, "error": "empty_command"}
        settings = self._load_settings()
        custom = [c for c in settings.get("custom_apps", []) if c.get("id") != app_id]
        custom.append({"id": app_id, "label": label, "command": argv})
        settings["custom_apps"] = custom
        self._save_settings(settings)
        return {"ok": True}

    async def remove_custom_app(self, app_id: str) -> dict:
        settings = self._load_settings()
        settings["custom_apps"] = [
            c for c in settings.get("custom_apps", []) if c.get("id") != app_id
        ]
        self._save_settings(settings)
        return {"ok": True}

    async def settings_get(self, key: str, default: Any = None) -> Any:
        return self._load_settings().get(key, default)

    async def settings_set(self, key: str, value: Any) -> dict:
        data = self._load_settings()
        data[key] = value
        self._save_settings(data)
        return {"ok": True}

    async def check_dependencies(self) -> dict:
        return {
            "Xvnc": shutil.which("Xvnc") is not None,
            "vncpasswd": shutil.which("vncpasswd") is not None,
            "websockify": shutil.which("websockify") is not None,
            "novnc": _novnc_dir() is not None,
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
        except asyncio.TimeoutError:
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

            app = next((a for a in self._all_apps() if a["id"] == app_id), None)
            if app is None:
                return {"ok": False, "error": "unknown_app"}

            if shutil.which("Xvnc") is None:
                return {"ok": False, "error": "missing_dependency:Xvnc"}

            token = secrets.token_hex(8)
            session = PipSession(app, token, audio_only=audio_only)
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
                (Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "vncpasswd").unlink(missing_ok=True)
            return {"ok": True}

    # ----- Discord GameMirror ----------------------------------------------

    async def _find_gamescope_pw_node(self) -> Optional[str]:
        proc = await asyncio.create_subprocess_exec(
            "pw-cli", "ls", "Node",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        current_id: Optional[str] = None
        for line in stdout.decode(errors="replace").splitlines():
            line = line.strip()
            if line.startswith("id "):
                # "id 42, type PipeWire:Interface:Node/3"
                current_id = line.split()[1].rstrip(",")
            elif "gamescope" in line.lower() and current_id is not None:
                return current_id
        return None

    async def start_game_mirror(self) -> dict:
        async with self._get_lock():
            if self.session is None:
                return {"ok": False, "error": "no_session"}
            if self.session.mirror is not None:
                return {"ok": False, "error": "already_mirroring"}
            if shutil.which("gst-launch-1.0") is None:
                return {"ok": False, "error": "missing_dependency:gstreamer"}

            node_id = await self._find_gamescope_pw_node()
            if node_id is None:
                return {"ok": False, "error": "no_gamescope_pw_node"}

            env = {**os.environ, "DISPLAY": DISPLAY}
            self.session.mirror = subprocess.Popen(
                [
                    "gst-launch-1.0", "-q",
                    "pipewiresrc", f"target-object={node_id}",
                    "!", "videoconvert",
                    "!", "ximagesink", "sync=false",
                ],
                env=env,
                preexec_fn=os.setsid,
            )

            # Give the sink a moment to create its window, then rename + fullscreen.
            await asyncio.sleep(1.2)
            mirror_pid = self.session.mirror.pid
            if shutil.which("xdotool") is not None:
                with contextlib.suppress(Exception):
                    proc = await asyncio.create_subprocess_exec(
                        "xdotool", "search", "--pid", str(mirror_pid),
                        env=env,
                        stdout=asyncio.subprocess.PIPE,
                    )
                    out, _ = await proc.communicate()
                    wid = out.decode().strip().splitlines()[0:1]
                    if wid:
                        await asyncio.create_subprocess_exec(
                            "xdotool", "set_window", "--name", "GameMirror", wid[0],
                            env=env,
                        )
            if shutil.which("wmctrl") is not None:
                with contextlib.suppress(Exception):
                    p = await asyncio.create_subprocess_exec(
                        "wmctrl", "-r", "GameMirror", "-b", "add,fullscreen",
                        env=env,
                    )
                    await p.wait()
            return {"ok": True}

    async def stop_game_mirror(self) -> dict:
        async with self._get_lock():
            if self.session is None or self.session.mirror is None:
                return {"ok": True}
            await _terminate(self.session.mirror)
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
