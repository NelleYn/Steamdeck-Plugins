"""rclone-driven sync for Ludusavi save backups.

rclone is a single static binary supporting 30+ cloud providers
(Drive, Dropbox, OneDrive, S3, SFTP, WebDAV, Yandex, …). We vendor a
pinned release under ``DECKY_PLUGIN_RUNTIME_DIR/vendored/rclone/`` so
the user doesn't need pacman / AUR. Configuration (creating remotes
with OAuth tokens etc.) is done with ``rclone config`` from Desktop
Mode once; the file lands at ``~/.config/rclone/rclone.conf`` and
DeckPiP picks it up automatically.

Save backups live under
``DECKY_PLUGIN_RUNTIME_DIR/ludusavi/backups``. After each Ludusavi
backup we can ``rclone sync`` that directory to ``<remote>:<path>``,
and pull it back with the reverse direction on a new install.
"""

from __future__ import annotations

import asyncio
import platform
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

RCLONE_VERSION = "1.69.1"
_BASE_URL = (
    f"https://github.com/rclone/rclone/releases/download/v{RCLONE_VERSION}"
)
_REMOTE_RE = re.compile(r"^([A-Za-z0-9_\-]+):$")


def _asset_name() -> str:
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        return f"rclone-v{RCLONE_VERSION}-linux-amd64.zip"
    if arch in ("aarch64", "arm64"):
        return f"rclone-v{RCLONE_VERSION}-linux-arm64.zip"
    raise RuntimeError(f"unsupported arch: {arch}")


def _root(runtime_dir: Path) -> Path:
    return Path(runtime_dir) / "vendored" / "rclone"


def binary_path(runtime_dir: Path) -> Path | None:
    """rclone's zip extracts to ``rclone-v<X>-linux-amd64/rclone``."""
    root = _root(runtime_dir)
    if not root.exists():
        return None
    for subdir in root.iterdir():
        candidate = subdir / "rclone"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def resolve_binary(runtime_dir: Path) -> str | None:
    vendored = binary_path(runtime_dir)
    if vendored is not None:
        return str(vendored)
    return shutil.which("rclone")


def parse_remotes(output: str) -> list[str]:
    """``rclone listremotes`` prints one remote per line as ``name:``.

    We tolerate extra whitespace and ignore any line that doesn't match.
    """
    out: list[str] = []
    for raw in output.splitlines():
        m = _REMOTE_RE.match(raw.strip())
        if m:
            out.append(m.group(1))
    return out


async def install(runtime_dir: Path, force: bool = False) -> dict:
    if binary_path(runtime_dir) is not None and not force:
        return {"ok": True, "skipped": True, "path": str(binary_path(runtime_dir))}
    root = _root(runtime_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        asset = _asset_name()
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    url = f"{_BASE_URL}/{asset}"
    archive = root / asset

    def _fetch() -> None:
        with urllib.request.urlopen(url, timeout=60) as resp, archive.open("wb") as fh:
            shutil.copyfileobj(resp, fh)

    try:
        await asyncio.to_thread(_fetch)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(root)
    except Exception as exc:
        return {"ok": False, "error": f"download_or_extract:{exc}"}
    finally:
        archive.unlink(missing_ok=True)

    bin_p = binary_path(runtime_dir)
    if bin_p is None:
        return {"ok": False, "error": "binary_missing_after_extract"}
    bin_p.chmod(0o755)
    return {"ok": True, "path": str(bin_p)}


async def _run(
    runtime_dir: Path, *args: str, timeout: float = 600.0,
) -> dict:
    bin_path = resolve_binary(runtime_dir)
    if bin_path is None:
        return {"ok": False, "error": "rclone_not_installed"}
    proc = await asyncio.create_subprocess_exec(
        bin_path, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return {"ok": False, "error": "timeout"}
    return {
        "ok": proc.returncode == 0,
        "rc": proc.returncode,
        "stdout": stdout.decode(errors="replace")[-2000:],
        "stderr": stderr.decode(errors="replace")[-2000:],
    }


async def list_remotes(runtime_dir: Path) -> dict:
    res = await _run(runtime_dir, "listremotes", timeout=15.0)
    if not res["ok"]:
        return res
    res["remotes"] = parse_remotes(res.get("stdout", ""))
    return res


async def sync_up(runtime_dir: Path, local: Path, remote: str, path: str) -> dict:
    """Push local Ludusavi backups to ``<remote>:<path>``."""
    return await _run(
        runtime_dir,
        "sync", "--progress=false",
        str(local), f"{remote}:{path}",
        timeout=1800.0,
    )


async def sync_down(runtime_dir: Path, local: Path, remote: str, path: str) -> dict:
    """Pull from ``<remote>:<path>`` into the local backup dir."""
    return await _run(
        runtime_dir,
        "sync", "--progress=false",
        f"{remote}:{path}", str(local),
        timeout=1800.0,
    )
