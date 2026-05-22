"""GameMirror: mirror the real gamescope output into Xvnc :42.

Lets Discord (running on the same Xvnc) share the game in Go Live
without going through xdg-desktop-portal, which is broken in Gaming
Mode.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import subprocess

from deckpip.session import DISPLAY

log = logging.getLogger(__name__)


async def find_gamescope_pw_node() -> str | None:
    """Locate the PipeWire node that Gamescope publishes its frames on.

    Returns the node id as a string, or None if not found / pw-cli
    failed.
    """
    proc = await asyncio.create_subprocess_exec(
        "pw-cli", "ls", "Node",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    return parse_gamescope_node(stdout.decode(errors="replace"))


def parse_gamescope_node(pw_output: str) -> str | None:
    """Return the id of the first Video/Source node whose metadata mentions
    gamescope. Audio sinks named "gamescope" are intentionally skipped.

    Falls back to a name-only match if no Video class was advertised — old
    pw-cli output may not include media.class.
    """
    current_id: str | None = None
    is_video = False
    name_only_candidate: str | None = None
    for raw in pw_output.splitlines():
        line = raw.strip()
        if line.startswith("id "):
            current_id = line.split()[1].rstrip(",")
            is_video = False
        elif "media.class" in line.lower():
            is_video = "video" in line.lower()
        elif "gamescope" in line.lower() and current_id is not None:
            if is_video:
                return current_id
            if name_only_candidate is None:
                name_only_candidate = current_id
    return name_only_candidate


async def start_mirror_window() -> subprocess.Popen:
    """Spawn the gst pipeline mirroring gamescope into Xvnc :42.

    Returns the gstreamer Popen handle. Raises FileNotFoundError if
    gstreamer is missing, RuntimeError if no gamescope node was found.
    """
    if shutil.which("gst-launch-1.0") is None:
        raise FileNotFoundError("gstreamer")
    node_id = await find_gamescope_pw_node()
    if node_id is None:
        raise RuntimeError("no_gamescope_pw_node")
    env = {**os.environ, "DISPLAY": DISPLAY}
    proc = subprocess.Popen(
        [
            "gst-launch-1.0", "-q",
            "pipewiresrc", f"target-object={node_id}",
            "!", "videoconvert",
            "!", "ximagesink", "sync=false",
        ],
        env=env,
        preexec_fn=os.setsid,
    )
    await _rename_and_fullscreen(proc.pid, env)
    return proc


async def _rename_and_fullscreen(pid: int, env: dict) -> None:
    """Poll for ximagesink's window to appear, then rename + fullscreen it."""
    if shutil.which("xdotool") is None:
        log.warning("xdotool missing — GameMirror window will not be renamed")
        return

    wid = await _find_window_for_pid(pid, env, deadline_seconds=4.0)
    if wid is None:
        log.warning("xdotool found no window for gst pid=%s within 4s", pid)
        return

    with contextlib.suppress(Exception):
        rename = await asyncio.create_subprocess_exec(
            "xdotool", "set_window", "--name", "GameMirror", wid,
            env=env,
        )
        await rename.wait()

    if shutil.which("wmctrl") is None:
        log.warning("wmctrl missing — GameMirror will not be fullscreen")
        return

    with contextlib.suppress(Exception):
        wm = await asyncio.create_subprocess_exec(
            "wmctrl", "-r", "GameMirror", "-b", "add,fullscreen",
            env=env,
        )
        await wm.wait()


async def _find_window_for_pid(pid: int, env: dict, deadline_seconds: float) -> str | None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + deadline_seconds
    while loop.time() < deadline:
        await asyncio.sleep(0.2)
        try:
            search = await asyncio.create_subprocess_exec(
                "xdotool", "search", "--pid", str(pid),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await search.communicate()
        except Exception:
            continue
        lines = out.decode(errors="replace").strip().splitlines()
        if lines:
            return lines[0]
    return None
