"""Per-guest volume control via pactl."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
from pathlib import Path

from deckpip.session import _as_user_argv, deck_env


async def _pactl_list_sink_inputs() -> str:
    if shutil.which("pactl") is None:
        return ""
    proc = await asyncio.create_subprocess_exec(
        *_as_user_argv(["pactl", "list", "sink-inputs"]),
        env=deck_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    return out.decode(errors="replace")


def parse_sink_inputs_for_pids(pactl_output: str, pids: set[int]) -> list[str]:
    """Return the sink-input ids whose application.process.id is in ``pids``.

    pactl output looks like:

        Sink Input #321
                Driver: <native>
                ...
                application.process.id = "12345"
                application.process.binary = "Discord"
    """
    sink_id: str | None = None
    sink_pid: str | None = None
    matches: list[str] = []
    targets = {str(p) for p in pids}

    def _flush() -> None:
        if sink_id is not None and sink_pid in targets:
            matches.append(sink_id)

    for raw in pactl_output.splitlines():
        line = raw.strip()
        if line.startswith("Sink Input #"):
            _flush()
            sink_id = line[len("Sink Input #"):].strip()
            sink_pid = None
        elif "application.process.id" in line and "=" in line:
            sink_pid = line.split("=", 1)[1].strip().strip('"')
    _flush()
    return matches


def parse_sink_inputs_for_pid(pactl_output: str, pid: int) -> list[str]:
    """Backwards-compatible single-pid wrapper around
    :func:`parse_sink_inputs_for_pids`."""
    return parse_sink_inputs_for_pids(pactl_output, {pid})


def _descendant_pids(root_pid: int, proc_root: Path = Path("/proc")) -> set[int]:
    """All pids in the process subtree rooted at ``root_pid`` (inclusive).

    Under the ``_root`` flag the guest is launched via ``runuser -u deck --``,
    so ``guest.pid`` is the launcher and the real audio-producing process is a
    descendant whose pid PulseAudio reports. We walk /proc once to map ppid ->
    children, then collect the subtree.
    """
    children: dict[int, list[int]] = {}
    try:
        entries = [p.name for p in proc_root.iterdir() if p.name.isdigit()]
    except OSError:
        return {root_pid}
    for name in entries:
        try:
            stat = (proc_root / name / "status").read_text()
        except OSError:
            continue
        ppid = 0
        for stat_line in stat.splitlines():
            if stat_line.startswith("PPid:"):
                with contextlib.suppress(ValueError):
                    ppid = int(stat_line.split(":", 1)[1].strip())
                break
        children.setdefault(ppid, []).append(int(name))

    out: set[int] = set()
    stack = [root_pid]
    while stack:
        pid = stack.pop()
        if pid in out:
            continue
        out.add(pid)
        stack.extend(children.get(pid, []))
    return out


async def set_guest_volume(guest_pid: int, percent: int) -> dict:
    """Set the volume of every sink-input belonging to ``guest_pid`` or any
    of its descendant processes.

    ``percent`` clamped to 0..150 (pactl allows up to 153 % but staying
    sane). Returns dict with ok/error and count of inputs that received
    the change.
    """
    if shutil.which("pactl") is None:
        return {"ok": False, "error": "missing_dependency:pactl"}
    percent = max(0, min(150, int(percent)))
    output = await _pactl_list_sink_inputs()
    pids = await asyncio.to_thread(_descendant_pids, guest_pid)
    sink_inputs = parse_sink_inputs_for_pids(output, pids)
    if not sink_inputs:
        return {"ok": True, "count": 0, "note": "no_audio_yet"}
    affected = 0
    for sid in sink_inputs:
        proc = await asyncio.create_subprocess_exec(
            *_as_user_argv(["pactl", "set-sink-input-volume", sid, f"{percent}%"]),
            env=deck_env(),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await proc.wait() == 0:
            affected += 1
    return {"ok": True, "count": affected, "percent": percent}
