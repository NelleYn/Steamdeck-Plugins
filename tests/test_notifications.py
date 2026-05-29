from deckpip.notifications import is_dbus_header, parse_notification_block

BLOCK_DISCORD = [
    'method call time=1.0 sender=:1.42 -> destination=:1.20 path=/org/freedesktop/Notifications member=Notify',
    '   string "Discord"',
    '   uint32 0',
    '   string ""',
    '   string "Alice"',
    '   string "Hello!"',
    '   array [ ]',
]


def test_parses_discord_block() -> None:
    parsed = parse_notification_block(BLOCK_DISCORD)
    assert parsed == {"app": "Discord", "summary": "Alice", "body": "Hello!"}


def test_returns_none_for_non_notify_block() -> None:
    block = [
        'method call sender=:1.42 path=/foo member=Something',
        '   string "ignored"',
    ]
    assert parse_notification_block(block) is None


def test_returns_none_for_too_few_strings() -> None:
    block = [
        'method call member=Notify',
        '   string "App"',
        '   uint32 0',
    ]
    assert parse_notification_block(block) is None


def test_returns_none_for_empty_block() -> None:
    assert parse_notification_block([]) is None


def test_real_headers_are_detected() -> None:
    assert is_dbus_header(
        "method call time=1.0 sender=:1.42 -> destination=:1.20 "
        "path=/org/freedesktop/Notifications member=Notify"
    )
    assert is_dbus_header("signal time=2.0 sender=:1.5 -> destination=(null) member=X")


def test_notification_content_is_not_mistaken_for_header() -> None:
    # A notification body whose text starts with "method call"/"signal" must
    # NOT be treated as a block boundary (no `sender=`), so it can't split or
    # drop a legitimate notification.
    assert not is_dbus_header("method call foo")
    assert not is_dbus_header('   string "signal received"')
    assert not is_dbus_header("signal lost")
