#!/usr/bin/env bash
# DeckPiP one-shot installer.
#
# Run in Desktop Mode (Konsole) as the 'deck' user:
#   bash setup.sh
#
# Or, if you trust this branch and just want it on the Deck:
#   curl -fsSL https://raw.githubusercontent.com/NelleYn/Steamdeck-Plugins/claude/steamdeck-gaming-plugin-9YVmO/setup.sh | bash
#
# Prerequisites:
#   - Decky Loader already installed (https://decky.xyz)
#   - Working network connection
#   - 'deck' user with a sudo password set

set -euo pipefail

REPO_URL="https://github.com/NelleYn/Steamdeck-Plugins.git"
BRANCH="claude/steamdeck-gaming-plugin-9YVmO"
PLUGIN_DIR="/home/deck/homebrew/plugins/DeckPiP"
SRC_DIR="${HOME}/.cache/deckpip-build"

say() { printf '\033[1;36m[deckpip]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[deckpip]\033[0m %s\n' "$*" >&2; exit 1; }

# --- sanity checks --------------------------------------------------------
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

# --- 2. fetch sources -----------------------------------------------------
say "fetching sources into ${SRC_DIR}"
rm -rf "$SRC_DIR"
git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$SRC_DIR"

# --- 3. build frontend ----------------------------------------------------
say "building frontend (pnpm)"
cd "$SRC_DIR"
pnpm install
pnpm run build

[[ -f "$SRC_DIR/dist/index.js" ]] || die "Build did not produce dist/index.js"

# --- 4. install into Decky plugins dir -----------------------------------
say "installing into ${PLUGIN_DIR}"
sudo rm -rf "$PLUGIN_DIR"
sudo mkdir -p "$PLUGIN_DIR"
# Copy everything except build-only artifacts
sudo cp -r \
    plugin.json main.py defaults dist package.json README.md \
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
  journalctl --user -u plugin_loader -e
  sudo journalctl -u plugin_loader -e
EOF
