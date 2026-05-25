"""Lightweight MPRIS client via ``dbus-send`` — no playerctl dep.

If Discord / Spotify / a YouTube tab is playing media on the user's
session bus, it announces an ``org.mpris.MediaPlayer2.<player>`` bus
name. We list those, expose play/pause/next/prev/stop actions, and
let the panel surface a transport bar.

We deliberately use ``dbus-send`` (libdbus, base SteamOS) rather than
``playerctl`` to keep the dep footprint at zero. dbus output is
plain text we parse line-by-line.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil

from deckpip.session import DISPLAY

MPRIS_PREFIX = "org.mpris.MediaPlayer2."

_VALID_ACTIONS = {"Play", "Pause", "PlayPause", "Next", "Previous", "Stop"}


def parse_listnames(output: str) -> list[str]:
    """Return the MPRIS bus names from the ``ListNames`` dbus-send dump.

    Output sample::

        method return time=1.0 sender=org.freedesktop.DBus -> destination=:1.42 reply_serial=2
           array [
              string "org.freedesktop.DBus"
              string "org.mpris.MediaPlayer2.spotify"
              string ":1.50"
           ]
    """
    names: list[str] = []
    for raw in output.splitlines():
        m = re.search(r'string\s+"(org\.mpris\.MediaPlayer2\.[^"]+)"', raw)
        if m:
            names.append(m.group(1))
    return names


def parse_metadata(output: str) -> dict[str, str]:
    """Parse ``Get``/``GetAll`` Property output. Returns a flat dict of
    string values we actually care about (title, artist, album, status)."""
    result: dict[str, str] = {}
    # Status comes back as a single ``variant string "Playing"`` line.
    status_match = re.search(r'variant\s+string\s+"(Playing|Paused|Stopped)"', output)
    if status_match:
        result["status"] = status_match.group(1)
    # Metadata keys live as ``string "xesam:title"`` followed by their
    # corresponding ``variant string "value"`` (single-string keys) or
    # ``variant array [ string "value" ... ]`` (artist array). We only
    # care about the first string value for each key.
    keys = ("xesam:title", "xesam:album", "xesam:artist")
    for key in keys:
        m = re.search(
            rf'string\s+"{re.escape(key)}".*?string\s+"([^"]*)"',
            output,
            re.DOTALL,
        )
        if m:
            short = key.split(":", 1)[1]
            result[short] = m.group(1)
    return result


async def _dbus_send(*args: str) -> tuple[int, str]:
    if shutil.which("dbus-send") is None:
        return -1, ""
    env = {**os.environ, "DISPLAY": DISPLAY}
    proc = await asyncio.create_subprocess_exec(
        "dbus-send", "--session", "--print-reply", *args,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    return proc.returncode or 0, out.decode(errors="replace")


async def list_players() -> list[dict]:
    """Returns a list of ``{bus_name, status, title, artist, album}``."""
    if shutil.which("dbus-send") is None:
        return []
    rc, out = await _dbus_send(
        "--dest=org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus.ListNames",
    )
    if rc != 0:
        return []
    names = parse_listnames(out)
    players: list[dict] = []
    for bus in names:
        meta: dict[str, str] = {"bus_name": bus}
        _, status_out = await _dbus_send(
            f"--dest={bus}",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player",
            "string:PlaybackStatus",
        )
        meta.update(parse_metadata(status_out))
        _, md_out = await _dbus_send(
            f"--dest={bus}",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player",
            "string:Metadata",
        )
        meta.update(parse_metadata(md_out))
        players.append(meta)
    return players


async def player_action(bus_name: str, action: str) -> dict:
    if action not in _VALID_ACTIONS:
        return {"ok": False, "error": "bad_action"}
    if not bus_name.startswith(MPRIS_PREFIX):
        return {"ok": False, "error": "bad_bus_name"}
    if shutil.which("dbus-send") is None:
        return {"ok": False, "error": "missing_dependency:dbus-send"}
    rc, _ = await _dbus_send(
        f"--dest={bus_name}",
        "/org/mpris/MediaPlayer2",
        f"org.mpris.MediaPlayer2.Player.{action}",
    )
    return {"ok": rc == 0}
