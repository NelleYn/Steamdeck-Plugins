"""PulseAudio mic mute/unmute as PTT. pactl ships with libpulse on SteamOS."""

from __future__ import annotations

import asyncio
import shutil

from deckpip.session import _as_user_argv, deck_env


async def _set_mute(muted: bool) -> dict:
    if shutil.which("pactl") is None:
        return {"ok": False, "error": "missing_dependency:pactl"}
    proc = await asyncio.create_subprocess_exec(
        *_as_user_argv([
            "pactl", "set-source-mute", "@DEFAULT_SOURCE@",
            "true" if muted else "false",
        ]),
        env=deck_env(),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"pactl_rc:{proc.returncode}:{stderr.decode(errors='replace').strip()[:200]}",
        }
    return {"ok": True}


async def ptt_press() -> dict:
    return await _set_mute(False)


async def ptt_release() -> dict:
    return await _set_mute(True)


async def send_key(_key_combo: str, action: str) -> dict:
    if action == "press":
        return await ptt_press()
    if action == "release":
        return await ptt_release()
    res = await ptt_press()
    if not res["ok"]:
        return res
    return await ptt_release()
