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

Since the release zip bundles TigerVNC, noVNC, websockify, and the
GameMirror GStreamer stack (see [Bundled dependencies](#bundled-dependencies-vs-the-pacman-fallback)
below), this usually only happens on a from-source build, or a zip
built without running the vendoring scripts. Check what `diagnostics`
reports for each binary's `path` — if it's empty, neither the bundled
copy nor PATH resolved it.

If you installed via `defaults/install.sh` (pacman) instead:

```sh
which Xvnc vncpasswd websockify xterm wmctrl
ls /usr/share/novnc/vnc.html
```

If any of those is missing, run `pacman -Q tigervnc python-websockify
novnc xterm wmctrl` and reinstall whichever returns "not found".

## Bundled dependencies vs. the pacman fallback

The release zip normally ships noVNC, websockify, Ludusavi, rclone,
TigerVNC (Xvnc/vncpasswd), and the optional GameMirror GStreamer stack
pre-built, so a fresh install needs nothing downloaded or
pacman-installed separately — see the README's
[Install on a Steam Deck](../README.md#install-on-a-steam-deck) section.
`deckpip/system_vendor.py` resolves these from
`<plugin_dir>/vendored/...` first and only falls back to whatever's on
PATH.

The TigerVNC/GameMirror half of that bundle is best-effort: it's built
in CI inside an Arch/Holo container (`scripts/bundle-system-deps.sh`,
`scripts/bundle-gst-plugins.sh`), smoke-tested there, but not validated
against every SteamOS build. If a bundled binary doesn't run on yours
(glibc/ABI mismatch — you'd see "error while loading shared libraries"
in `journalctl -u plugin_loader -e` when a PiP session or GameMirror
starts), fall back to the pacman path:

```sh
sudo bash /home/deck/homebrew/plugins/DeckPiP/defaults/install.sh
sudo systemctl restart plugin_loader
```

`shutil.which` picks up the pacman-installed copy automatically once
the bundled one is out of the picture (or just failing at exec time —
resolution doesn't currently probe that the bundled binary actually
runs, only that the file exists, so a broken bundle plus a working
pacman install both being present will still prefer the broken bundled
one; running the pacman install after removing
`<plugin_dir>/vendored/tigervnc` or `.../gstreamer` guarantees the
system copy wins).

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

## "F10 / F12 PTT don't work during gameplay"

Both hotkeys are DOM `keydown` listeners and **only fire when Steam UI
has keyboard focus**. When the game is in the foreground, Gamescope
routes input straight to it, bypassing Steam UI's CEF. So:

- F10 / F12 work while Quick Access is open ✅
- They don't work while you're actively playing ❌
- Touch / controller never trigger them (no DOM keydown)

### Workaround: Steam Input → keyboard key

The most reliable way to wire L4/L5/R4/R5 (or the rear buttons on
modded Decks) to DeckPiP's hotkeys is the Steam Controller Configurator:

1. In Gaming Mode, while a game is running, press the **STEAM** button
   → **Controller Settings** → **Edit Layout**.
2. Pick the button you want (L4 is a popular one for show/hide).
3. **Add Command** → **Keyboard** → press **F10** on a virtual / BT
   keyboard.
4. Save layout. **Apply Layout To: Per Game** or **Default**.
5. Repeat for **F12** if you want PTT.

Now while the game is focused, pressing L4 generates a synthetic F10
keystroke that Gamescope routes through Steam UI (where our DOM
listener picks it up).

Repeat per game if you don't pick **Apply Default Layout**. If your
PTT keys override game keys, set them in **Action Sets** instead of
the default layout so they can be toggled mid-game.

### Roadmap

Gamescope has experimental support for plugin-registered global
hotkeys (`gamescope_action_binding`), but the API is unstable. When it
ships in a release we ship with, DeckPiP will register F10/F12 there
directly and you won't need Steam Input config.

## "F12 PTT does nothing"

DeckPiP's PTT is OS-level: holding F12 calls `pactl set-source-mute
@DEFAULT_SOURCE@ false` (unmute mic), releasing F12 calls the same
with `true` (mute). It works regardless of which voice client is
running, as long as that client is reading from the default
PulseAudio/PipeWire source.

Things to check if F12 does nothing:

1. Steam UI must have keyboard focus — same caveat as F10.
2. `pactl` must be installed: `command -v pactl`. Should be present
   on every SteamOS by default (ships with libpulse). If missing,
   `sudo pacman -S libpulse`.
3. Your voice client must use the default source. In Discord:
   User Settings → Voice & Video → Input Device = "Default".
4. Diagnostic: from a SSH session, run
   `pactl get-source-mute @DEFAULT_SOURCE@` while holding F12 — it
   should print "Mute: no". If it doesn't change, the keydown isn't
   reaching the plugin.

## "no element pipewiresrc" or "no property target-object"

Old PipeWire installs (pre-1.0) used `path=N` instead of
`target-object=N` for the `pipewiresrc` element. DeckPiP auto-falls
back: it spawns the pipeline with `target-object=…` first, and if the
process exits within 0.5 s, it retries with `path=…`. If both fail,
you'll see `pipewiresrc_failed` in the toast.

The release zip normally bundles these plugins already (under
`<plugin_dir>/vendored/gstreamer/gst-plugins-1.0`, picked up via
`GST_PLUGIN_PATH` — see [Bundled dependencies](#bundled-dependencies-vs-the-pacman-fallback)).
If that bundle is missing or didn't work for your SteamOS build, fall
back to pacman:

```sh
sudo steamos-readonly disable
sudo pacman -S gst-plugin-pipewire gst-plugins-good
sudo steamos-readonly enable
```

Then verify:

```sh
gst-inspect-1.0 pipewiresrc
GST_PLUGIN_PATH=/home/deck/homebrew/plugins/DeckPiP/vendored/gstreamer/gst-plugins-1.0 \
    gst-inspect-1.0 pipewiresrc   # checks the bundled copy specifically
```

If that prints "No such element or plugin 'pipewiresrc'" — the
package isn't installed (or the bundle wasn't in the zip).

## "Xvnc launches but Discord (Flatpak) crashes immediately"

This is the canonical "Flatpak refuses to run as root" failure.
DeckPiP runs as root because of the Decky `_root` flag, but it now
wraps Xvnc and guest commands with `runuser -u deck --` so they run
as the desktop user. Verify:

```sh
ps -ef | grep -E "Xvnc|Discord" | grep -v grep
```

The UID column should say `deck`, not `root`. If it says `root`,
`runuser` may be missing or the dropping logic didn't activate
(check `journalctl -u plugin_loader -e` for the actual argv).

## Plugin won't uninstall cleanly

If a PiP session is still running when you remove the plugin, the
child processes may survive. Before uninstall, hit **Stop** in the
panel, then:

```sh
pgrep -af "Xvnc|websockify|gst-launch-1.0" | grep -v grep
```

If anything remains, `sudo pkill -f Xvnc` etc., then remove the
plugin from Decky's UI normally.
