"""Mirror desktop notifications from the Xvnc D-Bus into Decky's toaster.

Discord and Telegram emit ``org.freedesktop.Notifications.Notify`` calls
on their session bus. We listen with ``dbus-monitor`` and surface each
hit as an event back to the frontend, so the user sees DMs without
opening the PiP overlay.

Implementation notes:

* dbus-monitor runs against the **session bus of the deck user inside
  Xvnc :42**. We pass DBUS_SESSION_BUS_ADDRESS via the env we already
  set for guest apps.
* The output is line-oriented but multi-line per notification, so we
  buffer and emit only when we have a coherent block.
* No external deps. dbus-monitor ships with libdbus in the SteamOS
  base image.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import shutil
from collections.abc import Awaitable, Callable

from deckpip.session import _as_user_argv, deck_env

_APP_NAME_RE = re.compile(r'^string "(.*?)"$')


def is_dbus_header(line: str) -> bool:
    """True if ``line`` is a real dbus-monitor message header, not notification
    content that merely starts with ``signal``/``method call``.

    dbus-monitor headers always carry the message metadata (``sender=``), e.g.
    ``method call time=… sender=:1.42 → destination=… member=Notify``. A
    notification body containing a newline followed by ``method call foo`` has
    no ``sender=`` and so won't be mistaken for a block boundary.
    """
    return (
        line.startswith("method call") or line.startswith("signal")
    ) and "sender=" in line


def parse_notification_block(block: list[str]) -> dict | None:
    """Parse a dbus-monitor block into ``{app, summary, body}`` or None
    if it's not a Notify call.

    dbus-monitor outputs each method call as:

        method call ... member=Notify
           string "Discord"
           uint32 0
           string ""
           string "New message from Alice"
           string "Hello!"
           array [ ... ]
           dict entry( ... )
           int32 -1
    """
    if not block or "member=Notify" not in block[0]:
        return None
    strings: list[str] = []
    for raw in block[1:]:
        m = _APP_NAME_RE.match(raw.strip())
        if m:
            strings.append(m.group(1))
    # Notify signature: app_name, app_icon, summary, body, ...
    # The "uint32 0" (replaces_id) sits between app_name and app_icon as a
    # non-string line so it's filtered by the string-only regex.
    if len(strings) < 4:
        return None
    # strings[0] = app_name, [1] = app_icon, [2] = summary, [3] = body
    return {
        "app": strings[0],
        "summary": strings[2],
        "body": strings[3],
    }


class NotificationMirror:
    """Run dbus-monitor and invoke ``on_notification`` for each Notify
    call. Stop with ``await stop()``. Idempotent start/stop."""

    def __init__(
        self,
        on_notification: Callable[[dict], Awaitable[None]],
    ) -> None:
        self.on_notification = on_notification
        self._proc: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> dict:
        if self._proc is not None:
            return {"ok": False, "error": "already_running"}
        if shutil.which("dbus-monitor") is None:
            return {"ok": False, "error": "missing_dependency:dbus-monitor"}
        self._proc = await asyncio.create_subprocess_exec(
            *_as_user_argv([
                "dbus-monitor", "--session",
                "interface='org.freedesktop.Notifications'",
            ]),
            env=deck_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._task = asyncio.create_task(self._reader())
        return {"ok": True}

    async def stop(self) -> dict:
        if self._proc is None:
            return {"ok": True}
        with contextlib.suppress(ProcessLookupError):
            self._proc.terminate()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._proc.wait(), timeout=2.0)
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        self._proc = None
        self._task = None
        return {"ok": True}

    async def _reader(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            block: list[str] = []
            async for raw in self._proc.stdout:
                line = raw.decode(errors="replace").rstrip("\n")
                if is_dbus_header(line):
                    if block:
                        parsed = parse_notification_block(block)
                        if parsed is not None:
                            with contextlib.suppress(Exception):
                                await self.on_notification(parsed)
                    block = [line]
                elif block:
                    block.append(line)
            if block:
                parsed = parse_notification_block(block)
                if parsed is not None:
                    with contextlib.suppress(Exception):
                        await self.on_notification(parsed)
        finally:
            # dbus-monitor exited on its own (display torn down, bus gone) —
            # clear state so a future start() can spawn a fresh monitor instead
            # of being stuck on "already_running" forever.
            self._proc = None
            self._task = None
