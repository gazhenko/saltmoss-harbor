"""
Junk dredged up from the Grey Sea (Docs/DESIGN.md §3): old boot, tin can, tangled net. Bottom-centred, 0.2-0.45 m.
Nell pays a sand dollar a piece to keep the sea clean.
"""
import numpy as np
from clay import *
from kit_catch import *

KELP, KELP_DK, KELP_LT = "#5f6a2a", "#45481e", "#8f8a3a"


class Ribbon(Prim):
    """A flat strip swept along a curve: per segment a rounded box (length x width x thickness)."""

    def __init__(self, pts, width, thick, up=(0, 1, 0), twist=0.0, samples=6, ruffle=0.0, ruffle_freq=120.0):
        super().__init__()
        pts = np.asarray(pts, float)
        if len(pts) >= 3 and samples:
            pts = smooth_curve(pts, samples)
        n = len(pts)
        wd = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(np.atleast_1d(width))), np.atleast_1d(width))
        upv = np.asarray(up, float)
        self.segs = []
        for i in range(n - 1):
            a, b = pts[i], pts[i + 1]
            d = b - a
            L = np.linalg.norm(d)
            if L < 1e-7:
                continue
            t = d / L
            u = upv - t * (upv @ t)
            if np.linalg.norm(u) < 1e-6:
                u = np.cross(t, [1, 0, 0])
            u /= np.linalg.norm(u)
            side = np.cross(u, t)
            ang = twist * i / max(n - 1, 1)
            side, u = np.cos(ang) * side + np.sin(ang) * u, -np.sin(ang) * side + np.cos(ang) * u
            self.segs.append((a, t, side, u, L, 0.5 * (wd[i] + wd[i + 1])))
        self.th, self.ruffle, self.rf = thick, ruffle, ruffle_freq
        self.lo = pts.min(0) - wd.max() - thick - ruffle
        self.hi = pts.max(0) + wd.max() + thick + ruffle

    def sdf(self, P):
        d = np.full(len(P), 1e9)
        for a, t, side, u, L, w in self.segs:
            q = P - a
            al = q @ t
            sv = q @ side
            uv = q @ u
            if self.ruffle:
                uv = uv - self.ruffle * np.sin(al * self.rf) * np.clip(np.abs(sv) / (w * 0.5), 0, 1) ** 2
            dx = np.maximum(-al, al - L)
            dy = np.abs(sv) - w * 0.5
            dz = np.abs(uv) - self.th
            r = self.th * 0.9
            qq = np.stack([dx, dy + r, dz + r * 0.5], axis=1)
            dd = np.linalg.norm(np.maximum(qq, 0), axis=1) + np.minimum(qq.max(axis=1), 0) - r
            d = np.minimum(d, dd)
        return d

    def bounds(self):
        return self.lo, self.hi


def ribbon(piece, pts, width, thick, up=(0, 1, 0), k=None, color=None, gloss=None, twist=0.0, samples=6, ruffle=0.0):
    piece.add(Ribbon(pts, width, thick, up, twist, samples, ruffle), k=k if k is not None else thick, color=color, gloss=gloss)


def kelp_blade(piece, pts, width, thick=0.003, color=KELP, **kw):
    kw.setdefault("ruffle", thick * 0.9)
    ribbon(piece, pts, np.atleast_1d(width), thick, color=color, **kw)


# ==============================================================================================================
# old boot — a battered leather work boot, sole peeling at the toe like a mouth, a crab-sized hole, kelp draped on


