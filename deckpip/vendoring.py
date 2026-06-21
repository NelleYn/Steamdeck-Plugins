"""Self-contained runtime for noVNC + websockify.

To meet the Decky Store's "vendor your dependencies" expectation we
unpack a pinned noVNC release tarball and pip-install websockify into
``DECKY_PLUGIN_RUNTIME_DIR/vendored``. The bootstrap is idempotent:
once the directory exists we use it; ``rm -rf vendored`` forces a
re-fetch.

We keep two strategies live in parallel:

* ``vendored_paths()`` — the preferred result, no pacman dep.
* The system-wide installs (``/usr/share/novnc``, ``which websockify``)
  remain as a fallback when bootstrap hasn't been run yet.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

NOVNC_VERSION = "1.5.0"
NOVNC_URL = f"https://github.com/novnc/noVNC/archive/refs/tags/v{NOVNC_VERSION}.tar.gz"
NOVNC_DIRNAME = f"noVNC-{NOVNC_VERSION}"

# Pin websockify so a one-tap install pulls a known-good release instead of
# whatever PyPI happens to serve at install time (a yanked/compromised
# --upgrade would otherwise run with the plugin's elevated privileges).
WEBSOCKIFY_VERSION = "0.12.0"


def vendored_root(runtime_dir: Path) -> Path:
    return Path(runtime_dir) / "vendored"


def vendored_novnc(runtime_dir: Path) -> Path | None:
    p = vendored_root(runtime_dir) / NOVNC_DIRNAME
    return p if (p / "vnc.html").exists() else None


def vendored_websockify(runtime_dir: Path) -> Path | None:
    """Return path to the websockify executable inside the vendored
    Python environment, if installed. Looks for `bin/websockify`."""
    bin_path = vendored_root(runtime_dir) / "python" / "bin" / "websockify"
    return bin_path if bin_path.exists() else None


def status(runtime_dir: Path) -> dict:
    return {
        "novnc": str(vendored_novnc(runtime_dir) or ""),
        "websockify": str(vendored_websockify(runtime_dir) or ""),
        "root": str(vendored_root(runtime_dir)),
    }


async def _download_tarball(url: str, dest: Path) -> None:
    def _fetch() -> None:
        with urllib.request.urlopen(url, timeout=60) as resp, dest.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    await asyncio.to_thread(_fetch)


async def _extract_tarball(tarball: Path, into: Path) -> None:
    def _extract() -> None:
        with tarfile.open(tarball, "r:gz") as tf:
            # filter="data" is the post-CVE-2007-4559 safe extractor.
            tf.extractall(into, filter="data")
    await asyncio.to_thread(_extract)


async def install_novnc(runtime_dir: Path, force: bool = False) -> dict:
    target = vendored_root(runtime_dir) / NOVNC_DIRNAME
    if target.exists() and not force:
        return {"ok": True, "skipped": True, "path": str(target)}
    root = vendored_root(runtime_dir)
    root.mkdir(parents=True, exist_ok=True)
    tarball = root / f"novnc-{NOVNC_VERSION}.tar.gz"
    try:
        await _download_tarball(NOVNC_URL, tarball)
        await _extract_tarball(tarball, root)
    except Exception as exc:
        return {"ok": False, "error": f"download_or_extract:{exc}"}
    finally:
        tarball.unlink(missing_ok=True)
    if not (target / "vnc.html").exists():
        return {"ok": False, "error": "vnc_html_missing_after_extract"}
    return {"ok": True, "path": str(target)}


async def install_websockify(runtime_dir: Path, force: bool = False) -> dict:
    """pip install websockify into a vendored prefix. Wraps the resulting
    bin/websockify with a launcher that sets PYTHONPATH so imports resolve
    from the vendored site-packages."""
    target = vendored_root(runtime_dir) / "python"
    bin_path = target / "bin" / "websockify"
    if bin_path.exists() and not force:
        return {"ok": True, "skipped": True, "path": str(bin_path)}
    target.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "install",
        "--prefix", str(target),
        "--break-system-packages",  # PEP 668 SteamOS Python
        "--no-input",
        f"websockify=={WEBSOCKIFY_VERSION}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
    except TimeoutError:
        proc.kill()
        return {"ok": False, "error": "pip_install_timeout"}
    if proc.returncode != 0 or not bin_path.exists():
        return {
            "ok": False, "error": "pip_failed",
            "rc": proc.returncode,
            "stderr": stderr.decode(errors="replace")[-1000:],
            "stdout": stdout.decode(errors="replace")[-500:],
        }

    # bin/websockify imports the websockify package from
    # lib/python3.X/site-packages, which isn't on PYTHONPATH by default.
    # Locate the site-packages dir and bake a wrapper around the binary.
    site_packages: list[Path] = list(target.glob("lib/python*/site-packages"))
    if site_packages:
        wrapper = bin_path.with_suffix(".real")
        if not wrapper.exists():
            bin_path.rename(wrapper)
            bin_path.write_text(
                "#!/usr/bin/env bash\n"
                f'PYTHONPATH="{site_packages[0]}${{PYTHONPATH:+:$PYTHONPATH}}" '
                f'exec "{wrapper}" "$@"\n'
            )
            bin_path.chmod(0o755)
    return {"ok": True, "path": str(bin_path)}


async def install_all(runtime_dir: Path, force: bool = False) -> dict:
    novnc = await install_novnc(runtime_dir, force)
    ws = await install_websockify(runtime_dir, force)
    return {"ok": novnc["ok"] and ws["ok"], "novnc": novnc, "websockify": ws}
