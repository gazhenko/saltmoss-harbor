#!/usr/bin/env bash
# Scenario screenshots from the macOS build (Builds/shots/verify/<name>/*.png) for reviewing a build at a glance.
#   Tools/verify.sh [names…]     names: title town dialogue sea pots catch shop journal night storm
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Builds/mac/Saltmoss Harbor.app/Contents/MacOS"
BIN="$APP/$(ls "$APP" | head -1)"
OUT="$ROOT/Builds/shots/verify"
run() {
  local name=$1 times=$2; shift 2
  mkdir -p "$OUT/$name"; rm -f "$OUT/$name"/*.png
  "$BIN" -screen-width 1920 -screen-height 1080 -screen-fullscreen 0 -shots "$OUT/$name" -shotTimes "$times" -logFile "$OUT/$name/player.log" "$@" >/dev/null 2>&1
  echo "$name: $(ls "$OUT/$name" | grep -c png) shots, $(grep -cE 'Exception' "$OUT/$name/player.log") exceptions"
}
want=${*:-title town dialogue sea pots catch shop journal night storm seaplay}
for n in $want; do
  case $n in
    title)    run title 7 ;;
    town)     run town 6,9 -play -hour 10 -freezeClock ;;
    dialogue) run dialogue 5,8 -play -hour 10 -freezeClock -dialogue walter_hub,walter -keys "6.5:enter:tap" ;;
    sea)      run sea 7,10 -play -hour 13 -freezeClock -flags met_walter,met_nell -boatAt 20,180,10,6 ;;
    pots)     run pots 6 -play -hour 15 -freezeClock -flags met_walter,met_nell -boatAt -40,260,40 -pots 3 ;;
    catch)    run catch 5 -play -hour 11 -freezeClock -catch salmon ;;
    shop)     run shop 6,12 -play -hour 11 -freezeClock -flags met_nell -stock herring:4,mackerel:3,cod:2,dungeness:3,salmon:2 -openShop ;;
    journal)  run journal 5 -play -hour 11 -freezeClock -journal ;;
    night)    run night 6 -play -hour 21.5 -freezeClock -restoration 3 ;;
    seaplay)  run seaplay 3,6,9,16,33,40,47 -play -hour 10 -flags met_walter,met_nell -boatAt 10,135,0 -keys "2:e:tap,5:space:tap,14:space:tap,30:e:tap,30.4:space:down,31.1:space:up,31.30:space:down,31.56:space:up,31.76:space:down,32.02:space:up,32.22:space:down,32.48:space:up,32.68:space:down,32.94:space:up,33.14:space:down,33.40:space:up,33.60:space:down,33.86:space:up,34.06:space:down,34.32:space:up,34.52:space:down,34.78:space:up,34.98:space:down,35.24:space:up,35.44:space:down,35.70:space:up,35.90:space:down,36.16:space:up,36.36:space:down,36.62:space:up,36.82:space:down,37.08:space:up,37.28:space:down,37.54:space:up,37.74:space:down,38.00:space:up,38.20:space:down,38.46:space:up,38.66:space:down,38.92:space:up,39.12:space:down,39.38:space:up,39.58:space:down,39.84:space:up,40.04:space:down,40.30:space:up,40.50:space:down,40.76:space:up,40.96:space:down,41.22:space:up,41.42:space:down,41.68:space:up,41.88:space:down,42.14:space:up,42.34:space:down,42.60:space:up,42.80:space:down,43.06:space:up,43.26:space:down,43.52:space:up,43.72:space:down,43.98:space:up" ;;
    storm)    run storm 7 -play -hour 15 -freezeClock -weather 5 -flags met_walter -boatAt -60,560,30,4 ;;
  esac
done