def old_boot():
    m = Model("old_boot", res=0.004)
    LEATHER, LEATHER_DK, SOLE = "#7a5133", "#4f321f", "#2f2824"
    up = m.piece("upper", color=LEATHER, gloss=55, lumps=0.003, lump_freq=9, dents=22, dent_size=0.022, dent_depth=0.003,
                 res=0.0038, decimate=4300)
    # foot: toe box + vamp + heel counter, slumped shaft leaning back a touch
    up.add(Ellipsoid((0, 0.06, 0.055), (0.058, 0.05, 0.1)))
    up.add(Ellipsoid((0, 0.05, 0.12), (0.052, 0.04, 0.05)), k=0.03)  # round, scuffed toe cap
    up.add(Ellipsoid((0, 0.075, -0.07), (0.055, 0.065, 0.06)), k=0.04)  # heel counter
    up.add(Capsule((0, 0.09, -0.04), (0.004, 0.24, -0.06), 0.06, 0.064), k=0.05)  # shaft
    up.add(Torus((0.004, 0.245, -0.06), 0.062, 0.01, rot=(-6, 0, 0)), k=0.008, color=LEATHER_DK)  # padded collar
    up.sub(Capsule((0.004, 0.12, -0.05), (0.004, 0.3, -0.064), 0.05, 0.055), k=0.01, color="#2a1d15")  # the opening
    # tongue: a flap standing out of the lacing
    up.add(Ellipsoid((0.0, 0.2, 0.005), (0.035, 0.07, 0.012), rot=(-20, 0, 0)), k=0.012)
    up.add(Ellipsoid((0.0, 0.265, 0.02), (0.03, 0.025, 0.01), rot=(-35, 0, 0)), k=0.01)
    # creases where the ankle bends; stitching along the toe cap and the quarter seam
    for i, y in enumerate((0.13, 0.155, 0.18)):
        score(up, arc_pts((0, y, -0.045), (1, 0, 0), (0, -0.25, 1), 0.066, -15 - i * 8, 195 + i * 8, 9), 0.0028)
    score(up, arc_pts((0, 0.05, 0.088), (1, 0, 0), (0, 0.85, 0.4), 0.058, 10, 170, 9), 0.0016)
    for s in (-1, 1):
        score(up, [(s * 0.058, 0.05, -0.02), (s * 0.059, 0.1, -0.03), (s * 0.06, 0.17, -0.04)], 0.0016)
    # the crab-sized hole in the toe (ragged, dark inside)
    hc = np.array([0.03, 0.078, 0.115])
    up.sub(Ellipsoid(hc, (0.022, 0.018, 0.022)).lumpy(0.004, 60, 3), k=0.004)
    up.paint(Sphere(hc, 0.03), "#2a1d15", feather=0.008)
    up.paint(Sphere(hc, 0.036), LEATHER_DK, feather=0.01)
    # wear: scuffed pale toe, dark water stains, salt tide-lines
    up.paint(Ellipsoid((0, 0.07, 0.15), (0.05, 0.035, 0.03)), "#9c6f4a", feather=0.012)
    up.paint(func_prim(lambda P: P[:, 1] - 0.05 + 0.015 * fbm(P * 20, 2, 5)), "#5a3a25", feather=0.01)
    up.paint(func_prim(lambda P: np.abs(P[:, 1] - 0.125 - 0.01 * fbm(P * 12, 2, 6)) - 0.007), "#a5866a", feather=0.01)
    grime(up, "#3a2617", r=0.012, thresh=0.06)
    # eyelets (brass) and a broken lace
    ey = m.piece("eyelets", color=CP["brass"], gloss=180, lumps=0.0, res=0.0018, decimate=1200)
    lace_pts = []
    for i, y in enumerate((0.12, 0.155, 0.19, 0.225)):
        for s in (-1, 1):
            z = 0.035 - i * 0.022 + 0.012
            p = np.array([s * 0.034, y, z])
            nrm = np.array([s * 0.6, 0.15, 0.8])
            ey.add(Torus(p, 0.0075, 0.0028, rot=look_rot(nrm)), k=0.001)
            lace_pts.append(p)
    metal(ey, dark=CP["brass_dk"], r=0.004, tarnish=0.06)
    la = m.piece("lace", color="#c9b48c", gloss=30, lumps=0.0005, lump_freq=30, res=0.0022, decimate=1600)
    L = lace_pts
    for i in range(0, 6, 2):
        la.add(Tube([L[i] + (0, 0, 0.004), (0, (L[i][1] + L[i + 3][1]) / 2, L[i][2] + 0.008), L[i + 3] + (0, 0, 0.004)], 0.0035,
                    samples=4), k=0.002)
        la.add(Tube([L[i + 1] + (0, 0, 0.004), (0, (L[i][1] + L[i + 2][1]) / 2, L[i][2] + 0.01), L[i + 2] + (0, 0, 0.004)], 0.0035,
                    samples=4), k=0.002)
    # the loose broken end trailing down the side
    la.add(Tube([L[7] + (0, 0, 0.004), L[7] + (0.03, 0.01, 0.02), (0.075, 0.13, 0.04), (0.08, 0.06, 0.06), (0.09, 0.01, 0.07)],
                0.0035, samples=5), k=0.002)
    # sole: thick rubber with a heel block; the front peels open like a mouth
    so = m.piece("sole", color=SOLE, gloss=60, lumps=0.0015, lump_freq=10, dents=8, dent_size=0.02, dent_depth=0.002,
                 res=0.0035, decimate=2400)
    so.add(Cylinder((0, 0.018, -0.07), 0.058, 0.018, round=0.008))  # heel block
    so.add(Cylinder((0, 0.012, 0.0), 0.06, 0.012, round=0.007), k=0.03)
    so.add(Cylinder((0, 0.012, 0.06), 0.062, 0.012, round=0.007), k=0.03)
    # peeled toe sole flap dropped open like a jaw (rotated down from the ball of the foot)
    so.add(Ellipsoid((0, 0.008, 0.125), (0.056, 0.008, 0.06), rot=(14, 0, 0)), k=0.012)
    so.paint(func_prim(lambda P: np.abs(P[:, 1] - 0.022) - 0.0025), "#5a4a3c", feather=0.002)  # welt stitching line
    for z in np.linspace(-0.11, 0.02, 7):
        so.sub(Box((0, 0.0, z), (0.07, 0.003, 0.004)), k=0.002)  # tread grooves
    # the toe of the upper is lifted off the sole: carve the gap ("mouth") dark
    up.sub(Box((0, 0.012, 0.15), (0.07, 0.01, 0.06), rot=(16, 0, 0), round=0.006), k=0.006)
    up.paint(Box((0, 0.025, 0.15), (0.07, 0.014, 0.07), rot=(16, 0, 0)), "#2a1d15", feather=0.006)
    # kelp draped over the collar and down the side, glossy and wet
    kp = m.piece("kelp", color=KELP, gloss=200, lumps=0.0008, lump_freq=20, mottle=0.08, res=0.0024, decimate=2200)
    kelp_blade(kp, [(-0.03, 0.25, 0.0), (0.0, 0.282, -0.045), (0.045, 0.268, -0.095), (0.072, 0.2, -0.118), (0.08, 0.12, -0.11),
                    (0.074, 0.04, -0.1)], [0.03, 0.045, 0.05, 0.046, 0.04, 0.026], thick=0.0022, up=(0.6, 0.6, -0.5),
               twist=0.5)
    kelp_blade(kp, [(-0.04, 0.26, -0.03), (-0.068, 0.25, -0.06), (-0.077, 0.18, -0.05), (-0.072, 0.1, -0.03)],
               [0.028, 0.036, 0.03, 0.016], thick=0.0022, up=(-1, 0.3, 0), twist=-0.4, color=KELP_DK)
    kp.add(Ellipsoid((0.03, 0.272, -0.07), (0.012, 0.01, 0.012)), k=0.006, color=KELP_LT)  # float bladder
    kp.paint(blotch_prim(30, 0.25, seed=4), KELP_LT, feather=0.004)
    m.socket("hole", None, tuple(hc))
    return m


