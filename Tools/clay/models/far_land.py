"""
The coast beyond the harbour: the town's 200 m terrain patch (town_terrain.py) sits in a long coastline that runs
east and west out to the edge of the world, with beaches, cliffs and headlands, rolling hills behind the town and
mountains further inland. Seen from the sea it reads as a mainland, not a little island.

Coarse heightfield tiles (FAR_TILE m, CELL m grid) on a grid whose edges line up with the town patch's edges
(+-100 m), so every far tile either borders the patch along a full edge or not at all. Within BLEND m of the patch the
height eases from the patch's own edge heights to the far heightfield, and the tiles touching the patch reach a few
metres under its edge (a skirt) so the seam never shows sky.

Tiles: Game/Assets/Saltmoss/Models/terrain/far_<i>_<j>.claymesh (world coordinates, like the town tiles).
`height(x, z)` gives the combined ground height outside the patch (the map renderer uses it).
"""
from __future__ import annotations

import math

import numpy as np

from clay import Model, Piece, fbm, rgb
from kit_town import TP
import town_terrain as TT
from town_terrain import smoothstep, _noise2

FAR_TILE = 200.0
CELL = 5.0
FX0, FX1 = -1100.0, 1100.0       # tile grid edges (odd hundreds, so the patch edges at +-100 are tile edges)
FZ0, FZ1 = -900.0, 300.0
PATCH = 100.0                    # the town patch is [-PATCH, PATCH] in x and z
BLEND = 80.0
SKIRT = 6.0
SEA_FLOOR = -6.0
COAST_Z = 31.0                   # where the patch's coast meets its east and west edges


def coast_z(x):
    """Shoreline z for a given x (land to the south). Matches the patch near its edges, then wanders: bays,
    headlands, and a slow turn north towards the ends of the world."""
    x = np.asarray(x, float)
    ax = np.abs(x)
    zero = np.zeros_like(x)
    wander = 46.0 * _noise2(x, zero, 280.0, 3, 2) + 18.0 * _noise2(x, zero + 40.0, 110.0, 5, 2) + 6.0 * _noise2(x, zero + 80.0, 45.0, 7, 2)
    wander = wander / 0.6
    turn = 0.00035 * np.maximum(ax - 650.0, 0.0) ** 2
    return COAST_Z + (wander + turn) * smoothstep(PATCH, PATCH + 140.0, ax)


def far_height(x, z):
    """The mainland heightfield on its own (no blending with the patch)."""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    d = coast_z(x) - z                                  # metres inland (+) / out to sea (-)
    cliff = smoothstep(-0.15, 0.35, _noise2(x, z * 0.2, 180.0, 11, 2)) * smoothstep(PATCH + 60.0, PATCH + 220.0, np.abs(x))
    ch = 9.0 + 9.0 * _noise2(x, z, 90.0, 12, 2)
    h_beach = np.where(d > 0, 2.3 * (1 - np.exp(-d / 7.0)), 0.28 * d)
    h_cliff = np.where(d > 0, ch * (1 - np.exp(-d / 2.6)), 1.4 * d)
    h = h_beach * (1 - cliff) + h_cliff * cliff
    din = np.maximum(d - 6.0, 0.0)
    hills = 36.0 * (1 - np.exp(-din / 130.0)) * (0.8 + 0.9 * _noise2(x, z, 160.0, 13, 3))
    ridge = 1.0 - np.abs(_noise2(x, z, 240.0, 14, 3)) * 2.2
    mountains = 175.0 * smoothstep(200.0, 720.0, din) * np.clip(0.45 + 0.55 * ridge, 0.1, 1.2)
    lumps = 4.0 * _noise2(x, z, 42.0, 15, 3) + 1.4 * _noise2(x, z, 15.0, 16, 2)
    h = h + (np.maximum(hills, 0.0) + mountains + lumps) * smoothstep(0.0, 25.0, din)
    return np.maximum(h, SEA_FLOOR + 0.3 * _noise2(x, z, 30.0, 17, 2))


_EDGE = None


def edge_height(x, z):
    """The patch's heights, smoothed (sigma 6 m), at the nearest point of its border: what the mainland eases out
    from. Smoothing keeps the patch's small lumps from being dragged out across the blend as streaks."""
    global _EDGE
    from scipy import ndimage
    if _EDGE is None:
        _EDGE = ndimage.gaussian_filter(TT.heightmap()["H"], 6.0 / TT.G)
    fx = (np.clip(x, -PATCH, PATCH) - TT.X0) / TT.G
    fz = (np.clip(z, -PATCH, PATCH) - TT.Z0) / TT.G
    return ndimage.map_coordinates(_EDGE, [np.ravel(fx), np.ravel(fz)], order=1, mode="nearest").reshape(np.shape(x))


