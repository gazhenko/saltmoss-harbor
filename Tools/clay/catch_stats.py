"""Print per-piece triangle counts, pieces and sockets of .claymesh files: catch_stats.py fish [crabs/dungeness ...]"""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from clay import read_claymesh  # noqa: E402

MODELS = os.path.join(HERE, "../../Game/Assets/Saltmoss/Models")
verbose = "-v" in sys.argv
for it in [a for a in sys.argv[1:] if a != "-v"]:
    d = os.path.join(MODELS, it)
    paths = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".claymesh")) if os.path.isdir(d) else [d + ".claymesh"]
    for p in paths:
        m = read_claymesh(p)
        tris = sum(len(pc["f"]) for pc in m["pieces"])
        name = os.path.relpath(p, MODELS)[:-9]
        print(f"{name:28s} {tris:6d} tris  bones={[b[0] for b in m['bones']]}  sockets={[s[0] for s in m['sockets']]}")
        if verbose:
            for pc in m["pieces"]:
                v = pc["v"]
                print(f"    {pc['name']:18s} mat{pc['mat']} {len(pc['f']):6d} tris  rigid={pc['rigid']} hidden={pc['hidden']}  "
                      f"bbox=({v[:,0].min():.3f},{v[:,1].min():.3f},{v[:,2].min():.3f})..({v[:,0].max():.3f},{v[:,1].max():.3f},{v[:,2].max():.3f})")