# ==============================================================================================================
# tin can — dented, faded paper label with a fish logo, jagged lid bent up on its hinge


def tin_can():
    m = Model("tin_can", res=0.003)
    R, H = 0.075, 0.19
    TIN, TIN_DK = "#b7bcc0", "#6f757b"
    cn = m.piece("can", color=TIN, gloss=150, lumps=0.0012, lump_freq=14, dents=6, dent_size=0.02, dent_depth=0.002,
                 res=0.0025, decimate=8800)
    cn.add(Cylinder((0, H / 2, 0), R, H / 2, round=0.006))
    # rolled rims and the swaged ribs of the body
    cn.add(Torus((0, 0.005, 0), R - 0.002, 0.005), k=0.003)
    cn.add(Torus((0, H - 0.003, 0), R - 0.001, 0.0045), k=0.003)
    for y in (0.018, 0.028, H - 0.028, H - 0.018):
        cn.sub(Torus((0, y, 0), R + 0.001, 0.0022), k=0.002)
    for y in np.linspace(0.05, H - 0.05, 5):
        cn.sub(Torus((0, y, 0), R + 0.0012, 0.0016), k=0.0016)
    # big dents: one caved-in side, a crumple near the base (the wall is pushed in, the cavity follows it)
    dents_ = [(Ellipsoid((R + 0.012, 0.11, 0.03), (0.03, 0.045, 0.035)), 0.02), (Sphere((-0.05, 0.03, R + 0.006), 0.022), 0.015),
              (Sphere((-0.065, 0.16, -0.045), 0.016), 0.012)]
    for d_, k_ in dents_:
        cn.sub(d_, k=k_)
    shell_ = Piece(Model("tmp"), "tmp", lumps=0.0)
    shell_.add(Cylinder((0, H / 2 + 0.05, 0), R, H / 2 + 0.05, round=0.006))
    for d_, k_ in dents_:
        shell_.sub(d_, k=k_)
    cav = Func(lambda P: np.maximum(shell_._eval_shape(P) + 0.0042, 0.012 - P[:, 1]), (-R, 0, -R), (R, H + 0.1, R))
    cn.sub(cav, k=0.002, color="#7b6450")
    # faded label: a raised paper band (cream, red top band, blue bottom band) torn away at the back, a pressed-on
    # blue fish emblem on the front. Real geometry at every colour edge so decimation keeps the outlines crisp.
    def gap_(P):
        ang = np.arctan2(P[:, 0], P[:, 2])
        torn = 0.006 * fbm(P * 45, 2, 9)
        return (0.55 - np.abs(((ang - np.pi) + np.pi) % (2 * np.pi) - np.pi) + torn * 18) * 0.02
    GAP = Func(gap_, (-0.1, 0, -0.1), (0.1, 0.2, 0.1))
    LBL = inter_prim(func_prim(lambda P: np.abs(P[:, 1] - 0.096) - 0.064), GAP)
    lab = Func(lambda P: np.maximum(np.maximum(np.linalg.norm(P[:, [0, 2]], axis=1) - (R + 0.0012), np.abs(P[:, 1] - 0.096) - 0.064),
                                    gap_(P)), (-R - 0.01, 0.02, -R - 0.01), (R + 0.01, 0.17, R + 0.01))
    cn.add(lab, k=0.0015, color="#e2d3a8", gloss=35)
    for y in (0.126, 0.16, 0.034, 0.056):
        cn.sub(Torus((0, y, 0), R + 0.0016, 0.0013), k=0.001)
    cn.paint(inter_prim(LBL, func_prim(lambda P: np.abs(P[:, 1] - 0.143) - 0.017)), "#bf5a42", gloss=35, feather=0.0015)
    cn.paint(inter_prim(LBL, func_prim(lambda P: np.abs(P[:, 1] - 0.045) - 0.011)), "#4c7391", gloss=35, feather=0.0015)
    # fish emblem (raised)
    fc = np.array([0.0, 0.092, R + 0.001])
    cn.add(Ellipsoid(fc + (0.006, 0, 0), (0.032, 0.0165, 0.0035)), k=0.0015, color="#36668a", gloss=40)
    for s_ in (1, -1):
        cn.add(Capsule(fc + (-0.024, 0, 0), fc + (-0.046, s_ * 0.016, 0), 0.0035, 0.0045), k=0.003, color="#36668a", gloss=40)
    cn.add(Capsule(fc + (-0.044, 0.014, 0), fc + (-0.044, -0.014, 0), 0.0035), k=0.003, color="#36668a", gloss=40)
    cn.add(Sphere(fc + (0.026, 0.004, 0.003), 0.0038), k=0.001, color="#e2d3a8", gloss=60)
    cn.paint(Sphere(fc + (0.027, 0.004, 0.006), 0.002), "#1d2a33", feather=0.0008)
    score(cn, arc_pts(fc + (0.008, 0, 0.003), (0, 1, 0), (1, 0, 0), 0.014, -60, 60, 5), 0.0011)  # gill line
    # faded and water-stained, rust only at the rims and on bare tin where the label tore away
    cn.paint(inter_prim(LBL, blotch_prim(9, 0.35, seed=3)), "#ece2c6", feather=0.003)
    cn.paint(func_prim(lambda P: P[:, 1] - 0.013 + 0.006 * fbm(P * 30, 2, 2)), "#8c4f2b", gloss=40, feather=0.003)
    cn.paint(func_prim(lambda P: 0.188 - P[:, 1] + 0.004 * fbm(P * 30, 2, 3)), "#9a5a33", gloss=50, feather=0.002)
    cn.paint(inter_prim(not_prim(GAP), blotch_prim(16, 0.15, seed=6), func_prim(lambda P: np.abs(P[:, 1] - 0.096) - 0.064)),
             "#8c4f2b", gloss=40, feather=0.003)
    metal(cn, dark=TIN_DK, r=0.006, tarnish=0.1)
    # lid: jagged-edged disc, still hinged at the back rim, bent up and back
    hinge = np.array([0, H - 0.002, -R + 0.002])
    Rl = euler((-104, 0, 0))

    def lid(P):
        q = (P - hinge) @ Rl
        q = q - np.array([0, 0, R - 0.006])
        rho = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2)
        th = np.arctan2(q[:, 0], q[:, 2])
        jag = 0.006 * np.abs(((th * 9) % 2.0) - 1.0) * (np.abs(th) < 2.4)
        dish = 0.004 * (1 - (rho / R) ** 2)
        return np.maximum(rho - (R - 0.004 - jag), np.abs(q[:, 1] - dish) - 0.0018)
    ld = m.piece("lid", color="#a6abb1", gloss=160, lumps=0.0008, lump_freq=20, res=0.0018, decimate=2400)
    lo_ = hinge - np.array([R, R * 2.2, R * 2.2])
    hi_ = hinge + np.array([R, R * 2.2, R * 2.2])
    ld.add(Func(lid, lo_, hi_))
    for rr in (0.025, 0.05):  # stamped rings on the lid
        ld.paint(Func(lambda P, rr=rr: np.abs(np.linalg.norm(((P - hinge) @ Rl - (0, 0, R - 0.006))[:, [0, 2]], axis=1) - rr) - 0.0014,
                      lo_, hi_), "#8e949a", feather=0.001)
    ld.paint(blotch_prim(25, 0.3, seed=8), "#9a5a33", gloss=50, feather=0.003)
    ld.add(Box(hinge + (0, 0.004, 0.0), (0.016, 0.006, 0.0035), round=0.002), k=0.003)  # the bit of tin still holding it
    m.socket("mouth", None, (0, H, 0))
    return m


