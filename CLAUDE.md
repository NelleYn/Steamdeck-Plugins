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

## Key invariants

- All subprocess commands run with `preexec_fn=os.setsid` and are terminated via `os.killpg` — never leave orphaned processes.
- Xvnc and guest apps run as the `deck` user (via `runuser`) even when the plugin process is root.
- Settings are persisted atomically via tmp-file + `os.replace` in `deckpip/settings.py`.
- The `asyncio.Lock` in `Plugin` serialises start/stop to prevent start-twice races.
