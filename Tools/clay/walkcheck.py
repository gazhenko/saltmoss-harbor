"""
Walkability check for the town layout: rasterise every `collide: mesh` instance plus the terrain into a multi-layer
height grid (walkable = up-facing slope <= 30 deg and above the water), mark cells blocked by geometry 0.35..1.6 m
above a walkable layer (walls, rails, crates...), flood-fill from player_spawn with steps <= 0.3 m, and report which
anchors are reachable. Writes Tools/clay/previews/walkmap.png.

  Tools/.venv/bin/python Tools/clay/walkcheck.py [--cell 0.1]
"""
import json
import math
import os
import sys
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
sys.path[:0] = [HERE, os.path.join(HERE, "models")]
from clay import read_claymesh, euler  # noqa: E402

MODELS = os.path.join(ROOT, "Game/Assets/Saltmoss/Models")
LAYOUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Data/town_layout.json")
CELL = float(sys.argv[sys.argv.index("--cell") + 1]) if "--cell" in sys.argv else 0.1
X0, X1, Z0, Z1 = -48.0, 82.0, -50.0, 46.0
STEP, CLEAR_LO, CLEAR_HI = 0.3, 0.38, 1.5
WALK_NY = math.cos(math.radians(30.5))
NX, NZ = int((X1 - X0) / CELL), int((Z1 - Z0) / CELL)

_cache = {}


def mesh(path):
    if path not in _cache:
        d = read_claymesh(path)
        V, F = [], []
        base = 0
        for p in d["pieces"]:
            if p["hidden"] or p["mat"] in (2, 4):     # cotton and net cut-outs don't collide
                continue
            V.append(np.asarray(p["v"], np.float64))
            F.append(np.asarray(p["f"], np.int64) + base)
            base += len(p["v"])
        _cache[path] = (np.concatenate(V), np.concatenate(F)) if V else (np.zeros((0, 3)), np.zeros((0, 3), np.int64))
    return _cache[path]


def tris_world(path, pos, yaw, scale):
    V, F = mesh(path)
    W = V * scale @ euler((0, yaw, 0)).T + np.asarray(pos)
    return W[F]


def sample_points(T, spacing):
    """Points covering each triangle (barycentric grid sized by the longest edge)."""
    out = [T.mean(axis=1)]
    e = np.max(np.linalg.norm(T - np.roll(T, 1, axis=1), axis=2), axis=1)
    n = np.clip(np.ceil(e / spacing).astype(int), 1, 40)
    for k in np.unique(n):
        sel = T[n == k]
        if k == 1:
            out.append(sel.reshape(-1, 3))
            continue
        ij = [(i, j) for i in range(k + 1) for j in range(k + 1 - i)]
        B = np.array([(i / k, j / k, 1 - (i + j) / k) for i, j in ij])
        out.append(np.einsum("bk,tkd->tbd", B, sel).reshape(-1, 3))
    return np.concatenate(out)


