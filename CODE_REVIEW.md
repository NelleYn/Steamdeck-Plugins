# Code Review — Steamdeck-Plugins

Date: 2026-06-13

## Project summary

**DeckPiP** is a single Decky Loader plugin (not a multi-plugin repo) that
renders a Picture-in-Picture overlay of arbitrary Linux GUI apps (Discord,
Telegram, …) on top of a running game in Steam Deck Gaming Mode. It works by
running the guest app on a headless `Xvnc :42` display, bridging it through
`websockify` + noVNC, and embedding the noVNC client in an `<iframe>` rendered
by the Steam UI (which Gamescope composites over the game).

Layout:

- **Backend entry:** `main.py` — the Decky `Plugin` class exposing ~50 async
  callables. Logic lives in the `deckpip/` package (18 modules: session,
  apps, audio, mpris, ptt, trackpad, mirror, notifications, discovery,
  diagnostics, battery, settings, profiles, bookmarks, vendoring, ludusavi,
  cloud_sync, updater).
- **Frontend entry:** `src/index.tsx` (`definePlugin`) → `src/panel.tsx`
  (Quick Access UI) + `src/pip-view.tsx` (overlay route). State in
  `src/store.ts` / `src/store-core.ts`, API bindings in `src/api.ts`.
- **Shell:** `setup.sh` (installer), `defaults/install.sh` (pacman deps),
  `scripts/make-zip.sh` (release packaging).

## Overall assessment

The code is well above average in quality and security hygiene for a Decky
plugin. **No command-injection vulnerabilities were found**: every subprocess
invocation uses `asyncio.create_subprocess_exec` / `subprocess.Popen` with an
**argv list and never `shell=True`**; there is no `os.system`, `eval`, `exec`,
`pickle`, or YAML deserialization anywhere. Custom commands are `shlex.split`
into argv before execution, the VNC server binds `127.0.0.1` with
`-localhost yes`, archive extraction uses the post-CVE `filter="data"` safe
extractor, and the frontend wraps every SteamClient call in try/catch with
effect cleanup that is correctly returned from `definePlugin.onDismount`.

The findings below are mostly correctness/robustness and defense-in-depth
issues, plus one privilege-model bug that will break the core flow on real
hardware (the `_root`-owned VNC password file is unreadable by the
privilege-dropped `Xvnc`).

## Scope note

This was a manual read of all 18 backend modules, `main.py`, all frontend
`.ts`/`.tsx` sources, the three shell scripts, the CI workflow, and the
manifest. Tests under `tests/` and `src/__tests__/` were skimmed but not
executed (per instructions). No builds or tests were run; no source was
modified.

## Critical

None found.

## High

**1. VNC password file is written as root but read by a privilege-dropped Xvnc — core PiP flow fails on hardware**
`deckpip/session.py:182-196` (`_write_vnc_passwd`) and `deckpip/session.py:139-151` (`start`).
The plugin runs as root (`plugin.json:4` → `"flags": ["_root"]`). `_write_vnc_passwd`
writes `runtime_dir/vncpasswd` from the root process and `path.chmod(0o600)`,
leaving the file owned by `root:root` mode `0600`. But `Xvnc` is launched via
`_as_user_argv(...)` → `runuser -u deck -- Xvnc ... -PasswordFile <path>`
(`session.py:140-149`), i.e. as the **deck** user. The deck user cannot read a
`0600` root-owned file, so `Xvnc` fails to load the password and the session
never comes up — exactly the path the README calls the base feature. The same
mismatch applies to the runtime/vendored tree generally: files created by the
root backend may not be readable/owned by the deck user that runs the guest
processes. Fix: after writing the password file, `os.chown` it to the deck
user's uid/gid (resolve via `pwd.getpwnam(DECK_USER)`) when `os.geteuid()==0`,
or write it as the deck user; mirror that ownership fix for the vendored
runtime dir.

