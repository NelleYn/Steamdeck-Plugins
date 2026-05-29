import zipfile
from pathlib import Path

import pytest

from deckpip import cloud_sync


def test_binary_absent_initially(tmp_path: Path) -> None:
    assert cloud_sync.binary_path(tmp_path) is None


def test_binary_detected_inside_versioned_subdir(tmp_path: Path) -> None:
    sub = cloud_sync._root(tmp_path) / "rclone-v1.69.1-linux-amd64"
    sub.mkdir(parents=True)
    bin_p = sub / "rclone"
    bin_p.write_text("#!/bin/sh\necho fake\n")
    bin_p.chmod(0o755)
    assert cloud_sync.binary_path(tmp_path) == bin_p


def test_resolve_binary_prefers_vendored(monkeypatch, tmp_path: Path) -> None:
    sub = cloud_sync._root(tmp_path) / "rclone-vX-linux-amd64"
    sub.mkdir(parents=True)
    bin_p = sub / "rclone"
    bin_p.write_text("x")
    bin_p.chmod(0o755)
    monkeypatch.setattr("deckpip.cloud_sync.shutil.which", lambda _: "/usr/bin/rclone")
    assert cloud_sync.resolve_binary(tmp_path) == str(bin_p)


def test_resolve_binary_falls_back_to_system(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("deckpip.cloud_sync.shutil.which", lambda _: "/usr/bin/rclone")
    assert cloud_sync.resolve_binary(tmp_path) == "/usr/bin/rclone"


def test_resolve_binary_returns_none_when_nothing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("deckpip.cloud_sync.shutil.which", lambda _: None)
    assert cloud_sync.resolve_binary(tmp_path) is None


def test_parse_remotes_typical_output() -> None:
    out = "gdrive:\ndropbox:\nonedrive_personal:\n"
    assert cloud_sync.parse_remotes(out) == ["gdrive", "dropbox", "onedrive_personal"]


def test_parse_remotes_tolerates_whitespace_and_garbage() -> None:
    out = "  gdrive:  \nnot a remote\n\ns3-bucket:\n   \n"
    assert cloud_sync.parse_remotes(out) == ["gdrive", "s3-bucket"]


def test_parse_remotes_rejects_bad_chars() -> None:
    # rclone names allow A-Z, a-z, 0-9, _, - only.
    out = "good-name:\nbad/name:\nspaces here:\n"
    assert cloud_sync.parse_remotes(out) == ["good-name"]


def test_parse_remotes_empty() -> None:
    assert cloud_sync.parse_remotes("") == []


@pytest.mark.asyncio
async def test_sync_up_rejects_injection_remote(tmp_path: Path) -> None:
    # A connection-string-style remote must be rejected before rclone runs.
    res = await cloud_sync.sync_up(tmp_path, tmp_path, ":http,url=http://evil", "p")
    assert res == {"ok": False, "error": "invalid_remote"}


@pytest.mark.asyncio
async def test_sync_down_rejects_injection_remote(tmp_path: Path) -> None:
    res = await cloud_sync.sync_down(tmp_path, tmp_path, "has space", "p")
    assert res == {"ok": False, "error": "invalid_remote"}


def test_safe_extract_zip_rejects_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "pwned")
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(archive) as zf, pytest.raises(RuntimeError):
        cloud_sync._safe_extract_zip(zf, dest)
    assert not (tmp_path / "escape.txt").exists()


def test_safe_extract_zip_extracts_normal_members(tmp_path: Path) -> None:
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("rclone-vX/rclone", "binary")
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(archive) as zf:
        cloud_sync._safe_extract_zip(zf, dest)
    assert (dest / "rclone-vX" / "rclone").read_text() == "binary"
