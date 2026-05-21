"""GameMirror: mirror the real gamescope output into Xvnc :42.

Lets Discord (running on the same Xvnc) share the game in Go Live
without going through xdg-desktop-portal, which is broken in Gaming
Mode.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess

from deckpip.session import DISPLAY


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
    current_id: str | None = None
    for raw in pw_output.splitlines():
        line = raw.strip()
        if line.startswith("id "):
            current_id = line.split()[1].rstrip(",")
        elif "gamescope" in line.lower() and current_id is not None:
            return current_id
    return None


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
    # Let ximagesink create its window.
    await asyncio.sleep(1.2)
    await _rename_and_fullscreen(proc.pid, env)
    return proc


async def _rename_and_fullscreen(pid: int, env: dict) -> None:
    if shutil.which("xdotool") is not None:
        with contextlib.suppress(Exception):
            search = await asyncio.create_subprocess_exec(
                "xdotool", "search", "--pid", str(pid),
                env=env,
                stdout=asyncio.subprocess.PIPE,
            )
            out, _ = await search.communicate()
            wid_lines = out.decode().strip().splitlines()
            if wid_lines:
                rename = await asyncio.create_subprocess_exec(
                    "xdotool", "set_window", "--name", "GameMirror", wid_lines[0],
                    env=env,
                )
                await rename.wait()
    if shutil.which("wmctrl") is not None:
        with contextlib.suppress(Exception):
            wm = await asyncio.create_subprocess_exec(
                "wmctrl", "-r", "GameMirror", "-b", "add,fullscreen",
                env=env,
            )
            await wm.wait()
