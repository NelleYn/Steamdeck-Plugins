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

See [`docs/RESEARCH.md`](docs/RESEARCH.md) for the feasibility audit
and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the wiring
diagram.

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

```sh
# from the repo root, copy to the plugin dir
sudo cp -r . /home/deck/homebrew/plugins/DeckPiP
sudo systemctl restart plugin_loader
```

System dependencies expected on the Deck (not in the base image):

- `Xvfb` (`xorg-server-xvfb`)
- `kasmvncserver`
- the target app you want to mirror

A future iteration will bundle a portable KasmVNC tarball under
`DECKY_PLUGIN_RUNTIME_DIR` so the plugin is self-contained.

## Known gaps (intentional for the PoC)

- No controller-as-mouse inside the PiP — use the trackpad.
- No HDR passthrough.
- One PiP session at a time.
- Guest audio shares the game's PulseAudio sink.
- Process cleanup is SIGTERM-only; no escalation to SIGKILL on hang.

## Licence

BSD-3-Clause.
