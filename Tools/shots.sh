#!/usr/bin/env bash
# Run the macOS player for verification screenshots.
#   Tools/shots.sh <scene> <name> [times=3,6] [extra player args...]   -> Builds/shots/<name>/*.png
#   e.g. Tools/shots.sh Gallery chars 4 -cam 3,1.9,-3.2,3,1.5,0 -hour 15
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Builds/mac/Saltmoss Harbor.app/Contents/MacOS"
BIN="$APP/$(ls "$APP" | head -1)"
scene=${1:?scene}; name=${2:?name}; shift 2
times=${1:-3,6}; shift || true
OUT="$ROOT/Builds/shots/$name"; mkdir -p "$OUT"; rm -f "$OUT"/*.png
"$BIN" -screen-width 1920 -screen-height 1080 -screen-fullscreen 0 -scene "$scene" -shots "$OUT" -shotTimes "$times" -logFile "$OUT/player.log" "$@" || true
ls "$OUT"