# ==============================================================================================================
# tangled net — a knotted clump of faded green net balled around an orange foam float, kelp caught in it


class NetShell(Prim):
    """Net strands on a crumpled closed surface: where the surface meets two families of lattice planes."""

    def __init__(self, c, radii, rot, cell, r, seed=0, warp=0.02, cut=None, knot=None):
        super().__init__()
        self.c = np.asarray(c, float)
        self.radii = np.asarray(radii, float)
        self.R = euler(rot)
        self.cell, self.r, self.seed, self.warp = cell, r, seed, warp
        self.cut = cut  # optional prim: strands only where cut(P) < 0
        self.knot = knot or r * 1.6
        rng = np.random.default_rng(seed)
        A = rng.normal(size=(2, 3))
        A[0] /= np.linalg.norm(A[0])
        A[1] -= A[0] * (A[1] @ A[0])
        A[1] /= np.linalg.norm(A[1])
        self.A = A

    def sdf(self, P):
        Q = P + self.warp * np.column_stack([vnoise(P * 9, self.seed + i) for i in range(3)])
        q = (Q - self.c) @ self.R
        k0 = np.linalg.norm(q / self.radii, axis=1)
        k1 = np.linalg.norm(q / (self.radii ** 2), axis=1)
        s = k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        c = self.cell
        a = q @ self.A[0]
        b = q @ self.A[1]
        da = np.abs(a - np.round(a / c) * c)
        db = np.abs(b - np.round(b / c) * c)
        d = np.minimum(np.sqrt(s * s + da * da), np.sqrt(s * s + db * db)) - self.r
        dk = np.sqrt(s * s + da * da + db * db) - self.knot
        d = smin(d, dk, self.r * 0.5)[0]
        if self.cut is not None:
            d = np.maximum(d, self.cut(P))
        return d

    def bounds(self):
        e = np.abs(self.R) @ self.radii + self.warp + self.r + 0.01
        return self.c - e, self.c + e


