"""
The Sally Mae — Gran's old crab boat (Docs/DESIGN.md §3, §5.4). ~9 m long, ~3.2 m beam, bow toward +Z, waterline at
y = 0 (hull ~0.9 m below). Chunky red hull with a cream sheer stripe, rubbing strakes, tyre fenders, rust streaks and
a green algae waterline; flat plank working deck forward (y = 1.0) inside low bulwarks; white wheelhouse aft of
midships; mast with a slewing hydraulic crane boom (bone `boom`) and a pot-hauling winch drum (bone `winch`).
"""
import numpy as np
from scipy.interpolate import PchipInterpolator

from clay import *
from kit_catch import *

# --------------------------------------------------------------------------------------------------------------
# hull lines (tables over z)

ZS = np.linspace(-5.2, 5.4, 1600)


def _tab(zc, vc):
    zc, vc = np.asarray(zc, float), np.asarray(vc, float)
    return PchipInterpolator(zc, vc)(np.clip(ZS, zc[0], zc[-1]))


SHEER = _tab([-4.5, -3.0, -1.0, 1.0, 2.5, 3.6, 4.7], [1.42, 1.37, 1.35, 1.39, 1.52, 1.74, 1.98])
KEEL = _tab([-4.5, -4.0, -3.0, 0.0, 2.0, 3.0, 3.8, 4.4, 4.9], [-0.40, -0.62, -0.84, -0.92, -0.90, -0.74, -0.38, 0.25, 0.9])
HALF = _tab([-4.5, -3.2, -1.2, 0.6, 1.8, 2.8, 3.6, 4.2, 4.62, 4.9], [1.36, 1.54, 1.6, 1.6, 1.5, 1.27, 0.87, 0.43, 0.03, -0.3])
DECK = 1.0      # walkable deck height above the waterline
BT = 0.12       # bulwark thickness
ZT = -4.42      # transom (at the keel; raked aft toward the top)

RED, RED_DK, CREAM, BOTTOM, ALGAE = "#b8352c", "#8e2620", "#efe3c4", "#5b2828", "#4d6630"
WHITE, TRIM, ROOF = "#ece5d2", "#2f5b66", "#33605d"
CRANE, STEEL, RUBBER = "#e0a32e", "#8e9598", "#2d2c2e"
DECKWOOD = "#a77c50"