**2. CI workflow runs on untrusted `pull_request` events with `contents: write`**
`.github/workflows/build.yml:6-11`.
The workflow triggers on bare `pull_request:` (which includes PRs from forks)
and grants job-level `permissions: contents: write`. While the dangerous steps
(release publish / artifact upload) are correctly gated behind
`github.event_name == 'push'` / `!= 'pull_request'`, the *write* token is still
present in the fork-PR run, and untrusted PR code executes via `pnpm install`
(lifecycle scripts), `pnpm run build`, and `python -m pytest` before any
gating. A malicious PR can run arbitrary code with a write-scoped `GITHUB_TOKEN`
in scope. Fix: use `pull_request` only with `permissions: contents: read` (or
split into a separate read-only PR workflow), and reserve write permissions for
the `push`-triggered job. Consider `pull_request_target` is *not* a fix here —
keep untrusted code on a read-only token.

## Medium

**1. Root-privileged subprocesses are not dropped to the deck user**
`deckpip/trackpad.py:27,43`, `deckpip/ptt.py:12`, `deckpip/audio.py:12,66`,
`deckpip/mpris.py:99`, `deckpip/notifications.py:87`, `deckpip/mirror.py:125,136,149`.
`session.py` is careful to wrap `Xvnc`/guest/`websockify`/the gst pipeline in
`_as_user_argv` so they run as `deck`, but the per-action helpers
(`xdotool`, `pactl`, `dbus-send`, `dbus-monitor`) are spawned directly and
therefore run as **root**, talking to `DISPLAY=:42` and the user session bus.
Arguments are fixed/allowlisted so this is not injection, but running these as
root is an unnecessary privilege surface and can also fail to reach the deck
user's session bus (wrong `DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR`). Fix:
wrap these in `_as_user_argv` too, consistent with `session.py`.

**2. VNC auth secret is weak and travels in the iframe URL query string**
`main.py:327` and `deckpip/session.py:191,198-206`.
`secrets.token_hex(8)` yields 16 hex chars but only `self.token[:8]` is used —
both for the `vncpasswd` stdin (`session.py:191`) and as the `&password=` query
parameter in `url()` (`session.py:204`). VncAuth truncates to 8 bytes anyway,
so this is ~32 bits of effective entropy embedded in a URL that is also held in
React state / settings. It is mitigated by `-localhost yes` + `127.0.0.1` bind
(only loopback can connect), so impact is low on a single-user Deck, but the
8-char cap is a deliberate-looking truncation that reads like a bug. Fix: drop
the `[:8]` slices and let VncAuth take the full 8 bytes of a longer token, and
document that the secret in the URL is loopback-scoped.

**3. `parse_backup_summary` "errors" field is a dead/always-zero expression**
`deckpip/ludusavi.py:194`.
`"errors": overall.get("processedGames", 0) and 0` evaluates to `0` for every
non-zero `processedGames` and `0` otherwise — i.e. it is unconditionally `0`
and never reports errors. This is surfaced to the UI as the backup error count.
Fix: read the actual error/failed count from the Ludusavi `overall` object
(e.g. `overall.get("totalGames")`/a real error key) or remove the field.

**4. `dbus-send` return code is masked, hiding failures**
`deckpip/mpris.py:106` returns `proc.returncode or 0`. When `dbus-send` exits
with a real non-zero code that is falsy-coerced incorrectly this is fine, but
the construct `returncode or 0` turns a `None` (process not reaped) into `0`
(success) and is generally misleading. Combined with `stderr` being routed to
`DEVNULL` (`mpris.py:103`), MPRIS failures are silently reported as success to
the panel. Fix: return the real return code and surface a hint on failure.

## Low

**1. `_which` version probe runs every diagnosed binary with `--version` as root**
`deckpip/diagnostics.py:18-25`. Running `Xvnc --version`, `flatpak --version`,
etc. as root is benign for these tools but the broad `except (TimeoutError,
Exception)` (`diagnostics.py:26`) swallows everything including programming
errors; prefer catching `Exception` once (the `TimeoutError` is redundant since
`asyncio.wait_for` raises `TimeoutError` which is an `Exception` subclass on
3.11) and logging at debug level.

**2. `mpris.player_action` only prefix-checks the bus name**
`deckpip/mpris.py:147`. `bus_name.startswith("org.mpris.MediaPlayer2.")` is the
only validation before it is interpolated into `--dest=<bus_name>`. The action
is properly allowlisted, and `dbus-send` is argv-exec (no shell), so this is not
injection, but a caller could target an arbitrary `org.mpris.MediaPlayer2.*`
bus. Low impact; consider validating against the names returned by
`list_players`.