def tangled_net():
    m = Model("tangled_net", res=0.003)
    NET, NET2 = "#4f8a78", "#6b9a6a"
    # the float: a fat orange foam cylinder with a hole through it (peeks out of the tangle)
    fl = m.piece("float", color="#e8742a", gloss=90, lumps=0.002, lump_freq=12, dents=10, dent_size=0.02, dent_depth=0.003,
                 res=0.003, decimate=2200)
    fc = np.array([0.03, 0.105, 0.0])
    fl.add(Cylinder(fc, 0.07, 0.085, rot=(0, 20, 90), round=0.035))
    fl.sub(Cylinder(fc, 0.018, 0.2, rot=(0, 20, 90)), k=0.006, color="#7a3c18")
    fl.paint(blotch_prim(16, 0.2, seed=2), "#c9b18a", feather=0.004)  # sun-bleached, scuffed
    fl.paint(func_prim(lambda P: P[:, 1] - 0.06), "#a8642e", feather=0.01)
    # net layers: several crumpled shells, partly torn open, a different weave angle each
    nt = m.piece("net", color=NET, gloss=50, lumps=0.0006, lump_freq=30, mottle=0.1, res=0.0026, decimate=6500)
    layers = [
        ((0.0, 0.1, 0.0), (0.15, 0.1, 0.12), (0, 15, 5), None),
        ((-0.05, 0.085, 0.03), (0.13, 0.085, 0.1), (10, -30, 20), HalfSpace((0.02, 0.0, 0.0), (1, 0.2, 0))),
        ((0.07, 0.09, -0.02), (0.11, 0.09, 0.12), (-10, 50, -15), HalfSpace((0.0, 0.0, 0.0), (-1, 0.1, 0.3))),
        ((0.0, 0.14, 0.02), (0.09, 0.06, 0.1), (25, 70, 0), HalfSpace((0.0, 0.12, 0.0), (0, -1, 0.2))),
        ((-0.02, 0.05, -0.04), (0.17, 0.05, 0.11), (0, -60, 0), None),
    ]
    for i, (c, rad, rot, cut) in enumerate(layers):
        nt.add(NetShell(c, rad, rot, 0.038, 0.0038, seed=i * 3 + 1, warp=0.022, cut=cut), k=0.002)
    # loose flaps and strands trailing onto the table
    for i, pts in enumerate([[(0.14, 0.05, 0.05), (0.19, 0.02, 0.08), (0.23, 0.006, 0.07)],
                             [(-0.12, 0.08, -0.06), (-0.18, 0.03, -0.08), (-0.21, 0.006, -0.03), (-0.24, 0.005, 0.0)],
                             [(0.02, 0.18, 0.06), (0.05, 0.2, 0.1), (0.1, 0.15, 0.13), (0.12, 0.06, 0.14), (0.15, 0.006, 0.15)]]):
        nt.add(Tube(pts, 0.0034, samples=5), k=0.002)
    # a few fat knots
    rng = np.random.default_rng(7)
    for i in range(6):
        p = np.array([rng.uniform(-0.12, 0.12), rng.uniform(0.04, 0.17), rng.uniform(-0.1, 0.1)])
        nt.add(Sphere(p, 0.008), k=0.004)
    nt.paint(blotch_prim(10, 0.1, seed=5), NET2, feather=0.004)
    nt.paint(func_prim(lambda P: P[:, 1] - 0.03), shade(NET, 0.7), feather=0.01)
    # a frayed rope end and kelp caught in the mesh
    rp = m.piece("rope", color=CP["rope"], gloss=30, lumps=0.0008, lump_freq=20, res=0.0026, decimate=1500)
    rope(rp, [(-0.15, 0.04, 0.08), (-0.08, 0.13, 0.09), (0.02, 0.2, 0.03), (0.1, 0.16, -0.06), (0.17, 0.08, -0.08),
              (0.22, 0.015, -0.05)], 0.0075, twist=True, groove=CP["rope_dk"])
    for i in range(4):
        a = i * 1.4
        rp.add(Capsule((0.22, 0.015, -0.05), (0.22 + 0.025 * np.cos(a), 0.006, -0.05 + 0.025 * np.sin(a)), 0.0025, 0.0015),
               k=0.002)
    kp = m.piece("kelp", color=KELP, gloss=200, lumps=0.0008, lump_freq=20, mottle=0.08, res=0.0024, decimate=1600)
    kelp_blade(kp, [(-0.1, 0.17, -0.02), (-0.03, 0.215, -0.05), (0.06, 0.2, -0.1), (0.12, 0.11, -0.13), (0.14, 0.02, -0.14)],
               [0.03, 0.042, 0.046, 0.04, 0.026], thick=0.0022, up=(0, 1, 0.3), twist=0.6)
    kelp_blade(kp, [(0.05, 0.19, 0.08), (0.0, 0.15, 0.14), (-0.05, 0.06, 0.16), (-0.09, 0.006, 0.17)],
               [0.026, 0.036, 0.03, 0.018], thick=0.0022, up=(0, 0.5, 1), twist=-0.5, color=KELP_DK)
    kp.paint(blotch_prim(30, 0.25, seed=4), KELP_LT, feather=0.004)
    m.socket("float", None, tuple(fc))
    return m


MODELS = {
    "junk/old_boot": old_boot,
    "junk/tin_can": tin_can,
    "junk/tangled_net": tangled_net,
}
