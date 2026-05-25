"""One-click update via GitHub release polling.

The repo is private, so the user supplies a PAT in DeckPiP settings
(``github_token``). The updater hits the GitHub API to compare the
asset's SHA / created_at against what we have on disk, and runs the
bundled ``setup.sh`` if newer.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from pathlib import Path
from typing import Any

from deckpip.settings import SettingsStore

# Hardcoded repo for now; could be parameterised in settings later.
REPO = "NelleYn/Steamdeck-Plugins"
RELEASE_TAG = "dev"
API_URL = f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}"


async def check_release(store: SettingsStore) -> dict[str, Any]:
    token = store.get("github_token")
    if not token:
        return {"ok": False, "error": "no_token"}

    def _fetch() -> dict[str, Any]:
        req = urllib.request.Request(
            API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "DeckPiP-updater",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    try:
        data = await asyncio.to_thread(_fetch)
    except Exception as exc:
        return {"ok": False, "error": f"fetch_failed:{exc}"}

    return {
        "ok": True,
        "tag_name": data.get("tag_name"),
        "name": data.get("name"),
        "published_at": data.get("published_at"),
        "body": (data.get("body") or "")[:1024],
    }


async def run_setup(plugin_dir: Path) -> dict[str, Any]:
    """Run ``setup.sh`` from the installed plugin. Requires a checkout
    on disk; the easy case is when DeckPiP was installed via setup.sh
    in the first place and the source dir is still around.

    For the in-place case we just re-run the script that ships in the
    plugin and ask the user to take it from there.
    """
    script = Path(plugin_dir) / "setup.sh"
    if not script.exists():
        return {"ok": False, "error": "setup_sh_missing"}
    proc = await asyncio.create_subprocess_exec(
        "bash", str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=900)
    except TimeoutError:
        proc.kill()
        return {"ok": False, "error": "timeout"}
    return {
        "ok": proc.returncode == 0,
        "rc": proc.returncode,
        "stdout": stdout.decode(errors="replace")[-2000:],
        "stderr": stderr.decode(errors="replace")[-2000:],
    }
