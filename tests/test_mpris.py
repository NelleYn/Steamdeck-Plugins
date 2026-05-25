from deckpip.mpris import parse_listnames, parse_metadata

LISTNAMES_OUTPUT = """\
method return time=1.0 sender=org.freedesktop.DBus -> destination=:1.42 reply_serial=2
   array [
      string "org.freedesktop.DBus"
      string ":1.20"
      string "org.mpris.MediaPlayer2.spotify"
      string "org.mpris.MediaPlayer2.firefox.instance_pid_12345"
      string ":1.50"
      string "org.freedesktop.systemd1"
   ]
"""


def test_listnames_returns_only_mpris_buses() -> None:
    names = parse_listnames(LISTNAMES_OUTPUT)
    assert names == [
        "org.mpris.MediaPlayer2.spotify",
        "org.mpris.MediaPlayer2.firefox.instance_pid_12345",
    ]


def test_listnames_empty_input() -> None:
    assert parse_listnames("") == []


PROPERTIES_PLAYING = """\
method return time=1 sender=:1.50 -> destination=:1.42 reply_serial=2
   variant       string "Playing"
"""


def test_parses_status_playing() -> None:
    assert parse_metadata(PROPERTIES_PLAYING) == {"status": "Playing"}


def test_parses_status_paused() -> None:
    out = 'variant       string "Paused"'
    assert parse_metadata(out)["status"] == "Paused"


METADATA_OUTPUT = """\
method return reply_serial=2
   variant array [
      dict entry(
         string "xesam:title"
         variant string "Bohemian Rhapsody"
      )
      dict entry(
         string "xesam:album"
         variant string "A Night at the Opera"
      )
      dict entry(
         string "xesam:artist"
         variant array [
            string "Queen"
         ]
      )
   ]
"""


def test_parses_full_metadata() -> None:
    meta = parse_metadata(METADATA_OUTPUT)
    assert meta["title"] == "Bohemian Rhapsody"
    assert meta["album"] == "A Night at the Opera"
    assert meta["artist"] == "Queen"


def test_metadata_with_missing_keys() -> None:
    out = 'variant string "Playing"\nstring "xesam:title"\nvariant string "Song"'
    meta = parse_metadata(out)
    assert meta == {"status": "Playing", "title": "Song"}
