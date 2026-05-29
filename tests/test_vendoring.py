from pathlib import Path

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
