#!/usr/bin/env bash
# README screenshots from the macOS build -> Docs/media/*.png (1920x1080, resized by the README to 300 px thumbnails)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Builds/mac/Saltmoss Harbor.app/Contents/MacOS"
BIN="$APP/$(ls "$APP" | head -1)"
TMP="$ROOT/Builds/shots/readme"; mkdir -p "$TMP" "$ROOT/Docs/media"
shot() {
  local name=$1 t=$2; shift 2
  rm -rf "$TMP/$name"; mkdir -p "$TMP/$name"
  "$BIN" -screen-width 1920 -screen-height 1080 -screen-fullscreen 0 -shots "$TMP/$name" -shotTimes "$t" -logFile "$TMP/$name/player.log" "$@" >/dev/null 2>&1
  local f; f=$(ls "$TMP/$name"/*.png 2>/dev/null | tail -1)
  [ -n "$f" ] && sips -Z 1920 "$f" --out "$ROOT/Docs/media/$name.png" >/dev/null && echo "$name ok"
}
want=${*:-harbour deep shop dialogue catch night}
for n in $want; do
  case $n in
    harbour)  shot harbour 7 -play -noHud -hour 16.8 -freezeClock -cam 14,9,52,-2,3,-6,34 ;;
    deep)     shot deep 9 -play -noHud -hour 14.5 -freezeClock -weather 5 -flags met_walter -boatAt -60,560,30,4 ;;
    shop)     shot shop 16 -play -noHud -hour 11 -freezeClock -flags met_nell -stock herring:6,mackerel:5,cod:4,dungeness:5,salmon:3,halibut:2,flounder:4,snow_crab:3 -openShop ;;
    dialogue) shot dialogue 6 -play -hour 10 -freezeClock -dialogue intro,walter ;;
    catch)    shot catch 5 -play -noHud -hour 11 -freezeClock -catch golden_king ;;
    night)    shot night 8 -play -noHud -hour 21.6 -freezeClock -restoration 3 -cam 18,10,48,-2,4,-8,34 ;;
  esac
done
