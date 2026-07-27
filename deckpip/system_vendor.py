"""Bundled system-binary resolution: TigerVNC (Xvnc/vncpasswd) and the
GStreamer/wmctrl/xdotool stack GameMirror needs.

Historically these came from pacman (see ``defaults/install.sh``). CI now
also bundles them under ``<plugin_dir>/vendored/tigervnc`` and
``<plugin_dir>/vendored/gstreamer`` (see ``scripts/bundle-system-deps.sh``
and ``scripts/bundle-gst-plugins.sh``): each binary sits next to the
non-libc shared libraries it needs, rpath-patched to find them via
``$ORIGIN``, so it runs without the pacman package that normally provides
it.

Resolution always prefers the bundled copy and falls back to whatever is
on PATH — so a SteamOS build the CI bundle wasn't validated against still
works via the pacman fallback in ``defaults/install.sh``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _bundled_bin(plugin_dir: Path | str | None, subdir: str, name: str) -> Path | None:
    if plugin_dir is None:
        return None
    p = Path(plugin_dir) / "vendored" / subdir / "bin" / name
    return p if p.is_file() else None


def _resolve(plugin_dir: Path | str | None, subdir: str, name: str) -> str | None:
    bundled = _bundled_bin(plugin_dir, subdir, name)
    if bundled is not None:
        return str(bundled)
    return shutil.which(name)


def xvnc_path(plugin_dir: Path | str | None) -> str | None:
    return _resolve(plugin_dir, "tigervnc", "Xvnc")


def vncpasswd_path(plugin_dir: Path | str | None) -> str | None:
    return _resolve(plugin_dir, "tigervnc", "vncpasswd")


def gst_launch_path(plugin_dir: Path | str | None) -> str | None:
    return _resolve(plugin_dir, "gstreamer", "gst-launch-1.0")


def wmctrl_path(plugin_dir: Path | str | None) -> str | None:
    return _resolve(plugin_dir, "gstreamer", "wmctrl")


def xdotool_path(plugin_dir: Path | str | None) -> str | None:
    return _resolve(plugin_dir, "gstreamer", "xdotool")


def gst_plugins_dir(plugin_dir: Path | str | None) -> Path | None:
    if plugin_dir is None:
        return None
    p = Path(plugin_dir) / "vendored" / "gstreamer" / "gst-plugins-1.0"
    return p if p.is_dir() else None


def gst_plugin_env(plugin_dir: Path | str | None, base_env: dict) -> dict:
    """Point GST_PLUGIN_PATH at the bundled plugin .so directory when
    present, so gst-launch finds pipewiresrc/videoconvert/ximagesink
    without them being pacman-installed."""
    env = dict(base_env)
    plugins = gst_plugins_dir(plugin_dir)
    if plugins is not None:
        existing = env.get("GST_PLUGIN_PATH", "")
        env["GST_PLUGIN_PATH"] = (
            f"{plugins}{os.pathsep}{existing}" if existing else str(plugins)
        )
    return env


def status(plugin_dir: Path | str | None) -> dict:
    return {
        "Xvnc": xvnc_path(plugin_dir) or "",
        "vncpasswd": vncpasswd_path(plugin_dir) or "",
        "gst-launch-1.0": gst_launch_path(plugin_dir) or "",
        "wmctrl": wmctrl_path(plugin_dir) or "",
        "xdotool": xdotool_path(plugin_dir) or "",
        "gst_plugins_dir": str(gst_plugins_dir(plugin_dir) or ""),
    }
