#!/usr/bin/env bash
# Package Builds/{mac,win,linux} + the trailer and publish a GitHub release.
#   Tools/release.sh v1.0.0 [--draft]      (SM_NO_PUBLISH=1 packages without creating the release)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG=${1:?tag like v1.0.0}; shift || true
DRAFT=""; [[ "${1:-}" == "--draft" ]] && DRAFT="--draft"
OUT="$ROOT/Builds/release/$TAG"; rm -rf "$OUT"; mkdir -p "$OUT"
cd "$ROOT/Builds"
[ -d "mac/Saltmoss Harbor.app" ] && ditto -c -k --sequesterRsrc --keepParent "mac/Saltmoss Harbor.app" "$OUT/SaltmossHarbor-$TAG-macOS-universal.zip"
[ -d win ] && (cd win && zip -qr9 "$OUT/SaltmossHarbor-$TAG-Windows-x64.zip" . -x "*_BurstDebugInformation_DoNotShip/*" -x "*_BackUpThisFolder_ButDontShipItWithYourGame/*")
[ -d linux ] && (cd linux && tar --exclude="*_BurstDebugInformation_DoNotShip" --exclude="*_BackUpThisFolder_ButDontShipItWithYourGame" -czf "$OUT/SaltmossHarbor-$TAG-Linux-x64.tar.gz" .)
[ -f "$ROOT/Trailer/saltmoss_harbor_trailer.mp4" ] && cp "$ROOT/Trailer/saltmoss_harbor_trailer.mp4" "$OUT/Saltmoss-Harbor-trailer.mp4"
(cd "$OUT" && shasum -a 256 * > SHA256SUMS.txt)
# Every release ships the offline Mac and Windows installers alongside the portable archives, checked file by file
# against the archives they were built from (installer-validation.json).
python3 "$ROOT/Tools/installers/package.py" "$TAG" --release-dir "$OUT" --output "$OUT"
(cd "$ROOT/Tools/installers" && python3 verify.py "$TAG" --release-dir "$OUT" --output "$OUT")
(cd "$OUT" && files=(); for file in *; do [[ "$file" != SHA256SUMS.txt ]] && files+=("$file"); done; shasum -a 256 "${files[@]}" > SHA256SUMS.txt)
ls -lh "$OUT"
[[ "${SM_NO_PUBLISH:-}" == 1 ]] && exit 0
# the README's download links and the release notes have to point at this release's installers
for f in README.md Docs/RELEASE_NOTES.md; do
  grep -q "releases/download/$TAG/SaltmossHarbor-$TAG-macOS-universal.dmg" "$ROOT/$f" || { echo "$f: installer links don't point at $TAG"; exit 1; }
done
gh release create "$TAG" $DRAFT --title "Saltmoss Harbor $TAG" --notes-file "$ROOT/Docs/RELEASE_NOTES.md" "$OUT"/*
