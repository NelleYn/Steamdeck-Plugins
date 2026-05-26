from pathlib import Path

import pytest

from deckpip.settings import SettingsStore
from deckpip.updater import check_release, run_setup


@pytest.mark.asyncio
async def test_check_release_returns_no_token_when_unset(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    res = await check_release(store)
    assert res == {
        "ok": False,
        "error": "no_token",
        "hint": (
            "Set your GitHub PAT in System -> GitHub PAT first. "
            "Needs 'Contents: read' on this private repo."
        ),
    }


@pytest.mark.asyncio
async def test_check_release_returns_no_token_for_non_string(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set("github_token", 42)  # not a string
    res = await check_release(store)
    assert res["ok"] is False
    assert res["error"] == "no_token"


@pytest.mark.asyncio
async def test_run_setup_reports_missing_script(tmp_path: Path) -> None:
    res = await run_setup(tmp_path)  # tmp_path has no setup.sh
    assert res["ok"] is False
    assert res["error"] == "setup_sh_missing"
    assert "setup.sh" in res["hint"]
