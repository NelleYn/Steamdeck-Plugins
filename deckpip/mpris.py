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
    """Parse ``Get``/``GetAll`` Property output. Returns a flat dict with
    title/artist/album/status when present.

    dbus-send output is line-oriented. We walk the lines once, tracking
    the most recent ``string "xesam:foo"`` key, and when we see the next
    ``string|variant string "value"`` (skipping the variant-type lines
    that come between) we attach it. This avoids the regex pitfall of
    matching across unrelated entries when keys appear in a different
    order between calls.
    """
    result: dict[str, str] = {}
    pending_key: str | None = None
    KEY_NAMES = {"xesam:title": "title", "xesam:album": "album", "xesam:artist": "artist"}
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue

        # Top-level PlaybackStatus: ``variant string "Playing"``.
        m = re.match(r'^variant\s+string\s+"(Playing|Paused|Stopped)"\s*$', line)
        if m:
            result["status"] = m.group(1)
            continue

        # New key entry: ``string "xesam:title"``.
        m = re.match(r'^string\s+"([^"]+)"\s*$', line)
        if m:
            candidate = m.group(1)
            if candidate in KEY_NAMES:
                pending_key = candidate
            elif pending_key is not None:
                # This is the value belonging to the previous key
                # (e.g. ``string "Queen"`` inside artist array).
                result[KEY_NAMES[pending_key]] = candidate
                pending_key = None
            continue

        # Single-string value:  ``variant string "Bohemian Rhapsody"``.
        m = re.match(r'^variant\s+string\s+"([^"]*)"\s*$', line)
        if m and pending_key is not None:
            result[KEY_NAMES[pending_key]] = m.group(1)
            pending_key = None
            continue

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
