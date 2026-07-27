import pytest

from deckpip.mirror import gst_argv, parse_gamescope_node, start_mirror_window

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


def test_prefers_video_class_over_audio() -> None:
    out = (
        "\tid 1, type Node/3\n"
        "\t\tmedia.class = \"Audio/Sink\"\n"
        "\t\tnode.description = \"gamescope audio\"\n"
        "\tid 2, type Node/3\n"
        "\t\tmedia.class = \"Video/Source\"\n"
        "\t\tnode.description = \"gamescope video\"\n"
    )
    assert parse_gamescope_node(out) == "2"


def test_falls_back_to_name_match_when_no_video() -> None:
    out = (
        "\tid 5, type Node/3\n"
        "\t\tnode.description = \"gamescope (game session)\"\n"
    )
    assert parse_gamescope_node(out) == "5"


# ---- gst_argv() / start_mirror_window() dependency resolution ------------


def test_gst_argv_uses_given_binary() -> None:
    argv = gst_argv("/vendored/bin/gst-launch-1.0", "42", "target-object")
    assert argv[0] == "/vendored/bin/gst-launch-1.0"
    assert "target-object=42" in argv


@pytest.mark.asyncio
async def test_start_mirror_window_raises_when_gst_unresolvable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("deckpip.mirror.gst_launch_path", lambda _plugin_dir: None)
    with pytest.raises(FileNotFoundError):
        await start_mirror_window(None)