**3. Discovery `xterm -e {cleaned}` string-concatenates a parsed Exec line**
`deckpip/discovery.py:71`. `cleaned = f"xterm -e {cleaned}"` builds a command
*string* from a `.desktop` `Exec=` value; it is later re-parsed by `shlex.split`
in `add_custom_app`, so an `Exec` containing quotes/`;`/`&&` is split into argv
(no shell), but the naive concatenation can still produce a surprising argv
(e.g. the terminal app's own args get reparented under `xterm -e`). Low risk;
prefer building an argv list rather than a shell-looking string.

**4. `install_websockify` writes a wrapper script with an unquoted-safe but brittle path interpolation**
`deckpip/vendoring.py:122-132`. The generated bash wrapper embeds
`site_packages[0]` directly into a double-quoted `PYTHONPATH="..."`. Paths under
`DECKY_PLUGIN_RUNTIME_DIR` are controlled by Decky and unlikely to contain
`"`/`$`, so this is safe in practice, but a path with a double-quote or `$`
would break the wrapper. Low risk; use `shlex.quote` when generating the line.

## Nitpicks

**1. `src/panel.tsx` is 1323 lines** — a single monolithic `Content()` component
holding ~30 `useState` hooks and every tab's markup. It is the obvious
refactor target (split per-tab into ` AppsTab`/`SyncTab`/`WebTab`/`SystemTab`
components, lift shared state into a context or the store).
`src/panel.tsx:126-1323`.

**2. Brace-on-same-line formatting glitch** at `src/panel.tsx:612`
(`if (running) {    return (`) and a missing newline in `src/api.ts:31`
(`settingsSet... ("settings_set");export const addCustomApp`) — cosmetic, picked
up by prettier.

**3. README is stale vs. reality** — it states "Repository is private — Decky's
'Install from URL' doesn't work anonymously" (`README.md:164`) while also
claiming the repo is public elsewhere (`README.md:63`). Reconcile the two.

**4. `_set_mute`/PTT keeps the mic muted as the default state** — `ptt_release`
mutes (`deckpip/ptt.py:30-31`). If the plugin crashes or is unloaded mid-hold,
the mic is left muted with no guaranteed unmute on `_unload`. Consider unmuting
the default source in `Plugin._unload`.

## Strengths

- **No shell execution anywhere.** Every external command uses argv-based
  `create_subprocess_exec`/`Popen`; custom user commands pass through
  `shlex.split` (`deckpip/apps.py:47`) with length caps on id/label/command.
- **Sound privilege-drop design** in `session.py` (`_as_user_argv`,
  `os.setsid` + process-group `terminate`/`pause`/`resume` with SIGTERM→SIGKILL
  escalation) — the lifecycle management is genuinely careful.
- **Safe archive handling:** `tarfile.extractall(..., filter="data")`
  (`deckpip/vendoring.py:65`, `deckpip/ludusavi.py:100`) defeats path-traversal
  tar entries; downloads go to pinned versioned GitHub release URLs over HTTPS.
- **Atomic settings writes** via tmp-file + `os.replace` (`deckpip/settings.py:24-29`),
  with defensive `isinstance` validation on every loaded structure
  (apps/bookmarks/profiles).
- **Input validation** on bookmarks (`https?://` regex + length caps,
  `deckpip/bookmarks.py:32`) and a single-session `asyncio.Lock` guarding
  `start/stop/mirror` (`main.py:313` etc.).
- **Robust, well-isolated frontend:** all SteamClient access is wrapped in
  try/catch with fallbacks (`src/steam.ts`), every effect returns a cleanup
  function that is invoked from `onDismount` (`src/index.tsx:338-352`), the
  iframe is `sandbox`-ed with `referrerPolicy="no-referrer"`
  (`src/pip-view.tsx:198`), and promises are consistently `.catch()`-guarded.
- **Good test coverage scaffolding** — 18 backend test modules plus frontend
  vitest suites, and a CI lint/typecheck/test gate.
