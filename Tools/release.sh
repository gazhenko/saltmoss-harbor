#!/usr/bin/env bash
# Package Builds/{mac,win,linux} + the trailer and publish a GitHub release.
#   Tools/release.sh v1.0.0 [--draft]
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
ls -lh "$OUT"
gh release create "$TAG" $DRAFT --title "Saltmoss Harbor $TAG" --notes-file "$ROOT/Docs/RELEASE_NOTES.md" "$OUT"/*
