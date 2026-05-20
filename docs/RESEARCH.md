# DeckPiP — Feasibility Research

Status: research notes for the PoC. Last reviewed 2026-05-19.

## Goal

Provide convenient Picture-in-Picture (PiP) of an arbitrary Linux GUI
application (Discord, Telegram, IDE, etc.) on top of a running game while
the Steam Deck is in **Gaming Mode** (SteamOS 3.x official firmware).

## TL;DR

There is **no public Gamescope API** for embedding a third-party
application as an overlay over a running game. The only realistic path
without modifying Gamescope or waiting on Valve is to render the target
application's UI **inside the Steam UI's own CEF layer** — the same
layer that already composites over the game (Quick Access, Steam
Overlay, Big Picture). For a *generic* Linux GUI app, we wedge a
`Xvfb` + VNC (KasmVNC/noVNC) bridge in front of it and load the noVNC
URL into a CEF tab.

## Why Gamescope itself can't help

- **Gamescope is single-window-fullscreen-focused.** Composition of an
  arbitrary external client as a floating overlay is exactly the
  feature requested in
  [gamescope#288 "External application overlay"](https://github.com/Plagman/gamescope/issues/288)
  — open since Oct 2021, no upstream commitment.
- The Steam Shift+Tab overlay works via a **private Wayland protocol**
  (`gamescope_xwayland::override_window_content`) that is reserved for
  Steam UI / mangoapp. Third parties cannot piggyback on it
  ([#1225](https://github.com/ValveSoftware/gamescope/issues/1225),
   [#1537](https://github.com/ValveSoftware/gamescope/issues/1537)).
- Documented flags inspected (`--prefer-output`, `--xwayland-count`,
  `--expose-wayland`, `--steam`, `--mangoapp`, `--backend`,
  `--reshade-effect`) do **not** include `--external-overlay`, `--pip`,
  or `--embed`.
- `STEAM_MULTIPLE_XWAYLANDS=1 --xwayland-count 2` creates an "overlay"
  XWayland (server `:1`) intended for mangoapp/Steam UI. A second app
  launched on `DISPLAY=:1` will render, but Gamescope's WM logic
  doesn't expose positioning/sizing for it — it ends up fullscreen-ish
  and steals input.

## Paths considered

| # | Path | Verdict |
|---|---|---|
| A | Second XWayland (`--xwayland-count 2`) + launch app on `DISPLAY=:1` | Works as fullscreen toggle, not true PiP. Fallback only. |
| B | Nested gamescope-in-gamescope | Outer compositor still won't PiP the inner one (same #288). Rejected. |
| C | Custom Vulkan layer wrapping `vkQueuePresentKHR`, render captured frames as a textured quad on top of the game | True PiP, huge engineering effort, separate input-routing problem (uinput), conflicts with HDR/WSI. Rejected for PoC. |
| **D** | **Steam CEF tab + `Xvfb`/KasmVNC bridge to the target app** | **Chosen.** No Gamescope modification, generalizes "any Linux GUI", proven pattern (see Deckcord, DeckWebBrowser). |
| E | Hotswap focus via `gamescopectl` | Not PiP — toolbar-only fallback. |

## Prior art we lean on

- **[Deckcord](https://github.com/marios8543/Deckcord)** — Discord via
  CEF tab injection into Steam UI. Proves the CEF-tab path works in
  Gaming Mode.
- **[DeckWebBrowser](https://github.com/jessebofill/DeckWebBrowser)** —
  full browser inside Quick Access; reference for route patching.
- **[OverLaid](https://github.com/TheLogicMaster/OverLaid)** —
  custom widgets layered through the Steam React/CEF UI.
- **[Decky-QuickStart](https://github.com/Tormak9970/Decky-QuickStart)**
  / **[decky-plugin-template](https://github.com/SteamDeckHomebrew/decky-plugin-template)**
  — current plugin scaffolding.
- **[Decky Recorder](https://github.com/SteamDeckHomebrew/decky-plugin-database/pull/190)**
  — demonstrates capturing frames out of Gamescope via PipeWire
  screencast portal (useful precedent for Path C if we ever revisit
  it).
- **[mangoapp](https://wiki.archlinux.org/title/Gamescope)** — the only
  shipped example of a non-Steam process rendering on the overlay
  XWayland. Closest thing to "third-party overlay" that exists today.
- **[obs-vkcapture](https://github.com/nowrep/obs-vkcapture)** —
  reference for Vulkan-layer frame *export* (the opposite direction of
  what we'd need for Path C).

## Open risks for the chosen path (D)

1. **Performance.** Two extra processes (`Xvfb` + KasmVNC) plus the
   target app, on top of the game, on a 15W APU. Need to measure CPU
   and memory budget with a representative game running.
2. **Input routing.** Touch / keyboard / controller events inside the
   CEF tab must reach noVNC and then the underlying app. Decky exposes
   `gamescope_action_binding` for hotkeys; trackpad-as-mouse should
   work natively in CEF.
3. **Audio.** Guest audio defaults to the same PulseAudio sink as the
   game. Need an option to mute the guest sink or route it to a
   loopback.
4. **Lifecycle.** `Xvfb`, `KasmVNC`, and the child app must all be
   killed on plugin unload, plugin uninstall, and Gaming Mode logout.
   No zombies, no leaked sockets.
5. **Authentication.** KasmVNC must bind to `127.0.0.1` only, with a
   random per-session token, so nothing on the LAN can attach.
6. **Dependency footprint.** SteamOS root is immutable. `Xvfb` and a
   VNC server are not in the base image; we need to install them under
   `~/.local` or via a Flatpak/AppImage bundle shipped with the
   plugin.

## Side effect: fixes "Discord can't see other apps in Gaming Mode"

Because Discord (when launched through DeckPiP) lives on our private
`Xvfb :42`, we can place an X-window mirror of the real game on the
same display via a `pipewiresrc → ximagesink` gstreamer pipeline.
Discord then enumerates that mirror window through its own X11
capture path and shares it via Go Live — no `xdg-desktop-portal`
involvement, which is precisely the piece that's broken in Gaming
Mode. Full design in [`DISCORD_STREAMING.md`](DISCORD_STREAMING.md).

## Recommendation

Build a Decky plugin (Path D) with these explicit non-goals for the PoC:

- No support for HDR passthrough into the PiP window.
- No support for controller-as-mouse inside the PiP (use trackpad).
- No multi-monitor.
- One PiP session at a time.

If the PoC validates performance and input routing, the next iteration
investigates Path A (second XWayland) as a "native" fast-path for apps
that don't need free-floating placement.
