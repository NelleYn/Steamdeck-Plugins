"""Forward pointer events from Steam UI to the Xvnc display.

In Gaming Mode the Steam Deck's right trackpad generates regular
pointer events for Steam UI's CEF. By default those land on our
overlay container as drag/resize gestures. When the user switches
``inputMode`` to ``pointer``, the overlay layers a transparent
``pointer-capture`` div over the iframe and forwards each event to
``xdotool`` on ``DISPLAY=:42``, so clicks inside the PiP actually
hit Discord/Telegram/whatever is running on Xvnc.

Without this, the PiP is read-only on a stock Deck (no BT mouse).
"""

from __future__ import annotations

import asyncio
import shutil

from deckpip.session import DISPLAY, GEOMETRY


def _xvnc_size() -> tuple[int, int]:
    """Parse GEOMETRY (e.g. ``1280x800x24``) into (width, height)."""
    parts = GEOMETRY.split("x")
    return int(parts[0]), int(parts[1])


def pct_to_pixels(x_pct: float, y_pct: float) -> tuple[int, int]:
    """Translate an overlay-relative percent coordinate into pixel
    coordinates inside Xvnc, clamped to the screen bounds."""
    w, h = _xvnc_size()
    px = max(0, min(w - 1, int(x_pct * w / 100)))
    py = max(0, min(h - 1, int(y_pct * h / 100)))
    return px, py


async def mouse_move(x_pct: float, y_pct: float) -> dict:
    if shutil.which("xdotool") is None:
        return {"ok": False, "error": "missing_dependency:xdotool"}
    px, py = pct_to_pixels(x_pct, y_pct)
    env = {"DISPLAY": DISPLAY}
    proc = await asyncio.create_subprocess_exec(
        "xdotool", "mousemove", "--sync", str(px), str(py),
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return {"ok": (await proc.wait()) == 0}


async def mouse_button(button: int, action: str) -> dict:
    """``action`` is ``press`` / ``release`` / ``click``; ``button`` is
    1 (left), 2 (middle), 3 (right), 4 (scroll up), 5 (scroll down)."""
    if shutil.which("xdotool") is None:
        return {"ok": False, "error": "missing_dependency:xdotool"}
    cmd_map = {"press": "mousedown", "release": "mouseup", "click": "click"}
    cmd = cmd_map.get(action)
    if cmd is None or button not in (1, 2, 3, 4, 5):
        return {"ok": False, "error": "bad_input"}
    env = {"DISPLAY": DISPLAY}
    proc = await asyncio.create_subprocess_exec(
        "xdotool", cmd, str(button),
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return {"ok": (await proc.wait()) == 0}


async def mouse_scroll(direction: str) -> dict:
    """``direction`` is ``up`` / ``down`` — maps to buttons 4/5."""
    button = {"up": 4, "down": 5}.get(direction)
    if button is None:
        return {"ok": False, "error": "bad_direction"}
    return await mouse_button(button, "click")
