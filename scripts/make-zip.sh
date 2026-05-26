#!/usr/bin/env bash
# Build a Decky-compatible release zip of DeckPiP.
#
# Decky's "Install from URL" expects:
#   - a direct link to a .zip
#   - inside the zip: exactly one top-level folder containing plugin.json
#     (so paths look like "DeckPiP/plugin.json", "DeckPiP/main.py", ...)
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
