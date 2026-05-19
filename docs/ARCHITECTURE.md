# DeckPiP — PoC Architecture

```
+--------------------- Gaming Mode (gamescope) ---------------------+
|                                                                   |
|   +--------------- Game (Vulkan/GL fullscreen) ---------------+   |
|   |                                                            |   |
|   +------------------------------------------------------------+   |
|                                                                   |
|   +-- Steam UI (CEF, composited on top by gamescope) ---------+   |
|   |                                                            |   |
|   |   Quick Access  ->  DeckPiP panel  ->  "Start PiP"        |   |
|   |                                                            |   |
|   |   CEF tab (custom route):                                  |   |
|   |   +---------------------------------------------------+    |   |
|   |   |  <iframe src="http://127.0.0.1:6901/?token=..."/> |    |   |
|   |   |                  (noVNC client)                   |    |   |
|   |   +---------------------------------------------------+    |   |
|   +------------------------------------------------------------+   |
+-------------------------------------------------------------------+
                                |
                                |  HTTP/WebSocket on loopback
                                v
+-------------------- Decky backend (Python, root) -----------------+
|                                                                   |
|   Xvfb :42  <----+                                                |
|                  |  X11                                           |
|   target_app ----+                                                |
|                                                                   |
|   KasmVNC ---------> binds 127.0.0.1:6901, token-auth             |
|                                                                   |
+-------------------------------------------------------------------+
```

## Components

### Backend (`main.py`)

- `start_pip(app_id: str) -> {ok, url, token}`
  1. Allocate a free X display number (e.g. `:42`).
  2. Spawn `Xvfb :42 -screen 0 1280x800x24` as the `deck` user.
  3. Spawn the target app with `DISPLAY=:42` and a per-app env
     (e.g. `--no-sandbox` for Electron apps).
  4. Spawn `kasmvncserver` (or `x11vnc + websockify + noVNC`) bound to
     `127.0.0.1:6901` with a random token.
  5. Return the noVNC URL + token to the frontend.
- `stop_pip() -> {ok}` — kill the process group in reverse order;
  remove the X socket.
- `list_apps() -> [{id, label, command, icon}]` — read from
  `decky.DECKY_PLUGIN_SETTINGS_DIR/apps.json` (or built-in defaults).
- `_unload` and `_uninstall` must call `stop_pip()`.

### Frontend (`src/index.tsx`)

- Decky panel in Quick Access: list of apps, **Start / Stop** toggle.
- On **Start**, call `start_pip`, then register a custom route
  (`routerHook.addRoute("/deckpip/view", ...)`) that renders an
  `<iframe>` of the returned noVNC URL.
- Navigate to that route via `Navigation.Navigate("/deckpip/view")` —
  Steam UI compositor will show it on top of the game.
- On **Stop**, remove the route and call `stop_pip`.

### Lifecycle invariants

| Event | Action |
|---|---|
| Plugin load | nothing — wait for user |
| User Start | spawn Xvfb → app → KasmVNC; open route |
| User Stop | close route; kill processes |
| Plugin unload (`_unload`) | force stop if running |
| Plugin uninstall (`_uninstall`) | force stop + clean settings dir |
| Gaming Mode logout | systemd kills `deck` session → our children die with it |

### Security

- KasmVNC bound to `127.0.0.1` only.
- Random 32-byte hex token per session, regenerated on every Start.
- App command list is whitelist-only (no arbitrary `exec` from the UI).

### Dependencies (not in base SteamOS image)

PoC will assume the user installs these manually via `pacman` after
unlocking the root partition, OR via a Flatpak runtime. To be decided
once the wiring works. Candidates:

- `xorg-server-xvfb`
- `kasmvncserver` (preferred — bundles websockify and noVNC)
- target apps: `discord` (Flatpak `com.discordapp.Discord`),
  `telegram-desktop` (Flatpak `org.telegram.desktop`), etc.

A bootstrap script that downloads a portable KasmVNC tarball into
`decky.DECKY_PLUGIN_RUNTIME_DIR` is the leading idea — keeps the
plugin self-contained and survives SteamOS updates.
