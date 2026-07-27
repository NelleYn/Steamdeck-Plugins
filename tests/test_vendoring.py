from pathlib import Path

import pytest

from deckpip import vendoring


def test_vendored_paths_absent_returns_none(tmp_path: Path) -> None:
    assert vendoring.vendored_novnc(tmp_path) is None
    assert vendoring.vendored_websockify(tmp_path) is None


def test_vendored_novnc_detected_when_vnc_html_present(tmp_path: Path) -> None:
    target = vendoring.vendored_root(tmp_path) / vendoring.NOVNC_DIRNAME
    target.mkdir(parents=True)
    (target / "vnc.html").write_text("<html></html>")
    assert vendoring.vendored_novnc(tmp_path) == target


def test_vendored_websockify_detected_when_binary_present(tmp_path: Path) -> None:
    target = vendoring.vendored_root(tmp_path) / "python" / "bin"
    target.mkdir(parents=True)
    (target / "websockify").write_text("#!/usr/bin/env python3\n")
    (target / "websockify").chmod(0o755)
    assert vendoring.vendored_websockify(tmp_path) == target / "websockify"


def test_status_reflects_present_and_missing(tmp_path: Path) -> None:
    s = vendoring.status(tmp_path)
    assert s["novnc"] == ""
    assert s["websockify"] == ""
    assert s["root"].endswith("vendored")


# ---- bundled (shipped-in-zip) resolution ---------------------------------


def test_bundled_novnc_none_when_absent(tmp_path: Path) -> None:
    assert vendoring.bundled_novnc(tmp_path) is None


def test_bundled_novnc_detected(tmp_path: Path) -> None:
    target = vendoring.bundled_root(tmp_path) / vendoring.NOVNC_DIRNAME
    target.mkdir(parents=True)
    (target / "vnc.html").write_text("<html></html>")
    assert vendoring.bundled_novnc(tmp_path) == target


def test_bundled_websockify_root_none_when_absent(tmp_path: Path) -> None:
    assert vendoring.bundled_websockify_root(tmp_path) is None


def test_bundled_websockify_root_detected(tmp_path: Path) -> None:
    bin_dir = vendoring.bundled_root(tmp_path) / "python" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "websockify").write_text("#!/usr/bin/env bash\n")
    assert vendoring.bundled_websockify_root(tmp_path) == vendoring.bundled_root(tmp_path) / "python"


@pytest.mark.asyncio
async def test_install_novnc_uses_bundled_copy_without_network(
    monkeypatch, tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "plugin"
    bundled = plugin_dir / "vendored" / vendoring.NOVNC_DIRNAME
    bundled.mkdir(parents=True)
    (bundled / "vnc.html").write_text("<html></html>")
    runtime_dir = tmp_path / "runtime"

    async def _boom(*_a, **_kw):
        raise AssertionError("should not hit the network when a bundled copy exists")

    monkeypatch.setattr(vendoring, "_download_tarball", _boom)

    res = await vendoring.install_novnc(runtime_dir, plugin_dir=plugin_dir)
    assert res == {
        "ok": True,
        "path": str(vendoring.vendored_root(runtime_dir) / vendoring.NOVNC_DIRNAME),
        "source": "bundled",
    }
    assert (vendoring.vendored_root(runtime_dir) / vendoring.NOVNC_DIRNAME / "vnc.html").exists()


@pytest.mark.asyncio
async def test_install_novnc_falls_back_to_download_without_bundle(
    monkeypatch, tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "plugin"  # no vendored/ inside it
    calls: list[str] = []

    async def _fake_download(url, dest):
        calls.append(url)
        dest.write_bytes(b"fake")

    async def _fake_extract(tarball, into):
        target = into / vendoring.NOVNC_DIRNAME
        target.mkdir(parents=True, exist_ok=True)
        (target / "vnc.html").write_text("<html></html>")

    monkeypatch.setattr(vendoring, "_download_tarball", _fake_download)
    monkeypatch.setattr(vendoring, "_extract_tarball", _fake_extract)

    res = await vendoring.install_novnc(tmp_path / "runtime", plugin_dir=plugin_dir)
    assert res["ok"] is True
    assert res["source"] == "downloaded"
    assert calls  # network path was actually used


@pytest.mark.asyncio
async def test_install_novnc_skips_when_already_installed(tmp_path: Path) -> None:
    target = vendoring.vendored_root(tmp_path) / vendoring.NOVNC_DIRNAME
    target.mkdir(parents=True)
    (target / "vnc.html").write_text("x")
    res = await vendoring.install_novnc(tmp_path)
    assert res == {"ok": True, "skipped": True, "path": str(target)}


@pytest.mark.asyncio
async def test_install_websockify_uses_bundled_copy_without_pip(
    monkeypatch, tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "plugin"
    bundled_bin_dir = plugin_dir / "vendored" / "python" / "bin"
    bundled_bin_dir.mkdir(parents=True)
    (bundled_bin_dir / "websockify").write_text("#!/usr/bin/env bash\necho fake\n")
    (bundled_bin_dir / "websockify").chmod(0o755)
    runtime_dir = tmp_path / "runtime"

    async def _boom(*_a, **_kw):
        raise AssertionError("should not shell out to pip when a bundled copy exists")

    monkeypatch.setattr(vendoring.asyncio, "create_subprocess_exec", _boom)

    res = await vendoring.install_websockify(runtime_dir, plugin_dir=plugin_dir)
    assert res["ok"] is True
    assert res["source"] == "bundled"
    assert Path(res["path"]).exists()
