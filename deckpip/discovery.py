"""Discover already-installed GUI apps the user can launch in PiP.

Two sources:

* **Flatpak**: ``flatpak list --app --columns=application,name``.
  Available on every SteamOS install.
* **XDG .desktop entries** under ``~/.local/share/applications``,
  ``/usr/share/applications`` and the Flatpak exports dirs.

Each app is normalised to ``{name, exec, kind, id}``. ``exec`` is a
ready-to-run command line that the existing custom-app pipeline can
feed straight into ``shlex.split``.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

# Strip XDG placeholders (%f %F %u %U %i %c %k %m %n %v %D) from Exec=.
_EXEC_PLACEHOLDER = re.compile(r" ?%[fFuUikcmnvND]")


def parse_desktop_entry(text: str) -> dict | None:
    """Parse a ``.desktop`` file into ``{name, exec}`` or None if it isn't
    an actual application that we should expose."""
    in_main = False
    name: str | None = None
    exec_cmd: str | None = None
    type_: str | None = None
    no_display = False
    terminal = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            # New section — only the very first [Desktop Entry] block counts.
            if line == "[Desktop Entry]":
                in_main = True
                continue
            if in_main:
                break
            continue
        if not in_main or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key == "Name" and name is None:
            name = val
        elif key == "Exec" and exec_cmd is None:
            exec_cmd = val
        elif key == "Type":
            type_ = val
        elif key == "NoDisplay" and val.lower() == "true":
            no_display = True
        elif key == "Hidden" and val.lower() == "true":
            no_display = True
        elif key == "Terminal" and val.lower() == "true":
            terminal = True
    if type_ != "Application" or no_display or not name or not exec_cmd:
        return None
    # Strip XDG placeholders and any leading "env" wrappers that aren't ours
    # to worry about. Keep the rest verbatim so flatpak-spawn etc. still work.
    cleaned = _EXEC_PLACEHOLDER.sub("", exec_cmd).strip()
    if terminal:
        # We have no terminal in Xvnc :42, so wrap in xterm -e if present.
        cleaned = f"xterm -e {cleaned}"
    return {"name": name, "exec": cleaned}


def parse_flatpak_list(stdout: str) -> list[dict]:
    """Parse ``flatpak list --columns=application,name`` output."""
    apps: list[dict] = []
    for raw in stdout.splitlines():
        # Tab-separated by default.
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        app_id = parts[0].strip()
        display = parts[1].strip() or app_id
        if not app_id or app_id.lower() == "application id":
            continue
        apps.append({
            "name": display,
            "exec": f"flatpak run {app_id}",
            "kind": "flatpak",
            "id": app_id,
        })
    return apps


async def discover_flatpaks() -> list[dict]:
    if shutil.which("flatpak") is None:
        return []
    proc = await asyncio.create_subprocess_exec(
        "flatpak", "list", "--app", "--columns=application,name",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return []
    return parse_flatpak_list(out.decode(errors="replace"))


# Built-in system paths get sourced from outside ``home``. Tests pass an
# empty list so they don't accidentally pick up real system entries.
SYSTEM_PATHS_DEFAULT: list[Path] = [
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
]


def desktop_search_paths(home: Path, system_paths: list[Path] | None = None) -> list[Path]:
    sys_paths = SYSTEM_PATHS_DEFAULT if system_paths is None else system_paths
    return [
        home / ".local" / "share" / "applications",
        home / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
        *sys_paths,
    ]


def discover_desktop_files(home: Path, system_paths: list[Path] | None = None) -> list[dict]:
    seen_ids: set[str] = set()
    apps: list[dict] = []
    for root in desktop_search_paths(home, system_paths):
        if not root.exists():
            continue
        try:
            entries = sorted(root.glob("*.desktop"))
        except OSError:
            continue
        for f in entries:
            entry_id = f.stem
            if entry_id in seen_ids:
                continue
            try:
                parsed = parse_desktop_entry(f.read_text(errors="replace"))
            except OSError:
                continue
            if parsed is None:
                continue
            seen_ids.add(entry_id)
            apps.append({
                "name": parsed["name"],
                "exec": parsed["exec"],
                "kind": "desktop",
                "id": entry_id,
            })
    return apps


async def discover_all(home: Path | None = None) -> list[dict]:
    """Union of Flatpak and .desktop apps, deduplicated by id, sorted by
    name for a stable UI."""
    if home is None:
        home = Path.home()
    flatpaks = await discover_flatpaks()
    desktops = discover_desktop_files(home)
    by_id: dict[str, dict] = {}
    for app in flatpaks:
        by_id[app["id"]] = app
    for app in desktops:
        by_id.setdefault(app["id"], app)
    out = list(by_id.values())
    out.sort(key=lambda a: a["name"].lower())
    return out
