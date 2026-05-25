from pathlib import Path

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
