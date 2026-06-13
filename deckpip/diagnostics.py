"""Aggregates everything you'd want in a bug report."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from pathlib import Path
from typing import Any


async def _which(binary: str) -> dict[str, Any]:
    path = shutil.which(binary)
    if path is None:
        return {"present": False}
    out: dict[str, Any] = {"present": True, "path": path}
    proc = await asyncio.create_subprocess_exec(
        path, "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        text, _ = await asyncio.wait_for(proc.communicate(), timeout=3.0)
        out["version"] = text.decode(errors="replace").strip().splitlines()[0:1]
    except Exception:
        out["version"] = None
    return out


async def collect(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Gather a self-test snapshot. Safe to call any time."""
    bins = await asyncio.gather(
        _which("Xvnc"),
        _which("vncpasswd"),
        _which("websockify"),
        _which("xterm"),
        _which("wmctrl"),
        _which("xdotool"),
        _which("gst-launch-1.0"),
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
