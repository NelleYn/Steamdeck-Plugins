from pathlib import Path

import pytest

from deckpip import diagnostics


@pytest.mark.asyncio
async def test_collect_reports_absent_binaries_without_plugin_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _: None)
    info = await diagnostics.collect()
    assert info["binaries"]["Xvnc"] == {"present": False}
    assert info["binaries"]["websockify"] == {"present": False}
    assert "python" in info
    assert "kernel" in info


@pytest.mark.asyncio
async def test_collect_prefers_bundled_xvnc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "vendored" / "tigervnc" / "bin"
    bin_dir.mkdir(parents=True)
    xvnc = bin_dir / "Xvnc"
    xvnc.write_text("#!/bin/sh\nexit 1\n")
    xvnc.chmod(0o755)
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _: None)

    info = await diagnostics.collect(plugin_dir=tmp_path)
    assert info["binaries"]["Xvnc"]["present"] is True
    assert info["binaries"]["Xvnc"]["path"] == str(xvnc)


@pytest.mark.asyncio
async def test_collect_includes_runtime_dir_info(tmp_path: Path) -> None:
    info = await diagnostics.collect(runtime_dir=tmp_path)
    assert info["runtime_dir"]["path"] == str(tmp_path)
    assert info["runtime_dir"]["exists"] is True
    assert info["runtime_dir"]["vncpasswd_present"] is False
