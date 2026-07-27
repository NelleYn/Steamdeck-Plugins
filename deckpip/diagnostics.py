"""Aggregates everything you'd want in a bug report."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from deckpip.system_vendor import (
    gst_launch_path,
    vncpasswd_path,
    wmctrl_path,
    xdotool_path,
    xvnc_path,
)


async def _probe(path: str | None) -> dict[str, Any]:
    if path is None:
        return {"present": False}
    out: dict[str, Any] = {"present": True, "path": path}
    try:
        proc = await asyncio.create_subprocess_exec(
            path, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        text, _ = await asyncio.wait_for(proc.communicate(), timeout=3.0)
        out["version"] = text.decode(errors="replace").strip().splitlines()[0:1]
    except Exception:
        out["version"] = None
    return out


async def _which(binary: str) -> dict[str, Any]:
    return await _probe(shutil.which(binary))


async def collect(
    runtime_dir: Path | None = None, plugin_dir: Path | None = None,
) -> dict[str, Any]:
    """Gather a self-test snapshot. Safe to call any time.

    ``plugin_dir`` lets Xvnc/vncpasswd/wmctrl/xdotool/gst-launch-1.0 resolve
    a bundled copy shipped in the release zip before falling back to PATH —
    see ``deckpip.system_vendor``.
    """
    bins = await asyncio.gather(
        _probe(xvnc_path(plugin_dir)),
        _probe(vncpasswd_path(plugin_dir)),
        _which("websockify"),
        _which("xterm"),
        _probe(wmctrl_path(plugin_dir)),
        _probe(xdotool_path(plugin_dir)),
        _probe(gst_launch_path(plugin_dir)),
        _which("pw-cli"),
        _which("flatpak"),
    )
    keys = [
        "Xvnc", "vncpasswd", "websockify", "xterm",
        "wmctrl", "xdotool", "gst-launch-1.0", "pw-cli", "flatpak",
    ]
    binaries = dict(zip(keys, bins, strict=True))

    novnc: dict[str, Any] = {"present": False}
    for p in ("/usr/share/novnc/vnc.html", "/usr/share/webapps/novnc/vnc.html", "/usr/lib/novnc/vnc.html"):
        if Path(p).exists():
            novnc = {"present": True, "path": str(Path(p).parent)}
            break

    info: dict[str, Any] = {
        "python": platform.python_version(),
        "kernel": platform.release(),
        "uname": " ".join(platform.uname()),
        "pid": os.getpid(),
        "binaries": binaries,
        "novnc": novnc,
    }
    if runtime_dir is not None:
        rdir = Path(runtime_dir)
        info["runtime_dir"] = {
            "path": str(rdir),
            "exists": rdir.exists(),
            "vncpasswd_present": (rdir / "vncpasswd").exists(),
        }
    return info