def main():
    lay = json.load(open(LAYOUT))
    walk_pts, block_pts = [], []
    jobs = [(os.path.join(MODELS, it["model"] + ".claymesh"), it["pos"], it.get("yaw", 0.0), it.get("scale", 1.0), it.get("collide", "box"))
            for it in lay["instances"]]
    tdir = os.path.join(MODELS, "terrain")
    for f in sorted(os.listdir(tdir)):
        if f.endswith(".claymesh"):       # skip Unity .meta files
            jobs.append((os.path.join(tdir, f), (0, 0, 0), 0.0, 1.0, "mesh"))
    for path, pos, yaw, scale, col in jobs:
        if col == "none" or not os.path.exists(path):
            continue
        T = tris_world(path, pos, yaw, scale)
        lo, hi = T.min(axis=1), T.max(axis=1)
        keep = (hi[:, 0] > X0) & (lo[:, 0] < X1) & (hi[:, 2] > Z0) & (lo[:, 2] < Z1)
        T = T[keep]
        if not len(T):
            continue
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        if col == "box":
            # box colliders: the instance's footprint blocks (approximate with its triangles)
            block_pts.append(sample_points(T, CELL * 0.9))
            continue
        up = (n[:, 1] > WALK_NY) & (T[:, :, 1].mean(axis=1) > 0.25)
        if up.any():
            walk_pts.append(sample_points(T[up], CELL * 0.7))
        block_pts.append(sample_points(T[~up], CELL * 0.9))
    W = np.concatenate(walk_pts)
    Bp = np.concatenate(block_pts)
    print(f"[walk] walk samples {len(W)}, blocker samples {len(Bp)}")

    def cell_of(P):
        ix = ((P[:, 0] - X0) / CELL).astype(int)
        iz = ((P[:, 2] - Z0) / CELL).astype(int)
        ok = (ix >= 0) & (ix < NX) & (iz >= 0) & (iz < NZ)
        return ix[ok], iz[ok], P[ok, 1]

    # walkable layers: cluster heights per cell into layers (quantised to 0.12 m bins, keep the max per bin)
    ix, iz, y = cell_of(W)
    key = (ix.astype(np.int64) * NZ + iz) * 1000 + np.floor(y / 0.25).astype(np.int64) + 200
    order = np.argsort(key)
    key, y = key[order], y[order]
    uk, start = np.unique(key, return_index=True)
    ymax = np.maximum.reduceat(y, start)
    cells = uk // 1000
    layers = {}
    for c, h in zip(cells.tolist(), ymax.tolist()):
        layers.setdefault(c, []).append(h)
    # merge layers closer than 0.2 m
    for c, hs in layers.items():
        hs.sort()
        merged = [hs[0]]
        for h in hs[1:]:
            if h - merged[-1] < 0.2:
                merged[-1] = h
            else:
                merged.append(h)
        layers[c] = merged
    # blockers
    bx, bz, by = cell_of(Bp)
    bkey = bx.astype(np.int64) * NZ + bz
    border = np.argsort(bkey)
    bkey, by = bkey[border], by[border]
    bu, bstart = np.unique(bkey, return_index=True)
    blockers = {}
    ends = list(bstart[1:]) + [len(bkey)]
    for c, s0, s1 in zip(bu.tolist(), bstart.tolist(), ends):
        blockers[c] = by[s0:s1]

    def blocked(c, h):
        b = blockers.get(c)
        if b is None:
            return False
        return bool(np.any((b > h + CLEAR_LO) & (b < h + CLEAR_HI)))

    nodes = {}
    for c, hs in layers.items():
        for li, h in enumerate(hs):
            # also blocked if another walkable layer sits just above (no headroom)
            if any(h + 0.3 < h2 < h + CLEAR_HI for h2 in hs):
                continue
            if not blocked(c, h):
                nodes[(c, li)] = h
    print(f"[walk] walkable cells {len(nodes)}")

    def find(p):
        ix, iz = int((p[0] - X0) / CELL), int((p[2] - Z0) / CELL)
        best = None
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                c = (ix + dx) * NZ + (iz + dz)
                for li, h in enumerate(layers.get(c, [])):
                    if (c, li) in nodes:
                        d = abs(h - p[1]) + 0.05 * (abs(dx) + abs(dz))
                        if d < 0.6 and (best is None or d < best[0]):
                            best = (d, (c, li))
        return best[1] if best else None

    A = lay["anchors"]
    start = find(A["player_spawn"]["pos"])
    seen = set()
    if start:
        dq = deque([start])
        seen.add(start)
        while dq:
            c, li = dq.popleft()
            h = nodes[(c, li)]
            cx, cz = divmod(c, NZ)
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nc = (cx + dx) * NZ + (cz + dz)
                for nl, nh in enumerate(layers.get(nc, [])):
                    k = (nc, nl)
                    if k in nodes and k not in seen and abs(nh - h) <= STEP:
                        seen.add(k)
                        dq.append(k)
    print(f"[walk] reachable cells {len(seen)}")
    report = []
    pts = []
    for name, v in A.items():
        if name in ("lantern_lights", "window_lights", "bench_spots", "harbor_mouth", "lighthouse_lamp", "boat_berth"):
            continue
        if isinstance(v, dict) and "pos" in v:
            pts.append((name, v["pos"]))
        elif isinstance(v, list) and v and isinstance(v[0], list):
            pts += [(f"{name}[{i}]", p) for i, p in enumerate(v)]
        elif isinstance(v, dict) and "center" in v:
            pts.append((name, v["center"]))
    bad = []
    for name, p in pts:
        n = find(p)
        ok = n is not None and n in seen
        report.append((name, ok))
        if not ok:
            bad.append(name)
    print("[walk] anchors reachable:", sum(ok for _, ok in report), "/", len(report))
    if bad:
        print("[walk] UNREACHABLE:", bad)
    # map image
    from PIL import Image, ImageDraw
    img = np.full((NZ, NX, 3), 30, np.uint8)
    for (c, li), h in nodes.items():
        cx, cz = divmod(c, NZ)
        img[cz, cx] = (190, 170, 60)
    for (c, li) in seen:
        cx, cz = divmod(c, NZ)
        img[cz, cx] = (70, 170, 80) if nodes[(c, li)] < 3 else (60, 140, 160)
    for c in blockers:
        cx, cz = divmod(c, NZ)
        if not any((c, li) in seen for li in range(4)):
            img[cz, cx] = np.maximum(img[cz, cx], (90, 40, 40))
    im = Image.fromarray(img[::-1])
    d = ImageDraw.Draw(im)
    for (name, p), (_, ok) in zip(pts, report):
        x, z = (p[0] - X0) / CELL, NZ - (p[2] - Z0) / CELL
        d.ellipse([x - 5, z - 5, x + 5, z + 5], outline=(60, 120, 255) if ok else (255, 0, 255), width=2)
    out = os.path.join(HERE, "previews", "walkmap.png")
    scale = 1300 / NX
    im = im.resize((int(NX * scale), int(NZ * scale)), Image.NEAREST)
    im.save(out)
    print("[walk] map ->", out)


if __name__ == "__main__":
    main()
