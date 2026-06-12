# DeckPiP

Picture-in-Picture of arbitrary Linux GUI applications (Discord,
Telegram, IDEs, …) over a running game in **Steam Deck Gaming Mode**.

> Status: functional PoC. Runs on a real Deck with TigerVNC (`Xvnc`),
> websockify, and noVNC installed. Most features work; known gaps are
> listed below.

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

See:
- [`docs/RESEARCH.md`](docs/RESEARCH.md) — feasibility audit (with
  ASSUMED / VERIFIED / RULED-OUT statuses per path).
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — wiring diagram and
  callable surface.
- [`docs/DISCORD_STREAMING.md`](docs/DISCORD_STREAMING.md) — design
  that lets Discord share the running game in Gaming Mode (standard
  Go Live is broken there); includes the on-hardware validation
  checklist that gates implementation.
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — common
  install/runtime issues and how to debug them.
- [`docs/DECKY_STORE.md`](docs/DECKY_STORE.md) — submission status
  to the official Decky Plugin Store and what blocks it today.

## Layout

```
plugin.json          Decky manifest
package.json         Frontend deps + rollup build
rollup.config.js
tsconfig.json
main.py              Python backend — Plugin class (Decky entry point)
deckpip/             Python modules (testable without Decky runtime)
  apps.py            Built-in + custom app registry
  audio.py           Per-guest PulseAudio volume control
  battery.py         /sys/class/power_supply reader
  bookmarks.py       Web-PiP URL bookmarks
  cloud_sync.py      rclone-backed cloud sync for Ludusavi backups
  diagnostics.py     Self-test snapshot for bug reports
  discovery.py       Flatpak + .desktop app scanner
  ludusavi.py        Save-file backup/restore via vendored Ludusavi
  mirror.py          GameMirror: gst pipeline into Xvnc
  mpris.py           MPRIS media controls via dbus-send
  notifications.py   D-Bus notification mirror → Decky toaster
  profiles.py        Per-game overlay profiles
  ptt.py             Push-to-talk via pactl mic mute/unmute
  session.py         PipSession: Xvnc + guest + websockify lifecycle
  settings.py        Atomic JSON settings store
  trackpad.py        Trackpad-as-mouse via xdotool
  updater.py         GitHub release check + setup.sh runner
  vendoring.py       Self-contained noVNC + websockify bootstrap
src/index.tsx        Quick Access UI + iframe route
defaults/install.sh  pacman dependency installer
setup.sh             One-shot build + install script
scripts/             CI helper scripts (make-zip.sh)
tests/               pytest + vitest unit tests
docs/                Research and architecture notes
```

## Build

```sh
pnpm install
pnpm run build
```

## Install on a Steam Deck

> The repository is public — anonymous install works in all three paths.

### A. Decky "Install plugin from URL" (no terminal needed)

In Gaming Mode → Quick Access → Decky panel → gear → **Developer**
tab → enable **Developer mode** → **Install plugin from URL**, paste:

```
https://github.com/NelleYn/Steamdeck-Plugins/releases/download/dev/DeckPiP.zip
```

CI republishes this on every push to the feature branch. After the
plugin installs, open the DeckPiP panel and tap **Install everything**
in **System** to fetch noVNC + websockify + Ludusavi + rclone.

### B. One-shot installer (Desktop Mode)

```sh
curl -fsSL https://raw.githubusercontent.com/NelleYn/Steamdeck-Plugins/main/setup.sh | bash
```

Installs build tools, clones, builds, copies, runs the pacman deps
installer and restarts Decky. End to end.

### C. From an existing checkout

```sh
cd /path/to/Steamdeck-Plugins
bash setup.sh
```

`setup.sh` auto-detects the checkout and skips cloning.

### Manual steps (if you'd rather do it yourself)

