# DeckPiP — Discord Game Streaming

Status: design doc. Awaiting validation on real hardware before
implementation.

## Problem

Discord in **Gaming Mode** cannot see other Linux applications or the
running game. Three independent reasons stack up:

1. **Gamescope isolates XWayland servers.** Each app gets its own
   XWayland; cross-display X reads are forbidden, so Discord's "share
   a window" lists nothing useful.
2. **`xdg-desktop-portal` picker never appears.** Gaming Mode has no
   DE to render the screen-share chooser, so even when Discord uses
   the Wayland screencast portal the dialog hangs invisibly.
3. **Discord doesn't speak `wlr_screencopy_v1`** — the protocol
   Gamescope actually exports frames on.

Net effect: in Gaming Mode "Go Live" in Discord is functionally
broken for sharing anything except Discord itself.

## Solution: "GameMirror" on top of the DeckPiP architecture

DeckPiP already runs Discord inside a private `Xvfb :42`. Inside that
display Discord sees exactly the X windows we put there. So we put a
**mirror of the real game** there as another window, and Discord shares
it with its native X11 capture path — no portal required.

```
Real game (gamescope output)
        │ wlr_screencopy_v1 / PipeWire screencast node
        ▼
   gst pipeline:
   pipewiresrc → videoconvert → ximagesink display=:42
        │
        ▼
   Xvfb :42  ──┬──> window "GameMirror" (1280×800, fullscreened)
               └──> Discord window (same display)
                        │
                        ▼
                Discord Go Live
              "share window: GameMirror"
                        │
                        ▼
                friends in Discord
```

Discord and the mirror live on the same X display, so Discord
enumerates `GameMirror` as a normal window and streams it through its
own X11 capture path. The Gaming Mode portal bug is bypassed entirely.

## Components

### Frame source

Gamescope 3.14+ publishes its composited output as a PipeWire node
(this is the same mechanism Decky Recorder uses). Locate it at runtime:

```sh
pw-cli ls Node | awk '/gamescope/{print id}'
```

Cache the node id in `PipSession` for the duration of the session.

### Mirror pipeline

One gstreamer command launched as a child of `PipSession`:

```sh
gst-launch-1.0 -q \
  pipewiresrc target-object=<node-id> ! \
  videoconvert ! \
  ximagesink display=:42 sync=false
```

After the window appears, fullscreen it inside Xvfb:

```sh
DISPLAY=:42 wmctrl -r GameMirror -b add,fullscreen
```

(`xdotool` is an equally fine fallback for the same operation.)

### Audio

Create a PipeWire loopback so Discord's input source hears the game:

```sh
pw-loopback \
  --capture-props='media.class=Audio/Source target.object=<game-sink>.monitor' \
  --playback-props='media.class=Audio/Sink node.name=deckpip-game-loopback'
```

Discord then selects `deckpip-game-loopback` as a microphone source
(or as an additional source in the voice mixer).

### Flatpak permissions

Discord Flatpak needs, at minimum:

- `--socket=pulseaudio` (already default)
- `--filesystem=xdg-run/pipewire-0` (already default in recent
  releases; verify with `flatpak info --show-permissions
  com.discordapp.Discord`)

No new permissions to grant beyond the Flatpak defaults.

## Lifecycle

| Event | GameMirror action |
|---|---|
| User starts Discord PiP | nothing — mirror is opt-in |
| User toggles "Mirror game" | start gst pipeline + pw-loopback |
| User toggles "Mirror game" off | kill gst pipeline + pw-loopback |
| User stops PiP | kill Discord, kill mirror, kill Xvfb |
| Plugin unload / uninstall | force stop everything |

Mirror is a child process of the existing `PipSession` — same
process-group + SIGTERM cleanup as the rest.

## Backend API additions

```python
async def start_game_mirror(self) -> dict:
    # locate gamescope PipeWire node
    # spawn gst-launch-1.0 with DISPLAY=:42
    # spawn pw-loopback for game audio
    # return {"ok": True}

async def stop_game_mirror(self) -> dict:
    # kill mirror pipeline only; leave Discord/Xvfb alone
    # return {"ok": True}
```

## Frontend additions

One toggle in the panel: **"Mirror game into Discord"**, only enabled
when a Discord PiP session is running.

## Open risks (must be validated on hardware before we ship code)

1. **Will Discord enumerate windows from a virtual Xvfb display?**
   Linux Discord uses X11 `XComposite` + `XDamage` for window
   enumeration. This should work transparently on Xvfb — but it has
   not been confirmed end-to-end on SteamOS. If it doesn't, fall back
   to the virtual-camera path below.
2. **CPU/GPU overhead at 60 fps.** `pipewiresrc → videoconvert →
   ximagesink` does a CPU memcpy + colorspace conversion per frame.
   At 1280×800×60 fps this is non-trivial on the Deck APU while a game
   is running. Measure before claiming it works; consider
   `glupload ! glcolorconvert ! glimagesink` to keep frames on the
   GPU.
3. **Frame format mismatch.** Gamescope output may be 10-bit or
   HDR-tagged. `videoconvert` handles SDR fine; HDR is a future
   problem we explicitly punt on (consistent with the rest of DeckPiP).
4. **Audio echo.** If the game sink is routed both to speakers and
   into the Discord loopback, friends hear themselves echoed back via
   the user's mic. Default the loopback off; expose as a toggle.

## Fallback: PipeWire virtual camera

If Discord refuses to enumerate the mirror window from Xvfb, we
switch the source from "shared window" to "video call camera":

```
real screen node ──pw-loopback──> virtual camera node
                                          │
                                          ▼
                                  Discord video call
                                "select camera: Deck Screen"
```

Downside: presented as a webcam, not as Go Live — friends watch in
the video-call layout, not the streaming layout. Functionally
equivalent for the user's stated goal ("let friends see the game").
Easier to implement (no `wmctrl` choreography), worse UX.

## Validation checklist

Before any code lands:

- [ ] On a real Deck in Gaming Mode, find the gamescope PipeWire node
      while a game runs.
- [ ] Run the gst pipeline by hand against Xvfb :42 (DeckPiP already
      provides one) and confirm a `GameMirror` window appears.
- [ ] Launch Discord on the same `:42`, click Go Live → Window, and
      confirm `GameMirror` is selectable.
- [ ] Stream to a second account; confirm the friend sees the game.
- [ ] Measure FPS hit on the game with and without the mirror
      running (target: under 10 % drop at 60 fps).

If all five pass, implement; if (3) fails, switch to the virtual
camera fallback and re-run (4)–(5).
