"""Push-to-talk via PulseAudio source mute.

Why not xdotool-inject the Discord PTT keybind? Two reasons:

1. xdotool isn't in the SteamOS base image; injecting requires another
   pacman package.
2. The keybind approach only works if Discord is the focused window
   on Xvnc :42, and only for Discord — Mumble, Element, browser tabs
   all need separate setup.

``pactl`` ships with libpulse on every SteamOS, and toggling the
default source mute is **the** OS-level definition of PTT — works
with every voice client out of the box.
"""

from __future__ import annotations

import asyncio
import shutil


async def _set_mute(muted: bool) -> dict:
    if shutil.which("pactl") is None:
        return {"ok": False, "error": "missing_dependency:pactl"}
    proc = await asyncio.create_subprocess_exec(
        "pactl", "set-source-mute", "@DEFAULT_SOURCE@", "true" if muted else "false",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        return {"ok": False, "error": f"pactl_rc:{proc.returncode}:{stderr.decode(errors='replace').strip()[:200]}"}
    return {"ok": True}


async def ptt_press() -> dict:
    """Unmute the default microphone source (start talking)."""
    return await _set_mute(False)


async def ptt_release() -> dict:
    """Mute the default microphone source (stop talking)."""
    return await _set_mute(True)


# Legacy: old send_key API is kept callable to avoid breaking older frontends
# in the wild that called ``ptt(combo, "press"|"release")``. Maps to the new
# mute-based PTT and ignores the key combo.
async def send_key(_key_combo: str, action: str) -> dict:
    if action == "press":
        return await ptt_press()
    if action == "release":
        return await ptt_release()
    # action == "key" or anything else — interpret as a tap (toggle off then on).
    res = await ptt_press()
    if not res["ok"]:
        return res
    return await ptt_release()
