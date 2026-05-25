from pathlib import Path

from deckpip import battery


def test_no_battery_when_root_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(battery, "BATTERY_ROOT", tmp_path / "does-not-exist")
    assert battery.read_state() == {"present": False}


def test_no_battery_when_root_has_no_battery(monkeypatch, tmp_path: Path) -> None:
    # Create an AC adapter but no battery.
    ac = tmp_path / "AC"
    ac.mkdir()
    (ac / "type").write_text("Mains\n")
    monkeypatch.setattr(battery, "BATTERY_ROOT", tmp_path)
    assert battery.read_state() == {"present": False}


def test_reads_capacity_and_status_when_charging(monkeypatch, tmp_path: Path) -> None:
    bat = tmp_path / "BAT0"
    bat.mkdir()
    (bat / "type").write_text("Battery\n")
    (bat / "capacity").write_text("87\n")
    (bat / "status").write_text("Charging\n")
    monkeypatch.setattr(battery, "BATTERY_ROOT", tmp_path)
    state = battery.read_state()
    assert state["present"] is True
    assert state["percent"] == 87
    assert state["status"] == "Charging"
    assert state["charging"] is True
    assert state["on_battery"] is False


def test_reads_on_battery(monkeypatch, tmp_path: Path) -> None:
    bat = tmp_path / "BAT0"
    bat.mkdir()
    (bat / "type").write_text("Battery\n")
    (bat / "capacity").write_text("12\n")
    (bat / "status").write_text("Discharging\n")
    monkeypatch.setattr(battery, "BATTERY_ROOT", tmp_path)
    state = battery.read_state()
    assert state["on_battery"] is True
    assert state["charging"] is False
