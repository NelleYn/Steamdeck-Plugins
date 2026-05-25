from deckpip.audio import parse_sink_inputs_for_pid

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
