from pathlib import Path

from deckpip import system_vendor


def _make_bundled_bin(plugin_dir: Path, subdir: str, name: str) -> Path:
    bin_dir = plugin_dir / "vendored" / subdir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    p = bin_dir / name
    p.write_text("#!/bin/sh\necho fake\n")
    p.chmod(0o755)
    return p


def test_xvnc_path_none_when_absent_and_not_on_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_vendor.shutil, "which", lambda _: None)
    assert system_vendor.xvnc_path(tmp_path) is None


def test_xvnc_path_none_when_plugin_dir_is_none(monkeypatch) -> None:
    monkeypatch.setattr(system_vendor.shutil, "which", lambda _: None)
    assert system_vendor.xvnc_path(None) is None


def test_xvnc_path_prefers_bundled_over_system(monkeypatch, tmp_path: Path) -> None:
    bundled = _make_bundled_bin(tmp_path, "tigervnc", "Xvnc")
    monkeypatch.setattr(system_vendor.shutil, "which", lambda _: "/usr/bin/Xvnc")
    assert system_vendor.xvnc_path(tmp_path) == str(bundled)


def test_xvnc_path_falls_back_to_system_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        system_vendor.shutil, "which",
        lambda name: "/usr/bin/Xvnc" if name == "Xvnc" else None,
    )
    assert system_vendor.xvnc_path(tmp_path) == "/usr/bin/Xvnc"


def test_vncpasswd_path_prefers_bundled(monkeypatch, tmp_path: Path) -> None:
    bundled = _make_bundled_bin(tmp_path, "tigervnc", "vncpasswd")
    monkeypatch.setattr(system_vendor.shutil, "which", lambda _: "/usr/bin/vncpasswd")
    assert system_vendor.vncpasswd_path(tmp_path) == str(bundled)


def test_gst_launch_path_prefers_bundled(monkeypatch, tmp_path: Path) -> None:
    bundled = _make_bundled_bin(tmp_path, "gstreamer", "gst-launch-1.0")
    monkeypatch.setattr(system_vendor.shutil, "which", lambda _: "/usr/bin/gst-launch-1.0")
    assert system_vendor.gst_launch_path(tmp_path) == str(bundled)


def test_wmctrl_and_xdotool_path_fall_back_when_no_bundle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        system_vendor.shutil, "which",
        lambda name: f"/usr/bin/{name}",
    )
    assert system_vendor.wmctrl_path(tmp_path) == "/usr/bin/wmctrl"
    assert system_vendor.xdotool_path(tmp_path) == "/usr/bin/xdotool"


def test_gst_plugins_dir_none_when_absent(tmp_path: Path) -> None:
    assert system_vendor.gst_plugins_dir(tmp_path) is None
    assert system_vendor.gst_plugins_dir(None) is None


def test_gst_plugins_dir_present(tmp_path: Path) -> None:
    p = tmp_path / "vendored" / "gstreamer" / "gst-plugins-1.0"
    p.mkdir(parents=True)
    assert system_vendor.gst_plugins_dir(tmp_path) == p


def test_gst_plugin_env_adds_path_when_bundle_present(tmp_path: Path) -> None:
    p = tmp_path / "vendored" / "gstreamer" / "gst-plugins-1.0"
    p.mkdir(parents=True)
    env = system_vendor.gst_plugin_env(tmp_path, {"FOO": "bar"})
    assert env["FOO"] == "bar"
    assert env["GST_PLUGIN_PATH"] == str(p)


def test_gst_plugin_env_appends_to_existing_path(tmp_path: Path) -> None:
    p = tmp_path / "vendored" / "gstreamer" / "gst-plugins-1.0"
    p.mkdir(parents=True)
    env = system_vendor.gst_plugin_env(tmp_path, {"GST_PLUGIN_PATH": "/existing"})
    assert env["GST_PLUGIN_PATH"] == f"{p}:/existing"


def test_gst_plugin_env_unchanged_when_no_bundle(tmp_path: Path) -> None:
    env = system_vendor.gst_plugin_env(tmp_path, {"FOO": "bar"})
    assert "GST_PLUGIN_PATH" not in env
    assert env == {"FOO": "bar"}


def test_status_reports_all_keys(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_vendor.shutil, "which", lambda _: None)
    s = system_vendor.status(tmp_path)
    assert set(s.keys()) == {
        "Xvnc", "vncpasswd", "gst-launch-1.0", "wmctrl", "xdotool", "gst_plugins_dir",
    }
    assert s["Xvnc"] == ""
