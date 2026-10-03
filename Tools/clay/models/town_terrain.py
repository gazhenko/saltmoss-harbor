"""
Saltmoss coast terrain: a designed heightmap (coast polygon + per-region shore profiles, the quay street plateau,
west pebble/sand beach, grassy slopes rising to ~30 m hills behind the town, the eastern rocky headland, two rocky
harbour arms with a mouth at (0, 74), building pads and footpaths) turned into chunky sculpted clay: an SDF
(heightfield + 3D lumps/creases on rock) meshed per 40 m tile on a globally aligned grid so neighbouring tiles share
their border vertices exactly.

Tiles: Game/Assets/Saltmoss/Models/terrain/tile_<i>_<j>.claymesh, i over x (-100..100), j over z (-100..100).
`height(x, z)` gives the ground height (used by the layout generator).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage
from skimage.draw import polygon as rasterize

from clay import Model, Piece, fbm, vnoise, rgb, mix, shade, gradient, bake_ao
from kit_town import TP, crc

G = 0.5                      # heightmap cell (m)
X0, X1, Z0, Z1 = -112.0, 112.0, -112.0, 102.0
TILE = 40.0
TX0, TZ0 = -100.0, -100.0
NTX, NTZ = 5, 5
SEA_FLOOR = -4.4
STREET_Y = 1.72

# --- the plan (shared with the layout generator) -----------------------------------------------------------------
COAST = [  # land polygon (x, z), land to the south
    (-125, -125), (-125, 33), (-80, 32), (-64, 27), (-52, 23), (-42, 19.5), (-35, 15.5), (-29, 11), (-24.5, 4.5), (-20.5, -2.5),
    (-18.2, -7.0), (-16.6, -9.0), (-8, -9.0), (0, -9.0), (8, -9.0), (18.6, -9.0), (21.0, -6.0), (25, -2.5), (31, 0.5), (38, 4.5),
    (45, 10), (51, 17), (56, 25), (59.5, 31), (61, 38), (63.5, 46), (69, 52), (77, 53), (84, 48), (88, 40), (92, 33),
    (100, 30), (125, 30), (125, -125)]
WEST_ARM = [(-50, 22), (-46, 32), (-39, 43), (-31, 54), (-22, 64), (-14, 72), (-11.5, 76)]
EAST_ARM = [(63, 46), (55, 53), (45, 59), (34, 64), (24, 69), (15.5, 73), (12.0, 76)]
HEADLAND = ((73.0, 41.0), (15.0, 12.0), 12.5)        # centre, radii, height
# building pads: (x, z, half_x, half_z, yaw_deg, height or None=auto, feather)
PADS = [
    (-17.0, -14.6, 3.4, 3.0, 0, STREET_Y, 2.0),       # post office
    (-24.5, -7.5, 3.0, 2.6, 60, None, 2.5),           # net shed at the head of the beach
    (-32.0, 7.5, 9.0, 4.6, 155, None, 3.5),           # museum hull on the beach
    (-6.0, -24.0, 3.6, 3.4, 8, None, 3.0),            # cottage_a
    (12.5, -27.5, 3.6, 3.4, -14, None, 3.0),          # cottage_b
    (-23.5, -30.0, 3.6, 3.4, 18, None, 3.0),          # cottage_c
    (27.0, -21.0, 3.6, 3.4, -32, None, 3.0),          # cottage_a #2
    (3.5, -39.0, 3.6, 3.4, 4, None, 3.0),             # cottage_b #2
    (71.0, 40.0, 5.0, 5.0, 0, None, 4.0),             # lighthouse
]
# footpaths: polylines (x, z), half width
PATHS = [
    ([(-16.0, -12.0), (-21.0, -9.5), (-25.5, -3.0), (-28.5, 2.0), (-29.5, 4.0)], 1.4),       # street -> beach -> museum
    ([(-2.0, -15.5), (-3.5, -19.0), (-6.0, -21.0)], 1.1),                                   # street -> cottage_a
    ([(-3.5, -19.0), (2.0, -22.5), (8.0, -24.5), (11.5, -25.0)], 1.0),                      # -> cottage_b
    ([(-4.5, -20.0), (-12.0, -24.0), (-19.0, -27.0), (-22.0, -27.5)], 1.0),                 # -> cottage_c
    ([(8.0, -24.5), (5.0, -31.0), (3.5, -36.5)], 1.0),                                      # -> cottage_b #2
    ([(17.0, -15.0), (22.0, -18.0), (25.0, -19.0)], 1.0),                                   # -> cottage_a #2
    ([(19.0, -12.0), (26.0, -8.5), (33.0, -4.0), (41.0, 3.0), (48.0, 11.0), (54.0, 20.0), (58.5, 28.0), (63.0, 34.0), (67.5, 37.5)], 1.3),  # lighthouse walk
]
STREET = (-17.0, 19.0, -16.4, -9.0)      # x0, x1, z0, z1 of the flat quay street

# --- density pass: the hillside village (buildings from models/town_village.py, placed by town_layout.py) ----------
# pads for the new houses: two net sheds in a front row cut into the bank behind the street, cottages on terraces
PADS += [
    (-24.7, -15.0, 3.2, 2.9, 30, 2.15, 2.0),          # H1 net_shed_ochre (top of the beach, west of the post office)
    (9.0, -18.4, 3.2, 2.5, 0, 1.85, 1.5),             # H2 net_shed_blue (cut into the bank behind the street)
    (22.5, -32.5, 3.6, 3.4, -22, 5.8, 3.0),           # H3 cottage_a_sky (top of the east ramps)
    (-13.5, -33.0, 3.6, 3.4, 12, None, 3.0),          # H4 cottage_b_rose
    (-3.5, -33.5, 3.6, 3.4, 4, None, 3.0),            # H5 cottage_a_chalk
    (15.5, -40.5, 3.6, 3.4, -6, None, 3.0),           # H6 cottage_c_slate
    (-10.5, -42.5, 3.6, 3.4, 10, None, 3.0),          # H7 cottage_b_mustard
    (5.0, -47.5, 3.6, 3.4, 90, 11.2, 2.5),            # H8 cottage_a_red (top of the stairs, faces east)
    (36.0, -25.0, 3.6, 3.4, -50, None, 3.0),          # H9 cottage_c_green (east, above cottage_a #2)
    (1.5, -18.5, 2.3, 1.9, 0, None, 1.5),             # H10 smokehouse (the gap behind the street)
]
# lanes between the terraces
PATHS += [
    ([(6.0, -28.7), (0.5, -29.1), (-3.5, -29.3), (-9.0, -29.1), (-14.0, -28.9), (-18.5, -27.2)], 1.0),      # terrace 2 lane
    ([(10.0, -37.4), (3.5, -36.5), (-2.5, -37.9), (-8.0, -38.2), (-11.5, -38.5)], 1.0),                     # terrace 3 lane (west)
    ([(3.5, -36.5), (8.5, -36.2), (15.0, -37.0)], 1.0),                                                     # terrace 3 lane (east)
    ([(20.4, -16.8), (20.2, -19.4)], 1.1),                                                                  # street -> east ramps
    ([(25.0, -19.0), (29.5, -18.4), (33.6, -22.4)], 1.0),                                                   # -> H9
    ([(-21.6, -10.6), (-23.3, -12.5)], 1.0),                                                                # beach path -> H1
]
# boardwalk flights laid on the slope: (kind, x, z, yaw, y) = the kit piece placement (town_pier.py: stairs descend
# 1.8 m toward local +Z from a landing at y; ramps rise 1 m toward local +Z from y; squares are flat landings).
# The terrain under each one is graded to match (see heightmap), and town_layout.py places the pieces.
FLIGHTS = [
    ("ramp", 20.2, -21.5, 180, 3.8), ("ramp", 20.2, -25.5, 180, 4.8),                 # street lane -> H3
    ("stairs", 10.0, -39.8, 0, 9.4), ("square", 10.0, -43.0, 0, 9.4), ("stairs", 10.0, -46.2, 0, 11.2),   # -> H8
]


def flight_links():
    """Graded straight runs ((x0, z0, y0), (x1, z1, y1), half_width) under the FLIGHTS pieces."""
    out = []
    for kind, x, z, yaw, y in FLIGHTS:
        dx, dz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        if kind == "stairs":
            a, b = (x - 2 * dx, y - 0.08, z - 2 * dz), (x + 2 * dx, y - 1.88, z + 2 * dz)
        elif kind == "ramp":
            a, b = (x - 2 * dx, y - 0.15, z - 2 * dz), (x + 2 * dx, y + 0.85, z + 2 * dz)
        else:
            a, b = (x - 1.2 * dx, y - 0.1, z - 1.2 * dz), (x + 1.2 * dx, y - 0.1, z + 1.2 * dz)
        out.append((a, b, 1.25))
    return out


def _seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = np.clip(((px - ax) * dx + (pz - az) * dz) / max(L2, 1e-9), 0, 1)
    qx, qz = ax + t * dx, az + t * dz
    return np.hypot(px - qx, pz - qz), t


def poly_dist(px, pz, pts):
    d = np.full(px.shape, 1e9)
    s_at = np.zeros(px.shape)
    acc = 0.0
    total = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    for i in range(len(pts) - 1):
        di, t = _seg_dist(px, pz, pts[i], pts[i + 1])
        L = math.dist(pts[i], pts[i + 1])
        m = di < d
        d = np.where(m, di, d)
        s_at = np.where(m, (acc + t * L) / total, s_at)
        acc += L
    return d, s_at


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _noise2(X, Z, scale, seed, octaves=3):
    P = np.stack([X / scale, np.full(X.shape, 0.37 * seed), Z / scale], axis=-1).reshape(-1, 3)
    return fbm(P, octaves, seed).reshape(X.shape)


_HM = None


def heightmap():
    """-> dict(H, X, Z, masks...) on the G grid. Cached."""
    global _HM
    if _HM is not None:
        return _HM
    xs = np.arange(X0, X1 + G * 0.5, G)
    zs = np.arange(Z0, Z1 + G * 0.5, G)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    # signed distance to the coast (+ inland)
    poly = np.array(COAST)
    rr, cc = rasterize((poly[:, 0] - X0) / G, (poly[:, 1] - Z0) / G, X.shape)
    land = np.zeros(X.shape, bool)
    land[rr, cc] = True
    d = (ndimage.distance_transform_edt(land) - ndimage.distance_transform_edt(~land)) * G
    # region weights (smoothed so the profiles blend without seams)
    w_beach = smoothstep(-15.5, -21.0, X) * smoothstep(-26.0, -16.0, Z) * smoothstep(-75, -60, X)
    w_quay = smoothstep(-19.5, -16.0, X) * smoothstep(21.0, 18.0, X) * smoothstep(-30, -18, Z)
    w_beach = ndimage.gaussian_filter(w_beach, 4.0)
    w_quay = ndimage.gaussian_filter(w_quay, 2.0)
    w_rock = np.clip(1 - w_beach - w_quay, 0, 1)
    # shore profiles (height vs distance inland)
    h_beach = np.where(d > 0, 2.0 * (1 - np.exp(-d / 5.5)), 0.26 * d)
    h_quay = np.where(d > 0, STREET_Y, np.maximum(STREET_Y - 0.15 + 0.75 * d, -3.6))
    h_rockshore = np.where(d > 0, 2.6 * (1 - np.exp(-d / 3.5)), 0.85 * d)
    h = w_beach * h_beach + w_quay * h_quay + w_rock * h_rockshore
    # inland rise: one smooth field for everybody (starts behind the street), big lumpy hills further back
    din = np.maximum(d - 7.5, 0)
    nb = _noise2(X, Z, 34, 3, 2)
    rise = 0.22 * din + smoothstep(18, 70, din) * (9.0 + 9.0 * nb) + smoothstep(8, 30, din) * 2.5 * _noise2(X, Z, 15, 4, 2)
    rise = 31.0 * np.tanh(rise / 31.0)
    h = h + rise * smoothstep(0, 5, din)
    # hills: big lumpy swells
    hill_mask = smoothstep(14, 40, d)
    h = h + hill_mask * (2.0 * _noise2(X, Z, 22, 11) + 1.2 * _noise2(X, Z, 8, 12))
    # rock escarpments in the hills behind the town (short arcs, a few metres tall)
    for (cx, cz, L, ang, ht) in ((-22, -56, 26, 10, 5.0), (18, -62, 22, -15, 4.5), (-55, -40, 18, 35, 4.0), (48, -45, 20, -30, 4.0)):
        a = math.radians(ang)
        u = (X - cx) * math.cos(a) + (Z - cz) * math.sin(a)
        v = -(X - cx) * math.sin(a) + (Z - cz) * math.cos(a)
        along = 1 - smoothstep(L * 0.22, L * 0.55, np.abs(u) + 2.5 * _noise2(X, Z, 6, int(cx) + 5))
        front = smoothstep(1.2, -1.2, v + 1.5 * _noise2(X, Z, 4, int(cx)))
        back = smoothstep(-L * 0.75, -L * 0.25, v)
        h = h + ht * front * back * along
    # headland mound with cliffs on the seaward side
    (hx, hz), (rx, rz), hh = HEADLAND
    e = np.sqrt(((X - hx) / rx) ** 2 + ((Z - hz) / rz) ** 2)
    head = hh * (1 - smoothstep(0.55, 1.18, e)) + 2.0 * _noise2(X, Z, 7, 21) * (1 - smoothstep(0.7, 1.2, e))
    h = np.maximum(h, head + SEA_FLOOR * smoothstep(1.0, 1.5, e))
    # harbour arms: rocky ridges
    for pts, seed, top in ((WEST_ARM, 31, 4.2), (EAST_ARM, 37, 4.8)):
        da, s = poly_dist(X, Z, pts)
        width = 6.5 + 1.5 * _noise2(X, Z, 12, seed)
        crest = top * (0.75 + 0.25 * np.sin(s * 9.0 + seed)) * (1 - 0.45 * smoothstep(0.8, 1.0, s)) + 1.2 * _noise2(X, Z, 5, seed + 1)
        arm = crest * (1 - (da / width) ** 2) + (SEA_FLOOR - 0.5) * smoothstep(0.9, 1.6, da / width)
        arm = np.where(da < width, arm, SEA_FLOOR - 0.5 + 0 * da)
        # smooth max
        k = 2.0
        hk = np.clip(0.5 + 0.5 * (arm - h) / k, 0, 1)
        h = h * (1 - hk) + arm * hk + k * hk * (1 - hk)
    # rocky knolls / outcrops on the slopes
    rng = np.random.default_rng(7)
    knolls = []
    for _ in range(14):
        kx, kz = rng.uniform(-95, 95), rng.uniform(-95, -18)
        if -20 < kx < 30 and kz > -48:
            continue
        knolls.append((kx, kz, rng.uniform(3, 7), rng.uniform(1.0, 3.2)))
    knolls += [(-40, -8, 4, 1.6), (30, -12, 3.2, 1.4), (36, -2, 3.5, 1.8), (-36, -20, 4, 2.0), (44, -10, 5, 2.5), (-14, -46, 4, 1.8)]
    kn = np.zeros(X.shape)
    for kx, kz, r, ht in knolls:
        kn = np.maximum(kn, ht * np.exp(-(((X - kx) ** 2 + (Z - kz) ** 2) / (r * r)) ** 1.5))
    h = h + kn
    # general lumpiness (less on the beach, none on the street)
    amp = 0.35 * w_rock + 0.12 * w_beach + 0.3 * w_quay * smoothstep(9, 16, d)
    h = h + amp * _noise2(X, Z, 6, 41) + 0.5 * amp * _noise2(X, Z, 2.5, 42)
    # flatten the street, then building pads
    sm = smoothstep(-2.0, 0.0, -np.maximum.reduce([STREET[0] - X, X - STREET[1], STREET[2] - Z, Z - STREET[3]]))
    sm = sm * (d > -0.6)
    h = h * (1 - sm) + STREET_Y * sm
    pad_h = []
    for (px, pz, hxp, hzp, yaw, ph, fe) in PADS:
        a = math.radians(yaw)
        lx = (X - px) * math.cos(a) - (Z - pz) * math.sin(a)
        lz = (X - px) * math.sin(a) + (Z - pz) * math.cos(a)
        q = np.maximum(np.abs(lx) - hxp, np.abs(lz) - hzp)
        wgt = 1 - smoothstep(0, fe, q)
        if ph is None:
            inside = q < 0
            ph = float(np.median(h[inside])) if inside.any() else 0.0
        h = h * (1 - wgt) + ph * wgt
        pad_h.append(ph)
    # footpaths: a slope-limited profile along each path (max ~20 deg), blended in across the path width
    pmask = np.zeros(X.shape)
    hs_all = ndimage.gaussian_filter(h, 2.0)
    for pts, wdt in PATHS:
        dp, sp = poly_dist(X, Z, pts)
        L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        n = max(8, int(L / 0.5))
        ss = np.linspace(0, 1, n)
        acc = np.concatenate([[0], np.cumsum([math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)])]) / L
        px = np.interp(ss, acc, [p[0] for p in pts])
        pz = np.interp(ss, acc, [p[1] for p in pts])
        prof = ndimage.map_coordinates(hs_all, [(px - X0) / G, (pz - Z0) / G], order=1)
        prof = ndimage.gaussian_filter1d(prof, 3)
        ds = L / (n - 1)
        lim = math.tan(math.radians(19)) * ds
        for _ in range(3):
            for i in range(1, n):
                prof[i] = np.clip(prof[i], prof[i - 1] - lim, prof[i - 1] + lim)
            for i in range(n - 2, -1, -1):
                prof[i] = np.clip(prof[i], prof[i + 1] - lim, prof[i + 1] + lim)
        target = np.interp(sp, ss, prof)
        wgt = 1 - smoothstep(wdt * 0.9, wdt + 2.5, dp)
        h = h * (1 - wgt) + target * wgt
        pmask = np.maximum(pmask, 1 - smoothstep(wdt * 0.5, wdt * 1.15, dp + 0.25 * _noise2(X, Z, 1.5, 51)))
    # graded runs under the boardwalk ramps / stairs: the nearest run wins (chained runs share their end heights, so
    # the grade is continuous along a chain and one run's flat end-cap can't bleed over its neighbour)
    links = flight_links()
    if links:
        dmin = np.full(X.shape, 1e9)
        tgt = np.zeros(X.shape)
        for (a, b, wdt) in links:
            dp, tt = _seg_dist(X, Z, (a[0], a[2]), (b[0], b[2]))
            m = dp < dmin
            dmin = np.where(m, dp, dmin)
            tgt = np.where(m, a[1] + (b[1] - a[1]) * tt, tgt)
        wdt = links[0][2]
        wgt = 1 - smoothstep(wdt, wdt + 2.2, dmin)
        h = h * (1 - wgt) + tgt * wgt
        pmask = np.maximum(pmask, 1 - smoothstep(wdt * 0.7, wdt * 1.2, dmin + 0.25 * _noise2(X, Z, 1.5, 52)))
    h = np.maximum(h, SEA_FLOOR)
    # slope + region masks for the material
    gx, gz = np.gradient(h, G)
    slope = np.sqrt(gx * gx + gz * gz)
    lap = ndimage.laplace(ndimage.gaussian_filter(h, 2.0)) / (G * G)
    rockness = np.clip(smoothstep(0.55, 1.05, slope) + w_rock * smoothstep(0.5, -1.5, d) * (h < 3.8) + smoothstep(0.9, 2.2, kn + 0.8 * _noise2(X, Z, 2.5, 63)) * 0.95, 0, 1)
    # the arms and the headland are rock
    for pts in (WEST_ARM, EAST_ARM):
        da, _ = poly_dist(X, Z, pts)
        rockness = np.maximum(rockness, 1 - smoothstep(4.0, 7.0, da + 2 * _noise2(X, Z, 4, 61)))
    rockness = np.maximum(rockness, (1 - smoothstep(0.8, 1.05, e)) * smoothstep(0.35, 0.8, e + 0.3 * _noise2(X, Z, 5, 62)))
    rockness = np.clip(rockness * (1 - sm) * (1 - pmask * 0.85), 0, 1)
    sand = np.clip(w_beach * smoothstep(9.0, 2.0, h + 0.3 * _noise2(X, Z, 6, 71)) * (1 - rockness), 0, 1)
    _HM = dict(X=X, Z=Z, H=h, slope=slope, lap=lap, rock=rockness, sand=sand, path=pmask, street=sm, d=d, pad_h=pad_h, xs=xs, zs=zs)
    return _HM


def _interp(field, x, z):
    hm = heightmap()
    fx = (np.asarray(x) - X0) / G
    fz = (np.asarray(z) - Z0) / G
    return ndimage.map_coordinates(hm[field], [np.ravel(fx), np.ravel(fz)], order=1, mode="nearest").reshape(np.shape(x))


def height(x, z):
    """Ground height of the heightfield (without the small 3D rock lumps)."""
    return _interp("H", x, z)


# ----------------------------------------------------------------------------------------------------------------
# the clay


def rock_detail(P, w):
    """3D lumps + creases on rocky ground (positive = carve)."""
    if not np.any(w > 0.02):
        return np.zeros(len(P))
    out = np.zeros(len(P))
    m = w > 0.02
    Q = P[m]
    lump = fbm(Q / 2.6, 2, 81) * 0.55
    crease = (np.abs(vnoise(Q / np.array([1.6, 0.9, 1.6]), 82)) - 0.25) * 0.4
    facet = np.round(fbm(Q / 3.5, 2, 83) * 5.0) / 5.0 * 0.5
    out[m] = w[m] * (lump - crease + facet * 0.6)
    return out


class TerrainPiece(Piece):
    def __init__(self, model, name, lo, hi):
        super().__init__(model, name, color=TP["grass"], gloss=25, lumps=0.0, mottle=0.05, seed=1234, res=None, ao=False)
        self.lo, self.hi = np.asarray(lo, float), np.asarray(hi, float)
        self.ops = []

    def bounds(self):
        return self.lo, self.hi

    def _fields(self, P):
        x, z = P[:, 0], P[:, 2]
        H = _interp("H", x, z)
        sl = _interp("slope", x, z)
        rk = _interp("rock", x, z)
        return H, sl, rk

    def sdf(self, P):
        H, sl, rk = self._fields(P)
        base = (P[:, 1] - H) / np.sqrt(1 + sl * sl)
        near = np.abs(base) < 2.5
        if near.any():
            Q = P[near]
            det = rock_detail(Q, rk[near])
            # grass: soft thumb-pressed lumps and long tool strokes running down-slope
            gq = (1 - rk[near])
            det = det + gq * (0.06 * fbm(Q / 1.3, 2, 91))
            st = _interp("street", Q[:, 0], Q[:, 2])
            if np.any(st > 0.01):
                z = Q[:, 2]
                ruts = sum(np.exp(-((z - zc + 0.25 * np.sin(Q[:, 0] * 0.21 + zc)) / 0.22) ** 2) for zc in (-11.4, -13.0))
                det = det + st * (0.07 * ruts + 0.035 * fbm(Q / 0.9, 2, 92) - 0.04 * np.cos((z + 12.7) / 3.7 * np.pi / 2) ** 2)
            sd = _interp("sand", Q[:, 0], Q[:, 2])
            if np.any(sd > 0.01):
                det = det + sd * 0.025 * np.sin(Q[:, 0] * 2.2 + Q[:, 2] * 1.1 + 2 * fbm(Q / 3, 1, 93))
            base = base.copy()
            base[near] += det
        return base

    def attributes(self, P):
        hm = heightmap()
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        rk = _interp("rock", x, z)
        sd = _interp("sand", x, z)
        pa = _interp("path", x, z)
        st = _interp("street", x, z)
        lap = _interp("lap", x, z)
        n1 = fbm(P / 7.0, 2, 101)
        n2 = fbm(P / 2.2, 2, 102)
        n3 = fbm(P / 0.9, 2, 103)
        # grass: greens varying with lumps, drier on crests, lusher in hollows
        g_dry = rgb("#9a9a63")
        g_lush = rgb("#58703f")
        tdry = np.clip(0.45 + n1 * 1.5 - lap[:, None].ravel() * 0.6, 0, 1)[:, None]
        col = rgb(TP["grass"]) * (1 - tdry) + g_dry * tdry
        tl = np.clip(lap * 0.8 - 0.1 + n2 * 0.6, 0, 0.8)[:, None]
        col = col * (1 - tl) + g_lush * tl
        # tool-scored strokes as slightly darker lines (follow a slowly turning direction)
        ang = n1 * 3.0
        u = (x * np.cos(ang) + z * np.sin(ang)) / 0.9
        stroke = np.clip(np.cos(u * 2 * np.pi + n3 * 2.0), 0, 1) ** 4 * np.clip(n2 * 2 + 0.6, 0, 1)
        col = col * (1 - 0.12 * stroke[:, None])
        # little patches of sea-pinks / clover
        sp = fbm(P * 0.9, 2, 104)
        col = np.where((sp > 0.42)[:, None] & (rk < 0.3)[:, None] & (sd < 0.3)[:, None], mix(col, rgb("#c79aa4"), 0.45), col)
        # rock: grey clay with lichen
        rcol = rgb("#78766f") * (1 + 0.12 * n2[:, None]) + (rgb("#8f8b82") - rgb("#78766f")) * np.clip(n3, 0, 1)[:, None]
        rcol = rcol * (1 - 0.3 * smoothstep(0.1, 0.4, -n2))[:, None]
        lich = smoothstep(0.25, 0.35, fbm(P / 1.4, 2, 105))
        rcol = rcol * (1 - lich[:, None] * 0.55) + rgb("#b5874a")[None, :] * lich[:, None] * 0.55
        lich2 = smoothstep(0.3, 0.38, fbm(P / 0.8, 2, 106))
        rcol = rcol * (1 - lich2[:, None] * 0.6) + rgb("#b8b596")[None, :] * lich2[:, None] * 0.6
        wet = smoothstep(0.5, -0.1, y)[:, None]
        rcol = rcol * (1 - wet * 0.45) + rgb(TP["wood_wet"]) * wet * 0.45
        alg = (smoothstep(0.45, 0.15, y) * smoothstep(-0.9, -0.3, y))[:, None]
        rcol = rcol * (1 - alg * 0.8) + rgb("#56602f") * alg * 0.8
        bar = (smoothstep(0.7, 0.4, y) * smoothstep(-0.2, 0.2, y) * (vnoise(P * 4.0, 107) > 0.35))[:, None]
        rcol = rcol * (1 - bar * 0.6) + rgb(TP["barnacle"]) * bar * 0.6
        # sand: dry beige, wet & darker near the water, a wrack line of dark weed, pebbles
        scol = rgb("#c9ad85") * (1 + 0.05 * n1[:, None]) + (rgb("#b89c76") - rgb("#c9ad85")) * np.clip(n2 + 0.2, 0, 1)[:, None]
        sw = smoothstep(0.75, 0.15, y)[:, None]
        scol = scol * (1 - sw * 0.4) + rgb("#7d6e58") * sw * 0.4
        wr = (smoothstep(0.85, 1.0, y) * smoothstep(1.3, 1.12, y) * smoothstep(-0.2, 0.1, n2))[:, None]
        scol = scol * (1 - wr * 0.65) + rgb("#55503a") * wr * 0.65
        peb = (smoothstep(0.3, 0.45, fbm(P * 0.7, 2, 108)) * smoothstep(1.4, 0.4, y))[:, None]
        scol = scol * (1 - peb * 0.55) + rgb("#8f8a80") * peb * 0.55
        # paths: trodden earth & gravel; the street: packed grey-brown gravel with cart ruts
        pcol = rgb("#8f7b5e") * (1 + 0.1 * n2[:, None])
        pcol = np.where((vnoise(P * 4.5, 109) > 0.5)[:, None], rgb("#a39a88"), pcol)
        stc = rgb("#8a7f6a") * (1 + 0.08 * n2[:, None]) + (rgb("#a09685") - rgb("#8a7f6a")) * np.clip(n1 * 2, 0, 1)[:, None]
        rutc = sum(np.exp(-((z - zc + 0.25 * np.sin(x * 0.21 + zc)) / 0.3) ** 2) for zc in (-11.4, -13.0))
        stc = stc * (1 - 0.25 * rutc[:, None]) + rgb("#5f5545") * 0.25 * rutc[:, None]
        verge = smoothstep(-15.2, -16.4, z)[:, None]
        stc = stc * (1 - verge) + rgb(TP["grass_dk"]) * verge
        pud = (smoothstep(0.38, 0.45, fbm(P * 0.45, 2, 111)) * (1 - verge[:, 0]))
        # blend
        w_s = np.clip(sd, 0, 1)[:, None]
        col = col * (1 - w_s) + scol * w_s
        w_r = np.clip(rk * 1.2, 0, 1)[:, None]
        col = col * (1 - w_r) + rcol * w_r
        w_p = np.clip(pa, 0, 1)[:, None] * (1 - w_r * 0.5)
        col = col * (1 - w_p) + pcol * w_p
        w_st = np.clip(st, 0, 1)[:, None]
        col = col * (1 - w_st) + stc * w_st
        # under water: dark seabed (never seen through the opaque sea, keep it calm)
        uw = smoothstep(-0.6, -1.4, y)[:, None]
        col = col * (1 - uw) + rgb("#3d4840") * uw
        # cavity darkening for depth
        col = col * (1 - np.clip(lap * 0.25, -0.1, 0.25))[:, None]
        gloss = 25 + 120 * (smoothstep(0.5, 0.0, y) * (smoothstep(-1.0, -0.2, y))) + 20 * rk
        # puddles on the street: dark and wet
        col = col * (1 - (pud * st)[:, None] * 0.45) + rgb("#4c4a44") * (pud * st)[:, None] * 0.45
        gloss = gloss + 180 * pud * st
        return np.clip(col, 0, 1), gloss, {}


class TerrainModel(Model):
    def __init__(self, name, x0, z0, res, budget):
        super().__init__(name, res=res)
        self.x0, self.z0, self.budget = x0, z0, budget
        self.decimate_min = 10 ** 9
        hm = heightmap()
        sel = (hm["X"] >= x0 - 1) & (hm["X"] <= x0 + TILE + 1) & (hm["Z"] >= z0 - 1) & (hm["Z"] <= z0 + TILE + 1)
        self.ymax = float(hm["H"][sel].max()) + 2.5
        self.ymin = SEA_FLOOR - 0.3
        p = TerrainPiece(self, "ground", (x0, self.ymin, z0), (x0 + TILE, self.ymax, z0 + TILE))
        self.pieces.append(p)

    def _mesh_piece(self, p):
        from skimage.measure import marching_cubes
        import pyfqmr
        from clay import project
        h = self.res
        n = int(round(TILE / h))
        xs = self.x0 + np.arange(n + 1) * h
        zs = self.z0 + np.arange(n + 1) * h
        ys = self.ymin + np.arange(int(np.ceil((self.ymax - self.ymin) / h)) + 1) * h
        vol = np.empty((len(xs), len(ys), len(zs)), np.float32)
        Y, Zg = np.meshgrid(ys, zs, indexing="ij")
        for i, x in enumerate(xs):
            P = np.column_stack([np.full(Y.size, x), Y.ravel(), Zg.ravel()])
            vol[i] = p.sdf(P).reshape(len(ys), len(zs))
        # close the bottom so the slab is solid (flat floor below the seabed)
        vol[:, 0, :] = np.maximum(vol[:, 0, :], 0.01)
        verts, faces, _, _ = marching_cubes(vol, level=0.0, spacing=(h, h, h))
        verts = verts + np.array([xs[0], ys[0], zs[0]])
        # drop the flat floor faces (never visible) to save tris
        keep = ~(verts[faces][:, :, 1].max(axis=1) < self.ymin + h * 0.6)
        faces = faces[keep]
        used = np.unique(faces)
        remap = -np.ones(len(verts), np.int64)
        remap[used] = np.arange(len(used))
        verts, faces = verts[used], remap[faces]
        raw = len(faces)
        if raw > self.budget:
            s = pyfqmr.Simplify()
            s.setMesh(verts.astype(np.float64), faces.astype(np.int32))
            s.simplify_mesh(target_count=int(self.budget), aggressiveness=5, preserve_border=True, verbose=False)
            verts, faces, _ = s.getMesh()
            # keep border vertices exactly on the tile edges; pull the rest onto the surface
            border = (np.abs(verts[:, 0] - xs[0]) < 1e-4) | (np.abs(verts[:, 0] - xs[-1]) < 1e-4) | (np.abs(verts[:, 2] - zs[0]) < 1e-4) | (np.abs(verts[:, 2] - zs[-1]) < 1e-4)
            pv = project(p, verts, 2)
            verts = np.where(border[:, None], verts, pv)
        print(f"[terrain] {self.name}: raw {raw} -> {len(faces)} tris")
        return verts, faces


def tile_budget(i, j):
    cx, cz = TX0 + (i + 0.5) * TILE, TZ0 + (j + 0.5) * TILE
    dist = math.hypot(cx - 5, cz + 5)
    # one grid step for every tile so neighbours share their border vertices exactly (no T-junction cracks)
    if dist < 35:
        return 42000, 0.25
    if dist < 75:
        return 26000, 0.25
    return 13000, 0.25


def tile_exists(i, j):
    hm = heightmap()
    x0, z0 = TX0 + i * TILE, TZ0 + j * TILE
    sel = (hm["X"] >= x0) & (hm["X"] <= x0 + TILE) & (hm["Z"] >= z0) & (hm["Z"] <= z0 + TILE)
    return bool(hm["H"][sel].max() > -1.0)


def make_tile(i, j):
    def fn():
        budget, res = tile_budget(i, j)
        m = TerrainModel(f"tile_{i}_{j}", TX0 + i * TILE, TZ0 + j * TILE, res, budget)
        return m
    return fn


MODELS = {}
for _i in range(NTX):
    for _j in range(NTZ):
        if tile_exists(_i, _j):
            MODELS[f"terrain/tile_{_i}_{_j}"] = make_tile(_i, _j)
