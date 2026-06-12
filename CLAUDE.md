# DeckPiP — Claude Code conventions

## Git workflow

- Default branch is `main`.
- Push all commits directly to `main`; do not create feature branches unless explicitly asked.
- Never force-push, never skip hooks.

## Commit format

```
feat: short description
fix: short description
chore: short description
refactor: short description
docs: short description
```

One-line subject. Body only when the change is genuinely non-obvious.

## Code style

- No inline comments, no block comments, no docstrings unless explicitly requested.
- If a file exceeds 400 lines, split it into smaller focused modules before adding more code.
- No speculative abstractions. Extract a helper only when the same expression is duplicated three or more times and bugs have occurred in copies.
- Async all the way — no `.result()` or `.wait()` on coroutines.
- Never swallow exceptions silently; log or re-raise.

## Stack

- Backend: Python 3.11 / asyncio (Decky Loader plugin).
- Frontend: TypeScript / React / `@decky/api` / rollup.
- Tests: pytest (backend), vitest (frontend).
- Linter: ruff (backend), tsc --noEmit (frontend).

## Build / test

```sh
pnpm install && pnpm run build        # frontend
python -m pytest tests/ -v            # backend
pnpm test                             # frontend unit tests
ruff check .                          # lint
```

## Versioning

Version format: `X.YY.ZZZ` — three independent counters, each keeping its own running total.

- `X` (single digit, 0–9) — major / breaking changes.
- `YY` (two digits, 00–99) — medium changes / new features.
- `ZZZ` (three digits, 000–999) — small changes / fixes.

**Each counter is independent — bumping a higher segment does NOT reset the lower ones.**
Example: after `1.03.042`, a new feature makes it `1.04.042`; a subsequent fix makes it `1.04.043`.

Because JSON version fields reject leading zeros, store the value as plain dotted integers (`X.Y.Z`) and rely on the conceptual widths above to interpret the segments.
Both `package.json` and `plugin.json` (when it gains a `version` field) must stay in sync.

Bump on every meaningful commit pushed to `main`.

## Key invariants

- All subprocess commands run with `preexec_fn=os.setsid` and are terminated via `os.killpg` — never leave orphaned processes.
- Xvnc and guest apps run as the `deck` user (via `runuser`) even when the plugin process is root.
- Settings are persisted atomically via tmp-file + `os.replace` in `deckpip/settings.py`.
- The `asyncio.Lock` in `Plugin` serialises start/stop to prevent start-twice races.
