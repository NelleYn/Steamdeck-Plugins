from pathlib import Path

import pytest

from deckpip import ludusavi


def test_root_and_default_backup_dir(tmp_path: Path) -> None:
    assert ludusavi._root(tmp_path) == tmp_path / "vendored" / "ludusavi"
    assert ludusavi.default_backup_dir(tmp_path) == tmp_path / "ludusavi" / "backups"


def test_binary_path_absent_when_no_file(tmp_path: Path) -> None:
    assert ludusavi.binary_path(tmp_path) is None


def test_binary_path_detected_when_executable_present(tmp_path: Path) -> None:
    root = ludusavi._root(tmp_path)
    root.mkdir(parents=True)
    bin_p = root / "ludusavi"
    bin_p.write_text("#!/bin/sh\necho fake\n")
    bin_p.chmod(0o755)
    assert ludusavi.binary_path(tmp_path) == bin_p


def test_resolve_binary_prefers_vendored(monkeypatch, tmp_path: Path) -> None:
    root = ludusavi._root(tmp_path)
    root.mkdir(parents=True)
    bin_p = root / "ludusavi"
    bin_p.write_text("x")
    bin_p.chmod(0o755)
    # Pretend system has its own copy too — vendored should still win.
    monkeypatch.setattr("deckpip.ludusavi.shutil.which", lambda _: "/usr/bin/ludusavi")
    assert ludusavi.resolve_binary(tmp_path) == str(bin_p)


def test_resolve_binary_falls_back_to_system(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("deckpip.ludusavi.shutil.which", lambda _: "/usr/bin/ludusavi")
    assert ludusavi.resolve_binary(tmp_path) == "/usr/bin/ludusavi"


def test_resolve_binary_returns_none_when_nothing_present(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr("deckpip.ludusavi.shutil.which", lambda _: None)
    assert ludusavi.resolve_binary(tmp_path) is None


def test_summary_from_well_formed_payload() -> None:
    summary = ludusavi.parse_backup_summary({
        "overall": {"totalBytes": 12345, "processedGames": 3},
        "games": {"Game A": {}, "Game B": {}, "Game C": {}},
    })
    assert summary["games"] == 3
    assert summary["total_bytes"] == 12345


def test_summary_counts_failed_files() -> None:
    # A backup where some files failed must report a non-zero error count
    # (regression: the old `X and 0` idiom always reported 0).
    summary = ludusavi.parse_backup_summary({
        "overall": {"totalBytes": 10, "processedGames": 2},
        "games": {
            "Game A": {"files": {"/a": {"failed": False}, "/b": {"failed": True}}},
            "Game B": {"files": {"/c": {"failed": True}}},
        },
    })
    assert summary["errors"] == 2
    assert summary["games"] == 2


def test_summary_no_errors_when_all_succeed() -> None:
    summary = ludusavi.parse_backup_summary({
        "overall": {"totalBytes": 10, "processedGames": 1},
        "games": {"Game A": {"files": {"/a": {"failed": False}}}},
    })
    assert summary["errors"] == 0


# ---- bundled (shipped-in-zip) resolution ---------------------------------


def test_bundled_binary_none_when_absent(tmp_path: Path) -> None:
    assert ludusavi._bundled_binary(tmp_path) is None


def test_bundled_binary_detected(tmp_path: Path) -> None:
    root = ludusavi._bundled_root(tmp_path)
    root.mkdir(parents=True)
    bin_p = root / "ludusavi"
    bin_p.write_text("#!/bin/sh\necho fake\n")
    bin_p.chmod(0o755)
    assert ludusavi._bundled_binary(tmp_path) == bin_p


@pytest.mark.asyncio
async def test_install_uses_bundled_copy_without_network(monkeypatch, tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    bundled_root = ludusavi._bundled_root(plugin_dir)
    bundled_root.mkdir(parents=True)
    bundled_bin = bundled_root / "ludusavi"
    bundled_bin.write_text("#!/bin/sh\necho fake\n")
    bundled_bin.chmod(0o755)
    runtime_dir = tmp_path / "runtime"

    def _boom(*_a, **_kw):
        raise AssertionError("should not hit the network when a bundled copy exists")

    monkeypatch.setattr(ludusavi.urllib.request, "urlopen", _boom)

    res = await ludusavi.install(runtime_dir, plugin_dir=plugin_dir)
    assert res["ok"] is True
    assert res["source"] == "bundled"
    assert Path(res["path"]).exists()
    assert ludusavi.binary_path(runtime_dir) == Path(res["path"])


@pytest.mark.asyncio
async def test_install_skips_when_already_installed(tmp_path: Path) -> None:
    root = ludusavi._root(tmp_path)
    root.mkdir(parents=True)
    bin_p = root / "ludusavi"
    bin_p.write_text("x")
    bin_p.chmod(0o755)
    res = await ludusavi.install(tmp_path)
    assert res == {"ok": True, "skipped": True, "path": str(bin_p)}


def test_summary_from_garbage_payload() -> None:
    assert ludusavi.parse_backup_summary("not a dict") == {
        "games": 0, "total_bytes": 0, "errors": 0,
    }
    assert ludusavi.parse_backup_summary(None) == {
        "games": 0, "total_bytes": 0, "errors": 0,
    }
    assert ludusavi.parse_backup_summary({}) == {
        "games": 0, "total_bytes": 0, "errors": 0,
    }
