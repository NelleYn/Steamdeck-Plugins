#!/usr/bin/env python3
"""Build-time vendoring for the portable runtime deps: noVNC, websockify,
Ludusavi, rclone.

Runs the *exact same* install_*()  coroutines the plugin calls at runtime
(deckpip/vendoring.py, deckpip/ludusavi.py, deckpip/cloud_sync.py), just
against a build directory instead of DECKY_PLUGIN_RUNTIME_DIR. That keeps
a single source of truth for pinned versions/URLs and guarantees the tree
this produces has exactly the layout ``deckpip.vendoring.bundled_novnc()``
etc. expect to find inside the release zip.

Usage:
    scripts/fetch-vendored.py [out-dir]

``out-dir`` defaults to ``vendored-portable/`` and ends up containing a
``vendored/`` subdirectory — copy that into the plugin pack root
(alongside plugin.json) before zipping so it lands at
``<plugin_dir>/vendored/...`` on the Deck.
"""

from __future__ import annotations

import asyncio
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# The Steam Deck is always x86_64. This script may run on a different
# build/dev machine (e.g. an arm64 CI runner or laptop), so pin the arch
# the ludusavi/rclone asset pickers see instead of letting them detect the
# *build* host and vendor the wrong binary for the target device.
platform.machine = lambda: "x86_64"  # noqa: E731

from deckpip import cloud_sync, ludusavi, vendoring  # noqa: E402


async def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "vendored-portable")
    out.mkdir(parents=True, exist_ok=True)

    results = await asyncio.gather(
        vendoring.install_novnc(out),
        vendoring.install_websockify(out),
        ludusavi.install(out),
        cloud_sync.install(out),
    )
    ok = True
    for label, res in zip(["novnc", "websockify", "ludusavi", "rclone"], results, strict=True):
        print(f"[fetch-vendored] {label}: {res}")
        ok = ok and bool(res.get("ok"))
    if not ok:
        print("[fetch-vendored] one or more downloads failed", file=sys.stderr)
        return 1
    print(f"[fetch-vendored] done: {out / 'vendored'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