def _n(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def hz(z, tab):
    return np.interp(z, ZS, tab)


def norm_h(y, z):
    ys, yk = hz(z, SHEER), hz(z, KEEL)
    return (y - yk) / (ys - yk)


def half_w(y, z):
    """Half-beam of the hull at height y, station z (round bilge, raked stem, full stern)."""
    t = norm_h(y, z)
    tc = np.clip(t, 0, 1)
    zeff = z + ss(1.0, 3.6, z) * 0.95 * (1 - tc) ** 1.5
    hb = hz(zeff, HALF)
    u = np.clip(t / 0.62, 0, 1)
    rnd = np.sqrt(1 - (1 - u) ** 2)
    full = 0.2 + 0.3 * ss(-1.5, -4.4, z)
    f = full + (1 - full) * rnd + 0.05 * np.clip((t - 0.62) / 0.4, 0, 1.4)
    return hb * f


def transom_z(y, z):
    return ZT - 0.16 * np.clip(norm_h(y, z), 0, 1.2)


def _side_d(x, y, z, inset=0.0):
    e = 0.02
    w = half_w(y, z) - inset
    wy = (half_w(y + e, z) - half_w(y - e, z)) / (2 * e)
    wz = (half_w(y, z + e) - half_w(y, z - e)) / (2 * e)
    return (np.abs(x) - w) / np.sqrt(1 + wy * wy + wz * wz)


def hull_sdf(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ds = _side_d(x, y, z)
    db = (hz(z, KEEL) - y) * 0.85
    dt = y - hz(z, SHEER)
    dst = transom_z(y, z) - z
    d = smax(ds, db, 0.35)
    d = smax(d, dst, 0.1)
    d = smax(d, dt, 0.05)
    return d


def well_sdf(P):
    """The open deck well inside the bulwarks (subtracted from the hull)."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ds = _side_d(x, y, z, BT)
    dd = (DECK - 0.03) - y
    dst = (transom_z(y, z) + BT) - z
    return np.maximum(np.maximum(ds, dd), dst)


def deck_sdf(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ds = _side_d(x, np.full_like(y, DECK), z, BT - 0.025)
    dy = np.abs(y - (DECK - 0.05)) - 0.05
    dst = (transom_z(np.full_like(y, DECK), z) + BT - 0.025) - z
    return smax(smax(ds, dy, 0.015), dst, 0.015)


def side_pt(y, z, sx, out=0.0):
    """Point on the outside of the hull at height y, station z, side sx (+1 starboard / -1 port)."""
    return np.array([sx * (float(half_w(np.array([y]), np.array([z]))[0]) + out), y, z])


def sheer_y(z):
    return float(hz(z, SHEER))


def inner_x(z, y=DECK):
    return float(half_w(np.array([y]), np.array([z]))[0]) - BT


def ring_prim(c, half, rot, border, depth, round_in=0.08):
    """A rounded-rectangle frame (window trim): outer box minus inner box, `depth` thick along local z."""
    c = np.asarray(c, float)
    hx, hy = half
    outer = Box(c, (hx + border, hy + border, depth), rot=rot, round=min(round_in + border, depth * 0.9 + border))
    inner = Box(c, (hx, hy, depth * 3), rot=rot, round=round_in)
    lo, hi = outer.bounds()
    return Func(lambda P: np.maximum(outer(P), -inner(P)), lo, hi)


def streaks_prim(specs, seed=3):
    """Rust/grime streaks running down the hull side. specs: (z, side, y_top, length, width)."""
    def f(P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        d = np.full(len(P), 1.0)
        n = fbm(P * np.array([6.0, 1.5, 6.0]), 2, seed)
        for zc, sx, yt, ln, wd in specs:
            frac = np.clip((y - (yt - ln)) / ln, 0, 1)
            wob = 0.025 * np.sin(y * 7.0 + zc * 3) + 0.015 * n
            g = np.abs(z - zc - wob) - wd * (0.25 + 0.75 * frac) * (0.8 + 0.4 * n)
            g = np.maximum(g, y - yt)
            g = np.maximum(g, (yt - ln * (0.75 + 0.25 * n)) - y)
            g = np.maximum(g, 0.3 - sx * x)
            d = np.minimum(d, g)
        return d
    return Func(f, (-9, -9, -9), (9, 9, 9))


def cyl_between(a, b, r, round=0.0):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    L = np.linalg.norm(d)
    return Cylinder((a + b) / 2, r, L / 2, rot=look_rot(d), round=round)


def box_between(a, b, hw, hd, round=0.02, up=(0, 1, 0)):
    """Box from a to b with half-width hw (local x) and half-depth hd (local z)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    L = np.linalg.norm(d)
    return Box((a + b) / 2, (hw, L / 2, hd), rot=look_rot(d, up), round=round)


# --------------------------------------------------------------------------------------------------------------


def build():
    m = Model("sally_mae", res=0.03)
    m.decimate_min = 1500
    m.bone("root")
    MAST = np.array([0.0, DECK, -0.45])
    PIVOT = np.array([0.0, 2.32, -0.45])
    WINCH = np.array([0.72, 1.4, -0.33])
    m.bone("boom", "root", PIVOT)
    m.bone("winch", "root", WINCH)

    # ---------------------------------------------------------------------------------------------- hull
    hull = m.piece("hull_body", color=RED, gloss=95, res=0.04, lumps=0.012, lump_freq=2.2, dents=40, dent_size=0.14,
                   dent_depth=0.014, mottle=0.07, decimate=18000, merge="hull")
    hull.add(Func(hull_sdf, (-1.75, -1.0, -4.65), (1.75, 2.1, 4.75)))
    # keel, skeg and rudder
    hull.add(Box((0, -0.97, -0.7), (0.07, 0.12, 3.0), round=0.05), k=0.12)
    hull.add(Box((0, -0.45, -4.5), (0.05, 0.42, 0.2), round=0.04), k=0.04, color=BOTTOM)
    hull.add(Cylinder((0, -0.62, -4.18), 0.09, 0.12, rot=(90, 0, 0), round=0.03), k=0.05, color="#a37a3a", gloss=150)
    hull.sub(Func(well_sdf, (-1.7, 0.9, -4.6), (1.7, 2.2, 4.7)), k=0.07)
    # chunky cap rail along the bulwark tops + across the transom
    for sx in (1, -1):
        zs = np.linspace(-4.5, 4.62, 26)
        pts = [np.array([sx * (inner_x(z, sheer_y(z)) + BT * 0.5), sheer_y(z) + 0.025, z]) for z in zs]
        pts[0][2] = float(transom_z(np.array([pts[0][1]]), np.array([-4.5]))[0]) + 0.05
        pts[-1] = np.array([0.0, sheer_y(4.62) + 0.02, 4.62])
        hull.add(Tube(pts, 0.085, samples=3), k=0.03, color=CREAM, gloss=110)
    zt_top = float(transom_z(np.array([1.42]), np.array([-4.5]))[0])
    hull.add(Capsule((-1.32, 1.445, zt_top + 0.06), (1.32, 1.445, zt_top + 0.06), 0.085), k=0.03, color=CREAM, gloss=110)
    # rubbing strakes: an upper one following the sheer, a lower one at the turn of the hull
    stk = m.piece("strakes", color="#4a3426", gloss=80, res=0.02, lumps=0.004, lump_freq=4, dents=30, dent_size=0.06,
                  dent_depth=0.006, mottle=0.08, decimate=2600, merge="hull")
    for sx in (1, -1):
        up = [side_pt(sheer_y(z) - 0.44, z, sx, -0.01) for z in np.linspace(-4.42, 4.2, 22)]
        stk.add(Tube(up, 0.06, samples=3), k=0.02)
        lo = [side_pt(0.48, z, sx, -0.01) for z in np.linspace(-4.38, 3.5, 18)]
        stk.add(Tube(lo, 0.05, samples=3), k=0.02)
    grime(stk, "#2a1d15", r=0.03, thresh=0.1, noise=0.06, feather=0.12)
    # scuppers (deck drains) through the bulwarks, hawse pipes at the bow
    scup_z = [-3.9, -3.25, -0.1, 0.7, 1.5, 2.3]
    for sx in (1, -1):
        for z in scup_z:
            x = sx * (inner_x(z) + BT * 0.5)
            hull.sub(Box((x, DECK + 0.04, z), (0.14, 0.035, 0.1), round=0.025), k=0.02)
        hp = side_pt(1.52, 4.0, sx, -0.02)
        hull.sub(Cylinder(hp, 0.075, 0.12, rot=look_rot((sx, 0, 0.35))), k=0.02)
        hull.add(Torus(hp + np.array([sx * 0.02, 0, 0]), 0.09, 0.028, rot=look_rot((sx, 0, 0.35))), k=0.015, color=STEEL, gloss=140)
    # thumbed plank seams on the hull sides (shallow scored lines) — every ~0.3 m above the waterline
    for sx in (1, -1):
        for y in (0.22, 0.78, 1.0):
            pts = [side_pt(y, z, sx, 0.0) for z in np.linspace(-4.3, 3.2 if y < 0.5 else 3.7, 16)]
            score(hull, pts, 0.016, k=0.012, samples=3)
    # --- paint: algae waterline, bottom paint, cream sheer stripe, white inner bulwarks, rust streaks
    ys_f = lambda P: hz(P[:, 2], SHEER)
    outer = lambda P: (half_w(P[:, 1], P[:, 2]) - 0.05) - np.abs(P[:, 0])
    hull.paint(func_prim(lambda P: P[:, 1] - (-0.06 + 0.04 * fbm(P * 3.0, 2, 4))), BOTTOM, gloss=35, feather=0.03)
    alg = lambda P: np.abs(P[:, 1] - 0.02) - (0.07 + 0.05 * fbm(P * np.array([4, 1, 4]), 3, 8))
    hull.paint(func_prim(alg), ALGAE, gloss=150, feather=0.03)
    drips = lambda P: np.maximum(P[:, 1] - (0.12 + 0.22 * np.clip(fbm(P * np.array([9, 0.6, 9]), 2, 11) * 2.2, 0, 1)), -0.02 - P[:, 1])
    hull.paint(func_prim(drips), shade(ALGAE, 0.9), gloss=140, feather=0.025)
    stripe = lambda P: np.maximum(np.maximum((ys_f(P) - 0.33) - P[:, 1], P[:, 1] - (ys_f(P) - 0.19)), outer(P))
    rng = np.random.default_rng(12)
    specs = []
    for sx in (1, -1):
        for z in scup_z:
            specs.append((z + rng.uniform(-0.03, 0.03), sx, DECK + 0.02, rng.uniform(0.45, 0.85), 0.05))
        specs.append((4.0, sx, 1.47, 0.85, 0.06))
        for z in rng.uniform(-4.0, 3.0, 4):
            specs.append((z, sx, sheer_y(z) - 0.47, rng.uniform(0.25, 0.55), 0.035))
    hull.paint(streaks_prim(specs), "#a2602e", gloss=60, feather=0.03)
    hull.paint(streaks_prim([(z + 0.04, sx, yt - 0.05, ln * 0.6, w * 0.5) for z, sx, yt, ln, w in specs], seed=5), "#6e3a1c", gloss=50, feather=0.02)
    grime(hull, "#6b4632", r=0.06, thresh=0.1, noise=0.06, feather=0.12)

    # a strip of cream clay pressed along the sheer (crisp edges: its own mesh), and a white lining on the bulwarks
    def stripe_sdf(P):
        h = hull_sdf(P)
        yc = hz(P[:, 2], SHEER) - 0.2
        band = np.abs(P[:, 1] - yc) - 0.07
        return np.maximum(np.maximum(h - 0.016, -(h + 0.03)), np.maximum(band, transom_z(P[:, 1], P[:, 2]) + 0.02 - P[:, 2]))
    strip = m.piece("stripe", color=CREAM, gloss=110, res=0.022, lumps=0.004, lump_freq=3, dents=20, dent_size=0.08,
                    dent_depth=0.006, mottle=0.05, decimate=3200, merge="hull")
    strip.add(Func(stripe_sdf, (-1.75, 0.8, -4.7), (1.75, 2.0, 4.75)))
    for sx in (1, -1):
        hp = side_pt(1.52, 4.0, sx, -0.02)
        strip.sub(Cylinder(hp, 0.1, 0.2, rot=look_rot((sx, 0, 0.35))), k=0.02)
    grime(strip, "#b49f80", r=0.03, thresh=0.1, noise=0.06, feather=0.12)

    def algae_sdf(P):
        h = hull_sdf(P)
        y, z = P[:, 1], P[:, 2]
        n = fbm(P * np.array([5.0, 1.0, 5.0]), 3, 21)
        drip = 0.18 * np.clip(fbm(P * np.array([5.0, 0.3, 5.0]), 2, 23) * 2.6 - 0.8, 0, 1)
        top = 0.07 + 0.05 * n + drip
        band = np.maximum(-0.14 - y, y - top)
        return np.maximum(np.maximum(h - 0.014 - 0.006 * n, -(h + 0.03)), band)
    alg = m.piece("algae", color=ALGAE, gloss=160, res=0.022, lumps=0.006, lump_freq=5, dents=30, dent_size=0.06,
                  dent_depth=0.006, mottle=0.12, decimate=3600, merge="hull")
    alg.add(Func(algae_sdf, (-1.8, -0.2, -4.75), (1.8, 0.45, 4.6)))
    alg.paint(blotch_prim(3.0, 0.15, seed=31), "#3f5a22", gloss=170, feather=0.4)
    alg.paint(blotch_prim(6.0, 0.4, seed=32), "#6c7a36", gloss=140, feather=0.4)

    def lining_sdf(P):
        w = well_sdf(P)
        top = P[:, 1] - (hz(P[:, 2], SHEER) - 0.02)
        return np.maximum(np.maximum(w - 0.014, -(w + 0.03)), np.maximum(DECK - 0.005 - P[:, 1], top))
    lin = m.piece("lining", color="#e8dec4", gloss=80, res=0.024, lumps=0.004, lump_freq=3, dents=24, dent_size=0.08,
                  dent_depth=0.006, mottle=0.05, decimate=4200, merge="hull")
    lin.add(Func(lining_sdf, (-1.7, 0.95, -4.65), (1.7, 2.05, 4.7)))
    for sx in (1, -1):
        for z in scup_z:
            lin.sub(Box((sx * (inner_x(z) + BT * 0.5), DECK + 0.04, z), (0.16, 0.035, 0.1), round=0.025), k=0.02)
    grime(lin, "#a8977a", r=0.03, thresh=0.1, noise=0.06, feather=0.12)

    # ---------------------------------------------------------------------------------------------- deck planks
    deck = m.piece("deck", color=DECKWOOD, gloss=30, res=0.022, lumps=0.006, lump_freq=3.0, dents=25, dent_size=0.1,
                   dent_depth=0.006, mottle=0.08, decimate=8000)
    deck.add(Func(deck_sdf, (-1.7, DECK - 0.12, -4.6), (1.7, DECK + 0.02, 4.4)))
    pw = 0.19
    for i in range(-8, 9):
        x = i * pw + pw * 0.5
        deck.sub(Capsule((x, DECK + 0.014, -4.6), (x, DECK + 0.014, 4.5), 0.019), k=0.008)
        deck.paint(Capsule((x, DECK, -4.6), (x, DECK, 4.5), 0.016), "#4e3420", feather=0.008)
        # per-plank tint and staggered butt joints
        deck.paint(Box((x - pw * 0.5, DECK, 0), (pw * 0.42, 0.08, 5), round=0.0), shade(DECKWOOD, 0.9 + 0.18 * rng.random()), feather=0.01)
        for zb in np.arange(-4.0 + (i % 3) * 0.9, 4.2, 2.7):
            deck.sub(Capsule((x - pw + 0.02, DECK + 0.012, zb), (x - 0.02, DECK + 0.012, zb), 0.014), k=0.006)
    grime(deck, "#5d4128", r=0.05, thresh=0.1, noise=0.06, feather=0.12)

    # ---------------------------------------------------------------------------------------------- wheelhouse
    WZ0, WZ1 = -2.75, -0.78
    WC = (WZ0 + WZ1) / 2
    WH = 1.1
    wh = m.piece("wheelhouse", color=WHITE, gloss=70, res=0.024, lumps=0.007, lump_freq=2.5, dents=24, dent_size=0.1,
                 dent_depth=0.008, mottle=0.05, decimate=11000)
    wh.add(Box((0, 1.93, WC), (WH, 0.95, (WZ1 - WZ0) / 2), round=0.16))
    wh.sub(Box((0, 2.05, WC), (WH - 0.1, 1.08, (WZ1 - WZ0) / 2 - 0.1), round=0.07), k=0.03)
    fwin = [(-0.62, 0.25), (0.0, 0.27), (0.62, 0.25)]
    for x, hx in fwin:
        wh.sub(Box((x, 2.25, WZ1), (hx, 0.34, 0.2), round=0.11), k=0.02)
        wh.add(ring_prim((x, 2.25, WZ1 + 0.01), (hx, 0.34), None, 0.055, 0.035, round_in=0.11), k=0.015, color=TRIM, gloss=110)
    swin = [-1.25, -2.05]
    for sx in (1, -1):
        for z in swin:
            wh.sub(Box((sx * WH, 2.24, z), (0.2, 0.27, 0.27), round=0.1), k=0.02)
            wh.add(ring_prim((sx * (WH + 0.01), 2.24, z), (0.27, 0.27), (0, 90, 0), 0.055, 0.035), k=0.015, color=TRIM, gloss=110)
    # aft: an open doorway (starboard) and a small window (port)
    wh.sub(Box((0.38, 1.75, WZ0), (0.34, 0.78, 0.2), round=0.12), k=0.02)
    wh.add(ring_prim((0.38, 1.75, WZ0 - 0.01), (0.34, 0.78), None, 0.05, 0.03, round_in=0.12), k=0.012, color=TRIM, gloss=110)
    wh.sub(Box((-0.55, 2.24, WZ0), (0.22, 0.22, 0.2), round=0.1), k=0.02)
    wh.add(ring_prim((-0.55, 2.24, WZ0 - 0.01), (0.22, 0.22), None, 0.05, 0.03), k=0.012, color=TRIM, gloss=110)
    # kick band and a pin stripe
    wh.paint(Box((0, 1.04, WC), (WH + 0.2, 0.09, 1.2)), TRIM, gloss=110, feather=0.01)
    wh.paint(Box((0, 1.62, WC), (WH + 0.2, 0.022, 1.2)), TRIM, gloss=110, feather=0.006)
    grime(wh, "#b8ad94", r=0.04, thresh=0.16, noise=0.05, feather=0.1)
    # rust weeping from the window corners
    wh.paint(streaks_prim([(-1.25 + 0.2, 1, 1.95, 0.35, 0.02), (-2.05 - 0.22, -1, 1.95, 0.45, 0.02)], seed=8), "#a27450", feather=0.02)

    # roof with a visor over the front windows
    roof = m.piece("roof", color=ROOF, gloss=55, res=0.024, lumps=0.006, lump_freq=2.5, dents=10, dent_size=0.12,
                   dent_depth=0.008, decimate=2600, merge="fittings")
    roof.add(Box((0, 2.92, WC), (WH + 0.14, 0.075, (WZ1 - WZ0) / 2 + 0.16), round=0.07))
    roof.add(Ellipsoid((0, 2.95, WC), (WH + 0.05, 0.1, (WZ1 - WZ0) / 2 + 0.05)), k=0.05)
    roof.add(Box((0, 2.84, WZ1 + 0.25), (WH + 0.16, 0.04, 0.2), rot=(-16, 0, 0), round=0.035), k=0.04)
    grime(roof, shade(ROOF, 0.7), r=0.04, thresh=0.1, noise=0.06, feather=0.12)

    # ---------------------------------------------------------------------------------------------- glass (emissive)
    glass = m.piece("glass_panes", color="#a9cbd0", gloss=255, res=0.018, lumps=0.002, mottle=0.03, mat=1, merge="glass", ao=False,
                    decimate=900)
    for x, hx in fwin:
        glass.add(Box((x, 2.25, WZ1 - 0.04), (hx + 0.02, 0.36, 0.018), round=0.016))
    for sx in (1, -1):
        for z in swin:
            glass.add(Box((sx * (WH - 0.04), 2.24, z), (0.018, 0.29, 0.29), round=0.016))
    glass.add(Box((-0.55, 2.24, WZ0 + 0.04), (0.24, 0.24, 0.018), round=0.016))
    # bow portholes (fo'c'sle cabin lights)
    port_pts = []
    for sx in (1, -1):
        for z in (2.55, 3.15):
            p = side_pt(1.12, z, sx, -0.01)
            n = np.array([sx, 0, 0.25 * (z - 2.0)])
            port_pts.append((p, n))
            hull.sub(Cylinder(p, 0.1, 0.1, rot=look_rot(n)), k=0.01)
            glass.add(Cylinder(p - _n(n) * 0.03, 0.105, 0.03, rot=look_rot(n), round=0.01))

    # ---------------------------------------------------------------------------------------------- fittings
    fit = lambda name, **kw: m.piece(name, merge="fittings", **{**dict(res=0.016, lumps=0.003, lump_freq=6, mottle=0.06), **kw})

    # porthole brass rims
    rims = fit("port_rims", color=CP["brass"], gloss=170, decimate=900)
    for p, n in port_pts:
        rims.add(Torus(p + _n(n) * 0.015, 0.12, 0.03, rot=look_rot(n)))
        for a in range(0, 360, 90):
            pass
    metal(rims, CP["brass_dk"], CP["brass_lt"], r=0.02)

    # interior: console + spoked ship's wheel at the helm
    inside = fit("helm", color=CP["wood"], gloss=80, decimate=1600)
    inside.add(Box((0.32, 1.42, WZ1 - 0.22), (0.55, 0.42, 0.12), round=0.04), color="#6c4a2c")
    inside.add(Box((0.32, 1.9, WZ1 - 0.28), (0.5, 0.06, 0.16), rot=(-25, 0, 0), round=0.03), k=0.03, color="#3c3a38")
    wc = np.array([0.32, 1.72, WZ1 - 0.47])
    inside.add(Torus(wc, 0.24, 0.028, rot=(90, 0, 0)))
    inside.add(Cylinder(wc, 0.055, 0.06, rot=(90, 0, 0), round=0.02), k=0.01, color=CP["brass"])
    for a in range(0, 360, 45):
        r = np.radians(a)
        d = np.array([np.cos(r), np.sin(r), 0])
        inside.add(Capsule(wc, wc + d * 0.33, 0.017, 0.022), k=0.01)
    inside.add(Capsule(wc + (0, 0, 0.02), wc + (0, 0, 0.27), 0.03), k=0.01, color=CP["brass"])

    # smokestack (tilted aft a touch), black sooty top, red band
    st = fit("stack", color=CREAM, gloss=80, res=0.016, decimate=1500)
    sc0 = np.array([0.6, 2.95, -2.32])
    sc1 = np.array([0.6, 3.72, -2.42])
    st.add(Capsule(sc0, sc1, 0.17, 0.15))
    st.add(Torus(sc1 - (0, 0.01, 0), 0.15, 0.035), k=0.02)
    st.sub(Cylinder(sc1 + (0, 0.05, 0), 0.11, 0.12), k=0.02, color="#141414")
    st.paint(Box((0.6, 3.38, -2.37), (0.3, 0.07, 0.3)), "#b8352c", gloss=110, feather=0.01)
    st.paint(Box((0.6, 3.66, -2.4), (0.3, 0.1, 0.3)), "#1d1c1c", gloss=40, feather=0.04)
    st.add(Ellipsoid(sc0 + (0, 0.02, 0), (0.25, 0.06, 0.25)), k=0.04, color=ROOF)

    # radar dome on a stubby pedestal, whip antenna, searchlight
    rd = fit("radar", color="#f0ebe0", gloss=120, decimate=1300)
    rc = np.array([-0.45, 3.02, -1.35])
    rd.add(Cylinder(rc + (0, 0.1, 0), 0.07, 0.12, round=0.02), color=STEEL)
    rd.add(Cylinder(rc + (0, 0.27, 0), 0.34, 0.07, round=0.05), k=0.02)
    rd.add(Ellipsoid(rc + (0, 0.34, 0), (0.33, 0.15, 0.33)), k=0.06)
    rd.paint(Box(rc + (0, 0.23, 0), (0.4, 0.02, 0.4)), "#2f5b66", feather=0.01)
    rd.add(Capsule((-0.95, 2.98, -2.5), (-0.97, 4.05, -2.55), 0.02, 0.012), color=STEEL)
    rd.add(Sphere((-0.97, 4.06, -2.55), 0.035), k=0.01, color="#c23a2e")
    rd.add(Cylinder((0.55, 3.07, -0.98), 0.05, 0.07), color=STEEL)
    rd.add(Cylinder((0.55, 3.2, -0.95), 0.11, 0.1, rot=(80, 0, 0), round=0.03), k=0.02, color="#d8d0bd")

    # two spare pot buoys lashed on the roof (crabber look)
    bu = fit("roof_buoys", color="#e8642a", gloss=130, decimate=1100)
    for i, (bx, bz, r) in enumerate([(0.02, -2.4, 0.2), (-0.32, -2.2, 0.17)]):
        c = np.array([bx, 3.0 + r * 0.95, bz])
        bu.add(Sphere(c, r))
        bu.paint(Box(c, (r * 1.2, r * 0.18, r * 1.2)), "#efe6d6", feather=0.01)
        bu.add(Torus(c + (0, r * 1.0, 0), 0.04, 0.014), k=0.01, color="#2d2c2e")

    # mast, crosstree, pennant
    ms = fit("mast", color=CRANE, gloss=120, res=0.016, decimate=1800)
    ms.add(Cylinder(MAST + (0, 0.04, 0), 0.2, 0.04, round=0.02), color=STEEL)
    ms.add(Capsule(MAST, MAST + (0, 3.45, 0), 0.09, 0.075), k=0.04)
    ms.add(Capsule(MAST + (-0.66, 2.62, 0.02), MAST + (0.66, 2.62, 0.02), 0.045), k=0.03)
    ms.add(Sphere(MAST + (0, 3.48, 0), 0.09), k=0.02, color="#efe6d6")
    for sx in (1, -1):
        ms.add(Capsule(MAST + (0, 2.3, 0), MAST + (sx * 0.62, 2.6, 0.02), 0.025), k=0.02)
    ms.paint(Box(MAST + (0, 0.45, 0), (0.2, 0.2, 0.2)), "#2a2a2a", feather=0.01)
    for y in (0.3, 0.6):
        ms.paint(Box(MAST + (0, y, 0), (0.2, 0.05, 0.2), rot=(0, 0, 25)), CRANE, feather=0.005)
    grime(ms, "#8a5a24", r=0.03, thresh=0.1, noise=0.06, feather=0.12)
    flag = fit("pennant", color="#c23a2e", gloss=60, res=0.012, decimate=600)
    ftop = MAST + (0, 3.4, -0.07)
    flag.add(Fin(ftop, ftop + (0, -0.3, 0), [ftop + (0, -0.05, -0.55), ftop + (0, -0.12, -0.6)], (1, 0, 0), thick=0.018,
                 edge=0.012, scallop=0.0, ribs=0.0, wave=(0.04, 0.4)))

    # deck lights: two on the crosstree aimed at the working deck, one on the roof aimed aft
    lamps = fit("lamps", color="#3a3d40", gloss=120, decimate=1500)
    lamp_specs = [(MAST + (-0.6, 2.55, 0.12), (0.15, -0.6, 1.0)), (MAST + (0.6, 2.55, 0.12), (-0.15, -0.6, 1.0)),
                  (np.array([0.0, 3.02, WZ0 - 0.1]), (0, -0.6, -1.0))]
    lamp_out = []
    for c, d in lamp_specs:
        d = _n(d)
        lamps.add(Cylinder(c, 0.11, 0.09, rot=look_rot(d), round=0.03))
        lamps.add(Capsule(c - d * 0.08, c - d * 0.16 + (0, 0.08, 0), 0.025), k=0.02)
        glass.add(Cylinder(c + d * 0.085, 0.09, 0.015, rot=look_rot(d), round=0.012), color="#f3e7b5")
        lamp_out.append((c + d * 0.1, d))

    # winch: pedestal cheeks + hydraulic motor (static); the drum spins on bone `winch`
    wb = fit("winch_base", color="#4b5b63", gloss=100, decimate=1500)
    for sx in (-1, 1):
        wb.add(Box(WINCH + (sx * 0.28, -0.12, 0), (0.035, 0.3, 0.2), round=0.03))
        wb.add(Cylinder(WINCH + (sx * 0.3, 0, 0), 0.06, 0.05, rot=(0, 0, 90), round=0.015), k=0.01, color=STEEL)
    wb.add(Box(WINCH + (0, -0.36, 0), (0.36, 0.035, 0.24), round=0.025), k=0.02)
    wb.add(Cylinder(WINCH + (0.42, 0, 0), 0.11, 0.1, rot=(0, 0, 90), round=0.03), k=0.02, color="#2f5b66")
    wb.add(Capsule(WINCH + (0.42, -0.08, 0.08), WINCH + (0.42, -0.38, 0.2), 0.02), k=0.01, color="#1f1f1f")
    grime(wb, "#7a4a2a", r=0.03, thresh=0.1, noise=0.06, feather=0.12)
    drum = m.piece("winch_drum", color="#c33a2e", gloss=110, rigid="winch", res=0.012, lumps=0.003, lump_freq=6, decimate=2600)
    drum.add(Cylinder(WINCH, 0.13, 0.25, rot=(0, 0, 90), round=0.02))
    for sx in (-1, 1):
        drum.add(Cylinder(WINCH + (sx * 0.23, 0, 0), 0.24, 0.025, rot=(0, 0, 90), round=0.012), k=0.01)
        for a in range(0, 360, 60):
            r = np.radians(a)
            drum.sub(Sphere(WINCH + (sx * 0.26, np.sin(r) * 0.17, np.cos(r) * 0.17), 0.025), k=0.005)
        drum.paint(Box(WINCH + (sx * 0.24, 0.16, 0), (0.05, 0.06, 0.04)), "#efe6d6", feather=0.005)
    for i, xx in enumerate(np.linspace(-0.18, 0.18, 7)):
        drum.add(Torus(WINCH + (xx, 0, 0), 0.155, 0.03, rot=(0, 0, 90)), k=0.008, color=CP["rope"], gloss=30)
    drum.add(Torus(WINCH + (-0.05, 0, 0), 0.19, 0.03, rot=(0, 0, 90)), k=0.008, color=CP["rope"], gloss=30)
    drum.add(Torus(WINCH + (0.08, 0, 0), 0.19, 0.03, rot=(0, 0, 90)), k=0.008, color=CP["rope"], gloss=30)

    # crane boom (slews about the mast on bone `boom`): collars, box-section arm, ram, sheave block, hook
    bm = m.piece("boom", color=CRANE, gloss=120, rigid="boom", res=0.018, lumps=0.004, lump_freq=4, decimate=4500)
    TIP = np.array([0.0, 3.32, 2.45])
    root = PIVOT + (0, 0.04, 0.12)
    bm.add(Cylinder(PIVOT, 0.15, 0.13, round=0.04))
    bm.add(Cylinder(PIVOT + (0, -0.66, 0), 0.13, 0.08, round=0.03), k=0.01)
    bm.add(box_between(root, TIP, 0.085, 0.11, round=0.05), k=0.05)
    bm.add(box_between(root + (0, -0.02, 0), root + (0, 0.25, 0.65), 0.07, 0.07, round=0.04), k=0.06)
    # hydraulic ram: barrel + chrome rod from the lower collar up to the boom
    r0 = PIVOT + (0, -0.66, 0.12)
    r2 = root + (TIP - root) * 0.42 + (0, -0.1, 0)
    r1 = r0 + (r2 - r0) * 0.58
    bm.add(Capsule(r0, r1, 0.065), k=0.02, color="#2e2e30")
    bm.add(Capsule(r1, r2, 0.035), k=0.015, color="#d5dade", gloss=230)
    bm.add(Sphere(r2, 0.07), k=0.03)
    # sheave block at the tip and the hook hanging below
    bm.add(Cylinder(TIP + (0, -0.03, 0.08), 0.14, 0.06, rot=(0, 0, 90), round=0.03), k=0.02, color="#2e2e30")
    bm.add(Cylinder(TIP + (0, -0.03, 0.08), 0.06, 0.08, rot=(0, 0, 90), round=0.02), k=0.01, color=STEEL)
    hook_top = TIP + (0, -0.17, 0.12)
    bm.add(Capsule(hook_top, hook_top + (0, -0.42, 0), 0.016), k=0.006, color=CP["rope"], gloss=30)
    hk = hook_top + (0, -0.52, 0)
    bm.add(Box(hk + (0, 0.06, 0), (0.05, 0.07, 0.04), round=0.02), k=0.01, color="#2e2e30")
    bm.add(Tube([hk + (0, 0.0, 0), hk + (0, -0.1, 0), hk + (0, -0.15, 0.06), hk + (0, -0.1, 0.11), hk + (0, -0.05, 0.1)], 0.018, samples=4),
           k=0.006, color=STEEL, gloss=180)
    # hazard stripes near the tip
    d = _n(TIP - root)
    for i in range(4):
        c = TIP - d * (0.3 + i * 0.13)
        bm.paint(Box(c, (0.2, 0.026, 0.2), rot=look_rot(d) @ euler((28, 0, 0))), "#232222", gloss=90, feather=0.004)
    grime(bm, "#8a5a24", r=0.03, thresh=0.1, noise=0.06, feather=0.12)

    # pot launcher on the starboard rail: tilting rack + ram
    pl = fit("launcher", color=STEEL, gloss=110, decimate=1800)
    lz0, lz1 = 0.2, 1.55
    xin = 0.98
    for z in (lz0, lz1):
        xo = inner_x(z, sheer_y(z)) + BT + 0.12
        a = np.array([xin, DECK + 0.1, z])
        b = np.array([xo, sheer_y(z) + 0.12, z])
        pl.add(Capsule(a, b, 0.04))
        pl.add(Capsule(a, a + (0, -0.1, 0), 0.03), k=0.02)
    for t in (0.0, 0.33, 0.66, 1.0):
        za, zb = lz0, lz1
        xa = xin + t * (inner_x(za, sheer_y(za)) + BT + 0.12 - xin)
        ya = DECK + 0.1 + t * (sheer_y(za) + 0.02)
        pl.add(Capsule((xa, DECK + 0.1 + t * (sheer_y(za) + 0.02 - DECK), za), (xa, DECK + 0.1 + t * (sheer_y(zb) + 0.02 - DECK), zb), 0.032), k=0.02)
    pl.add(Capsule((xin + 0.15, DECK + 0.02, 0.85), (xin + 0.38, DECK + 0.2, 0.85), 0.045), k=0.02, color="#2e2e30")
    grime(pl, CP["rust"], r=0.03, thresh=0.1, noise=0.06, feather=0.12)

    # hold hatch on the aft deck
    HOLD = np.array([0.15, DECK, -3.45])
    hh = fit("hatch", color=WHITE, gloss=70, decimate=1300)
    hh.add(Box(HOLD + (0, 0.07, 0), (0.45, 0.08, 0.42), round=0.04))
    hh.add(Box(HOLD + (0, 0.17, 0), (0.42, 0.04, 0.39), round=0.035), k=0.015, color=TRIM)
    hh.sub(Box(HOLD + (0, 0.21, 0), (0.34, 0.02, 0.31), round=0.03), k=0.01)
    for sx in (-1, 1):
        hh.add(Torus(HOLD + (sx * 0.22, 0.215, 0), 0.06, 0.016, rot=(0, 0, 90)), k=0.005, color=STEEL)
    for cx in (-0.36, 0.36):
        for cz in (-0.33, 0.33):
            hh.add(Sphere(HOLD + (cx, 0.2, cz), 0.02), k=0.005, color=STEEL)
    grime(hh, "#9a8f78", r=0.03, thresh=0.1, noise=0.06, feather=0.12)

    # tyre fenders hung over the bulwarks on ropes
    fd = fit("fenders", color=RUBBER, gloss=40, res=0.016, decimate=3000)
    for sx in (1, -1):
        for z in (-3.4, -1.3, 0.9):
            yc = 0.62
            c = side_pt(yc, z, sx, 0.09)
            fd.add(Torus(c, 0.16, 0.075, rot=look_rot((sx, 0, 0.0))))
            for a in range(0, 360, 30):
                r = np.radians(a)
                q = c + np.array([sx * 0.06, np.sin(r) * 0.16, np.cos(r) * 0.16])
                fd.sub(Sphere(q, 0.022), k=0.008)
            top = side_pt(sheer_y(z), z, sx, -BT * 0.5) + (0, 0.1, 0)
            mid = side_pt(sheer_y(z) - 0.2, z, sx, 0.06)
            fd.add(Tube([top, mid, c + (sx * 0.02, 0.2, 0)], 0.022, samples=4), k=0.01, color=CP["rope"])
            fd.add(Capsule(top + (-sx * 0.08, 0.0, 0), top + (sx * 0.02, -0.02, 0), 0.03), k=0.01, color=CP["rope"])

    # coiled lines on the aft deck
    rp = fit("ropes", color=CP["rope"], gloss=25, res=0.014, decimate=2600)
    for c0, ph, col in ((np.array([1.0, DECK + 0.03, -3.95]), 0.0, CP["rope"]), (np.array([-0.95, DECK + 0.03, -3.9]), 1.3, "#d9c49a")):
        pts = coil(c0, 0.1, 0.3, 3.2, 0.012, n_per_turn=12, phase=ph)
        rp.add(Tube(pts, 0.032, samples=2), k=0.012, color=col)
        rp.add(Tube(coil(c0 + (0, 0.05, 0), 0.26, 0.2, 1.3, 0.03, n_per_turn=12, phase=ph + 0.5), 0.032, samples=2), k=0.012, color=col)
        tail = [c0 + (0.28, 0.02, 0.05), c0 + (0.42, 0.02, 0.2), c0 + (0.35, 0.02, 0.38)]
        rp.add(Tube(tail, 0.03, samples=4), k=0.012, color=col)

    # mooring bitts / cleats on the bulwark tops, bow roller
    bt = fit("bitts", color="#2f2f33", gloss=100, decimate=1300)
    for sx in (1, -1):
        for z in (-4.05, 3.7):
            x = sx * inner_x(z, sheer_y(z)) - sx * 0.05
            y = DECK
            if z > 0:
                c = np.array([x * 0.55, DECK, z - 0.1])
            else:
                c = np.array([x - sx * 0.2, DECK, z])
            for dz in (-0.12, 0.12):
                bt.add(Capsule(c + (0, 0, dz), c + (0, 0.28, dz), 0.055))
                bt.add(Cylinder(c + (0, 0.29, dz), 0.075, 0.02, round=0.01), k=0.01)
            bt.add(Box(c + (0, 0.03, 0), (0.1, 0.03, 0.22), round=0.02), k=0.02)
    bt.add(Cylinder((0, sheer_y(4.5) + 0.1, 4.48), 0.07, 0.1, rot=(0, 0, 90), round=0.02), color=STEEL)
    bt.add(Box((0, sheer_y(4.5) + 0.05, 4.4), (0.12, 0.08, 0.18), round=0.03), k=0.02)
    grime(bt, CP["rust"], r=0.02, thresh=0.1, noise=0.06, feather=0.12)

    # the wheelhouse door, swung open aft against its hinge (teal, porthole, brass knob)
    dr = fit("door", color=TRIM, gloss=110, res=0.014, decimate=900)
    dc = np.array([0.79, 1.74, WZ0 - 0.37])
    dr.add(Box(dc, (0.032, 0.76, 0.33), round=0.03))
    dr.sub(Cylinder(dc + (0, 0.36, 0), 0.11, 0.06, rot=(0, 0, 90)), k=0.01)
    dr.add(Torus(dc + (0, 0.36, 0), 0.12, 0.022, rot=(0, 0, 90)), k=0.008, color=CP["brass"], gloss=170)
    dr.add(Sphere(dc + (-0.05, 0.0, -0.25), 0.03), k=0.008, color=CP["brass"], gloss=180)
    dr.sub(Box(dc + (0.035, -0.25, 0), (0.02, 0.2, 0.22), round=0.03), k=0.02)
    for y in (-0.55, 0.55):
        dr.add(Box(dc + (0, y, 0.33), (0.045, 0.06, 0.03), round=0.01), k=0.01, color="#2e2e30")
    glass.add(Cylinder(dc + (0, 0.36, 0), 0.105, 0.012, rot=(0, 0, 90), round=0.008))
    grime(dr, shade(TRIM, 0.7), r=0.02, thresh=0.12, noise=0.05, feather=0.1)

    # life ring on the port side of the wheelhouse
    lr = fit("life_ring", color="#e2e0d8", gloss=110, decimate=1200)
    lrc = np.array([-(WH + 0.07), 1.62, -1.65])
    lr.add(Torus(lrc, 0.19, 0.06, rot=(0, 0, 90)))
    for a in (0, 90, 180, 270):
        r = np.radians(a + 45)
        lr.paint(Sphere(lrc + np.array([0, np.sin(r), np.cos(r)]) * 0.19, 0.09), "#d0392d", feather=0.01)
    lr.add(Torus(lrc + (-0.01, 0, 0), 0.19, 0.012, rot=(0, 0, 90)), k=0.002, color=CP["rope"])
    lr.add(Capsule(lrc + (0.04, 0.24, 0), lrc + (0.04, 0.17, 0), 0.025), k=0.01, color=STEEL)

    # name board on the transom (Unity writes SALLY MAE on it)
    nb = fit("name_board", color=CREAM, gloss=100, res=0.014, decimate=900)
    zn = float(transom_z(np.array([0.85]), np.array([-4.5]))[0])
    nb.add(Box((0, 0.85, zn - 0.005), (0.82, 0.19, 0.035), rot=(-5, 0, 0), round=0.03))
    nb.add(ring_prim((0, 0.85, zn - 0.03), (0.78, 0.15), (-5, 0, 0), 0.04, 0.025, round_in=0.03), k=0.01, color=TRIM)
    for sx in (-1, 1):
        nb.add(Sphere((sx * 0.74, 0.85, zn - 0.045), 0.025), k=0.005, color=CP["brass"])

    # every add without an explicit colour/gloss takes its piece's own (no inherited blends)
    for p in m.pieces:
        for op in p.ops:
            if op.kind == "add":
                if op.color is None:
                    op.color = p.color.copy()
                if op.gloss is None:
                    op.gloss = p.gloss

    # ---------------------------------------------------------------------------------------------- sockets
    m.socket("helm", None, (0.32, DECK, WZ1 - 0.8))
    m.socket("rail_cast", None, (-(inner_x(-3.2) - 0.18), DECK, -3.2), rot=(0, -90, 0))
    m.socket("winch", "winch", WINCH)
    m.socket("boom_tip", "boom", TIP + (0, -0.18, 0.12))
    slots = [(-0.52, 0.47), (0.5, 0.47), (-0.52, 1.51), (0.5, 1.51), (-0.49, 2.55), (0.47, 2.55)]
    for i, (x, z) in enumerate(slots):
        m.socket(f"pot_slot_{i}", None, (x, DECK, z))
    m.socket("smoke", None, sc1 + (0, 0.07, 0))
    for i, (c, d) in enumerate(lamp_out):
        m.socket(f"deck_light_{i}", None, c, rot=look_rot(d) @ euler((-90, 0, 0)))
    m.socket("hold", None, HOLD + (0, 0.21, 0))
    m.socket("bow", None, (0, 1.5, 4.5))
    m.socket("stern", None, (0, DECK, float(transom_z(np.array([DECK]), np.array([-4.5]))[0])))
    m.socket("name_plate", None, (0, 0.85, zn - 0.045), rot=(0, 180, 0))
    return m


MODELS = {"boat/sally_mae": build}