_BORDER = None


def _border_profiles():
    """Height along the patch's three landward edges, read from the built town tiles themselves (their marching-cubes
    surface wanders a little off the heightmap), so the mainland meets the tiles' real edges."""
    global _BORDER
    if _BORDER is not None:
        return _BORDER
    import os
    from clay import read_claymesh
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../Game/Assets/Saltmoss/Models/terrain"))
    pts = {"w": [], "e": [], "s": []}
    for i in range(TT.NTX):
        for j in range(TT.NTZ):
            p = os.path.join(root, f"tile_{i}_{j}.claymesh")
            if not os.path.exists(p):
                continue
            for pc in read_claymesh(p)["pieces"]:
                v = pc["v"]
                for key, m, along in (("w", np.abs(v[:, 0] + PATCH) < 1e-3, 2), ("e", np.abs(v[:, 0] - PATCH) < 1e-3, 2),
                                      ("s", np.abs(v[:, 2] + PATCH) < 1e-3, 0)):
                    if m.any():
                        pts[key].append(np.column_stack([v[m, along], v[m, 1]]))
    _BORDER = {}
    for key, arrs in pts.items():
        if not arrs:
            continue
        a = np.concatenate(arrs)
        a = a[np.argsort(a[:, 0])]
        # the surface is the top of each column of edge vertices
        t = np.round(a[:, 0], 3)
        ut, inv = np.unique(t, return_inverse=True)
        top = np.full(len(ut), -1e9)
        np.maximum.at(top, inv, a[:, 1])
        _BORDER[key] = (ut, top)
    return _BORDER


def border_height(x, z):
    """Height at the nearest point of the patch's border: the town tiles' own edge where we have it, else the
    heightmap (the seaward north edge and the corners)."""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    cx, cz = np.clip(x, -PATCH, PATCH), np.clip(z, -PATCH, PATCH)
    h = TT.height(cx, cz)
    prof = _border_profiles()
    for key, sel, along in (("w", (x < -PATCH) & (np.abs(z) < PATCH), cz), ("e", (x > PATCH) & (np.abs(z) < PATCH), cz),
                            ("s", (z < -PATCH) & (np.abs(x) < PATCH), cx)):
        if key in prof and sel.any():
            t, top = prof[key]
            h = np.where(sel, np.interp(along, t, top), h)
    return h


def patch_dist(x, z):
    """Distance outside the town patch (0 inside)."""
    dx = np.maximum(np.abs(x) - PATCH, 0.0)
    dz = np.maximum(np.abs(z) - PATCH, 0.0)
    return np.hypot(dx, dz)


def height(x, z):
    """Ground height outside the patch: the patch's edge heights eased into the mainland over BLEND metres. Inside
    the patch (the skirt) it sits well under the patch's own surface."""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    q = patch_dist(x, z)
    inside = (np.abs(x) < PATCH - 1e-6) & (np.abs(z) < PATCH - 1e-6)
    # right at the border take the patch's own height (so the seam meets), then its smoothed edge profile
    near = border_height(x, z)
    edge = near * (1 - smoothstep(0.0, 30.0, q)) + edge_height(x, z) * smoothstep(0.0, 30.0, q)
    w = smoothstep(0.0, BLEND, q)
    h = edge * (1 - w) + far_height(x, z) * w
    return np.where(inside, TT.height(x, z) - 1.4, h)


