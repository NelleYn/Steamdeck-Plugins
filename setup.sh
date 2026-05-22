#!/usr/bin/env bash
# DeckPiP installer.
#
# Two supported workflows (the repo is private, so plain anonymous clone won't
# work).
#
# A. From an already-checked-out copy (simplest, recommended):
#      cd /path/to/Steamdeck-Plugins
#      bash setup.sh
#    The script detects it's inside a checkout (plugin.json + main.py + src/
#    in the same directory) and skips the clone.
#
# B. With a GitHub Personal Access Token:
#      export GITHUB_TOKEN=ghp_xxx          # fine-grained PAT, "contents: read" on this repo
#      curl -fsSL -H "Authorization: Bearer $GITHUB_TOKEN" \
#        https://raw.githubusercontent.com/NelleYn/Steamdeck-Plugins/claude/steamdeck-gaming-plugin-9YVmO/setup.sh \
#        | bash
#    The PAT is forwarded to the inner git clone via the URL.
#
# Prerequisites in both cases:
#   - Decky Loader already installed (https://decky.xyz)
#   - Working network connection
#   - 'deck' user with a sudo password set

set -euo pipefail

REPO_URL="https://github.com/NelleYn/Steamdeck-Plugins.git"
BRANCH="claude/steamdeck-gaming-plugin-9YVmO"
PLUGIN_DIR="/home/deck/homebrew/plugins/DeckPiP"
SRC_DIR_DEFAULT="${HOME}/.cache/deckpip-build"

say() { printf '\033[1;36m[deckpip]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[deckpip]\033[0m %s\n' "$*" >&2; exit 1; }

[[ "$(id -un)" == "deck" ]] || die "Run as the 'deck' user (Desktop Mode terminal)."
[[ -d "$HOME/homebrew" ]] || die "Decky Loader not detected. Install from https://decky.xyz first."

# --- 1. build toolchain ---------------------------------------------------
need=()
for bin in node pnpm git; do
    command -v "$bin" >/dev/null || need+=("$bin")
done
if (( ${#need[@]} )); then
    say "installing build tools (${need[*]}) via pacman"
    sudo steamos-readonly disable
    sudo pacman-key --init >/dev/null 2>&1 || true
    sudo pacman-key --populate >/dev/null 2>&1 || true
    sudo pacman -Sy --needed --noconfirm nodejs pnpm git
    sudo steamos-readonly enable
fi

# --- 2. locate or fetch sources ------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
if [[ -n "$SCRIPT_DIR" \
      && -f "$SCRIPT_DIR/plugin.json" \
      && -f "$SCRIPT_DIR/main.py" \
      && -d "$SCRIPT_DIR/src" ]]; then
    SRC_DIR="$SCRIPT_DIR"
    say "using existing checkout at $SRC_DIR"
else
    SRC_DIR="$SRC_DIR_DEFAULT"
    say "fetching sources into $SRC_DIR"
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        REPO_URL_AUTH="https://oauth2:${GITHUB_TOKEN}@github.com/NelleYn/Steamdeck-Plugins.git"
    else
        die "Repository is private. Either run this script from an existing checkout, or set GITHUB_TOKEN before running."
    fi
    rm -rf "$SRC_DIR"
    git clone --depth 1 -b "$BRANCH" "$REPO_URL_AUTH" "$SRC_DIR" \
        || die "git clone failed (check your token's permissions: contents: read on this repo)"
fi

cd "$SRC_DIR"

# --- 3. build frontend ----------------------------------------------------
say "building frontend (pnpm)"
pnpm install
pnpm run build
[[ -f dist/index.js ]] || die "Build did not produce dist/index.js"

# --- 4. install into Decky plugins dir -----------------------------------
say "installing into ${PLUGIN_DIR}"
sudo rm -rf "$PLUGIN_DIR"
sudo mkdir -p "$PLUGIN_DIR"
# Strip any local __pycache__ that pytest may have produced.
find deckpip -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
sudo cp -r \
    plugin.json main.py deckpip defaults dist package.json README.md LICENSE \
    "$PLUGIN_DIR/"
sudo chown -R deck:deck "$PLUGIN_DIR"

# --- 5. runtime dependencies ---------------------------------------------
say "installing runtime deps (TigerVNC, websockify, noVNC, xterm, wmctrl)"
sudo bash "$PLUGIN_DIR/defaults/install.sh"

# --- 6. restart Decky -----------------------------------------------------
say "restarting plugin_loader"
sudo systemctl restart plugin_loader

cat <<EOF

\033[1;32m[deckpip]\033[0m done.

Next steps:
  1. Switch back to Gaming Mode (Steam menu -> Power -> Switch to Gaming Mode).
  2. Press the '...' button to open Quick Access.
  3. Open the Decky panel (plug icon) -> DeckPiP.
  4. Optional: in the panel tap "Check dependencies" to confirm everything
     installed correctly.
  5. Try the "xterm (debug)" launcher first; it has no Flatpak dependency.

If the plugin does not appear, check the Decky logs:
  sudo journalctl -u plugin_loader -e
EOF
