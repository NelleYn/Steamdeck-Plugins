"""One-click update via GitHub release polling.

The repo is private, so the user supplies a PAT in DeckPiP settings
(``github_token``). The updater hits the GitHub API to compare the
asset's published_at against what we have on disk, and runs the
bundled ``setup.sh`` if newer.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
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
    if not token or not isinstance(token, str):
        return {
            "ok": False,
            "error": "no_token",
            "hint": (
                "Set your GitHub PAT in System -> GitHub PAT first. "
                "Needs 'Contents: read' on this private repo."
            ),
        }

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
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return {
                "ok": False, "error": "auth_failed",
                "hint": "GitHub rejected the token. Re-generate the PAT.",
            }
        if exc.code == 404:
            return {
                "ok": False, "error": "not_found",
                "hint": (
                    "Either the dev release tag doesn't exist yet, or the PAT "
                    "is missing 'Contents: read' scope on this repo."
                ),
            }
        return {"ok": False, "error": f"http_{exc.code}", "hint": str(exc)[:200]}
    except urllib.error.URLError as exc:
        return {
            "ok": False, "error": "network",
            "hint": f"Couldn't reach api.github.com: {exc.reason}",
        }
    except Exception as exc:
        return {"ok": False, "error": "fetch_failed", "hint": str(exc)[:200]}

    return {
        "ok": True,
        "tag_name": data.get("tag_name"),
        "name": data.get("name"),
        "published_at": data.get("published_at"),
        "body": (data.get("body") or "")[:1024],
    }


async def run_setup(plugin_dir: Path) -> dict[str, Any]:
    """Run ``setup.sh`` from the installed plugin. The script must have
    been bundled at install time — older builds shipped without it."""
    script = Path(plugin_dir) / "setup.sh"
    if not script.exists():
        return {
            "ok": False,
            "error": "setup_sh_missing",
            "hint": (
                "setup.sh wasn't bundled with this install. Reinstall by "
                "running bash setup.sh from your local checkout in Desktop "
                "Mode — newer builds include the script in the plugin dir."
            ),
        }
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
