# DeckPiP

Picture-in-Picture of arbitrary Linux GUI applications (Discord,
Telegram, IDEs, …) over a running game in **Steam Deck Gaming Mode**.

> Status: research / PoC scaffolding. Not yet runnable on a real Deck —
> needs `kasmvncserver` and `Xvfb` installed, and the audio/input
> wiring is intentionally minimal in this skeleton.

## How it works

Gamescope (the Wayland compositor used by Gaming Mode) does **not**
expose a public API to overlay third-party windows on top of a running
game ([gamescope#288](https://github.com/Plagman/gamescope/issues/288)).
The only surface Gamescope already composites over the game is the
Steam UI itself.

DeckPiP exploits that fact:

1. A Decky plugin renders a custom route inside the Steam UI.
2. The route contains an `<iframe>` pointing at a noVNC client.
3. The noVNC client connects to a `KasmVNC` server running on
   `127.0.0.1`, attached to an `Xvfb` display where the target Linux
   app is running.
4. Steam UI composites the iframe over the game — this is the actual
   "PiP".

See [`docs/RESEARCH.md`](docs/RESEARCH.md) for the feasibility audit,
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the wiring
diagram, and [`docs/DISCORD_STREAMING.md`](docs/DISCORD_STREAMING.md)
for the design that lets Discord share the running game in Gaming
Mode (the standard "Go Live" path is broken there).

## Layout

```
plugin.json          Decky manifest
package.json         Frontend deps + rollup build
rollup.config.js
tsconfig.json
main.py              Python backend (Xvfb + app + KasmVNC lifecycle)
src/index.tsx        Quick Access UI + iframe route
docs/                Research and architecture notes
```

## Build

```sh
pnpm install
pnpm run build
```

## Install on a Steam Deck

> The repository is **private**, so Decky's "Install plugin from URL"
> won't work (Decky downloads anonymously and would get 404). You
> need to install from a local checkout. Two paths:

### A. From an existing checkout (recommended)

Pull the repository to the Deck however you like (clone with a PAT
via Konsole, copy from another machine over SSH/USB, GitHub Desktop,
etc.). Then in Desktop Mode → Konsole:

```sh
cd /path/to/Steamdeck-Plugins
bash setup.sh
```

`setup.sh` detects it's inside a checkout, installs `nodejs`/`pnpm`/`git`
if missing, builds the frontend, copies the plugin into
`~/homebrew/plugins/DeckPiP`, runs `defaults/install.sh` for runtime
deps (TigerVNC + websockify + noVNC + xterm + wmctrl), and restarts
Decky.

### B. Fresh clone with a GitHub Personal Access Token

Create a fine-grained PAT with **"Contents: read"** on this repo
(https://github.com/settings/tokens?type=beta), then in Desktop Mode
→ Konsole:

```sh
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxx
curl -fsSL -H "Authorization: Bearer $GITHUB_TOKEN" \
    https://raw.githubusercontent.com/NelleYn/Steamdeck-Plugins/claude/steamdeck-gaming-plugin-9YVmO/setup.sh \
    | bash
```

The token is forwarded to the inner `git clone` via the URL. Token
never lands on disk.

### Manual steps (if you'd rather do it yourself)

```sh
sudo pacman -Sy nodejs pnpm git
# clone with your auth method of choice, e.g.:
git clone -b claude/steamdeck-gaming-plugin-9YVmO \
    https://oauth2:$GITHUB_TOKEN@github.com/NelleYn/Steamdeck-Plugins.git DeckPiP
cd DeckPiP
pnpm install && pnpm run build

sudo mkdir -p /home/deck/homebrew/plugins/DeckPiP
sudo cp -r plugin.json main.py defaults dist package.json README.md \
    /home/deck/homebrew/plugins/DeckPiP/
sudo chown -R deck:deck /home/deck/homebrew/plugins/DeckPiP
sudo bash /home/deck/homebrew/plugins/DeckPiP/defaults/install.sh
sudo systemctl restart plugin_loader
```

To build the release-format zip for offline use:

```sh
bash scripts/make-zip.sh   # produces build-pack/DeckPiP.zip
```

## Features

- Quick Access panel with a list of preset apps
  (Discord/Telegram/xterm) and one-tap launch.
- Drag the PiP overlay by its title bar; **opacity slider** (20–100 %);
  **click-through** toggle so input goes to the game; presets:
  *small bottom-right*, *medium left*, *fullscreen*.
- **Audio-only mode** for each app — runs guest in Xvnc with audio,
  doesn't open the iframe, saves a chunk of CPU.
- **Dependency self-check / installer** built into the panel.

## Known gaps (intentional for the PoC)

- No controller-as-mouse inside the PiP — use the trackpad.
- No HDR passthrough.
- One PiP session at a time.
- Guest audio shares the game's PulseAudio sink.
- Process cleanup is SIGTERM-only; no escalation to SIGKILL on hang.
- Hotkey toggle for show/hide is not wired up yet — use the panel.

## Next steps

In rough priority order:

1. `pnpm install && pnpm run build` on a real machine; fix whatever
   the rollup config complains about.
2. Bootstrap script that fetches a portable KasmVNC tarball into
   `DECKY_PLUGIN_RUNTIME_DIR`, so the plugin does not depend on
   `pacman`-installed binaries on the immutable SteamOS root.
3. Whitelist + custom-command UI: let the user register their own
   apps in `apps.json` from the panel.
4. Audio routing: create a per-session PulseAudio sink for the guest
   app, optional mute / volume slider in the panel.
5. Controller-as-mouse: bind the right trackpad to noVNC pointer
   events via `gamescope_action_binding`.
6. Measure FPS and CPU overhead while a Vulkan game is running;
   document the budget honestly.

## Licence

BSD-3-Clause.
