"""Battery state reader: pure /sys/class/power_supply, no extra deps."""

from __future__ import annotations

from pathlib import Path

BATTERY_ROOT = Path("/sys/class/power_supply")


def _find_battery() -> Path | None:
    if not BATTERY_ROOT.exists():
        return None
    for entry in BATTERY_ROOT.iterdir():
        try:
            t = (entry / "type").read_text().strip()
        except OSError:
            continue
        if t == "Battery":
            return entry
    return None


def read_state() -> dict:
    """Return ``{percent, charging, on_battery, present}`` or
    ``{present: False}`` if no battery is exposed (desktop / dock)."""
    bat = _find_battery()
    if bat is None:
        return {"present": False}
    try:
        cap = int((bat / "capacity").read_text().strip())
    except (OSError, ValueError):
        cap = -1
    try:
        status = (bat / "status").read_text().strip()
    except OSError:
        status = "Unknown"
    charging = status in ("Charging", "Full")
    return {
        "present": True,
        "percent": cap,
        "status": status,
        "charging": charging,
        "on_battery": not charging,
    }