```sh
sudo pacman -Sy nodejs pnpm git
git clone https://github.com/NelleYn/Steamdeck-Plugins.git DeckPiP
cd DeckPiP
pnpm install && pnpm run build

sudo mkdir -p /home/deck/homebrew/plugins/DeckPiP
sudo cp -r plugin.json main.py deckpip defaults dist setup.sh \
    package.json README.md LICENSE \
    /home/deck/homebrew/plugins/DeckPiP/
sudo chown -R deck:deck /home/deck/homebrew/plugins/DeckPiP
sudo bash /home/deck/homebrew/plugins/DeckPiP/defaults/install.sh
sudo systemctl restart plugin_loader
```

To build the same zip Decky consumes (path A) yourself:

```sh
bash scripts/make-zip.sh   # produces build-pack/DeckPiP.zip
```

## Features

- **Apps panel** in Quick Access — built-in entries for Discord
  (Flatpak) and Telegram (Flatpak); one-tap launch. (Add any other
  command — including `xterm` if you want a debug terminal — via
  the Custom-app form.)
- **Custom apps** — register your own command from the panel
  (shlex-parsed argv, persisted server-side).
- **Web-PiP mode** — load an arbitrary `http(s)://` URL in the PiP
  iframe without spawning Xvnc; bookmark frequently used URLs.
- **Audio-only mode** — runs the guest in Xvnc with audio, skips the
  iframe, saves a chunk of CPU when you only need voice chat.
- **Overlay controls** — drag-bar header, resize handle, **opacity**
  slider (20–100 %), **click-through** toggle so input goes to the
  game, **snap-to-edges** at drop, three position presets, **touch
  mode** that doubles drag/resize hit areas.
- **Per-game profile** — save current overlay (app, geom, opacity)
  for the foreground Steam app; toggle **auto-launch on this game**
  to start DeckPiP automatically when that game launches.
- **Hotkeys** — **F10** toggles visibility, **F12 hold** acts as
  push-to-talk by un-/muting the default PulseAudio source via
  `pactl` (so it works with Discord, Mumble, Element, any voice
  client; no Discord-specific binding needed). Both hotkeys require
  Steam UI to have keyboard focus; see TROUBLESHOOTING.
- **GameMirror** — when Discord is the active PiP, optional toggle
  spawns a gstreamer pipeline that mirrors the real gamescope output
  into Xvnc as a window named `GameMirror`, so Discord's Go Live can
  share the game (works around the Gaming Mode portal bug).
- **Dependency self-check / installer** — System panel surfaces
  missing binaries and runs the bundled `defaults/install.sh`.
- **Diagnostics** — one-tap JSON snapshot of binaries, versions,
  paths; useful for bug reports.
- **One-click self-update** — polls a GitHub release (private repo
  supported via PAT entered in the System panel) and re-runs
  `setup.sh` in place.

## Known gaps (intentional for the PoC)

- No controller-as-mouse inside the PiP — use the trackpad.
- No HDR passthrough.
- One PiP session at a time.
- Guest audio shares the game's PulseAudio sink (no per-app loopback
  / audio ducking yet).
- DOM-based hotkeys don't fire while the game has input focus.
- One PiP session at a time (no multi-window).

## Next steps

In rough priority order:

1. On-hardware validation: test end-to-end on a real Steam Deck and
   update `docs/RESEARCH.md` statuses from [ASSUMED] to [VERIFIED].
2. Controller-as-mouse: bind the right trackpad to noVNC pointer
   events; current `trackpad.py` uses `xdotool` which needs focus.
3. Per-session PulseAudio sink for the guest app (audio ducking /
   per-app volume isolation, not just the global volume slider).
4. Global hotkeys via `gamescope_action_binding` when that API
   stabilises in a released SteamOS — avoids the Steam Input workaround.
5. Measure FPS and CPU overhead during a Vulkan game; document the
   budget honestly and consider GPU-copy path for GameMirror.

## Licence

BSD-3-Clause.
