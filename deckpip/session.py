"""PipSession: lifecycle of Xvnc + guest app + websockify."""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
import subprocess
from pathlib import Path

DISPLAY = ":42"
GEOMETRY = "1280x800"
DEPTH = "24"

VNC_BIND = "127.0.0.1"
VNC_RFB_PORT = 5942
VNC_WEB_PORT = 6901

# Decky plugins with _root flag run main.py as root, but Xvnc / guest apps
# need to run as the desktop user so they can talk to PulseAudio, read
# ~/.config and ~/.var (Flatpak), and own /tmp/.X42-lock. We drop privileges
# via `runuser -u <user> --` if we're actually root.
DECK_USER = "deck"


def _as_user_argv(argv: list[str]) -> list[str]:
    """Wrap argv with runuser so it runs as DECK_USER, if we are root and
    runuser is available. No-op otherwise."""
    if os.geteuid() != 0:
        return argv
    runuser = shutil.which("runuser")
    if runuser is None:
        return argv
    return [runuser, "-u", DECK_USER, "--", *argv]


NOVNC_CANDIDATES = [
    "/usr/share/novnc",
    "/usr/share/webapps/novnc",
    "/usr/lib/novnc",
]


def novnc_dir(runtime_dir: Path | None = None) -> str | None:
    """Prefer the vendored copy under runtime_dir/vendored if present,
    otherwise fall back to the system-wide install paths."""
    if runtime_dir is not None:
        from deckpip.vendoring import vendored_novnc
        vendored = vendored_novnc(runtime_dir)
        if vendored is not None:
            return str(vendored)
    for path in NOVNC_CANDIDATES:
        if Path(path, "vnc.html").exists():
            return path
    return None


def websockify_argv(runtime_dir: Path | None = None) -> list[str] | None:
    """Build the leading argv for websockify, preferring the vendored
    binary if present. Returns None if no copy is available."""
    if runtime_dir is not None:
        from deckpip.vendoring import vendored_websockify
        vw = vendored_websockify(runtime_dir)
        if vw is not None:
            return [str(vw)]
    system = shutil.which("websockify")
    if system is not None:
        return [system]
    return None


async def wait_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Active-wait until TCP port accepts a connection, or give up."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=0.5
            )
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return True
        except (TimeoutError, ConnectionRefusedError, OSError):
            await asyncio.sleep(0.1)
    return False


async def terminate(proc: subprocess.Popen | None, grace: float = 3.0) -> None:
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
    except TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        await asyncio.to_thread(proc.wait)


class PipSession:
    """Owns the Xvnc + target app + websockify process group for one session."""

    def __init__(
        self,
        app: dict,
        token: str,
        audio_only: bool,
        runtime_dir: Path,
    ) -> None:
        self.app = app
        self.token = token
        self.audio_only = audio_only
        self.runtime_dir = Path(runtime_dir)
        self.xvnc: subprocess.Popen | None = None
        self.guest: subprocess.Popen | None = None
        self.websockify: subprocess.Popen | None = None
        self.mirror: subprocess.Popen | None = None
        self.paused: bool = False

    async def start(self) -> None:
        if shutil.which(self.app["command"][0]) is None:
            raise FileNotFoundError(self.app["command"][0])

        passwd_path = await self._write_vnc_passwd()

        self.xvnc = subprocess.Popen(
            _as_user_argv([
                "Xvnc", DISPLAY,
                "-geometry", GEOMETRY,
                "-depth", DEPTH,
                "-SecurityTypes", "VncAuth",
                "-PasswordFile", passwd_path,
                "-localhost", "yes",
                "-rfbport", str(VNC_RFB_PORT),
                "-AlwaysShared",
            ]),
            preexec_fn=os.setsid,
        )
        if not await wait_port("127.0.0.1", VNC_RFB_PORT, timeout=5.0):
            raise RuntimeError(f"Xvnc did not start listening on {VNC_RFB_PORT}")

        env = {**os.environ, "DISPLAY": DISPLAY}
        self.guest = subprocess.Popen(
            _as_user_argv(self.app["command"]), env=env, preexec_fn=os.setsid
        )

        if self.audio_only:
            return

        novnc = novnc_dir(self.runtime_dir)
        if novnc is None:
            raise FileNotFoundError("novnc")
        ws_head = websockify_argv(self.runtime_dir)
        if ws_head is None:
            raise FileNotFoundError("websockify")

        self.websockify = subprocess.Popen(
            _as_user_argv([
                *ws_head,
                "--web", novnc,
                f"{VNC_BIND}:{VNC_WEB_PORT}",
                f"127.0.0.1:{VNC_RFB_PORT}",
            ]),
            preexec_fn=os.setsid,
        )
        if not await wait_port(VNC_BIND, VNC_WEB_PORT, timeout=5.0):
            raise RuntimeError(f"websockify did not start listening on {VNC_WEB_PORT}")

    async def _write_vnc_passwd(self) -> str:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        path = self.runtime_dir / "vncpasswd"
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

    def url(self) -> str | None:
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
            await terminate(proc)
        self.mirror = self.websockify = self.guest = self.xvnc = None
        # Best-effort cleanup of the per-session VNC password.
        with contextlib.suppress(FileNotFoundError):
            (self.runtime_dir / "vncpasswd").unlink()

    def _signal_all(self, sig: int) -> None:
        for proc in (self.mirror, self.websockify, self.guest, self.xvnc):
            if proc is None or proc.poll() is not None:
                continue
            try:
                pgid = os.getpgid(proc.pid)
            except ProcessLookupError:
                continue
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pgid, sig)

    def pause(self) -> None:
        """SIGSTOP every child process group. Idempotent."""
        if self.paused:
            return
        self._signal_all(signal.SIGSTOP)
        self.paused = True

    def resume(self) -> None:
        """SIGCONT every child process group. Idempotent."""
        if not self.paused:
            return
        self._signal_all(signal.SIGCONT)
        self.paused = False
