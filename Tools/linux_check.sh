#!/usr/bin/env bash
# Launch the Linux player on the build VM under Xvfb (software OpenGL) and fetch a screenshot + log.
#   Tools/linux_check.sh      -> Builds/shots/linux/
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${SM_HOST:-kiki-unity}"
OUT="$ROOT/Builds/shots/linux"; mkdir -p "$OUT"
ssh "$HOST" 'set -e; D=$HOME/Projects/saltmoss-harbor/Builds/linux; S=/tmp/saltmoss-linux-check; rm -rf $S; mkdir -p $S; cd $D; chmod +x SaltmossHarbor.x86_64;
  LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe timeout 600 xvfb-run -a -s "-screen 0 1280x720x24" ./SaltmossHarbor.x86_64 -force-glcore \
    -screen-width 1280 -screen-height 720 -screen-fullscreen 0 -play -hour 16.5 -freezeClock -cam 14,9,52,-2,3,-6,34 \
    -shots $S -shotTimes 45 -quitAfter 300 -logFile $S/player.log || true; ls -la $S'
rsync -az "$HOST:/tmp/saltmoss-linux-check/" "$OUT/"
grep -E "Exception|GfxDevice|OpenGL|Vulkan" "$OUT/player.log" | head -8
ls "$OUT"
