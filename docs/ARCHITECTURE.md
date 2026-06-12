# DeckPiP — Architecture

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
|   |   Custom route /deckpip/view:                              |   |
|   |   +---------------------------------------------------+    |   |
|   |   |  <iframe src="http://127.0.0.1:6901/vnc.html...">|    |   |
|   |   |                  (noVNC client)                   |    |   |
|   |   +---------------------------------------------------+    |   |
|   +------------------------------------------------------------+   |
+-------------------------------------------------------------------+
                                |
                                |  HTTP+WebSocket on loopback
                                v
+-------------------- Decky backend (Python, root) -----------------+
|                                                                   |
|   Xvnc :42  -RfbPort 5942-                                        |
|     (TigerVNC, X server + VNC built-in)                           |
|        |                                                          |
|   target_app (DISPLAY=:42)                                        |
|                                                                   |
|   websockify --web /usr/share/novnc 127.0.0.1:6901 <-> :5942      |
|                                                                   |
|   (optional) gst-launch-1.0 pipewiresrc ! ximagesink display=:42  |
|        -> "GameMirror" window on Xvnc, sees real game frames      |
|        -> Discord on the same Xvnc can Go Live it                 |
|                                                                   |
+-------------------------------------------------------------------+
```

## Process layout

One `PipSession` owns the process group for a running session:

| Process | Purpose | Lifetime |
|---|---|---|
| `Xvnc :42` | TigerVNC X server with built-in VNC, listens on `127.0.0.1:5942` | start → stop |
| target app | `flatpak run …` / `xterm` / custom command, `DISPLAY=:42` | start → stop |
| `websockify` | bridges `127.0.0.1:6901` ↔ `127.0.0.1:5942`, serves `/usr/share/novnc/vnc.html` | non-audio-only sessions only |
| `gst-launch-1.0` | `pipewiresrc → videoconvert → ximagesink display=:42`, only when GameMirror is on | toggle in UI |

All four are launched with `preexec_fn=os.setsid` so we can `killpg` the
whole group on stop. Stop is two-phase: `SIGTERM`, wait 3 s, then
`SIGKILL` for anything that didn't exit.

## Callable surface (frontend ↔ backend)

| Callable | Purpose |
|---|---|
| `list_apps` | Built-ins + persisted custom apps |
| `add_custom_app(id, label, command)` | shlex-parsed command, stored in settings.json |
| `remove_custom_app(id)` | |
| `settings_get(key, default)` | UI state persistence (geom, opacity, click-through) |
| `settings_set(key, value)` | |
| `check_dependencies()` | which Xvnc/websockify/noVNC/xterm/wmctrl are present |
| `install_dependencies()` | runs `defaults/install.sh` (pacman, with steamos-readonly toggle) |
| `start_pip(app_id, audio_only)` | spawn Xvnc + guest [+ websockify] |
| `stop_pip()` | reverse-order termination, clean up vncpasswd |
| `start_game_mirror()` | find gamescope PipeWire node, spawn gst pipeline, rename + fullscreen window |
| `stop_game_mirror()` | kill the gst pipeline only |

`start_pip`/`stop_pip`/`start_game_mirror`/`stop_game_mirror` are
serialized by a single `asyncio.Lock` to prevent the start-twice race
and ensure stop sees a consistent session state.

## Frontend layout

- Quick Access panel (`Content`): app list, install/check deps,
  Web-PiP URL field, Custom-app form, persisted toggles.
- Custom Steam UI route `/deckpip/view` rendering `<PipView>`:
  absolutely-positioned container holding the iframe, with drag-bar
  header, resize handle (bottom-right), opacity, click-through.
- State held in a module-level singleton with `useSyncExternalStore`;
  persisted slice (`geom`, `opacity`, `clickThrough`) is sent through
  `settings_set` on every change.
- `F10` toggles visibility (DOM keydown listener installed at plugin
  load).

## Lifecycle invariants

| Event | Action |
|---|---|
| Plugin load (`_main`) | initialize `asyncio.Lock` |
| User Start | acquire lock → spawn → release; open route, set state.url |
| User Stop | acquire lock → SIGTERM/SIGKILL all four; clear state |
| Plugin unload (`_unload`) | force stop if running |
| Plugin uninstall (`_uninstall`) | force stop + (future) clean settings dir |
| Gaming Mode logout | systemd kills the `deck` session → our children die with it |

## Security

- KasmVNC bound to `127.0.0.1` only.
- 8-character TigerVNC password (TigerVNC limit) regenerated on every
  Start — loopback-only, so length isn't a security boundary.
- `_root` flag: backend runs as root. We never accept shell strings
  from the frontend; custom-app commands are split with `shlex.split`
  and exec'd as argv, not via a shell.
- Pacman install never runs without explicit user click on **Install
  dependencies**.

## Backend module map

| Module | Purpose |
|---|---|
| `main.py` | `Plugin` class — Decky entry point, composes all modules |
| `deckpip/session.py` | `PipSession`, `terminate`, port-wait helper |
| `deckpip/apps.py` | Built-in + custom app registry; shlex validation |
| `deckpip/audio.py` | Per-guest volume via `pactl sink-input` |
| `deckpip/battery.py` | `/sys/class/power_supply` reader |
| `deckpip/bookmarks.py` | Web-PiP URL bookmarks (http/https only) |
| `deckpip/cloud_sync.py` | rclone vendoring + sync up/down |
| `deckpip/diagnostics.py` | Binary version snapshot for bug reports |
| `deckpip/discovery.py` | Flatpak list + `.desktop` scanner |
| `deckpip/ludusavi.py` | Save backup/restore via vendored Ludusavi |
| `deckpip/mirror.py` | GameMirror: `pipewiresrc → ximagesink` pipeline |
| `deckpip/mpris.py` | MPRIS transport via `dbus-send` |
| `deckpip/notifications.py` | `dbus-monitor` → Decky toaster bridge |
| `deckpip/profiles.py` | Per-game overlay profiles keyed by Steam appid |
| `deckpip/ptt.py` | Push-to-talk via `pactl set-source-mute` |
| `deckpip/settings.py` | Atomic JSON store (tmp + `os.replace`) |
| `deckpip/trackpad.py` | Trackpad-as-mouse percentage → `xdotool` pixels |
| `deckpip/updater.py` | GitHub release poll + `setup.sh` runner |
| `deckpip/vendoring.py` | noVNC tarball + websockify pip install |

## Runtime dependencies (not in base SteamOS)

Provided by `defaults/install.sh` (pacman) or automatically vendored
at first use:

### Vendored (no pacman needed, auto-downloaded by plugin)

- `noVNC` v1.5.0 — unpacked into `DECKY_PLUGIN_RUNTIME_DIR/vendored/`
- `websockify` — pip-installed into the vendored Python prefix
- `ludusavi` v0.27.0 — static binary for save backup/restore
- `rclone` v1.69.1 — static binary for cloud sync

### Pacman (required, not vendored yet)

- `tigervnc` (provides `Xvnc` and `vncpasswd`)

### Pacman (optional, GameMirror only)

- `gst-plugins-good` (`ximagesink`)
- `gst-plugin-pipewire` (`pipewiresrc`)
- `xdotool`
- `wmctrl`

Guests are user-installed Flatpak / native packages; the plugin just execs them.
