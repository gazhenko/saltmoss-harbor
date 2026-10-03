#!/usr/bin/env bash
# Film the trailer shots in the macOS build (24 fps frames + game audio per shot) into Trailer/capture/<shot>/.
#   Tools/trailer/capture.sh [shot,shot,...]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/Builds/mac/Saltmoss Harbor.app/Contents/MacOS"
BIN="$APP/$(ls "$APP" | head -1)"
OUT="$ROOT/Trailer/capture"; mkdir -p "$OUT"
ONLY=()
[ -n "${1:-}" ] && ONLY=(-only "$1")
"$BIN" -screen-width 1920 -screen-height 1080 -screen-fullscreen 0 -trailer -capture "$OUT" -noHud -logFile "$OUT/trailer.log" "${ONLY[@]}"
grep -E "\[Trailer\]|Exception" "$OUT/trailer.log" | head -40
for d in "$OUT"/*/; do echo "$(basename "$d"): $(ls "$d" | grep -c jpg) frames"; done
