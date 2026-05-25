"""Per-guest volume control via pactl."""

from __future__ import annotations

import asyncio
import shutil


async def _pactl_list_sink_inputs() -> str:
    if shutil.which("pactl") is None:
        return ""
    proc = await asyncio.create_subprocess_exec(
        "pactl", "list", "sink-inputs",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    return out.decode(errors="replace")


def parse_sink_inputs_for_pid(pactl_output: str, pid: int) -> list[str]:
    """Return the sink-input ids whose application.process.id == pid.

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
    target = str(pid)
    for raw in pactl_output.splitlines():
        line = raw.strip()
        if line.startswith("Sink Input #"):
            if sink_id is not None and sink_pid == target:
                matches.append(sink_id)
            sink_id = line[len("Sink Input #"):].strip()
            sink_pid = None
        elif "application.process.id" in line and "=" in line:
            sink_pid = line.split("=", 1)[1].strip().strip('"')
    if sink_id is not None and sink_pid == target:
        matches.append(sink_id)
    return matches


async def set_guest_volume(guest_pid: int, percent: int) -> dict:
    """Set the volume of every sink-input belonging to ``guest_pid``.

    ``percent`` clamped to 0..150 (pactl allows up to 153 % but staying
    sane). Returns dict with ok/error and count of inputs that received
    the change.
    """
    if shutil.which("pactl") is None:
        return {"ok": False, "error": "missing_dependency:pactl"}
    percent = max(0, min(150, int(percent)))
    output = await _pactl_list_sink_inputs()
    sink_inputs = parse_sink_inputs_for_pid(output, guest_pid)
    if not sink_inputs:
        return {"ok": True, "count": 0, "note": "no_audio_yet"}
    affected = 0
    for sid in sink_inputs:
        proc = await asyncio.create_subprocess_exec(
            "pactl", "set-sink-input-volume", sid, f"{percent}%",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await proc.wait() == 0:
            affected += 1
    return {"ok": True, "count": affected, "percent": percent}
