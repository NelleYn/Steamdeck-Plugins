"""Push-to-talk: inject keypress into the Xvnc display so Discord's PTT picks it up.

The Discord (or any other guest) running on DISPLAY=:42 sees a synthetic
key event. By default we use Ctrl+Shift+M which Discord remaps to PTT
when configured; users can override the key combo in settings.
"""

from __future__ import annotations

import asyncio
import shutil

from deckpip.session import DISPLAY


async def send_key(key_combo: str, action: str) -> dict:
    """`action` is "press" or "release". `key_combo` is xdotool syntax,
    e.g. "ctrl+shift+m"."""
    if shutil.which("xdotool") is None:
        return {"ok": False, "error": "missing_dependency:xdotool"}
    if action not in ("press", "release", "key"):
        return {"ok": False, "error": "bad_action"}
    env = {"DISPLAY": DISPLAY}
    cmd = ["xdotool", "key" + ("up" if action == "release" else "down" if action == "press" else ""), key_combo]
    # xdotool subcommands: keydown / keyup / key
    if action == "press":
        cmd = ["xdotool", "keydown", key_combo]
    elif action == "release":
        cmd = ["xdotool", "keyup", key_combo]
    else:
        cmd = ["xdotool", "key", key_combo]
    proc = await asyncio.create_subprocess_exec(*cmd, env={**env})
    rc = await proc.wait()
    return {"ok": rc == 0, "rc": rc}
