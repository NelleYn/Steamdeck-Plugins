# DeckPiP — Troubleshooting

Common stumbling blocks, in roughly the order you'll hit them.

## Plugin doesn't appear in the Decky list

```sh
sudo journalctl -u plugin_loader -e
```

Likely causes:

- `plugin.json` malformed (Decky logs `Failed to load plugin: ...`).
- `dist/index.js` missing — did `pnpm run build` actually run? Check
  `/home/deck/homebrew/plugins/DeckPiP/dist/index.js` exists.
- `main.py` import error — Decky logs the traceback. Most often
  `ModuleNotFoundError: No module named 'decky'` means you're trying
  to run main.py outside Decky. That's expected, it only works when
  loaded by the Decky harness.

## "Check dependencies" shows everything missing after install

The pacman install ran but installed somewhere PATH doesn't reach.
SteamOS resets PATH at session start. After `Install dependencies`:

```sh
which Xvnc vncpasswd websockify xterm wmctrl
ls /usr/share/novnc/vnc.html
```

If any of those is missing, run `pacman -Q tigervnc python-websockify
novnc xterm wmctrl` and reinstall whichever returns "not found".

## `pacman-key` errors during install

```
error: failed to commit transaction (invalid or corrupted package (PGP signature))
```

Fresh SteamOS sometimes hasn't initialized the pacman keyring. The
bundled `defaults/install.sh` calls `pacman-key --init && pacman-key
--populate`, but if that fails:

```sh
sudo steamos-readonly disable
sudo rm -rf /etc/pacman.d/gnupg
sudo pacman-key --init
sudo pacman-key --populate archlinux holo
sudo steamos-readonly enable
```

## "Xvnc did not start listening on 5942"

Another process is already using the port, or Xvnc crashed at startup.

```sh
ss -lntp | grep 5942        # who has the port?
ls /tmp/.X42-lock           # stale X lock from a previous crash
```

If a stale lock exists, remove it: `sudo rm /tmp/.X42-lock`. If the
port is busy, kill the holder, or set DISPLAY/port via a feature
request (we currently hardcode `:42` / `5942`).

## "PiP starts, but the iframe is black"

The websockify bridge is up, but Xvnc isn't drawing anything yet —
usually means the guest app failed silently. From Konsole in Desktop
Mode:

```sh
DISPLAY=:42 xeyes              # does anything show up?
DISPLAY=:42 flatpak run com.discordapp.Discord
```

If Discord errors out, it's almost always a Flatpak permission
(`org.freedesktop.portal.Desktop` not reachable in the headless
session). Workaround: run `flatpak override --user
--socket=session-bus com.discordapp.Discord` once.

## "Discord Go Live doesn't list 'GameMirror'"

Three things to check, in order:

1. Is the gst pipeline running? `pgrep -af gst-launch-1.0`
2. Is the window actually on `:42`? `DISPLAY=:42 wmctrl -l` should
   include a line ending in `GameMirror`.
3. Is Discord running on the same `:42`? If you started Discord on
   the host display by accident, it won't see the Xvnc window. Always
   launch Discord through the DeckPiP panel.

If 1 fails, check `journalctl -u plugin_loader -e` for the gst
output — most often "no element 'pipewiresrc'" means
`gst-plugin-pipewire` isn't installed.

## "Game performance dropped a lot after enabling DeckPiP"

Expected for the first PoC. The `pipewiresrc → ximagesink` pipeline
copies frames through CPU. Future work: switch to
`glupload ! glcolorconvert ! glimagesink` to keep them on the GPU.

For now: lower the in-game framerate, or use audio-only mode for
Discord (no video iframe = no compositor cost on top of the game).

## "F10 doesn't toggle visibility"

The hotkey is a DOM `keydown` listener — it only fires if a keyboard
is attached and Steam UI has focus. Touch / controller don't trigger
it. On the Deck specifically:

- Connect a Bluetooth keyboard for testing.
- Or open Quick Access and use the **Visible** toggle in the panel.

A proper gamescope-level hotkey is on the roadmap.

## Plugin won't uninstall cleanly

If a PiP session is still running when you remove the plugin, the
child processes may survive. Before uninstall, hit **Stop** in the
panel, then:

```sh
pgrep -af "Xvnc|websockify|gst-launch-1.0" | grep -v grep
```

If anything remains, `sudo pkill -f Xvnc` etc., then remove the
plugin from Decky's UI normally.
