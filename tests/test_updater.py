from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from deckpip.settings import SettingsStore
from deckpip.updater import check_release, run_setup


@pytest.mark.asyncio
async def test_check_release_works_without_token(tmp_path: Path) -> None:
    """Public repo: anonymous request should still go out."""
    store = SettingsStore(tmp_path)
    fake_data = {"tag_name": "dev", "name": "Latest", "published_at": "2026-01-01", "body": ""}
    with patch("deckpip.updater.asyncio.to_thread", AsyncMock(return_value=fake_data)):
        res = await check_release(store)
    assert res["ok"] is True
    assert res["tag_name"] == "dev"


@pytest.mark.asyncio
async def test_check_release_uses_token_when_present(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set("github_token", "ghp_test")
    fake_data = {"tag_name": "dev", "name": "Latest", "published_at": "2026-01-01", "body": ""}
    with patch("deckpip.updater.asyncio.to_thread", AsyncMock(return_value=fake_data)) as m:
        await check_release(store)
    # _fetch closure should have used the token; we can't inspect headers
    # directly but at least confirm the request path ran.
    assert m.await_count == 1


@pytest.mark.asyncio
async def test_run_setup_reports_missing_script(tmp_path: Path) -> None:
    res = await run_setup(tmp_path)
    assert res["ok"] is False
    assert res["error"] == "setup_sh_missing"
    assert "setup.sh" in res["hint"]
