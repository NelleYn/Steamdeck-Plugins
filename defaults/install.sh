#!/usr/bin/env bash
# DeckPiP runtime-dependency installer.
#
# Invoked by the plugin backend (Plugin.install_dependencies) running as root.
# Also runnable by hand in Desktop Mode for users who prefer the manual path.
#
# Steps:
#   1. Disable steamos-readonly (no-op if already writable)
#   2. Initialize pacman keyring (idempotent)
#   3. Install: tigervnc, python-websockify, novnc, xterm, wmctrl
#   4. Re-enable steamos-readonly
#
# Re-enables read-only even on failure via trap.

set -u
set -o pipefail

PACKAGES=(tigervnc python-websockify novnc xterm wmctrl)

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

echo "[deckpip] installing: ${PACKAGES[*]}"
pacman -Sy --needed --noconfirm "${PACKAGES[@]}"
rc=$?

if [[ $rc -ne 0 ]]; then
    echo "[deckpip] pacman exited with rc=$rc" >&2
    exit $rc
fi

echo "[deckpip] verifying:"
for bin in Xvnc vncpasswd websockify xterm wmctrl; do
    if command -v "$bin" >/dev/null 2>&1; then
        echo "  ok  $bin -> $(command -v "$bin")"
    else
        echo "  MISSING $bin" >&2
    fi
done

for d in /usr/share/novnc /usr/share/webapps/novnc /usr/lib/novnc; do
    if [[ -f "$d/vnc.html" ]]; then
        echo "  ok  novnc -> $d"
        break
    fi
done

echo "[deckpip] done"
