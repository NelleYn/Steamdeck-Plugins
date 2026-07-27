#!/usr/bin/env bash
# Harvest the GameMirror stack: gst-launch-1.0, wmctrl, xdotool (bundled the
# same way as scripts/bundle-system-deps.sh — see that file for the
# rationale), plus the actual GStreamer plugin .so's GameMirror needs
# (pipewiresrc from gst-plugin-pipewire; videoconvert + ximagesink from
# gst-plugins-good), which aren't executables so they need their own
# discovery via the owning package's file list.
#
# Meant to run inside an Arch/Holo container with tigervnc, wmctrl,
# gst-plugin-pipewire, gst-plugins-good and patchelf already pacman-installed
# — see .github/workflows/build.yml's vendor-system job.
#
# Usage: bundle-gst-plugins.sh <out-dir>
#
# Produces (merged into the same tree as bundle-system-deps.sh's tigervnc
# output, under a sibling "gstreamer" root):
#   <out-dir>/bin/gst-launch-1.0, wmctrl, xdotool   (rpath $ORIGIN/../lib)
#   <out-dir>/gst-plugins-1.0/*.so                  (rpath $ORIGIN/../lib)
#   <out-dir>/lib/*.so*                             (shared shared-lib closure)
#
# deckpip.system_vendor.gst_plugin_env() points GST_PLUGIN_PATH at
# gst-plugins-1.0/ at runtime so gst-launch-1.0 finds these without a
# GStreamer registry rebuild or pacman install.

set -euo pipefail

OUT="${1:?usage: bundle-gst-plugins.sh <out-dir>}"
mkdir -p "$OUT/bin" "$OUT/gst-plugins-1.0" "$OUT/lib"

skip_lib() {
    case "$1" in
        libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|ld-linux*|libresolv.so*|libnsl.so*|linux-vdso.so*)
            return 0 ;;
        *) return 1 ;;
    esac
}

bundle_closure() {
    # $1 = source file to copy, $2 = destination file path
    cp -L "$1" "$2"
    ldd "$1" 2>/dev/null | awk '{print $3}' | grep '^/' | while read -r lib; do
        base="$(basename "$lib")"
        skip_lib "$base" && continue
        cp -Ln "$lib" "$OUT/lib/$base" 2>/dev/null || true
    done
}

for name in gst-launch-1.0 wmctrl xdotool; do
    src="$(command -v "$name" || true)"
    if [[ -z "$src" ]]; then
        echo "[bundle-gst-plugins] skipping optional binary not found: $name" >&2
        continue
    fi
    bundle_closure "$src" "$OUT/bin/$name"
done

PLUGIN_FILES="$(pacman -Ql gst-plugin-pipewire gst-plugins-good 2>/dev/null \
    | awk '{print $2}' | grep -E '/gstreamer-1\.0/.*\.so$' || true)"

if [[ -z "$PLUGIN_FILES" ]]; then
    echo "[bundle-gst-plugins] no gstreamer-1.0 plugin .so files found" >&2
    exit 1
fi

while read -r so; do
    [[ -f "$so" ]] || continue
    bundle_closure "$so" "$OUT/gst-plugins-1.0/$(basename "$so")"
done <<< "$PLUGIN_FILES"

command -v patchelf >/dev/null || { echo "patchelf required (pacman -S patchelf)" >&2; exit 1; }
for f in "$OUT"/bin/* "$OUT"/gst-plugins-1.0/*.so; do
    [[ -f "$f" ]] || continue
    patchelf --set-rpath '$ORIGIN/../lib' "$f" 2>/dev/null || true
done
for f in "$OUT"/lib/*.so*; do
    [[ -f "$f" ]] || continue
    patchelf --set-rpath '$ORIGIN' "$f" 2>/dev/null || true
done

echo "[bundle-gst-plugins] bundled binaries: $(ls "$OUT/bin" 2>/dev/null | tr '\n' ' ')"
echo "[bundle-gst-plugins] bundled $(ls "$OUT/gst-plugins-1.0" | wc -l) gstreamer plugin(s)"
echo "[bundle-gst-plugins] $(ls "$OUT/lib" | wc -l) shared librar(y/ies) alongside"
