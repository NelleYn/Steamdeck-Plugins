import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from deckpip.session import PipSession, terminate, wait_port

# ---- url() formatting ----------------------------------------------------


def test_url_audio_only_is_none() -> None:
    app = {"id": "x", "label": "x", "command": ["xterm"]}
    s = PipSession(app, "abcdef12_extra", audio_only=True, runtime_dir=Path("/tmp"))
    assert s.url() is None


def test_url_normal_contains_full_token() -> None:
    app = {"id": "x", "label": "x", "command": ["xterm"]}
    token = "0123456789abcdef" * 2
    s = PipSession(app, token, audio_only=False, runtime_dir=Path("/tmp"))
    url = s.url()
    assert url is not None
    # Full token travels in the loopback-scoped URL; VncAuth truncates to
    # 8 bytes client-side.
    assert f"password={token}" in url
    assert "vnc.html" in url
    assert "autoconnect=1" in url
    assert "resize=remote" in url


# ---- terminate() lifecycle ----------------------------------------------


@pytest.mark.asyncio
async def test_terminate_none_is_noop() -> None:
    await terminate(None)


@pytest.mark.asyncio
async def test_terminate_already_dead_is_noop() -> None:
    proc = MagicMock()
    proc.poll.return_value = 0  # already exited
    await terminate(proc)


@pytest.mark.asyncio
async def test_terminate_signals_then_kills_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the process doesn't exit within grace, SIGKILL is sent."""
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 12345
    monkeypatch.setattr("deckpip.session.os.getpgid", lambda pid: pid)

    killed_with: list[int] = []
    monkeypatch.setattr(
        "deckpip.session.os.killpg",
        lambda pgid, sig: killed_with.append(int(sig)),
    )
    # Force the wait to time out without actually waiting.
    monkeypatch.setattr(
        "deckpip.session.asyncio.to_thread",
        lambda fn, *a, **kw: asyncio.sleep(10),
    )

    await terminate(proc, grace=0.01)

    import signal as _signal
    assert _signal.SIGTERM in killed_with
    assert _signal.SIGKILL in killed_with


@pytest.mark.asyncio
async def test_terminate_handles_disappeared_proc(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = MagicMock()
    proc.poll.return_value = None
    proc.pid = 1

    def raise_lookup(pid: int) -> int:
        raise ProcessLookupError()

    monkeypatch.setattr("deckpip.session.os.getpgid", raise_lookup)
    # Should not raise.
    await terminate(proc)


# ---- wait_port() ---------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_port_returns_false_on_unreachable() -> None:
    # Port 1 is privileged + nothing listens => connect refused.
    assert await wait_port("127.0.0.1", 1, timeout=0.2) is False


# ---- vncpasswd cleanup ---------------------------------------------------


@pytest.mark.asyncio
async def test_stop_removes_vncpasswd_file(tmp_path: Path) -> None:
    app = {"id": "x", "label": "x", "command": ["xterm"]}
    s = PipSession(app, "abc12345", audio_only=True, runtime_dir=tmp_path)
    (tmp_path / "vncpasswd").write_bytes(b"hunter2")
    await s.stop()
    assert not (tmp_path / "vncpasswd").exists()


@pytest.mark.asyncio
async def test_stop_is_noop_when_vncpasswd_missing(tmp_path: Path) -> None:
    app = {"id": "x", "label": "x", "command": ["xterm"]}
    s = PipSession(app, "abc12345", audio_only=True, runtime_dir=tmp_path)
    # No file present.
    await s.stop()  # should not raise
