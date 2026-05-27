"""Save-file sync via Ludusavi.

Ludusavi (mtkennerly/ludusavi, MIT licensed) is a save-backup tool
that reads PCGamingWiki manifests to locate save files, totally
independent of Steam — which means it works for **non-Steam games and
pirated copies** the same way it works for legitimate ones.

We vendor a pinned static Linux release into
``DECKY_PLUGIN_RUNTIME_DIR/vendored/ludusavi/`` so the user never has
to deal with pacman or AUR. Backups go to
``DECKY_PLUGIN_RUNTIME_DIR/ludusavi/backups`` by default; the user can
override via settings (and point it at an rclone/cloud-synced folder).

API surface kept small:

* ``backup(game=None)`` — back up everything or one game
* ``restore(game=None)`` — restore
* ``find_games(...)`` — list candidates so the UI can show what's
  detectable
* All four return parsed Ludusavi --api JSON to the frontend.
"""

from __future__ import annotations

import asyncio
import json
import platform
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

LUDUSAVI_VERSION = "0.27.0"
_BASE_URL = (
    "https://github.com/mtkennerly/ludusavi/releases/download/"
    f"v{LUDUSAVI_VERSION}"
)


def _asset_name() -> str:
    """Pick the right asset for the host architecture. SteamOS is x86_64;
    we still want to behave on aarch64 dev machines."""
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        return f"ludusavi-v{LUDUSAVI_VERSION}-linux.tar.gz"
    if arch in ("aarch64", "arm64"):
        return f"ludusavi-v{LUDUSAVI_VERSION}-linux-arm64.tar.gz"
    raise RuntimeError(f"unsupported arch: {arch}")


def _root(runtime_dir: Path) -> Path:
    return Path(runtime_dir) / "vendored" / "ludusavi"


def binary_path(runtime_dir: Path) -> Path | None:
    """Where the vendored ludusavi binary lives, or None if not installed."""
    # Static tar bundles `ludusavi` at the archive root.
    candidate = _root(runtime_dir) / "ludusavi"
    return candidate if candidate.exists() and candidate.is_file() else None


def resolve_binary(runtime_dir: Path) -> str | None:
    """Vendored copy preferred, fallback to anything on PATH."""
    vendored = binary_path(runtime_dir)
    if vendored is not None:
        return str(vendored)
    return shutil.which("ludusavi")


def default_backup_dir(runtime_dir: Path) -> Path:
    return Path(runtime_dir) / "ludusavi" / "backups"


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
    except Exception as exc:
        return {"ok": False, "error": f"download:{exc}"}

    try:
        if asset.endswith(".tar.gz") or asset.endswith(".tgz"):
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(root, filter="data")
        elif asset.endswith(".zip"):
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(root)
        else:
            return {"ok": False, "error": f"unknown_archive_type:{asset}"}
    except Exception as exc:
        return {"ok": False, "error": f"extract:{exc}"}
    finally:
        archive.unlink(missing_ok=True)

    bin_p = binary_path(runtime_dir)
    if bin_p is None:
        return {"ok": False, "error": "binary_missing_after_extract"}
    bin_p.chmod(0o755)
    return {"ok": True, "path": str(bin_p)}


async def _run(
    runtime_dir: Path,
    *args: str,
    timeout: float = 120.0,
    try_update: bool = False,
) -> dict:
    """Invoke the vendored ludusavi binary with --api. ``try_update`` adds
    --try-update, which pulls a fresh PCGamingWiki manifest — only worth
    paying that cost for `find`, not for every auto-backup."""
    bin_path = resolve_binary(runtime_dir)
    if bin_path is None:
        return {"ok": False, "error": "ludusavi_not_installed"}
    backup_dir = default_backup_dir(runtime_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    cmd = [bin_path, "--api"]
    if try_update:
        cmd.append("--try-update")
    cmd.extend(args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return {"ok": False, "error": "timeout"}
    raw = stdout.decode(errors="replace")
    try:
        payload: Any = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        payload = {"raw": raw[:2000]}
    return {
        "ok": proc.returncode == 0,
        "rc": proc.returncode,
        "payload": payload,
        "stderr": stderr.decode(errors="replace")[-1000:],
    }


async def backup(runtime_dir: Path, game: str | None = None) -> dict:
    args = ["backup", "--force", "--path", str(default_backup_dir(runtime_dir))]
    if game:
        args.append(game)
    return await _run(runtime_dir, *args, timeout=600.0)


async def restore(runtime_dir: Path, game: str | None = None) -> dict:
    args = ["restore", "--force", "--path", str(default_backup_dir(runtime_dir))]
    if game:
        args.append(game)
    return await _run(runtime_dir, *args, timeout=600.0)


async def find_games(runtime_dir: Path, query: str | None = None) -> dict:
    args = ["find"]
    if query:
        args.append(query)
    return await _run(runtime_dir, *args, timeout=60.0, try_update=True)


def parse_backup_summary(payload: Any) -> dict:
    """Pull a {games: int, total_bytes: int, errors: int} summary from the
    Ludusavi --api JSON, gracefully handling shape changes between
    versions."""
    if not isinstance(payload, dict):
        return {"games": 0, "total_bytes": 0, "errors": 0}
    overall = payload.get("overall", {}) if isinstance(payload.get("overall"), dict) else {}
    games = payload.get("games", {})
    total_bytes = overall.get("totalBytes", 0)
    if not isinstance(total_bytes, int):
        total_bytes = 0
    return {
        "games": len(games) if isinstance(games, dict) else 0,
        "total_bytes": total_bytes,
        "errors": overall.get("processedGames", 0) and 0,
    }
