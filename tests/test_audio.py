from pathlib import Path

from deckpip.audio import (
    _descendant_pids,
    parse_sink_inputs_for_pid,
    parse_sink_inputs_for_pids,
)

PACTL_OUTPUT = """\
Sink Input #321
\tDriver: <native>
\tapplication.name = "Discord"
\tapplication.process.id = "12345"
\tapplication.process.binary = "Discord"

Sink Input #322
\tDriver: <native>
\tapplication.process.id = "99999"
\tapplication.process.binary = "Steam"

Sink Input #323
\tapplication.process.id = "12345"
\tapplication.process.binary = "Discord-helper"
"""


def test_finds_multiple_sinks_for_one_pid() -> None:
    assert parse_sink_inputs_for_pid(PACTL_OUTPUT, 12345) == ["321", "323"]


def test_no_match_returns_empty() -> None:
    assert parse_sink_inputs_for_pid(PACTL_OUTPUT, 11111) == []


def test_empty_input_returns_empty() -> None:
    assert parse_sink_inputs_for_pid("", 1) == []


def test_pid_must_match_exactly() -> None:
    # 1234 must not match 12345
    assert parse_sink_inputs_for_pid(PACTL_OUTPUT, 1234) == []


def test_matches_any_pid_in_set() -> None:
    # The guest's audio process is a descendant of the runuser launcher, so we
    # match against the whole subtree, not a single pid.
    assert parse_sink_inputs_for_pids(PACTL_OUTPUT, {99999, 12345}) == [
        "321", "322", "323",
    ]


def _write_proc(root: Path, pid: int, ppid: int) -> None:
    d = root / str(pid)
    d.mkdir()
    (d / "status").write_text(f"Name:\tx\nPid:\t{pid}\nPPid:\t{ppid}\n")


def test_descendant_pids_walks_subtree(tmp_path: Path) -> None:
    # 100 -> 200 -> 300, plus an unrelated 999.
    _write_proc(tmp_path, 100, 1)
    _write_proc(tmp_path, 200, 100)
    _write_proc(tmp_path, 300, 200)
    _write_proc(tmp_path, 999, 1)
    assert _descendant_pids(100, proc_root=tmp_path) == {100, 200, 300}


def test_descendant_pids_handles_missing_proc(tmp_path: Path) -> None:
    # Empty /proc: only the root pid itself is returned.
    assert _descendant_pids(42, proc_root=tmp_path) == {42}
