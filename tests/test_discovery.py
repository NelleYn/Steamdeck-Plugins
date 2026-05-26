from pathlib import Path

from deckpip.discovery import (
    discover_desktop_files,
    parse_desktop_entry,
    parse_flatpak_list,
)

# ---- parse_desktop_entry -------------------------------------------------


SIMPLE_DESKTOP = """\
[Desktop Entry]
Type=Application
Name=Hello World
Exec=hello-world %U
"""


def test_parses_minimal_desktop() -> None:
    parsed = parse_desktop_entry(SIMPLE_DESKTOP)
    assert parsed == {"name": "Hello World", "exec": "hello-world"}


def test_no_display_returns_none() -> None:
    text = SIMPLE_DESKTOP + "NoDisplay=true\n"
    assert parse_desktop_entry(text) is None


def test_hidden_returns_none() -> None:
    text = SIMPLE_DESKTOP + "Hidden=true\n"
    assert parse_desktop_entry(text) is None


def test_link_type_returns_none() -> None:
    text = "[Desktop Entry]\nType=Link\nName=X\nURL=https://example.com\n"
    assert parse_desktop_entry(text) is None


def test_action_section_does_not_override_main() -> None:
    text = (
        "[Desktop Entry]\nType=Application\nName=Real\nExec=real\n"
        "[Desktop Action Open]\nName=Open\nExec=other\n"
    )
    assert parse_desktop_entry(text) == {"name": "Real", "exec": "real"}


def test_terminal_app_is_wrapped_in_xterm() -> None:
    text = "[Desktop Entry]\nType=Application\nName=Tcli\nExec=tcli\nTerminal=true\n"
    assert parse_desktop_entry(text) == {"name": "Tcli", "exec": "xterm -e tcli"}


def test_strips_all_xdg_placeholders() -> None:
    text = "[Desktop Entry]\nType=Application\nName=X\nExec=mycmd %U %f %i\n"
    assert parse_desktop_entry(text)["exec"] == "mycmd"


def test_missing_name_returns_none() -> None:
    text = "[Desktop Entry]\nType=Application\nExec=cmd\n"
    assert parse_desktop_entry(text) is None


def test_ignores_comments_and_blank_lines() -> None:
    text = "# a header\n\n[Desktop Entry]\n# inline\nType=Application\nName=X\nExec=cmd\n"
    assert parse_desktop_entry(text) == {"name": "X", "exec": "cmd"}


# ---- parse_flatpak_list --------------------------------------------------


def test_parses_flatpak_list_tab_separated() -> None:
    out = "com.discordapp.Discord\tDiscord\norg.telegram.desktop\tTelegram Desktop\n"
    items = parse_flatpak_list(out)
    assert items == [
        {
            "name": "Discord",
            "exec": "flatpak run com.discordapp.Discord",
            "kind": "flatpak",
            "id": "com.discordapp.Discord",
        },
        {
            "name": "Telegram Desktop",
            "exec": "flatpak run org.telegram.desktop",
            "kind": "flatpak",
            "id": "org.telegram.desktop",
        },
    ]


def test_skips_header_line() -> None:
    out = "Application ID\tName\norg.x.App\tXapp\n"
    items = parse_flatpak_list(out)
    assert [a["id"] for a in items] == ["org.x.App"]


def test_falls_back_to_id_when_name_blank() -> None:
    out = "org.x.App\t\n"
    items = parse_flatpak_list(out)
    assert items[0]["name"] == "org.x.App"


def test_ignores_malformed_lines() -> None:
    assert parse_flatpak_list("nope\nnope\t\torg.x.A\tname2\n")[0]["id"] == "nope"


# ---- discover_desktop_files (fs-backed) ----------------------------------


def test_discovers_desktop_files_in_local_share(tmp_path: Path) -> None:
    apps_dir = tmp_path / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True)
    (apps_dir / "good.desktop").write_text(SIMPLE_DESKTOP)
    (apps_dir / "bad-link.desktop").write_text(
        "[Desktop Entry]\nType=Link\nName=B\nURL=https://x\n"
    )
    (apps_dir / "hidden.desktop").write_text(SIMPLE_DESKTOP + "NoDisplay=true\n")

    apps = discover_desktop_files(tmp_path, system_paths=[])
    assert [a["id"] for a in apps] == ["good"]


def test_dedupes_id_across_locations(tmp_path: Path) -> None:
    local = tmp_path / ".local" / "share" / "applications"
    local.mkdir(parents=True)
    (local / "dup.desktop").write_text(SIMPLE_DESKTOP)
    fp = tmp_path / ".local" / "share" / "flatpak" / "exports" / "share" / "applications"
    fp.mkdir(parents=True)
    (fp / "dup.desktop").write_text("[Desktop Entry]\nType=Application\nName=Other\nExec=other\n")

    apps = discover_desktop_files(tmp_path, system_paths=[])
    assert len(apps) == 1
    # First-seen wins (local/share/applications is searched first).
    assert apps[0]["exec"] == "hello-world"


def test_returns_empty_when_no_directories(tmp_path: Path) -> None:
    assert discover_desktop_files(tmp_path, system_paths=[]) == []