class FarPiece(Piece):
    def __init__(self, model, lo, hi):
        super().__init__(model, "ground", color=TP["grass"], gloss=25, lumps=0.0, mottle=0.05, seed=4321, res=None, ao=False)
        self.lo, self.hi = np.asarray(lo, float), np.asarray(hi, float)
        self.ops = []

    def bounds(self):
        return self.lo, self.hi

    def sdf(self, P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        e = 0.6
        H = height(x, z)
        gx = (height(x + e, z) - height(x - e, z)) / (2 * e)
        gz = (height(x, z + e) - height(x, z - e)) / (2 * e)
        # thumb-pressed lumps between the grid points, so the big clay slopes still catch the light unevenly
        det = 1.1 * fbm(P / 9.0, 2, 201) + 0.45 * fbm(P / 3.5, 2, 202)
        return (y - H) / np.sqrt(1 + gx * gx + gz * gz) + det

    def attributes(self, P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        e = 1.5
        gx = (height(x + e, z) - height(x - e, z)) / (2 * e)
        gz = (height(x, z + e) - height(x, z - e)) / (2 * e)
        slope = np.sqrt(gx * gx + gz * gz)
        d = coast_z(x) - z
        n1 = fbm(P / 60.0, 2, 211)
        n2 = fbm(P / 9.0, 2, 212)
        n3 = fbm(P / 2.5, 2, 213)
        # grass: dry on the tops, lush in the hollows, with tool-scored strokes like the town's slopes
        col = rgb(TP["grass"]) * np.ones((len(P), 1))
        tdry = np.clip(0.2 + n1 * 1.2 + smoothstep(25, 90, y) * 0.3, 0, 1)[:, None]
        col = col * (1 - tdry) + rgb("#9a9a63") * tdry
        tl = np.clip(-n2 * 0.9 + 0.15, 0, 0.7)[:, None]
        col = col * (1 - tl) + rgb("#58703f") * tl
        ang = n1 * 3.0
        u = (x * np.cos(ang) + z * np.sin(ang)) / 3.0
        stroke = np.clip(np.cos(u * 2 * np.pi + n3 * 2.0), 0, 1) ** 4 * np.clip(n2 * 2 + 0.6, 0, 1)
        col = col * (1 - 0.1 * stroke[:, None])
        # heather and bracken on the high moor, gorse patches lower down
        moor = (smoothstep(45, 110, y) * np.clip(0.5 + n1, 0, 1))[:, None]
        col = col * (1 - moor * 0.65) + rgb("#7d6a6e") * moor * 0.65
        brk = (smoothstep(0.15, 0.3, fbm(P / 22.0, 2, 214)) * smoothstep(20, 60, y))[:, None]
        col = col * (1 - brk * 0.5) + rgb("#9c7a4a") * brk * 0.5
        gorse = (smoothstep(0.32, 0.4, fbm(P / 6.0, 2, 215)) * smoothstep(3, 8, y) * smoothstep(40, 25, y))[:, None]
        col = col * (1 - gorse * 0.45) + rgb("#b8973a") * gorse * 0.45
        # rock: cliffs, steep slopes and the mountain tops
        rockness = np.clip(smoothstep(0.4, 0.8, slope) + smoothstep(120, 170, y) * 0.8 + smoothstep(0.25, 0.4, n2) * smoothstep(60, 100, y) * 0.6
                           + smoothstep(0.3, 0.42, fbm(P / 14.0, 2, 217)) * smoothstep(0.2, 0.4, slope) * 0.8, 0, 1)
        rcol = rgb("#78766f") * (1 + 0.12 * n2[:, None]) + (rgb("#8f8b82") - rgb("#78766f")) * np.clip(n3, 0, 1)[:, None]
        lich = smoothstep(0.25, 0.35, fbm(P / 4.0, 2, 216))[:, None]
        rcol = rcol * (1 - lich * 0.5) + rgb("#b5874a") * lich * 0.5
        wet = smoothstep(1.2, 0.0, y)[:, None]
        rcol = rcol * (1 - wet * 0.45) + rgb(TP["wood_wet"]) * wet * 0.45
        # beaches: sand from the waterline up the first few metres where there is no cliff
        sand = np.clip(smoothstep(4.5, 1.5, y + 0.6 * n2) * smoothstep(-6, 0, d) * (1 - smoothstep(0.35, 0.7, slope)), 0, 1)[:, None]
        scol = rgb("#c9ad85") * (1 + 0.05 * n1[:, None])
        scol = scol * (1 - wet * 0.4) + rgb("#7d6e58") * wet * 0.4
        col = col * (1 - sand) + scol * sand
        w_r = np.clip(rockness * 1.2, 0, 1)[:, None] * (1 - sand)
        col = col * (1 - w_r) + rcol * w_r
        # under water: dark seabed
        uw = smoothstep(-0.6, -1.6, y)[:, None]
        col = col * (1 - uw) + rgb("#3d4840") * uw
        gloss = 22 + 110 * smoothstep(0.6, 0.0, y) * smoothstep(-1.2, -0.2, y) + 15 * rockness
        return np.clip(col, 0, 1), gloss, {}


def touches_patch(x0, z0):
    cx, cz = x0 + FAR_TILE / 2, z0 + FAR_TILE / 2
    return abs(cx) < 2 * FAR_TILE and abs(cz) < 2 * FAR_TILE - 1


class FarTile(Model):
    def __init__(self, name, x0, z0):
        super().__init__(name, res=CELL)
        self.x0, self.z0 = x0, z0
        # the tiles round the town get a finer grid; their edges shared with other far tiles keep to the coarse grid
        self.cell = CELL / 2 if touches_patch(x0, z0) else CELL
        self.decimate_min = 10 ** 9
        # reach a few metres under the patch on the side(s) that touch it
        x1, z1 = x0 + FAR_TILE, z0 + FAR_TILE
        over_x = abs(z0 + FAR_TILE / 2) < PATCH
        over_z = abs(x0 + FAR_TILE / 2) < PATCH
        self.gx0 = x0 - (SKIRT if over_x and abs(x0 - PATCH) < 1e-6 else 0.0)
        self.gx1 = x1 + (SKIRT if over_x and abs(x1 + PATCH) < 1e-6 else 0.0)
        self.gz0 = z0 - (SKIRT if over_z and abs(z0 - PATCH) < 1e-6 else 0.0)
        self.gz1 = z1 + (SKIRT if over_z and abs(z1 + PATCH) < 1e-6 else 0.0)
        self.pieces.append(FarPiece(self, (self.gx0, SEA_FLOOR - 2, self.gz0), (self.gx1, 260.0, self.gz1)))

    def _axis(self, a0, a1, e0, e1):
        core = a0 + np.arange(int(round((a1 - a0) / self.cell)) + 1) * self.cell
        pre = [e0] if e0 < a0 - 1e-6 else []
        post = [e1] if e1 > a1 + 1e-6 else []
        return np.array(pre + list(core) + post)

    def _mesh_piece(self, p):
        xs = self._axis(self.x0, self.x0 + FAR_TILE, self.gx0, self.gx1)
        zs = self._axis(self.z0, self.z0 + FAR_TILE, self.gz0, self.gz1)
        X, Z = np.meshgrid(xs, zs, indexing="ij")
        H = height(X.ravel(), Z.ravel()).reshape(X.shape)
        if self.cell < CELL:
            # on edges shared with coarse tiles, the in-between vertices sit on the coarse edge's straight line
            x1, z1 = self.x0 + FAR_TILE, self.z0 + FAR_TILE
            for ax, coord, val in ((0, xs, self.x0), (0, xs, x1), (1, zs, self.z0), (1, zs, z1)):
                k = int(np.argmin(np.abs(coord - val)))
                if abs(coord[k] - val) > 1e-6 or (ax == 0 and abs(val) == PATCH and abs(self.z0 + FAR_TILE / 2) < PATCH) \
                        or (ax == 1 and abs(val) == PATCH and abs(self.x0 + FAR_TILE / 2) < PATCH):
                    continue                                    # the side against the town patch keeps its detail
                line = H[k, :] if ax == 0 else H[:, k]
                other = zs if ax == 0 else xs
                lo, hi = (self.z0, z1) if ax == 0 else (self.x0, x1)
                for j in range(len(other)):
                    t = (other[j] - lo) / CELL
                    if lo - 1e-6 <= other[j] <= hi + 1e-6 and abs(t - round(t)) > 1e-6:
                        j0 = int(np.argmin(np.abs(other - (lo + math.floor(t) * CELL))))
                        j1 = int(np.argmin(np.abs(other - (lo + math.ceil(t) * CELL))))
                        line[j] = 0.5 * (line[j0] + line[j1])
        verts = np.column_stack([X.ravel(), H.ravel(), Z.ravel()])
        nx, nz = len(xs), len(zs)
        idx = np.arange(nx * nz).reshape(nx, nz)
        a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
        # wind so the faces point up (+y): (a, d, b) and (b, d, c) with x along i and z along j
        f1 = np.stack([a, d, b], -1).reshape(-1, 3)
        f2 = np.stack([b, d, c], -1).reshape(-1, 3)
        faces = np.concatenate([f1, f2])
        # drop quads that lie entirely on the deep seabed (never seen through the opaque sea)
        keep = verts[faces][:, :, 1].max(axis=1) > SEA_FLOOR + 1.2
        faces = faces[keep]
        used = np.unique(faces)
        remap = -np.ones(len(verts), np.int64)
        remap[used] = np.arange(len(used))
        print(f"[far] {self.name}: {len(faces)} tris")
        return verts[used], remap[faces]


def tile_origin(i, j):
    return FX0 + i * FAR_TILE, FZ0 + j * FAR_TILE


def tile_exists(i, j):
    x0, z0 = tile_origin(i, j)
    if abs(x0 + FAR_TILE / 2) < PATCH and abs(z0 + FAR_TILE / 2) < PATCH:
        return False                                    # the town patch itself
    xs = np.linspace(x0, x0 + FAR_TILE, 21)
    zs = np.linspace(z0, z0 + FAR_TILE, 21)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    return bool(far_height(X.ravel(), Z.ravel()).max() > -1.0)


def make_tile(i, j):
    def fn():
        x0, z0 = tile_origin(i, j)
        return FarTile(f"far_{i}_{j}", x0, z0)
    return fn


NI = int(round((FX1 - FX0) / FAR_TILE))
NJ = int(round((FZ1 - FZ0) / FAR_TILE))
MODELS = {}
for _i in range(NI):
    for _j in range(NJ):
        if tile_exists(_i, _j):
            MODELS[f"terrain/far_{_i}_{_j}"] = make_tile(_i, _j)
