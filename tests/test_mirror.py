from deckpip.mirror import parse_gamescope_node

PW_OUTPUT = """\
\tid 35, type PipeWire:Interface:Node/3
\t\tnode.name = "alsa_input.pci-0000_05_00.6.analog-stereo"
\tid 78, type PipeWire:Interface:Node/3
\t\tnode.description = "gamescope (game session)"
\tid 100, type PipeWire:Interface:Node/3
\t\tnode.name = "alsa_output.pci-0000_05_00.6.analog-stereo"
"""


def test_parses_gamescope_id() -> None:
    assert parse_gamescope_node(PW_OUTPUT) == "78"


def test_returns_none_when_no_gamescope() -> None:
    out = "\tid 1, type Node/3\n\t\tnode.name = \"alsa\"\n"
    assert parse_gamescope_node(out) is None


def test_returns_none_for_empty_input() -> None:
    assert parse_gamescope_node("") is None


def test_matches_case_insensitively() -> None:
    out = "\tid 7, type Node/3\n\t\tnode.description = \"GameScope Output\"\n"
    assert parse_gamescope_node(out) == "7"


def test_first_match_wins() -> None:
    out = (
        "\tid 1, type Node/3\n\t\tnode.description = \"gamescope a\"\n"
        "\tid 2, type Node/3\n\t\tnode.description = \"gamescope b\"\n"
    )
    assert parse_gamescope_node(out) == "1"
