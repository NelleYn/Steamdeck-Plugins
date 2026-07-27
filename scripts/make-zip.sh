#!/usr/bin/env bash
# Build a Decky-compatible release zip of DeckPiP.
#
# Decky's "Install from URL" expects:
#   - a direct link to a .zip
#   - inside the zip: exactly one top-level folder containing plugin.json
#     (so paths look like "DeckPiP/plugin.json", "DeckPiP/main.py", ...)
#
# Also vendors the runtime deps into the zip so a fresh install needs
# nothing downloaded or pacman-installed separately (see
# scripts/fetch-vendored.py and deckpip/vendoring.py for the "why"):
#   - noVNC, websockify, Ludusavi, rclone: fetched here on any machine.
#   - TigerVNC (Xvnc/vncpasswd) + the GameMirror GStreamer stack: only
#     bundled when this runs on an Arch/Holo host with pacman + patchelf
#     (i.e. the CI vendor-system job) — see scripts/bundle-system-deps.sh
#     and scripts/bundle-gst-plugins.sh. Skipped elsewhere with a warning;
#     `defaults/install.sh` (pacman) remains the fallback for those.
#
# Output: build-pack/DeckPiP.zip relative to the repo root.

set -euo pipefail
cd "$(dirname "$0")/.."

NAME="DeckPiP"
OUT_DIR="build-pack"

if ! command -v pnpm >/dev/null; then
    echo "pnpm not found. Install Node.js + pnpm first." >&2
    exit 1
fi

echo "[make-zip] building frontend"
pnpm install
pnpm run build
[[ -f dist/index.js ]] || { echo "dist/index.js missing after build" >&2; exit 1; }

echo "[make-zip] packing"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/$NAME"
find deckpip -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
cp -r \
    plugin.json \
    main.py \
    deckpip \
    defaults \
    dist \
    package.json \
    README.md \
    LICENSE \
    setup.sh \
    "$OUT_DIR/$NAME/"

echo "[make-zip] vendoring noVNC + websockify + Ludusavi + rclone"
python3 scripts/fetch-vendored.py "$OUT_DIR/$NAME"

if command -v pacman >/dev/null && command -v patchelf >/dev/null; then
    echo "[make-zip] vendoring TigerVNC + GameMirror (Arch/Holo host detected)"
    bash scripts/bundle-system-deps.sh "$OUT_DIR/$NAME/vendored/tigervnc" Xvnc vncpasswd
    bash scripts/bundle-gst-plugins.sh "$OUT_DIR/$NAME/vendored/gstreamer"
else
    echo "[make-zip] skipping TigerVNC/GameMirror vendoring (needs pacman + patchelf," \
        "i.e. an Arch/Holo host — CI's vendor-system job does this)." >&2
    echo "[make-zip] the zip will fall back to defaults/install.sh (pacman) for those." >&2
fi

cd "$OUT_DIR"
rm -f "$NAME.zip"
zip -qr "$NAME.zip" "$NAME"
cd -

echo "[make-zip] done: $(pwd)/$OUT_DIR/$NAME.zip"
echo
echo "To install in Decky:"
echo "  1. Host this zip somewhere with a direct HTTPS link"
echo "     (GitHub Release asset is the canonical place)."
echo "  2. In Gaming Mode -> Quick Access -> Decky -> gear icon"
echo "     -> Developer -> 'Install plugin from URL' -> paste the URL."
