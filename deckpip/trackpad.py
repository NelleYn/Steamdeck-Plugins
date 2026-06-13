"""Forward Steam UI pointer events to Xvnc :42 via xdotool."""

from __future__ import annotations

import asyncio
import shutil

from deckpip.session import DISPLAY, GEOMETRY, _as_user_argv


def _xvnc_size() -> tuple[int, int]:
    parts = GEOMETRY.split("x")
    return int(parts[0]), int(parts[1])


def pct_to_pixels(x_pct: float, y_pct: float) -> tuple[int, int]:
    w, h = _xvnc_size()
    px = max(0, min(w - 1, int(x_pct * w / 100)))
    py = max(0, min(h - 1, int(y_pct * h / 100)))
    return px, py


async def mouse_move(x_pct: float, y_pct: float) -> dict:
    if shutil.which("xdotool") is None:
        return {"ok": False, "error": "missing_dependency:xdotool"}
    px, py = pct_to_pixels(x_pct, y_pct)
    proc = await asyncio.create_subprocess_exec(
        *_as_user_argv(["xdotool", "mousemove", "--sync", str(px), str(py)]),
        env={"DISPLAY": DISPLAY},
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return {"ok": (await proc.wait()) == 0}


async def mouse_button(button: int, action: str) -> dict:
    if shutil.which("xdotool") is None:
        return {"ok": False, "error": "missing_dependency:xdotool"}
    cmd_map = {"press": "mousedown", "release": "mouseup", "click": "click"}
    cmd = cmd_map.get(action)
    if cmd is None or button not in (1, 2, 3, 4, 5):
        return {"ok": False, "error": "bad_input"}
    proc = await asyncio.create_subprocess_exec(
        *_as_user_argv(["xdotool", cmd, str(button)]),
        env={"DISPLAY": DISPLAY},
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return {"ok": (await proc.wait()) == 0}


async def mouse_scroll(direction: str) -> dict:
    button = {"up": 4, "down": 5}.get(direction)
    if button is None:
        return {"ok": False, "error": "bad_direction"}
    return await mouse_button(button, "click")
