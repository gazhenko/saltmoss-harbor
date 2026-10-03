"""Regenerate every Saltmoss Harbor audio asset (music, jingles, SFX, ambiences).

    Tools/.venv/bin/python Tools/audio/build_all.py            # everything
    Tools/.venv/bin/python Tools/audio/build_all.py --only music
    Tools/.venv/bin/python Tools/audio/build_all.py --only sfx
    Tools/.venv/bin/python Tools/audio/build_all.py --only title_theme gull_1

Outputs
    Game/Assets/Saltmoss/Audio/Music/*.ogg   (music + jingles, Vorbis q6)
    Game/Assets/Saltmoss/Audio/Sfx/*.wav     (SFX + ambiences, 16-bit)
    Tools/audio/manifest.json                (one entry per output file)
    Tools/audio/trailer_cues.json            (hit / downbeat seconds for the trailer cut)
    Tools/audio/out/                         (scratch: spectrograms, reports)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MUSIC_DIR = os.path.join(ROOT, "Game", "Assets", "Saltmoss", "Audio", "Music")
SFX_DIR = os.path.join(ROOT, "Game", "Assets", "Saltmoss", "Audio", "Sfx")
OUT_DIR = os.path.join(HERE, "out")
MANIFEST = os.path.join(HERE, "manifest.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None,
                    help="'music', 'sfx', or individual asset names (no extension)")
    ap.add_argument("-j", "--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    args = ap.parse_args()
    only = args.only or None
    groups = {"music", "sfx"}
    want_music = only is None or "music" in only or not (set(only) & groups)
    want_sfx = only is None or "sfx" in only or not (set(only) & groups)
    names = None if only is None else [o for o in only if o not in groups] or None

    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    results = []
    if want_music:
        import music
        results += music.build(MUSIC_DIR, OUT_DIR, only=names, jobs=args.jobs)
    if want_sfx:
        import sfx
        results += sfx.build(SFX_DIR, OUT_DIR, only=names, jobs=args.jobs)

    # merge into the existing manifest (partial rebuilds keep other entries)
    old = []
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            old = json.load(f)
    by_file = {e["file"]: e for e in old}
    for r in results:
        by_file[r["entry"]["file"]] = r["entry"]
    # drop entries whose files no longer exist
    def exists(e):
        d = MUSIC_DIR if e["file"].endswith(".ogg") else SFX_DIR
        return os.path.exists(os.path.join(d, e["file"]))
    order = {"music": 0, "jingle": 1, "ambience": 2, "sfx": 3}
    manifest = sorted((e for e in by_file.values() if exists(e)),
                      key=lambda e: (order.get(e["kind"], 9), e["file"]))
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

    # diagnostics report
    rep_path = os.path.join(OUT_DIR, "report.json")
    rep = {}
    if os.path.exists(rep_path):
        with open(rep_path) as f:
            rep = json.load(f)
    for r in results:
        rep[r["entry"]["file"]] = {**r["entry"], **r["diag"]}
    with open(rep_path, "w") as f:
        json.dump(rep, f, indent=2)

    problems = []
    for r in results:
        e, d = r["entry"], r["diag"]
        if d.get("nan"):
            problems.append(f"{e['file']}: NaN/inf")
        if d.get("clip"):
            problems.append(f"{e['file']}: clipping")
        if d.get("dc", 0) > 0.002:
            problems.append(f"{e['file']}: DC {d['dc']:.4f}")
        seam_bad = (not d["seam_ok"]) if "seam_ok" in d else d.get("rms_diff_db", 0) > 3.0
        if e["loop"] and (seam_bad or d.get("seam_ratio", 0) > 1.5):
            problems.append(f"{e['file']}: loop seam rms_diff={d.get('rms_diff_db')} "
                            f"ratio={d.get('seam_ratio'):.2f}")
    total = sum(os.path.getsize(os.path.join(MUSIC_DIR if e["file"].endswith(".ogg") else SFX_DIR, e["file"]))
                for e in manifest)
    print(f"\nbuilt {len(results)} files in {time.time() - t0:.0f}s; manifest has {len(manifest)} entries, "
          f"{total / 1e6:.1f} MB total")
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems))
    else:
        print("all checks passed")


if __name__ == "__main__":
    main()
