from deckpip.trackpad import pct_to_pixels


def test_center_maps_to_center() -> None:
    px, py = pct_to_pixels(50, 50)
    assert px == 640
    assert py == 400


def test_origin_maps_to_zero() -> None:
    assert pct_to_pixels(0, 0) == (0, 0)


def test_max_clamps_to_screen_bounds() -> None:
    px, py = pct_to_pixels(100, 100)
    # 1280x800 - 1 pixel margin (max coordinate index, not size)
    assert px == 1279
    assert py == 799


def test_overshoot_clamps_to_max() -> None:
    px, py = pct_to_pixels(150, 200)
    assert px == 1279
    assert py == 799


def test_negative_clamps_to_zero() -> None:
    assert pct_to_pixels(-10, -50) == (0, 0)
