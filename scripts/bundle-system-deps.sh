#!/usr/bin/env bash
# Harvest a system binary + its shared-library closure into a portable,
# rpath-patched bundle so it runs without the pacman package that provides
# it. Used in CI (inside an Arch/Holo container — see
# .github/workflows/build.yml's vendor-system job) to vendor TigerVNC
# (Xvnc, vncpasswd) so the release zip doesn't need `pacman -S tigervnc`
# on a fresh Deck.
#
# Usage: bundle-system-deps.sh <out-dir> <binary-name> [<binary-name> ...]
#
# Produces:
#   <out-dir>/bin/<name>   (rpath $ORIGIN/../lib)
#   <out-dir>/lib/*.so*    (non-libc shared-lib closure)
#
# Deliberately keeps glibc/libpthread/libdl/libm/librt/ld-linux dynamic:
# those must match the *running* kernel/NSS setup and are already present
# on every SteamOS install, so bundling them would only add risk without
# buying anything.
#
# This is a best-effort build-time step, not a hardware-validated one — see
# docs/DECKY_STORE.md for the fallback (defaults/install.sh / pacman) used
# when a bundled binary doesn't run on a given SteamOS build.

set -euo pipefail

OUT="${1:?usage: bundle-system-deps.sh <out-dir> <binary> [binary ...]}"
shift
[[ $# -ge 1 ]] || { echo "need at least one binary name" >&2; exit 1; }

mkdir -p "$OUT/bin" "$OUT/lib"

skip_lib() {
    case "$1" in
        libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|ld-linux*|libresolv.so*|libnsl.so*|linux-vdso.so*)
            return 0 ;;
        *) return 1 ;;
    esac
}

bundle_one() {
    local name="$1" src
    src="$(command -v "$name")" || { echo "not found: $name" >&2; return 1; }
    cp -L "$src" "$OUT/bin/$name"
    # ldd prints "name => /path (addr)"; column 3 is the resolved path, but
    # statically-linked or vdso-only entries don't have one, hence the grep.
    ldd "$src" | awk '{print $3}' | grep '^/' | while read -r lib; do
        base="$(basename "$lib")"
        skip_lib "$base" && continue
        cp -Ln "$lib" "$OUT/lib/$base" 2>/dev/null || true
    done
}

for name in "$@"; do
    bundle_one "$name"
done

command -v patchelf >/dev/null || { echo "patchelf required (pacman -S patchelf)" >&2; exit 1; }
for f in "$OUT"/bin/*; do
    patchelf --set-rpath '$ORIGIN/../lib' "$f"
done
for f in "$OUT"/lib/*.so*; do
    [[ -f "$f" ]] || continue
    patchelf --set-rpath '$ORIGIN' "$f" 2>/dev/null || true
done

echo "[bundle-system-deps] bundled into $OUT:"
ls "$OUT/bin"
echo "[bundle-system-deps] $(ls "$OUT/lib" | wc -l) shared librar(y/ies) alongside"
