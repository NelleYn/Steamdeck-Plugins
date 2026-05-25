#!/usr/bin/env bash
# DeckPiP runtime-dependency installer.
#
# Invoked by the plugin backend (Plugin.install_dependencies) running as
# root. Also runnable by hand in Desktop Mode for users who prefer the
# manual path.
#
# Strategy: keep the required set as small as possible. Optional packages
# unlock extra features (GameMirror) but the base PiP flow works without
# them.

set -u
set -o pipefail

REQUIRED=(
    tigervnc           # Xvnc, vncpasswd — only true required pacman dep
)
# Notes on what we DON'T pacman-install any more:
#  - python-websockify  vendored via pip into DECKY_PLUGIN_RUNTIME_DIR
#  - novnc              vendored via tarball download from GitHub
# Use the panel's "Install vendored runtime" button after pacman is done.

OPTIONAL=(
    wmctrl              # GameMirror: rename + fullscreen the mirror window
    gst-plugin-pipewire # GameMirror: the `pipewiresrc` GStreamer element
    gst-plugins-good    # GameMirror: videoconvert + ximagesink
)
# Notes on things NOT installed here:
#  - pactl       ships with libpulse, already in the SteamOS base image
#  - xterm       removed; add as a Custom App from the panel if you want it
#  - xdotool     removed; PTT now uses pactl, GameMirror works without it
#  - flatpak     base image; only needed if you launch flatpak'd guests

PACKAGES=("${REQUIRED[@]}" "${OPTIONAL[@]}")

was_readonly=0
restore_readonly() {
    if [[ "$was_readonly" == "1" ]]; then
        steamos-readonly enable || true
    fi
}
trap restore_readonly EXIT

if command -v steamos-readonly >/dev/null 2>&1; then
    if steamos-readonly status 2>/dev/null | grep -qi enabled; then
        was_readonly=1
        echo "[deckpip] disabling steamos-readonly"
        steamos-readonly disable
    fi
fi

if [[ ! -d /etc/pacman.d/gnupg ]] || [[ -z "$(ls -A /etc/pacman.d/gnupg 2>/dev/null)" ]]; then
    echo "[deckpip] initializing pacman keyring"
    pacman-key --init
    pacman-key --populate archlinux holo 2>/dev/null || pacman-key --populate
fi

echo "[deckpip] installing required: ${REQUIRED[*]}"
pacman -Sy --needed --noconfirm "${REQUIRED[@]}"
rc=$?

if [[ $rc -ne 0 ]]; then
    echo "[deckpip] required-package install failed (rc=$rc)" >&2
    exit $rc
fi

echo "[deckpip] installing optional: ${OPTIONAL[*]} (failures non-fatal)"
pacman -S --needed --noconfirm "${OPTIONAL[@]}" || \
    echo "[deckpip] some optional packages did not install; GameMirror may be unavailable"

echo "[deckpip] verifying required:"
for bin in Xvnc vncpasswd websockify pactl; do
    if command -v "$bin" >/dev/null 2>&1; then
        echo "  ok  $bin -> $(command -v "$bin")"
    else
        echo "  MISSING $bin" >&2
    fi
done

echo "[deckpip] verifying optional:"
for bin in wmctrl gst-launch-1.0 pw-cli; do
    if command -v "$bin" >/dev/null 2>&1; then
        echo "  ok  $bin -> $(command -v "$bin")"
    else
        echo "  -- $bin not installed (GameMirror unavailable)"
    fi
done

for d in /usr/share/novnc /usr/share/webapps/novnc /usr/lib/novnc; do
    if [[ -f "$d/vnc.html" ]]; then
        echo "  ok  novnc -> $d"
        break
    fi
done

echo "[deckpip] done"
