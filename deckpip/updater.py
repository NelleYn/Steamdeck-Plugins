"""GitHub release polling + setup.sh runner."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from deckpip.settings import SettingsStore

REPO = "NelleYn/Steamdeck-Plugins"
RELEASE_TAG = "dev"
API_URL = f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}"


async def check_release(store: SettingsStore) -> dict[str, Any]:
    # Token is optional now that the repo is public — only sent when present
    # to lift the unauthenticated rate limit.
    token = store.get("github_token")

    def _fetch() -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "DeckPiP-updater",
        }
        if isinstance(token, str) and token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(API_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    try:
        data = await asyncio.to_thread(_fetch)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return {"ok": False, "error": "auth_failed", "hint": "Token rejected — re-generate it."}
        if exc.code == 403:
            return {
                "ok": False, "error": "rate_limited",
                "hint": "GitHub anonymous rate limit hit — try again later or set a PAT.",
            }
        if exc.code == 404:
            return {
                "ok": False, "error": "not_found",
                "hint": "Dev release tag doesn't exist yet — wait for CI to publish.",
            }
        return {"ok": False, "error": f"http_{exc.code}", "hint": str(exc)[:200]}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": "network", "hint": f"Couldn't reach api.github.com: {exc.reason}"}
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
    script = Path(plugin_dir) / "setup.sh"
    if not script.exists():
        return {
            "ok": False,
            "error": "setup_sh_missing",
            "hint": "Reinstall from a local checkout: bash setup.sh in Desktop Mode.",
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
