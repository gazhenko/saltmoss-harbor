"""
Deep-sea treasures, batch B (Docs/DESIGN.md §3 dredging, §5.4): megalodon_tooth, grand_conch, figurehead,
porcelain_teapot, ship_lantern, sextant, music_box, ship_in_bottle, sunken_crown, treasure_chest.

Bottom-centred (y = 0 is the resting surface, centred in x/z), 0.15-0.8 m. Metals are "metallic clay" (warm base,
higher gloss, tarnish in crevices + worn bright edges via kit_catch.metal). Glass that should be see-through is a
separate hollow piece named `glass_clear`; glowing glass is matClass 1 `glass`.
"""
import numpy as np
from clay import *
from kit_catch import *

TAU = 2 * np.pi


def _n(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


# ==============================================================================================================
# local helpers


class Posed(Prim):
    """Wrap a prim with a rigid transform: world = R (local - pivot) + pivot + t."""

    def __init__(self, prim, rot=None, t=(0, 0, 0), pivot=(0, 0, 0)):
        super().__init__()
        self.p = prim
        self.R = euler(rot)
        self.t = np.asarray(t, float)
        self.piv = np.asarray(pivot, float)

    def sdf(self, P):
        return self.p((P - self.piv - self.t) @ self.R + self.piv)

    def bounds(self):
        lo, hi = self.p.bounds()
        lo, hi = np.maximum(lo, -50), np.minimum(hi, 50)
        C = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        W = (C - self.piv) @ self.R.T + self.piv + self.t
        return W.min(0), W.max(0)


class Scaled(Prim):
    """Uniformly scale a prim about a pivot."""

    def __init__(self, prim, s, pivot=(0, 0, 0)):
        super().__init__()
        self.p, self.s, self.piv = prim, float(s), np.asarray(pivot, float)

    def sdf(self, P):
        return self.p((P - self.piv) / self.s + self.piv) * self.s

    def bounds(self):
        lo, hi = self.p.bounds()
        return (lo - self.piv) * self.s + self.piv, (hi - self.piv) * self.s + self.piv


def pose_piece(piece, rot=None, t=(0, 0, 0), pivot=(0, 0, 0)):
    """Re-pose every op of a finished piece (sculpt in a canonical frame, then tilt/place it)."""
    for op in piece.ops:
        op.prim = Posed(op.prim, rot, t, pivot)
    return piece


def pose_point(p, rot=None, t=(0, 0, 0), pivot=(0, 0, 0)):
    R = euler(rot)
    return R @ (np.asarray(p, float) - np.asarray(pivot, float)) + np.asarray(pivot, float) + np.asarray(t, float)


def ground_offset(pieces, lo=(-1, -1, -1), hi=(1, 1, 1), h=0.008, centre=True):
    """Translation that puts the union of `pieces` on y = 0 (and centres it in x/z), from a coarse SDF sample."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    axes = [np.arange(lo[i], hi[i], h) for i in range(3)]
    X, Y, Z = np.meshgrid(*axes, indexing="ij")
    P = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    d = np.full(len(P), 1e9)
    for pc in pieces:
        d = np.minimum(d, pc._eval_shape(P))
    inside = P[d < 0]
    mn, mx = inside.min(0), inside.max(0)
    t = np.array([-(mn[0] + mx[0]) / 2 if centre else 0.0, -mn[1] + h * 0.3, -(mn[2] + mx[2]) / 2 if centre else 0.0])
    return t


def closed_curve(pts, n=4):
    P = np.asarray(pts, float)
    m = len(P)
    out = []
    for i in range(m):
        p0, p1, p2, p3 = P[i - 1], P[i], P[(i + 1) % m], P[(i + 2) % m]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return np.array(out)


class Pillow(Prim):
    """A lens-shaped slab: a closed 2D outline (in the plane u,v through o) puffed to half-thickness t in the middle,
    rounding down to `edge` at the rim over `fall`. offset(p2) bends the slab along n; edge_mod(p2) adds to the
    outline distance (serrations); back scales the thickness on the -n side."""

    def __init__(self, poly, t, edge, fall, o=(0, 0, 0), u=(1, 0, 0), v=(0, 1, 0), offset=None, edge_mod=None, back=1.0):
        super().__init__()
        self.poly = np.asarray(poly, float)
        self.o = np.asarray(o, float)
        self.u, self.v = _n(u), _n(v)
        self.n = _n(np.cross(self.u, self.v))
        self.t, self.edge, self.fall = t, edge, fall
        self.offset, self.edge_mod, self.back = offset, edge_mod, back

    def sdf(self, P):
        q = P - self.o
        p2 = np.column_stack([q @ self.u, q @ self.v])
        c = q @ self.n
        if self.offset is not None:
            c = c - self.offset(p2)
        ds0 = poly_sdf(p2, self.poly)
        ds = ds0 + self.edge_mod(p2) if self.edge_mod is not None else ds0
        f = np.clip(-ds0 / self.fall, 0, 1)
        th = self.edge + (self.t - self.edge) * np.sqrt(1 - (1 - f) ** 2)
        if self.back != 1.0:
            th = np.where(c < 0, th * self.back, th)
        rr = self.edge * 0.9
        wx = ds + rr
        wy = np.abs(c) - np.maximum(th - rr, 1e-4)
        return np.minimum(np.maximum(wx, wy), 0) + np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wy, 0) ** 2) - rr

    def bounds(self):
        lo2, hi2 = self.poly.min(0), self.poly.max(0)
        C = []
        T = max(self.t, self.t * self.back) + 0.02
        for a in (lo2[0], hi2[0]):
            for b in (lo2[1], hi2[1]):
                for c in (-T, T):
                    C.append(self.o + a * self.u + b * self.v + c * self.n)
        C = np.array(C)
        return C.min(0) - 0.01, C.max(0) + 0.01


def frame_rot(x, y, z):
    """Rotation matrix whose local x/y/z axes are the given world vectors (orthonormalised)."""
    z = _n(z)
    x = _n(np.asarray(x, float) - z * (np.asarray(x, float) @ z))
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


def ribbon(piece, pts, width, thick, up=(0, 1, 0), k=0.006, color=None, gloss=None, samples=4, seed=0, frill=0.25):
    """A floppy seaweed ribbon: overlapping flattened lozenges along a curve (frilly, slightly uneven)."""
    rng = np.random.default_rng(seed)
    P = smooth_curve(np.asarray(pts, float), samples)
    W = np.broadcast_to(np.asarray(width, float), (len(pts),))
    Ws = np.interp(np.linspace(0, 1, len(P)), np.linspace(0, 1, len(W)), W)
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        t = _n(b - a)
        side = _n(np.cross(t, up))
        nrm = np.cross(side, t)
        L = np.linalg.norm(b - a)
        w = Ws[i] * (1 + rng.uniform(-frill, frill))
        R = np.column_stack([side, nrm, t])
        piece.add(Ellipsoid((a + b) / 2, (w, thick, L * 0.75 + thick), rot=R), k=k, color=color, gloss=gloss)


def barnacle(piece, c, nrm, r, color="#d9d3c3", inner="#4a4038", k=None):
    """A little acorn barnacle: a ridged cone with a dark slot on top."""
    nrm = _n(nrm)
    c = np.asarray(c, float)
    top = c + nrm * r * 0.95
    piece.add(Capsule(c - nrm * r * 0.3, top, r, r * 0.58), k=k if k is not None else r * 0.35, color=color, gloss=45)
    side = _n(np.cross(nrm, [0.3, 0.2, 0.9]))
    side2 = np.cross(nrm, side)
    for i in range(6):
        a = i / 6 * TAU
        d = np.cos(a) * side + np.sin(a) * side2
        piece.sub(Capsule(c + d * r * 1.0 + nrm * r * 0.05, top + d * r * 0.6, r * 0.11), k=r * 0.08)
    piece.sub(Capsule(top - nrm * r * 0.25, top + nrm * r * 0.8, r * 0.3), k=r * 0.12)
    piece.paint(Sphere(top - nrm * r * 0.15, r * 0.36), inner, gloss=90, feather=r * 0.12)


def grain_prim(axis, freq=90.0, warp=1.6, thresh=0.55, seed=1, origin=(0, 0, 0)):
    """Negative along wood-grain lines running along `axis`."""
    a = _n(axis)
    p1 = _n(np.cross(a, [0.13, 0.71, 0.69]))
    o = np.asarray(origin, float)

    def f(P):
        q = P - o
        along = q @ a
        across = q @ p1
        w = fbm(np.column_stack([along * 3.0, across * 30.0, (q @ np.cross(a, p1)) * 30.0]), 2, seed)
        s = np.sin((across * freq + warp * w + 0.4 * np.sin(along * 9.0)) * TAU / 6.0)
        return (thresh - s) * 0.02
    return Func(f, (-9, -9, -9), (9, 9, 9))


def coin(piece, c, nrm, r=0.022, th=0.0032, color=None, k=0.002, rim=True):
    """A gold coin: a flat disc with a raised rim and a stamped centre."""
    R = look_rot(_n(nrm))
    c = np.asarray(c, float)
    piece.add(Cylinder(c, r, th, rot=R, round=th * 0.7), k=k, color=color)
    if rim:
        piece.sub(Cylinder(c + _n(nrm) * th * 1.15, r * 0.78, th * 0.35, rot=R, round=th * 0.2), k=th * 0.3)
        piece.add(Sphere(c + _n(nrm) * th * 0.3, r * 0.42), k=th * 0.8)


class CoinPile(Prim):
    """Many stamped coins (discs with a rim, recess and boss) as one SDF, spatially hashed so hundreds stay cheap."""

    def __init__(self, centres, normals, radii, th=0.0034, cell=0.06):
        super().__init__()
        self.C = np.asarray(centres, float)
        self.Rm = np.array([look_rot(_n(n)) for n in normals])
        self.r = np.broadcast_to(np.asarray(radii, float), (len(self.C),)).copy()
        self.th, self.cell = th, cell
        pad = self.r.max() + th + 0.004
        self.lo, self.hi = self.C.min(0) - pad, self.C.max(0) + pad

    def _coin(self, P, i):
        q = (P - self.C[i]) @ self.Rm[i]
        r, th = self.r[i], self.th
        rd = th * 0.6
        rr = np.hypot(q[:, 0], q[:, 2])
        dx, dy = rr - (r - rd), np.abs(q[:, 1]) - (th - rd)
        d = np.minimum(np.maximum(dx, dy), 0) + np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) - rd
        rec = np.maximum(rr - r * 0.8, np.abs(np.abs(q[:, 1]) - th) - th * 0.32)
        d = np.maximum(d, -rec)
        boss = np.hypot(rr / (r * 0.5), (np.abs(q[:, 1]) - th * 0.45) / (th * 0.55)) - 1.0
        return np.minimum(d, boss * th * 0.55)

    def sdf(self, P):
        d = np.full(len(P), 0.05)
        cs = self.cell
        n = np.ceil((self.hi - self.lo) / cs).astype(int) + 1
        k3 = np.floor((P - self.lo) / cs).astype(np.int64)
        valid = np.all((k3 >= 0) & (k3 < n), axis=1)
        key = np.where(valid, (k3[:, 0] * n[1] + k3[:, 1]) * n[2] + k3[:, 2], -1)
        order = np.argsort(key, kind="stable")
        sk = key[order]
        reach = self.r.max() + self.th + 0.003
        for i, c in enumerate(self.C):
            a = np.floor((c - reach - self.lo) / cs).astype(int)
            b = np.floor((c + reach - self.lo) / cs).astype(int)
            idx = []
            for x in range(max(a[0], 0), min(b[0], n[0] - 1) + 1):
                for y in range(max(a[1], 0), min(b[1], n[1] - 1) + 1):
                    for z in range(max(a[2], 0), min(b[2], n[2] - 1) + 1):
                        kk = (x * n[1] + y) * n[2] + z
                        i0, i1 = np.searchsorted(sk, kk, "left"), np.searchsorted(sk, kk, "right")
                        if i1 > i0:
                            idx.append(order[i0:i1])
            if not idx:
                continue
            idx = np.concatenate(idx)
            d[idx] = np.minimum(d[idx], self._coin(P[idx], i))
        return d

    def bounds(self):
        return self.lo, self.hi


class HashedSpheres(Prim):
    """Union of many equal spheres, spatially hashed (scale cups, dimples, rivet fields)."""

    def __init__(self, centres, r, cell=None):
        super().__init__()
        self.C = np.asarray(centres, float)
        self.r = float(r)
        self.cell = cell or max(4 * r, 0.02)
        self.lo, self.hi = self.C.min(0) - r - 0.004, self.C.max(0) + r + 0.004

    def sdf(self, P):
        d = np.full(len(P), 0.05)
        cs = self.cell
        n = np.ceil((self.hi - self.lo) / cs).astype(int) + 1
        k3 = np.floor((P - self.lo) / cs).astype(np.int64)
        valid = np.all((k3 >= 0) & (k3 < n), axis=1)
        key = np.where(valid, (k3[:, 0] * n[1] + k3[:, 1]) * n[2] + k3[:, 2], -1)
        order = np.argsort(key, kind="stable")
        sk = key[order]
        reach = self.r + 0.004
        for c in self.C:
            a = np.floor((c - reach - self.lo) / cs).astype(int)
            b = np.floor((c + reach - self.lo) / cs).astype(int)
            idx = []
            for x in range(max(a[0], 0), min(b[0], n[0] - 1) + 1):
                for y in range(max(a[1], 0), min(b[1], n[1] - 1) + 1):
                    for z in range(max(a[2], 0), min(b[2], n[2] - 1) + 1):
                        kk = (x * n[1] + y) * n[2] + z
                        i0, i1 = np.searchsorted(sk, kk, "left"), np.searchsorted(sk, kk, "right")
                        if i1 > i0:
                            idx.append(order[i0:i1])
            if idx:
                idx = np.concatenate(idx)
                d[idx] = np.minimum(d[idx], np.linalg.norm(P[idx] - c, axis=1) - self.r)
        return d

    def bounds(self):
        return self.lo, self.hi


def scatter_on(surface_pts, normals, spacing, rng, tilt=0.5, n_max=400):
    """Greedy blue-noise pick of coin spots from candidate surface points."""
    keep, nrm = [], []
    for p, nn in zip(surface_pts, normals):
        if keep and np.min(np.linalg.norm(np.asarray(keep) - p, axis=1)) < spacing:
            continue
        keep.append(p)
        nrm.append(_n(nn + rng.normal(0, tilt, 3)))
        if len(keep) >= n_max:
            break
    return np.array(keep), np.array(nrm)


# ==============================================================================================================
# megalodon tooth — a big fossil tooth standing on its root lobes


def megalodon_tooth():
    m = Model("megalodon_tooth", res=0.0016)
    ENAMEL, ENAMEL2, BOUR, ROOT = "#47423e", "#5f6a75", "#29231f", "#7f6247"
    outline = [(-0.092, 0.012), (-0.07, 0.0), (-0.038, 0.002), (-0.015, 0.012), (0.0, 0.021), (0.015, 0.012),
               (0.038, 0.002), (0.07, 0.0), (0.092, 0.012), (0.096, 0.03), (0.088, 0.046), (0.077, 0.056),
               (0.06, 0.092), (0.04, 0.132), (0.019, 0.17), (0.006, 0.192), (0.0, 0.198), (-0.007, 0.19),
               (-0.021, 0.168), (-0.042, 0.131), (-0.062, 0.091), (-0.078, 0.056), (-0.089, 0.046), (-0.096, 0.03)]
    poly = closed_curve(outline, 4)

    def serr(p2):
        x, y = p2[:, 0], p2[:, 1]
        blade = np.clip((y - 0.062) / 0.012, 0, 1) * np.clip((0.19 - y) / 0.01, 0, 1)
        ph = (y / 0.0045 + 0.5 * np.sign(x)) % 1.0
        tri = 1 - 2 * np.abs(ph - 0.5)
        return -0.0017 * tri * blade

    def bend(p2):
        y = p2[:, 1]
        return -0.014 * np.clip((y - 0.06) / 0.14, 0, 1) ** 2

    tooth = m.piece("tooth", color=ENAMEL, gloss=205, lumps=0.0007, lump_freq=22, dents=12, dent_size=0.014,
                    dent_depth=0.0012, mottle=0.07, decimate=9200)
    tooth.add(Pillow(poly, 0.02, 0.0011, 0.05, o=(0, 0, 0), offset=bend, edge_mod=serr, back=1.3))
    # root: flared lobes, a touch thicker than the crown
    tooth.add(Ellipsoid((-0.046, 0.022, -0.004), (0.046, 0.02, 0.019), rot=(0, 0, -8)), k=0.012)
    tooth.add(Ellipsoid((0.046, 0.022, -0.004), (0.046, 0.02, 0.019), rot=(0, 0, 8)), k=0.012)
    tooth.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.002)
    # a couple of hairline cracks in the enamel and a nick out of one edge
    score(tooth, [(-0.02, 0.15, 0.009), (-0.012, 0.13, 0.012), (-0.016, 0.105, 0.015), (-0.008, 0.088, 0.017)], r=0.0009)
    score(tooth, [(0.03, 0.11, 0.011), (0.022, 0.094, 0.015), (0.027, 0.078, 0.017)], r=0.0008)
    tooth.sub(Sphere((0.05, 0.116, 0.0), 0.0055), k=0.002)
    # colours: variegated blue-grey enamel, dark chevron "bourlette", pale porous root
    tooth.paint(blotch_prim(16, 0.08, seed=3, stretch=(1.6, 0.25, 1)), ENAMEL2, feather=0.04)
    tooth.paint(blotch_prim(26, 0.28, seed=8, stretch=(1.4, 0.35, 1)), "#34302d", feather=0.03)
    tooth.paint(blotch_prim(12, 0.32, seed=15), "#6a5240", feather=0.04)

    def yc(P):
        return 0.044 + 0.022 * (1 - np.clip(np.abs(P[:, 0]) / 0.09, 0, 1))

    tooth.paint(func_prim(lambda P: P[:, 1] - yc(P) + 0.003), ROOT, gloss=40, feather=0.004)
    tooth.paint(inter_prim(func_prim(lambda P: P[:, 1] - yc(P) + 0.008), blotch_prim(60, 0.15, seed=11)), "#6b533d", gloss=30, feather=0.02)
    tooth.paint(inter_prim(func_prim(lambda P: P[:, 1] - yc(P) + 0.008), blotch_prim(90, 0.45, seed=17)), "#3f3127", gloss=20, feather=0.01)
    tooth.paint(func_prim(lambda P: np.abs(P[:, 1] - yc(P) - 0.004) - 0.0075), BOUR, gloss=120, feather=0.003)
    tooth.paint(func_prim(lambda P: P[:, 1] - 0.008), "#7d644b", gloss=30, feather=0.004)
    m.socket("top", None, (0, 0.198, 0))
    return m


# ==============================================================================================================
# porcelain teapot — blue-and-white glaze, a chipped lid and a barnacle hitch-hiker


def _tp_R(y):
    return 0.12 * np.sqrt(np.clip(1 - ((y - 0.105) / 0.095) ** 2, 0, 1))


def _tp_frame(y, phi, off=0.0):
    """Surface point + (along-phi, up, normal) on the teapot belly."""
    R = _tp_R(y)
    n = _n([np.cos(phi) / 0.12 ** 2 * R, (y - 0.105) / 0.095 ** 2, np.sin(phi) / 0.12 ** 2 * R])
    p = np.array([R * np.cos(phi), y, R * np.sin(phi)]) + n * off
    u = np.array([-np.sin(phi), 0, np.cos(phi)])
    v = _n(np.cross(n, u))
    return p, u, v, n


_TP_BELLY = Ellipsoid((0, 0.105, 0), (0.12, 0.095, 0.12))


def skin_prim(base, lo=-0.0006, hi=0.0024):
    """A thin skin hugging the surface of prim `base` (for pressed-on appliqué)."""
    mid, half = (lo + hi) / 2, (hi - lo) / 2
    return Func(lambda P: np.abs(base(P) - mid) - half, (-9, -9, -9), (9, 9, 9))


def appliqué(m, name, color, prims, base, gloss=200, res=0.0011, decimate=320, lo=-0.0006, hi=0.0024, merge="decor"):
    """Thin pressed-on shapes of coloured clay: union of `prims` clipped to a skin over `base`."""
    pc = m.piece(name, color=color, gloss=gloss, lumps=0.0003, lump_freq=40, mottle=0.03, res=res, decimate=decimate,
                 merge=merge, ao=False)
    for q in prims:
        pc.add(q, k=0.0015)
    pc.inter(skin_prim(base, lo, hi), k=0.0006)
    return pc


def _tp_flower(y, phi, s, petals=8):
    p, u, v, n = _tp_frame(y, phi)
    out = []
    for i in range(petals):
        a = i / petals * TAU + 0.2
        d = np.cos(a) * u + np.sin(a) * v
        out.append(Ellipsoid(p + d * s * 0.92, (s * 0.6, s * 0.33, 0.02), rot=frame_rot(d, np.cross(n, d), n)))
    return out


def _tp_leaf(y, phi, ang, s):
    p, u, v, n = _tp_frame(y, phi)
    d = np.cos(np.radians(ang)) * u + np.sin(np.radians(ang)) * v
    return Ellipsoid(p + d * s, (s * 1.05, s * 0.42, 0.02), rot=frame_rot(d, np.cross(n, d), n))


def _tp_stroke(pts_yphi, w):
    pts = [_tp_frame(y, ph)[0] for y, ph in pts_yphi]
    return Tube(pts, w, samples=5)


def porcelain_teapot():
    m = Model("porcelain_teapot", res=0.0028)
    WHITE, BLUE, BLUE_D, BISQUE = "#f3f1ea", "#2d4fa3", "#1e3477", "#d8cdb8"
    pot = m.piece("pot", color=WHITE, gloss=215, lumps=0.0011, lump_freq=22, dents=9, dent_size=0.018, dent_depth=0.0012,
                  mottle=0.025, decimate=4500)
    pot.add(_TP_BELLY)
    pot.add(Cylinder((0, 0.014, 0), 0.074, 0.014, round=0.005), k=0.022)
    pot.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.002)
    pot.sub(Cylinder((0, 0.205, 0), 0.064, 0.018), k=0.006)
    pot.add(Torus((0, 0.188, 0), 0.068, 0.0075), k=0.008)
    # spout: a swan neck rising from the belly
    pot.add(Tube([(0.085, 0.07, 0), (0.135, 0.09, 0), (0.172, 0.13, 0), (0.197, 0.178, 0)], [0.036, 0.026, 0.018, 0.0145], samples=6), k=0.022)
    pot.add(Torus((0.199, 0.182, 0), 0.0135, 0.004, rot=(0, 0, -30)), k=0.004)
    pot.sub(Capsule((0.192, 0.168, 0), (0.212, 0.2, 0), 0.0085), k=0.003)
    # handle: a loop with a thumb rest
    hpts = [(-0.1, 0.158, 0), (-0.158, 0.174, 0), (-0.196, 0.13, 0), (-0.188, 0.078, 0), (-0.148, 0.05, 0), (-0.105, 0.056, 0)]
    pot.add(Tube(hpts, [0.0135, 0.0135, 0.014, 0.0135, 0.013, 0.013], samples=6), k=0.014)
    pot.add(Ellipsoid((-0.158, 0.183, 0), (0.016, 0.007, 0.012), rot=(0, 0, -12)), k=0.008)
    # barnacles near the foot (it lay on the sea bed a long time)
    for (y, ph, r) in ((0.036, 3.55, 0.0115), (0.052, 3.82, 0.008), (0.03, 3.98, 0.0065)):
        p, u, v, n = _tp_frame(y, ph)
        barnacle(pot, p - n * 0.002, n, r)
    grime(pot, "#a59a7a", r=0.006, thresh=0.12, gloss=70, noise=0.02, feather=0.05)

    # --- blue clay pressed onto the glaze -------------------------------------------------------------------
    def ring(y0, half, rmax=0.13):
        return Func(lambda P: np.maximum(np.abs(P[:, 1] - y0) - half, np.hypot(P[:, 0], P[:, 2]) - rmax),
                    (-0.13, y0 - half, -0.13), (0.13, y0 + half, 0.13))

    swags = []
    for i in range(14):
        ph = i / 14 * TAU + 0.12
        if abs(np.cos(ph)) > 0.9:
            continue
        swags.append(_tp_stroke([(0.162 - 0.015 * np.sin(t * np.pi), ph - 0.21 + t * 0.42) for t in np.linspace(0, 1, 6)], 0.0042))
        swags.append(Sphere(_tp_frame(0.139, ph)[0], 0.0058))
    appliqué(m, "band_top", BLUE, [ring(0.17, 0.0085)] + swags, _TP_BELLY, decimate=1000)
    appliqué(m, "band_foot", BLUE, [ring(0.032, 0.008, 0.125), ring(0.05, 0.0028, 0.125)], _TP_BELLY, decimate=400)
    for side, ph0 in ((1, np.pi / 2), (-1, -np.pi / 2)):
        big = _tp_flower(0.098, ph0, 0.024)
        small = _tp_flower(0.074, ph0 + 0.5 * side, 0.015, petals=6) + _tp_flower(0.12, ph0 - 0.52 * side, 0.014, petals=6)
        vine = [_tp_stroke([(0.066, ph0 - 0.62), (0.058, ph0 - 0.34), (0.064, ph0 - 0.06), (0.056, ph0 + 0.22), (0.066, ph0 + 0.62)], 0.0032)]
        leaves = [_tp_leaf(0.098 + dy, ph0 + dph * side, ang if side > 0 else 180 - ang, s)
                  for (dy, dph, ang, s) in ((0.008, 0.28, 15, 0.014), (-0.028, -0.18, 205, 0.013), (0.03, -0.3, 135, 0.012),
                                            (-0.034, 0.34, -35, 0.011))]
        birds = []
        for (by, bph, s) in ((0.142, ph0 + 0.36 * side, 0.011),):
            p, u, v, n = _tp_frame(by, bph)
            for sgn in (-1, 1):
                birds.append(Tube([p + u * sgn * s * 1.15 + v * s * 0.55, p + u * sgn * s * 0.5 + v * s * 0.2, p], 0.0025, samples=4))
        tag = "F" if side > 0 else "B"
        appliqué(m, f"flower_{tag}", BLUE, big, _TP_BELLY, decimate=480)
        appliqué(m, f"flowers_{tag}", BLUE, small, _TP_BELLY, decimate=460)
        appliqué(m, f"vine_{tag}", BLUE_D, vine + leaves + birds, _TP_BELLY, decimate=620)
        p, u, v, n = _tp_frame(0.098, ph0)
        dot = m.piece(f"eye_{tag}", color=WHITE, gloss=215, lumps=0.0, mottle=0.02, res=0.0011, decimate=120, merge="decor", ao=False)
        dot.add(Sphere(p + n * 0.0016, 0.0085))
        dot.inter(skin_prim(_TP_BELLY, 0.0, 0.0032))
        dot2 = m.piece(f"eye2_{tag}", color=BLUE_D, gloss=215, lumps=0.0, mottle=0.02, res=0.0011, decimate=100, merge="decor", ao=False)
        dot2.add(Sphere(p, 0.0045))
        dot2.inter(skin_prim(_TP_BELLY, 0.0, 0.0042))
    # a rolled blue snake along the handle and round the spout tip
    trim = m.piece("trim", color=BLUE, gloss=205, lumps=0.0003, lump_freq=40, mottle=0.03, res=0.0013, decimate=450, merge="decor")
    trim.add(Tube([(-0.106, 0.169, 0), (-0.158, 0.188, 0), (-0.209, 0.132, 0), (-0.2, 0.074, 0), (-0.152, 0.038, 0)], 0.0034, samples=6))
    trim.add(Torus((0.199, 0.182, 0), 0.0142, 0.0042, rot=(0, 0, -30)))

    lid = m.piece("lid", color=WHITE, gloss=215, lumps=0.001, lump_freq=22, dents=3, dent_size=0.012, dent_depth=0.001,
                  mottle=0.025, res=0.0022, decimate=1000)
    lid.add(Cylinder((0, 0.194, 0), 0.071, 0.0045, round=0.003))
    lid.add(Ellipsoid((0, 0.196, 0), (0.061, 0.029, 0.061)), k=0.008)
    lid.add(Capsule((0, 0.222, 0), (0, 0.232, 0), 0.008), k=0.006)
    lid.inter(HalfSpace((0, 0.1885, 0), (0, -1, 0)))
    lid.sub(Cylinder((0.034, 0.222, 0.0), 0.0035, 0.01), k=0.001)  # steam hole
    lid.sub(Sphere((0.052, 0.198, 0.05), 0.013), k=0.002)  # the chip
    lid.paint(Sphere((0.052, 0.198, 0.05), 0.0145), BISQUE, gloss=30, feather=0.0012)
    lidtop = Ellipsoid((0, 0.196, 0), (0.061, 0.029, 0.061))
    dots = [Sphere((np.cos(a) * 0.047, 0.2125, np.sin(a) * 0.047), 0.0062) for a in np.linspace(0, TAU, 9)[:-1] + 0.3]
    rim = [Func(lambda P: np.maximum(np.abs(np.hypot(P[:, 0], P[:, 2]) - 0.03) - 0.004, np.abs(P[:, 1] - 0.222) - 0.02),
                (-0.04, 0.2, -0.04), (0.04, 0.24, 0.04))]
    appliqué(m, "lid_decor", BLUE, dots + rim, lidtop, decimate=480)
    knob = m.piece("knob", color=BLUE, gloss=215, lumps=0.0006, lump_freq=30, mottle=0.03, res=0.0018, decimate=260, merge="decor")
    knob.add(Ellipsoid((0, 0.243, 0), (0.0165, 0.0145, 0.0165)))
    knob.add(Torus((0, 0.233, 0), 0.01, 0.0035), k=0.003)
    m.socket("top", None, (0, 0.26, 0))
    return m


# ==============================================================================================================
# ship lantern — brass globe lantern with a warm glowing glass and a ring handle


def ship_lantern():
    m = Model("ship_lantern", res=0.0035)
    B, BD, BL = "#b9862c", CP["brass_dk"], "#e6c06a"
    body = m.piece("frame", color=B, gloss=G_METAL, lumps=0.0012, lump_freq=18, dents=12, dent_size=0.016,
                   dent_depth=0.0015, mottle=0.06, decimate=6200)
    # base: stepped dish
    body.add(Cylinder((0, 0.016, 0), 0.098, 0.016, round=0.007))
    body.add(Cylinder((0, 0.038, 0), 0.088, 0.008, round=0.004), k=0.006)
    body.add(Torus((0, 0.05, 0), 0.084, 0.0065), k=0.004)
    body.add(Torus((0, 0.006, 0), 0.096, 0.006), k=0.004)
    # top collar + conical cap with vents, chimney, rain hood
    body.add(Cylinder((0, 0.272, 0), 0.084, 0.01, round=0.004))
    body.add(Torus((0, 0.262, 0), 0.083, 0.0055), k=0.003)
    body.add(Capsule((0, 0.282, 0), (0, 0.33, 0), 0.08, 0.036), k=0.01)
    for i in range(8):
        a = i / 8 * TAU + 0.2
        c = np.array([np.cos(a) * 0.06, 0.305, np.sin(a) * 0.06])
        body.sub(Ellipsoid(c, (0.009, 0.006, 0.009)), k=0.002)
    body.add(Cylinder((0, 0.348, 0), 0.03, 0.02, round=0.004), k=0.006)
    body.add(Cylinder((0, 0.376, 0), 0.046, 0.0055, round=0.004), k=0.002)
    body.add(Ellipsoid((0, 0.384, 0), (0.03, 0.012, 0.03)), k=0.006)
    for i in range(4):
        a = i / 4 * TAU + np.pi / 4
        body.add(Capsule((np.cos(a) * 0.026, 0.355, np.sin(a) * 0.026), (np.cos(a) * 0.036, 0.372, np.sin(a) * 0.036), 0.0035), k=0.003)
    # bail mount and ring handle
    body.add(Capsule((0, 0.39, 0), (0, 0.404, 0), 0.008), k=0.005)
    body.add(Torus((0, 0.433, 0), 0.032, 0.0065, rot=(90, 0, 0)), k=0.004)
    metal(body, BD, mix(B, BL, 0.6), r=0.009, tarnish=0.05, wear=0.1, noise=0.01)
    grime(body, CP["verdigris"], r=0.007, thresh=0.11, gloss=60, noise=0.04, seed=3, feather=0.05)
    for (a, y, r) in ((0.5, 0.02, 0.011), (0.85, 0.016, 0.008), (0.2, 0.012, 0.007), (3.9, 0.02, 0.009)):
        nrm = np.array([np.cos(a), 0.25, np.sin(a)])
        barnacle(body, np.array([np.cos(a) * 0.094, y, np.sin(a) * 0.094]), nrm, r)

    # cage: vertical guard wires bowed round the globe + a mid ring
    cage = m.piece("cage", color="#a87a2a", gloss=G_METAL, lumps=0.0006, lump_freq=30, mottle=0.06, res=0.002, decimate=2600)
    for i in range(4):
        a = i / 4 * TAU + np.pi / 4
        d = np.array([np.cos(a), 0, np.sin(a)])
        pts = [d * 0.08 + (0, 0.05, 0), d * 0.1 + (0, 0.1, 0), d * 0.104 + (0, 0.16, 0), d * 0.1 + (0, 0.22, 0), d * 0.08 + (0, 0.268, 0)]
        cage.add(Tube(pts, 0.0058, samples=6), k=0.002)
    cage.add(Torus((0, 0.16, 0), 0.104, 0.0055), k=0.003)
    cage.add(Torus((0, 0.105, 0), 0.098, 0.004), k=0.003)
    cage.add(Torus((0, 0.215, 0), 0.098, 0.004), k=0.003)
    metal(cage, BD, None, r=0.006, tarnish=0.06, noise=0.02)
    cage.paint(blotch_prim(25, 0.35, seed=4), "#d0a650", gloss=210, feather=0.05)

    # glowing globe (matClass 1): ribbed amber glass, hottest where the flame sits
    gl = m.piece("glass", color="#f2a640", gloss=G_GLASS, mat=1, lumps=0.0006, lump_freq=20, mottle=0.03, res=0.003,
                 decimate=1800, ao=False)
    gl.add(Ellipsoid((0, 0.158, 0), (0.088, 0.122, 0.088)))
    gl.inter(Box((0, 0.158, 0), (0.2, 0.106, 0.2)), k=0.006)
    for y in (0.08, 0.1, 0.12, 0.196, 0.216, 0.236):
        gl.sub(Torus((0, y, 0), 0.09, 0.0028), k=0.003)
    gl.paint(func_prim(lambda P: np.minimum(P[:, 1] - 0.078, 0.24 - P[:, 1])), "#c4782a", feather=0.012)
    gl.paint(Ellipsoid((0, 0.15, 0), (0.2, 0.06, 0.2)), "#ffcf6a", feather=0.02)
    gl.paint(Ellipsoid((0, 0.145, 0), (0.2, 0.028, 0.2)), "#fff0b8", feather=0.015)
    m.socket("flame", None, (0, 0.15, 0))
    m.socket("hang", None, (0, 0.465, 0))
    return m


# ==============================================================================================================
# grand conch — a queen-conch style shell big enough for a hermit-crab kid to move into


def grand_conch():
    m = Model("grand_conch", res=0.0065)
    CREAM, TAN, BROWN, PINK, CORAL, DEEP = "#ead9b4", "#c99a64", "#9a6a3e", "#f4ab92", "#ea8574", "#b85a55"
    sh = m.piece("shell", color=CREAM, gloss=95, lumps=0.003, lump_freq=7, dents=26, dent_size=0.03, dent_depth=0.003,
                 mottle=0.07, decimate=10400)
    X = (1, 0, 0)
    # body whorl: a heavy cone, widest at the knobbly shoulder, tapering to the siphonal canal
    sh.add(Capsule((-0.11, 0.0, 0.0), (0.26, -0.012, 0.0), 0.158, 0.04))
    sh.add(Ellipsoid((-0.1, 0.0, 0.0), (0.095, 0.172, 0.168)), k=0.06)
    sh.add(Capsule((0.24, -0.012, 0.0), (0.33, -0.03, 0.01), 0.032, 0.02), k=0.03)
    # spire: stacked whorls with little knobs, sutures between them
    whorls = [(-0.175, 0.098, 0.024), (-0.215, 0.07, 0.019), (-0.249, 0.047, 0.015), (-0.276, 0.029, 0.011), (-0.295, 0.015, 0.008)]
    sh.add(Capsule((-0.15, 0, 0), (-0.305, 0.0, 0.0), 0.112, 0.007), k=0.025)
    for i, (x, R, r) in enumerate(whorls):
        sh.add(Torus((x, 0, 0), R, r, rot=(0, 0, 90)), k=r * 0.9)
        nk = 9 - i
        for j in range(nk):
            a = j / nk * TAU + i * 0.5
            d = np.array([0, np.cos(a), np.sin(a)])
            sh.add(Sphere(np.array([x, 0, 0]) + d * (R + r * 0.55), r * 0.7), k=r * 0.6)
        if i < len(whorls) - 1:
            xn = 0.5 * (x + whorls[i + 1][0])
            sh.sub(Torus((xn, 0, 0), 0.5 * (R + whorls[i + 1][1]) + 0.002, 0.0028, rot=(0, 0, 90)), k=0.004)
    # the big blunt shoulder knobs (none on the lip side)
    for j, deg in enumerate(np.linspace(-55, 205, 9)):
        a = np.radians(deg)
        d = np.array([0, np.cos(a), -np.sin(a)])
        L = 0.05 + 0.02 * np.sin(j * 1.7) ** 2 + (0.02 if j in (0, 1) else 0)
        base = np.array([-0.1, 0, 0]) + d * 0.12
        tip = np.array([-0.12 - 0.008 * (j % 2), 0, 0]) + d * (0.17 + L * 0.6)
        sh.add(Capsule(base, tip, 0.046, 0.021), k=0.035)
    # growth ridges round the body whorl
    for x in np.linspace(-0.02, 0.24, 9):
        R = 0.15 + (0.034 - 0.15) * (x + 0.11) / 0.38
        sh.sub(Torus((x, -0.012 * (x + 0.11) / 0.38, 0), R + 0.002, 0.0038, rot=(0, 0, 90 + 4 * np.sin(x * 40))), k=0.005)
    # flared lip: a thick dished sheet in front of the body, rising into a wing beside the spire
    lip_o, lip_u, lip_v = np.array([0.0, 0.0, 0.118]), np.array([1.0, 0, 0]), np.array([0, 0.94, -0.34])
    lip_outline = closed_curve([(0.24, -0.04), (0.16, -0.1), (0.04, -0.125), (-0.08, -0.118), (-0.17, -0.07), (-0.22, 0.03),
                                (-0.24, 0.15), (-0.205, 0.225), (-0.13, 0.22), (-0.05, 0.165), (0.06, 0.095), (0.16, 0.04)], 4)
    lip_dish = lambda p2: 0.38 * (0.55 * (p2[:, 0] + 0.06) ** 2 + (p2[:, 1] - 0.03) ** 2)
    lip = Pillow(lip_outline, 0.027, 0.011, 0.05, o=lip_o, u=lip_u, v=lip_v, offset=lip_dish)
    sh.add(lip, k=0.045)
    # aperture: a long opening into the hollow body
    aperture = Ellipsoid((0.05, -0.028, 0.12), (0.2, 0.047, 0.13), rot=(0, 0, -6))
    sh.sub(Capsule((-0.1, 0.0, 0.0), (0.25, -0.01, 0.0), 0.122, 0.02), k=0.02)
    sh.sub(aperture, k=0.02)
    # --- colour -----------------------------------------------------------------------------------------------
    def axial_bands(P):
        w = fbm(P * np.array([6.0, 14.0, 14.0]), 2, 21)
        s = np.sin((P[:, 0] * 55.0 + 2.2 * w) )
        return (0.45 - s) * 0.02
    sh.paint(func_prim(axial_bands), TAN, feather=0.012)
    sh.paint(blotch_prim(16, 0.3, seed=5, stretch=(2.5, 1, 1)), BROWN, feather=0.02)
    sh.paint(Ellipsoid((-0.3, 0, 0), (0.06, 0.06, 0.06)), "#e6b9a0", feather=0.03)
    # glossy pink lip face and the deep coral throat
    front = lip_o + 0.0 * lip_u
    nrm = np.cross(lip_u, lip_v)

    def lip_face(P):
        q = P - lip_o
        p2 = np.column_stack([q @ lip_u, q @ lip_v])
        c = q @ nrm - lip_dish(p2)
        return np.maximum(poly_sdf(p2, lip_outline) - 0.012, -0.004 - c)
    sh.paint(func_prim(lip_face), PINK, gloss=225, feather=0.012)
    sh.paint(Capsule((-0.1, 0.0, 0.0), (0.25, -0.01, 0.0), 0.135, 0.03), CORAL, gloss=200, feather=0.015)
    sh.paint(Capsule((-0.12, 0.0, 0.0), (0.2, -0.01, 0.0), 0.11, 0.03), DEEP, gloss=170, feather=0.02)
    sh.paint(Ellipsoid((0.05, -0.04, 0.16), (0.2, 0.05, 0.05), rot=(0, 0, -6)), "#f6c4ae", gloss=235, feather=0.015)
    grime(sh, "#8f7a5a", r=0.012, thresh=0.12, gloss=40, noise=0.03, feather=0.06)
    # pose: rolled so the pink lip faces the viewer and up; rest it on the table
    rot = (-40, -10, -8)
    pose_piece(sh, rot)
    t = ground_offset([sh], (-0.5, -0.5, -0.5), (0.5, 0.5, 0.5), 0.008)
    pose_piece(sh, None, t)
    m.socket("mouth", None, pose_point(pose_point((0.04, -0.03, 0.16), rot), None, t))
    m.socket("top", None, pose_point(pose_point((-0.1, 0.17, 0.0), rot), None, t))
    return m


# ==============================================================================================================
# sunken crown — gold, pearls, cabochon gems, a velvet cap, seaweed draped over one point, a bit bent


def ring_band(R, half_t, y0, y1, rd=0.002, c=(0, 0, 0)):
    c = np.asarray(c, float)

    def f(P):
        q = P - c
        r = np.hypot(q[:, 0], q[:, 2])
        wx = np.abs(r - R) - (half_t - rd)
        wy = np.abs(q[:, 1] - (y0 + y1) / 2) - ((y1 - y0) / 2 - rd)
        return np.minimum(np.maximum(wx, wy), 0) + np.hypot(np.maximum(wx, 0), np.maximum(wy, 0)) - rd
    e = R + half_t + 0.01
    return Func(f, c + (-e, y0 - 0.01, -e), c + (e, y1 + 0.01, e))


def gem_shape(c, r, out, h=None):
    """A faceted cabochon-ish gem: an ellipsoid trimmed by a few facet planes."""
    out = _n(out)
    h = h or r * 0.55
    R = look_rot(out)
    body = Ellipsoid(c, (r, h, r), rot=R)
    facets = [HalfSpace(np.asarray(c) + out * h * 0.78, out)]
    side = _n(np.cross(out, [0.2, 0.97, 0.1]))
    side2 = np.cross(out, side)
    for i in range(6):
        a = i / 6 * TAU
        d = _n(out * 0.9 + (np.cos(a) * side + np.sin(a) * side2) * 1.2)
        facets.append(HalfSpace(np.asarray(c) + d * r * 0.72, d))
    return body, facets


def sunken_crown():
    m = Model("sunken_crown", res=0.003)
    G, GD, GL = CP["gold"], "#7a4f10", CP["gold_lt"]
    R = 0.122
    gold = m.piece("gold", color=G, gloss=185, lumps=0.0012, lump_freq=14, dents=14, dent_size=0.016, dent_depth=0.0018,
                   mottle=0.05, decimate=6000)
    gold.add(ring_band(R, 0.0065, 0.0, 0.074))
    gold.add(Torus((0, 0.007, 0), R + 0.002, 0.0085), k=0.004)
    gold.add(Torus((0, 0.07, 0), R + 0.002, 0.0072), k=0.004)
    pts = []
    for i in range(8):
        ph = i / 8 * TAU + np.pi / 2
        tall = i % 2 == 0
        d = np.array([np.cos(ph), 0, np.sin(ph)])
        u = np.array([-np.sin(ph), 0, np.cos(ph)])
        lean = 0.1 + (0.12 if i == 2 else 0.0)  # one point bent outward
        v = _n(np.array([0, 1, 0]) + d * lean)
        H = 0.118 if tall else 0.068
        Wd = 0.044 if tall else 0.036
        outline = closed_curve([(-Wd, -0.004), (-Wd * 0.72, H * 0.25), (-Wd * 0.3, H * 0.6), (0.0, H), (Wd * 0.3, H * 0.6),
                                (Wd * 0.72, H * 0.25), (Wd, -0.004)], 4)
        o = d * R + np.array([0, 0.064, 0])
        gold.add(Pillow(outline, 0.0068, 0.0035, 0.014, o=o, u=u, v=v), k=0.006)
        tip = o + v * H
        pts.append((tip, d, u, v, tall, o, H))
        if not tall:
            gold.add(Sphere(tip + v * 0.008, 0.0105), k=0.004)
        # pierced trefoil hole in the tall points
        if tall:
            gold.sub(Sphere(o + v * H * 0.58, 0.0085), k=0.002)
    # bezels for the band gems
    gems_at = []
    for i in range(8):
        ph = i / 8 * TAU + np.pi / 2 + (np.pi / 8)
        d = np.array([np.cos(ph), 0, np.sin(ph)])
        c = d * (R + 0.006) + np.array([0, 0.038, 0])
        gold.add(Torus(c, 0.0145, 0.0035, rot=look_rot(d)), k=0.003)
        gems_at.append((c, d, ["#c41a33", "#1d8f4e", "#2b52b8", "#c41a33"][i % 4]))
    for (tip, d, u, v, tall, o, H) in pts:
        if tall:
            c = o + v * H * 0.3 + d * 0.006
            gold.add(Torus(c, 0.0105, 0.0028, rot=look_rot(d)), k=0.002)
            gems_at.append((c, d, "#2b52b8" if np.dot(d, [1, 0, 0]) > 0.5 else "#1d8f4e"))
    gold.add(Sphere((0, 0.155, 0), 0.016), k=0.004)  # little orb on the cap
    gold.add(Capsule((0, 0.155, 0), (0, 0.183, 0), 0.0045), k=0.003)
    gold.add(Capsule((-0.012, 0.175, 0), (0.012, 0.175, 0), 0.0045), k=0.003)
    # chased band decoration: scored zigzag between the rims
    for i in range(32):
        ph = i / 32 * TAU + 0.1
        if i % 4 == 1:
            continue
        gold.sub(Sphere((np.cos(ph) * (R + 0.0085), 0.022 + 0.032 * (i % 2), np.sin(ph) * (R + 0.0085)), 0.0055), k=0.003)
    gold.sub(Sphere((R + 0.027, 0.035, 0.03), 0.03), k=0.01)  # a knock in the band
    metal(gold, GD, mix(G, GL, 0.55), r=0.011, tarnish=0.05, wear=0.11, noise=0.01, light_gloss=200)
    for (a, y, r) in ((1.0, 0.02, 0.009), (1.25, 0.03, 0.0065), (4.4, 0.016, 0.0075)):
        d = np.array([np.cos(a), 0.15, np.sin(a)])
        barnacle(gold, np.array([np.cos(a) * (R + 0.006), y, np.sin(a) * (R + 0.006)]), d, r)

    pearls = m.piece("pearls", color=CP["pearl"], gloss=240, lumps=0.0002, lump_freq=40, mottle=0.03, res=0.0018, decimate=1500, ao=False)
    for (tip, d, u, v, tall, o, H) in pts:
        if tall:
            pearls.add(Sphere(tip + v * 0.012, 0.0145), k=0.0)
    pearls.paint(func_prim(lambda P: -P[:, 1] + 0.0), "#f1ebe0")
    pearls.paint(blotch_prim(60, 0.25, seed=2), "#f3dfe8", feather=0.1)
    gems = m.piece("gems", color="#c41a33", gloss=250, lumps=0.0002, lump_freq=40, mottle=0.02, res=0.0016, decimate=900, ao=False)
    for c, d, col in gems_at:
        body, facets = gem_shape(c + d * 0.002, 0.0125 if np.linalg.norm(c[[0, 2]]) > R else 0.0095, d)
        gp = m.piece(f"gem_{len(gems.ops)}", color=col, gloss=250, lumps=0.0, mottle=0.02, res=0.0014, decimate=90,
                     merge="gems", ao=False)
        gp.add(body)
        for f in facets:
            gp.inter(f, k=0.0008)
        gp.paint(Sphere(c + d * 0.012 + np.array([0, 0.005, 0]), 0.004), shade(col, 1.45), gloss=255, feather=0.002)
        gems.ops.append(None) if False else None
    m.pieces.remove(gems)

    vel = m.piece("velvet", color="#7a1630", gloss=18, lumps=0.002, lump_freq=12, dents=10, dent_size=0.02, dent_depth=0.003,
                  mottle=0.09, res=0.0045, decimate=1300)
    vel.add(Ellipsoid((0, 0.07, 0), (R - 0.004, 0.08, R - 0.004)))
    vel.inter(HalfSpace((0, 0.03, 0), (0, -1, 0)), k=0.004)
    for i in range(4):
        a = i / 4 * TAU + np.pi / 4
        vel.sub(Capsule((np.cos(a) * 0.06, 0.16, np.sin(a) * 0.06), (np.cos(a) * 0.125, 0.09, np.sin(a) * 0.125), 0.008), k=0.012)
    vel.paint(blotch_prim(30, 0.25, seed=7), "#952440", feather=0.06)

    weed = m.piece("seaweed", color=CP["kelp"], gloss=150, lumps=0.0008, lump_freq=30, mottle=0.08, res=0.0022, decimate=1100)
    tip0 = pts[2][0]
    d0 = pts[2][1]
    ribbon(weed, [tip0 + (0, 0.006, 0) - d0 * 0.014, tip0 + d0 * 0.02 + (0, -0.004, 0), tip0 + d0 * 0.036 + (0, -0.05, 0),
                  tip0 + d0 * 0.052 + (0, -0.11, 0.012), tip0 + d0 * 0.08 + (0, -0.17, 0.0), tip0 + d0 * 0.15 + (0.0, -0.2, 0.04),
                  tip0 + d0 * 0.22 + (0.02, -0.21, 0.07)],
           [0.012, 0.018, 0.022, 0.024, 0.026, 0.024, 0.016], 0.0016, up=d0, k=0.004, seed=3, frill=0.35)
    ribbon(weed, [tip0 - d0 * 0.012 + (0, 0.006, 0), tip0 - d0 * 0.032 + (0.0, -0.02, 0), tip0 - d0 * 0.05 + (0.004, -0.065, 0),
                  tip0 - d0 * 0.055 + (0.012, -0.1, 0)],
           [0.008, 0.013, 0.012, 0.007], 0.0015, up=d0, k=0.003, seed=4, frill=0.35)
    weed.paint(blotch_prim(40, 0.2, seed=6), CP["kelp_dk"], feather=0.05)
    weed.paint(func_prim(lambda P: 0.04 - P[:, 1]), "#7d8a3a", feather=0.04)

    # pose: tipped over a little onto one side, resting on the sea-bed table
    rot = (-7, 18, 11)
    allp = [p for p in m.pieces]
    for pc in allp:
        pose_piece(pc, rot)
    t = ground_offset([gold], (-0.3, -0.3, -0.3), (0.3, 0.4, 0.3), 0.006)
    for pc in allp:
        pose_piece(pc, None, t)
    weed.inter(HalfSpace((0, 0.0015, 0), (0, -1, 0)), k=0.002)
    m.socket("top", None, pose_point(pose_point((0, 0.2, 0), rot), None, t))
    return m


# ==============================================================================================================
# treasure chest — iron-banded, lid thrown open (bone `lid`), heaped and spilling with gold


def treasure_chest():
    m = Model("treasure_chest", res=0.004)
    W, D, H = 0.28, 0.17, 0.28   # half width, half depth, height
    WOOD, WOOD_D, IRON, IRON_D, RUST = "#7f5230", "#4a2d18", "#3f3d3c", "#252424", "#8e4a26"
    hinge = np.array([0, H, -D])
    m.bone("root")
    m.bone("lid", "root", hinge)
    LID_ROT = (-104, 0, 0)

    def lidp(p):
        return pose_point(p, LID_ROT, (0, 0, 0), hinge)

    # --- box ---------------------------------------------------------------------------------------------------
    box = m.piece("chest", color=WOOD, gloss=40, lumps=0.003, lump_freq=8, dents=22, dent_size=0.03, dent_depth=0.003,
                  mottle=0.09, decimate=2800)
    box.add(Box((0, H / 2, 0), (W, H / 2, D), round=0.014))
    box.sub(Box((0, H / 2 + 0.04, 0), (W - 0.024, H / 2, D - 0.024), round=0.01), k=0.006)
    for y in (0.072, 0.142, 0.212):
        for zs in (1, -1):
            box.sub(Box((0, y, zs * (D + 0.002)), (W + 0.01, 0.0035, 0.004), round=0.002), k=0.003)
        for xs in (1, -1):
            box.sub(Box((xs * (W + 0.002), y, 0), (0.004, 0.0035, D + 0.01), round=0.002), k=0.003)
    box.paint(grain_prim((1, 0, 0), freq=70, seed=2), WOOD_D, feather=0.004)
    box.paint(blotch_prim(9, 0.25, seed=12), "#6f6a50", feather=0.06)   # sea-greyed patches
    grime(box, "#2f2116", r=0.012, thresh=0.1, noise=0.03, feather=0.05)
    box.paint(inter_prim(func_prim(lambda P: P[:, 1] - 0.055 - 0.03 * fbm(P * 14, 2, 4)), blotch_prim(16, -0.1, seed=14)), "#5a6a33", gloss=70, feather=0.03)  # algae
    for (x, y, zs, r) in ((0.2, 0.05, 1, 0.012), (0.225, 0.075, 1, 0.009), (0.17, 0.035, 1, 0.008), (-0.26, 0.06, 0, 0.011)):
        if zs:
            barnacle(box, (x, y, D + 0.002), (0, 0.1, 1), r)
        else:
            barnacle(box, (-W - 0.002, y, 0.06), (-1, 0.1, 0), r)

    # --- iron furniture -------------------------------------------------------------------------------------
    ir = m.piece("bands", color=IRON, gloss=110, lumps=0.0015, lump_freq=12, dents=12, dent_size=0.02, dent_depth=0.0015,
                 mottle=0.08, res=0.0028, decimate=2000)
    for xs in (-0.17, 0.17):
        ir.add(Box((xs, H / 2 - 0.003, 0), (0.022, H / 2 + 0.003, D + 0.006), round=0.004))
        ir.sub(Box((xs, H / 2 + 0.02, 0), (0.03, H / 2 + 0.02, D - 0.0005), round=0.002), k=0.001)
        ir.sub(Box((xs, -0.05, 0), (0.03, 0.05, D - 0.0005)), k=0.001)
    rim = Box((0, H - 0.017, 0), (W + 0.006, 0.017, D + 0.006), round=0.004)
    ir.add(rim, k=0.003)
    ir.sub(Box((0, H - 0.01, 0), (W - 0.0005, 0.04, D - 0.0005)), k=0.001)
    for xs in (-1, 1):   # corner caps at the foot
        for zs in (-1, 1):
            ir.add(Box((xs * (W - 0.02), 0.026, zs * (D - 0.02)), (0.028, 0.03, 0.028), round=0.006), k=0.002)
    ir.sub(Box((0, H / 2 + 0.03, 0), (W - 0.0005, H / 2, D - 0.0005)), k=0.001)
    ir.add(Box((0, 0.2, D + 0.005), (0.042, 0.05, 0.007), round=0.008), k=0.003)  # lock plate
    ir.sub(Capsule((0, 0.19, D + 0.012), (0, 0.172, D + 0.012), 0.005), k=0.001)
    ir.sub(Sphere((0, 0.198, D + 0.012), 0.0085), k=0.001)
    for xs in (-1, 1):   # side ring handles
        ir.add(Box((xs * (W + 0.006), 0.2, 0), (0.007, 0.022, 0.03), round=0.004), k=0.002)
        ir.add(Torus((xs * (W + 0.016), 0.17, 0), 0.03, 0.0065, rot=(0, 0, 90)), k=0.002)
    rivets = []
    for xs in (-0.17, 0.17):
        for y in (0.035, 0.1, 0.165, 0.23):
            for zs in (1, -1):
                rivets.append((xs, y, zs * (D + 0.007)))
    for x in np.linspace(-0.25, 0.25, 7):
        rivets.append((x, H - 0.016, D + 0.0075))
    for r in rivets:
        ir.add(Sphere(r, 0.0062), k=0.002)
    metal(ir, IRON_D, "#7b7670", r=0.006, tarnish=0.05, wear=0.09, noise=0.02, light_gloss=150)
    ir.paint(blotch_prim(18, 0.3, seed=9), RUST, gloss=40, feather=0.05)
    ir.paint(blotch_prim(30, 0.45, seed=10), "#b0672f", gloss=30, feather=0.04)

    # --- lid (rigid to bone `lid`): curved planked top, iron straps, hasp ------------------------------------
    lid = m.piece("lid", color=WOOD, gloss=40, rigid="lid", lumps=0.003, lump_freq=8, dents=12, dent_size=0.03,
                  dent_depth=0.003, mottle=0.09, decimate=1400)
    LC, LR = np.array([0, H - 0.1, 0]), 0.2
    lid.add(Cylinder(LC, LR, W, rot=(0, 0, 90), round=0.012))
    lid.inter(HalfSpace((0, H + 0.002, 0), (0, -1, 0)), k=0.004)
    lid.inter(Box((0, H + 0.06, 0), (W, 0.07, D), round=0.01), k=0.004)
    lid.sub(Cylinder(LC, LR - 0.022, W - 0.022, rot=(0, 0, 90)), k=0.006)
    for a in (-0.5, -0.17, 0.17, 0.5):
        nn = np.array([0, np.cos(a), np.sin(a)])
        lid.sub(Capsule(LC + nn * (LR + 0.002) + (-W - 0.01, 0, 0), LC + nn * (LR + 0.002) + (W + 0.01, 0, 0), 0.0035), k=0.003)
    lid.paint(grain_prim((1, 0, 0), freq=70, seed=5), WOOD_D, feather=0.004)
    lid.paint(blotch_prim(9, 0.25, seed=13), "#6f6a50", feather=0.06)
    lid.paint(Cylinder(LC, LR - 0.012, W - 0.012, rot=(0, 0, 90)), "#3a2414", feather=0.01)   # dark inside
    lb = m.piece("lid_bands", color=IRON, gloss=110, rigid="lid", lumps=0.0015, lump_freq=12, dents=6, dent_size=0.02,
                 dent_depth=0.0015, mottle=0.08, res=0.0028, decimate=900)
    for xs in (-0.17, 0.17):
        lb.add(Cylinder((xs, LC[1], 0), LR + 0.006, 0.022, rot=(0, 0, 90), round=0.004))
        lb.sub(Cylinder((xs, LC[1], 0), LR - 0.0005, 0.03, rot=(0, 0, 90)), k=0.001)
    lb.add(Box((0, H + 0.012, 0), (W + 0.006, 0.012, D + 0.006), round=0.004), k=0.002)
    lb.sub(Box((0, H + 0.012, 0), (W - 0.0005, 0.03, D - 0.0005)), k=0.001)
    lb.inter(HalfSpace((0, H + 0.0005, 0), (0, -1, 0)), k=0.001)
    lb.inter(Box((0, H + 0.08, 0), (W + 0.01, 0.09, D + 0.01)), k=0.001)
    lb.add(Box((0, H + 0.0, D + 0.008), (0.016, 0.034, 0.005), round=0.004), k=0.002)  # hasp
    for xs in (-0.17, 0.17):
        for a in (-0.6, -0.2, 0.2, 0.6):
            nn = np.array([0, np.cos(a), np.sin(a)])
            lb.add(Sphere((xs, 0, 0) + LC * (0, 1, 1) + nn * (LR + 0.007), 0.0062), k=0.002)
    metal(lb, IRON_D, "#7b7670", r=0.006, tarnish=0.05, wear=0.09, noise=0.02, light_gloss=150)
    lb.paint(blotch_prim(18, 0.3, seed=19), RUST, gloss=40, feather=0.05)
    for pc in (lid, lb):
        pose_piece(pc, LID_ROT, (0, 0, 0), hinge)

    # --- the hoard: a heaped mound of coins inside, a cascade over the front and a spill on the ground ------
    rng = np.random.default_rng(7)
    G, GD, GL = CP["gold"], "#7d5212", CP["gold_lt"]
    heap = m.piece("gold", color=G, gloss=190, lumps=0.0008, lump_freq=14, mottle=0.06, res=0.003, decimate=2100, merge="gold")
    mc, mr = np.array([0.0, 0.25, 0.0]), np.array([0.245, 0.105, 0.148])
    heap.add(Ellipsoid(mc, mr))
    heap.add(Ellipsoid((0.05, 0.3, 0.07), (0.12, 0.06, 0.1)), k=0.03)
    dirs = rng.normal(size=(4000, 3))
    dirs[:, 1] = np.abs(dirs[:, 1]) * 1.4
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    cand = mc + mr * dirs
    ok = cand[:, 1] > H - 0.008
    cn = _n(1) if False else None
    nrms = dirs / mr
    nrms /= np.linalg.norm(nrms, axis=1, keepdims=True)
    C, N = scatter_on(cand[ok] + nrms[ok] * 0.002, nrms[ok], 0.031, rng, tilt=0.38, n_max=170)
    heap.add(CoinPile(C, N, rng.uniform(0.021, 0.026, len(C)), th=0.0038), k=0.0015)
    spill = m.piece("gold_spill", color=G, gloss=190, lumps=0.0008, lump_freq=14, mottle=0.06, res=0.0028, decimate=1300, merge="gold")
    path = np.array([(0.06, 0.29, 0.13), (0.085, 0.272, 0.19), (0.1, 0.18, 0.2), (0.12, 0.08, 0.21), (0.14, 0.014, 0.25)])
    spill.add(Tube(path, [0.022, 0.018, 0.012, 0.012, 0.016], samples=5))
    spill.add(Ellipsoid((0.15, 0.0, 0.29), (0.09, 0.016, 0.065)), k=0.02)
    spill.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.002)
    dense = smooth_curve(path, 6)
    SC, SN = [], []
    for i in range(1, len(dense)):
        for j in range(2):
            c = dense[i] + rng.normal(0, 0.012, 3) * (1, 0.5, 0.6) + (0, 0, 0.012)
            SC.append(c)
            SN.append(_n(np.array([0, 0.4, 1.0]) + rng.normal(0, 0.8, 3)))
    for i in range(26):   # a little drift of coins on the ground in front, some leaning on others
        a, rr = rng.uniform(0, TAU), np.sqrt(rng.uniform(0, 1)) * 0.11
        c = np.array([0.15 + np.cos(a) * rr * 1.3, 0.0, 0.3 + np.sin(a) * rr * 0.8])
        c[1] = 0.004 + 0.016 * max(0, 1 - rr / 0.08) + rng.uniform(0, 0.006)
        SC.append(c)
        SN.append(_n(np.array([0, 1, 0]) + rng.normal(0, 0.3, 3)))
    for (c, tilt) in (((0.0, 0.016, 0.27), 70), ((0.27, 0.014, 0.25), -55), ((-0.07, 0.004, 0.33), 5), ((0.3, 0.004, 0.36), 10)):
        SC.append(np.asarray(c))
        SN.append(euler((tilt, 30, 0)) @ np.array([0, 1, 0]))
    spill.add(CoinPile(SC, SN, rng.uniform(0.02, 0.025, len(SC)), th=0.0038), k=0.0015)
    for pc in (heap, spill):
        metal(pc, GD, None, r=0.008, tarnish=0.04, noise=0.01)
        pc.paint(blotch_prim(22, 0.3, seed=31), "#f0c855", gloss=230, feather=0.05)
    # a rope of pearls draped over the front edge, and two fat gems
    pr = m.piece("pearls", color=CP["pearl"], gloss=240, lumps=0.0002, lump_freq=40, mottle=0.03, res=0.0018, decimate=700, ao=False)
    strand = smooth_curve(np.array([(-0.17, 0.318, 0.06), (-0.12, 0.31, 0.15), (-0.08, 0.286, 0.19), (-0.06, 0.22, 0.195),
                                    (-0.035, 0.18, 0.192), (-0.01, 0.215, 0.19), (0.02, 0.29, 0.18), (0.03, 0.33, 0.12)]), 6)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(strand, axis=0), axis=1))]
    for sv in np.arange(0, seg[-1], 0.017):
        c = np.array([np.interp(sv, seg, strand[:, i]) for i in range(3)])
        pr.add(Sphere(c, 0.0082), k=0.0)
    pr.paint(blotch_prim(60, 0.25, seed=2), "#f3dfe8", feather=0.1)
    for j, (c, col, r) in enumerate((((-0.07, 0.36, 0.07), "#c41a33", 0.03), ((0.14, 0.345, 0.02), "#1d8f4e", 0.026))):
        body, facets = gem_shape(c, r, (0.1, 1, 0.3), h=r * 0.75)
        gp = m.piece(f"gem{j}", color=col, gloss=250, lumps=0.0, mottle=0.02, res=0.0022, decimate=160, merge="gems", ao=False)
        gp.add(body)
        for f in facets:
            gp.inter(f, k=0.0008)
        gp.paint(Sphere(np.asarray(c) + (0.0, r * 0.6, r * 0.35), r * 0.3), shade(col, 1.5), gloss=255, feather=0.003)
    m.socket("loot", None, (0, 0.36, 0))
    m.socket("lid_top", "lid", lidp((0, H + 0.1, 0)))
    return m


# ==============================================================================================================
# sextant — brass frame standing on its arc: silver scale, index arm, mirrors, telescope, wooden handle


def sextant():
    m = Model("sextant", res=0.0024)
    B, BD, BL = "#a8792e", "#4f3712", "#d6aa52"
    PATINA = "#7c5b22"
    P0 = np.array([0.0, 0.3, 0.0])
    Ra = 0.235
    A = np.radians(31)

    def arc(rad, a):
        return P0 + rad * np.array([np.sin(a), -np.cos(a), 0])

    fr = m.piece("frame", color=B, gloss=G_METAL, lumps=0.0008, lump_freq=18, dents=12, dent_size=0.014, dent_depth=0.0012,
                 mottle=0.06, decimate=5200)
    outline = [P0[:2] + (0, 0.018)] + [arc(Ra + 0.018, a)[:2] for a in np.linspace(-A - 0.02, A + 0.02, 13)]
    outline = closed_curve(np.array(outline)[::-1], 2)
    fr.add(Pillow(outline, 0.0045, 0.0028, 0.006, o=(0, 0, 0)))
    # openwork: windows between the spokes, leaving a lattice of bars and a ring
    def window(a0, a1, r0, r1):
        pts = [arc(r0, a)[:2] for a in np.linspace(a0, a1, 6)] + [arc(r1, a)[:2] for a in np.linspace(a1, a0, 6)]
        return Pillow(closed_curve(np.array(pts), 2), 0.02, 0.02, 0.001)
    for (a0, a1) in ((-A + 0.06, -0.03), (0.03, A - 0.06)):
        fr.sub(window(a0, a1, 0.055, 0.105), k=0.004)
        fr.sub(window(a0, a1, 0.125, Ra - 0.03), k=0.004)
    fr.add(Torus(arc(0.155, 0.0), 0.024, 0.0045, rot=(90, 0, 0)), k=0.003)
    # the limb: a thick curved bar carrying the scale
    def limb(P):
        q = P - P0
        rr = np.hypot(q[:, 0], q[:, 1])
        ang = np.arctan2(q[:, 0], -q[:, 1])
        wx = np.abs(rr - Ra) - 0.016
        wy = np.abs(q[:, 2] - 0.001) - 0.0065
        wa = (np.abs(ang) - (A + 0.02)) * Ra
        d = np.minimum(np.maximum(np.maximum(wx, wy), wa), 0) + np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wy, 0) ** 2 + np.maximum(wa, 0) ** 2)
        return d - 0.002
    fr.add(Func(limb, P0 + (-0.16, -0.26, -0.02), P0 + (0.16, -0.18, 0.02)), k=0.004)
    # mounts for the telescope ring and the horizon mirror, pivot boss
    fr.add(Cylinder(P0 + (0, 0, 0.006), 0.017, 0.007, rot=(90, 0, 0), round=0.003), k=0.004)
    hm = arc(0.12, -A + 0.05) + (0, 0, 0.012)
    fr.add(Box(hm + (0.005, 0, 0.004), (0.004, 0.026, 0.016), round=0.003), k=0.003)
    tc = arc(0.12, A - 0.07)
    fr.add(Capsule(tc + (0, 0, 0.004), tc + (0, 0.0, 0.034), 0.006), k=0.003)
    fr.add(Torus(tc + (0, 0.0, 0.044), 0.015, 0.004, rot=(0, 0, 90)), k=0.002)
    # three little legs on the back and the handle posts
    for a, rr in ((-A + 0.08, Ra - 0.01), (A - 0.08, Ra - 0.01), (0.0, 0.06)):
        q = arc(rr, a)
        fr.add(Capsule(q + (0, 0, -0.004), q + (0, 0, -0.022), 0.0055, 0.0045), k=0.003)
    fr.paint(blotch_prim(7, 0.05, seed=24), PATINA, gloss=120, feather=0.08)
    metal(fr, BD, None, r=0.006, tarnish=0.05, noise=0.01)
    fr.paint(blotch_prim(14, 0.3, seed=21), BL, gloss=215, feather=0.06)
    grime(fr, CP["verdigris"], r=0.008, thresh=0.22, gloss=60, noise=0.02, seed=4, feather=0.04)

    # silver scale inlaid on the limb, ticks scored every 2 degrees, longer every 10
    sc = m.piece("scale", color="#d6d8da", gloss=200, lumps=0.0002, lump_freq=30, mottle=0.04, res=0.0012, decimate=1500)
    def strip(P):
        q = P - P0
        rr = np.hypot(q[:, 0], q[:, 1])
        ang = np.arctan2(q[:, 0], -q[:, 1])
        wx = np.abs(rr - Ra) - 0.0095
        wy = np.abs(q[:, 2] - 0.0088) - 0.0022
        wa = (np.abs(ang) - A) * Ra
        return np.minimum(np.maximum(np.maximum(wx, wy), wa), 0) + np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wy, 0) ** 2 + np.maximum(wa, 0) ** 2) - 0.0005
    sc.add(Func(strip, P0 + (-0.16, -0.26, 0.0), P0 + (0.16, -0.2, 0.02)))
    sc.paint(blotch_prim(30, 0.35, seed=2), "#b3b8bd", feather=0.05)
    for i, a in enumerate(np.linspace(-A + 0.02, A - 0.02, 27)):
        long = i % 5 == 0
        p0 = arc(Ra - 0.0085, a) + (0, 0, 0.0108)
        p1 = arc(Ra - (0.0005 if long else 0.0045), a) + (0, 0, 0.0108)
        tk = m.piece(f"tick{i}", color="#2e3034", gloss=120, lumps=0.0, mottle=0.02, res=0.0008, decimate=40, merge="ticks", ao=False)
        tk.add(Capsule(p0, p1, 0.0011 if long else 0.0008))

    # index arm swung a little to one side, with vernier and micrometer drum
    ang = np.radians(9)
    arm = m.piece("index_arm", color=B, gloss=G_METAL, lumps=0.0006, lump_freq=18, mottle=0.06, res=0.002, decimate=1900)
    tip = arc(Ra - 0.004, ang)
    d = _n(tip - P0)
    side = np.cross(d, [0, 0, 1])
    arm.add(Box((P0 + tip) / 2 + (0, 0, 0.012), (0.0085, np.linalg.norm(tip - P0) / 2, 0.0028), rot=frame_rot(side, d, (0, 0, 1)), round=0.002))
    arm.add(Cylinder(P0 + (0, 0, 0.016), 0.022, 0.004, rot=(90, 0, 0), round=0.002), k=0.003)
    arm.add(Box(tip + (0, 0, 0.014), (0.024, 0.014, 0.003), rot=frame_rot(side, d, (0, 0, 1)), round=0.003), k=0.003)
    arm.add(Cylinder(tip - d * 0.03 + side * 0.022 + (0, 0, 0.018), 0.012, 0.006, rot=frame_rot(d, side, (0, 0, 1)) @ euler((0, 0, 90)), round=0.003), k=0.002)
    for i in range(12):
        a2 = i / 12 * TAU
        cdir = np.cos(a2) * d + np.sin(a2) * np.array([0, 0, 1])
        arm.sub(Sphere(tip - d * 0.03 + side * 0.028 + (0, 0, 0.018) + cdir * 0.012, 0.0022), k=0.001)
    arm.add(Capsule(tip - d * 0.03 + side * 0.009 + (0, 0, 0.018), tip - d * 0.03 + side * 0.018 + (0, 0, 0.018), 0.004), k=0.002)
    # index mirror frame standing on the pivot
    mframe = P0 + d * 0.004 + (0, 0.02, 0.026)
    arm.add(Box(mframe + (0.004, 0, 0), (0.005, 0.03, 0.022), round=0.003), k=0.003)
    arm.paint(blotch_prim(7, 0.05, seed=25), PATINA, gloss=120, feather=0.08)
    metal(arm, BD, None, r=0.006, tarnish=0.05, noise=0.01)
    arm.paint(blotch_prim(14, 0.3, seed=22), BL, gloss=215, feather=0.06)

    mir = m.piece("mirrors", color="#cfd8de", gloss=255, lumps=0.0, mottle=0.02, res=0.0013, decimate=500, ao=False)
    mir.add(Box(mframe + (-0.0035, 0, 0), (0.003, 0.025, 0.018), round=0.0018))
    mir.add(Box(hm + (0.0, 0, 0.012), (0.003, 0.021, 0.014), round=0.0018))
    mir.paint(func_prim(lambda P: P[:, 1] - hm[1]), "#9fb8c0", gloss=255)

    # telescope across the frame toward the horizon mirror
    tel = m.piece("telescope", color=B, gloss=G_METAL, lumps=0.0006, lump_freq=18, mottle=0.06, res=0.0022, decimate=1300)
    ta, tb = tc + (0.06, 0.004, 0.044), tc + (-0.075, 0.012, 0.044)
    tel.add(Capsule(ta, tb, 0.0125, 0.0105))
    tel.add(Cylinder(ta, 0.016, 0.009, rot=look_rot(tb - ta), round=0.003), k=0.002)
    tel.add(Cylinder(tb, 0.013, 0.006, rot=look_rot(tb - ta), round=0.003), k=0.002)
    for f in (0.3, 0.62):
        tel.add(Torus(ta + (tb - ta) * f, 0.0128, 0.0028, rot=look_rot(tb - ta)), k=0.002)
    tel.sub(Sphere(ta + _n(ta - tb) * 0.012, 0.009), k=0.002)
    tel.paint(blotch_prim(7, 0.05, seed=26), PATINA, gloss=120, feather=0.08)
    metal(tel, BD, mix(B, BL, 0.6), r=0.012, tarnish=0.05, wear=0.12, noise=0.01, light_gloss=215)
    tel.paint(Sphere(ta + _n(ta - tb) * 0.006, 0.0095), "#1c1d22", gloss=240, feather=0.002)

    # coloured sun shades on hinges in front of the horizon mirror
    for j, col in enumerate(("#b8352e", "#3f7d5a", "#5a6b8f")):
        sh = m.piece(f"shade{j}", color=col, gloss=245, lumps=0.0, mottle=0.03, res=0.0014, decimate=110, merge="shades", ao=False)
        c = hm + (0.03 + j * 0.0075, 0.0, 0.012)
        sh.add(Cylinder(c, 0.0125, 0.0018, rot=(0, 90 - 12 * j, 0), round=0.0012))

    # varnished wooden handle on the back
    hd = m.piece("handle", color="#5a3420", gloss=150, lumps=0.0012, lump_freq=14, dents=5, dent_size=0.012, dent_depth=0.0012,
                 mottle=0.08, res=0.0028, decimate=1100)
    hb = P0 + (-0.03, -0.12, -0.055)
    ht = P0 + (-0.045, -0.02, -0.055)
    hd.add(Capsule(hb, ht, 0.015, 0.0135))
    hd.add(Ellipsoid((hb + ht) / 2 + (0.002, 0, 0), (0.0175, 0.04, 0.0175)), k=0.02)
    for q in (hb, ht):
        hd.add(Capsule(q + (0, 0, 0.004), q + (0.01, 0.0, 0.052), 0.0045), k=0.004, color=B, gloss=G_METAL)
    hd.paint(grain_prim((0, 1, 0), freq=110, seed=3), "#3a2014", feather=0.004)

    t = ground_offset([fr], (-0.3, -0.1, -0.2), (0.3, 0.4, 0.2), 0.004)
    t[0], t[2] = 0.0, 0.0
    for pc in m.pieces:
        pose_piece(pc, None, t)
    m.socket("eyepiece", None, pose_point(ta, None, t))
    return m


# ==============================================================================================================
# music box — wooden box, lid open with a mirror (bone `lid`), a tiny dancer (bone `dancer`), a wind-up key (bone `key`)


def music_box():
    m = Model("music_box", res=0.0024)
    W, D, H = 0.13, 0.085, 0.13          # half width, half depth, top of the box
    F = 0.016                              # foot height
    WOOD, WOOD_D, INLAY, BR, BRD = "#7c3d22", "#4a2213", "#e3c08a", "#b07c26", "#553a12"
    VEL = "#8f1d3a"
    m.bone("root")
    hinge = np.array([0, H, -D])
    m.bone("lid", "root", hinge)
    plinth = np.array([0.03, 0.067, 0.012])
    m.bone("dancer", "root", plinth)
    keyc = np.array([W + 0.004, 0.07, 0.0])
    m.bone("key", "root", keyc)
    LID_ROT = (-100, 0, 0)

    box = m.piece("box", color=WOOD, gloss=135, lumps=0.0007, lump_freq=12, dents=12, dent_size=0.016, dent_depth=0.0014,
                  mottle=0.07, decimate=2600)
    box.add(Box((0, (F + H) / 2, 0), (W, (H - F) / 2, D), round=0.008))
    box.add(Box((0, F + 0.008, 0), (W + 0.006, 0.008, D + 0.006), round=0.005), k=0.003)   # moulded base
    box.add(Box((0, H - 0.005, 0), (W + 0.003, 0.005, D + 0.003), round=0.003), k=0.002)    # top rim
    box.sub(Box((0, H, 0), (W - 0.012, H - 0.062, D - 0.012), round=0.004), k=0.003)
    box.paint(grain_prim((1, 0, 0), freq=90, seed=8), WOOD_D, feather=0.004)
    box.paint(Box((0, H - 0.06, 0), (W - 0.0115, H - 0.06, D - 0.0115)), "#3c1a0e", feather=0.004)
    grime(box, "#2d150b", r=0.006, thresh=0.1, noise=0.02, feather=0.05)

    # inlay: pale wood stringing round the front panel, a diamond on each side, an escutcheon
    inl = m.piece("inlay", color=INLAY, gloss=150, lumps=0.0002, lump_freq=30, mottle=0.04, res=0.0012, decimate=900)
    def frame_strip(c, hw, hh, axis):
        a, b = np.asarray(c, float), None
        return [Box(a + (0, hh, 0), (hw, 0.0022, 0.0018) if axis == "z" else (0.0018, 0.0022, hw)),
                Box(a - (0, hh, 0), (hw, 0.0022, 0.0018) if axis == "z" else (0.0018, 0.0022, hw)),
                Box(a + ((hw, 0, 0) if axis == "z" else (0, 0, hw)), (0.0022, hh, 0.0018) if axis == "z" else (0.0018, hh, 0.0022)),
                Box(a - ((hw, 0, 0) if axis == "z" else (0, 0, hw)), (0.0022, hh, 0.0018) if axis == "z" else (0.0018, hh, 0.0022))]
    for q in frame_strip((0, 0.077, D + 0.0002), W - 0.018, 0.033, "z"):
        inl.add(q, k=0.001)
    for xs in (1, -1):
        c = np.array([xs * (W + 0.0002), 0.077, 0])
        inl.add(Box(c, (0.0018, 0.022, 0.022), rot=(45, 0, 0), round=0.002), k=0.001)
        inl.sub(Box(c + (xs * 0.002, 0, 0), (0.003, 0.015, 0.015), rot=(45, 0, 0), round=0.001), k=0.0008)
    inl.add(Box((0, 0.077, D + 0.0004), (0.016, 0.0018, 0.0016), rot=(0, 0, 45)), k=0.001)
    inl.add(Box((0, 0.077, D + 0.0004), (0.016, 0.0018, 0.0016), rot=(0, 0, -45)), k=0.001)
    inl.paint(blotch_prim(40, 0.2, seed=3), "#cfa66e", feather=0.05)

    # brass: corner caps, bun feet, the plinth and the music cylinder + comb at the back of the well
    br = m.piece("brass", color=BR, gloss=G_METAL, lumps=0.0006, lump_freq=18, mottle=0.06, res=0.0018, decimate=2300)
    for xs in (-1, 1):
        for zs in (-1, 1):
            br.add(Sphere((xs * (W - 0.01), 0.009, zs * (D - 0.01)), 0.011), k=0.002)
            br.add(Box((xs * (W + 0.002), H - 0.012, zs * (D + 0.002)), (0.011, 0.012, 0.011), round=0.003), k=0.002)
    br.add(Cylinder(plinth - (0, 0.005, 0), 0.02, 0.006, round=0.003), k=0.002)
    br.add(Box((-0.045, 0.072, -0.04), (0.06, 0.006, 0.02), round=0.003), k=0.002)    # bedplate
    cyl_c = np.array([-0.045, 0.087, -0.045])
    br.add(Cylinder(cyl_c, 0.011, 0.045, rot=(0, 0, 90), round=0.002), k=0.002)
    rng = np.random.default_rng(3)
    for i in range(36):
        a = rng.uniform(0, TAU)
        x = rng.uniform(-0.04, 0.04)
        br.add(Sphere(cyl_c + (x, np.cos(a) * 0.0115, np.sin(a) * 0.0115), 0.0017), k=0.0006)
    for i in range(11):
        x = -0.085 + i * 0.008
        br.add(Box((x, 0.083, -0.027), (0.0028, 0.0012, 0.012), round=0.0008), k=0.0008, color="#b9bcbf", gloss=210)
    br.add(Torus((0, 0.077, D + 0.0012), 0.0085, 0.0022, rot=(90, 0, 0)), k=0.001)    # escutcheon
    metal(br, BRD, "#d8aa4c", r=0.01, tarnish=0.05, wear=0.13, noise=0.01, light_gloss=215)

    vel = m.piece("velvet", color=VEL, gloss=20, lumps=0.0012, lump_freq=16, dents=8, dent_size=0.012, dent_depth=0.0015,
                  mottle=0.09, res=0.0024, decimate=900)
    vel.add(Box((0.03, 0.065, 0.018), (0.088, 0.004, 0.052), round=0.004))
    vel.add(Box((0, 0.1, D - 0.0135), (W - 0.013, 0.033, 0.0015), round=0.0015), k=0.002)
    for xs in (-1, 1):
        vel.add(Box((xs * (W - 0.0135), 0.1, 0.0), (0.0015, 0.033, D - 0.014), round=0.0015), k=0.002)
    vel.paint(blotch_prim(40, 0.2, seed=5), "#a9284b", feather=0.06)

    # lid (rigid to `lid`): domed top with inlay star, mirror inside
    lid = m.piece("lid", color=WOOD, gloss=135, rigid="lid", lumps=0.0007, lump_freq=12, dents=6, dent_size=0.016,
                  dent_depth=0.0014, mottle=0.07, decimate=1500)
    lid.add(Box((0, H + 0.012, 0), (W + 0.003, 0.012, D + 0.003), round=0.006))
    lid.add(Ellipsoid((0, H + 0.022, 0), (W - 0.01, 0.012, D - 0.012)), k=0.01)
    lid.sub(Box((0, H + 0.002, 0), (W - 0.012, 0.007, D - 0.012), round=0.003), k=0.002)
    lid.paint(grain_prim((1, 0, 0), freq=90, seed=9), WOOD_D, feather=0.004)
    for i in range(8):
        a = i / 8 * TAU
        lid.paint(Ellipsoid((np.cos(a) * 0.022, H + 0.034, np.sin(a) * 0.022), (0.02, 0.01, 0.006),
                            rot=(0, -np.degrees(a), 0)), INLAY if i % 2 == 0 else "#a86d3c", gloss=160, feather=0.002)
    lid.paint(Sphere((0, H + 0.034, 0), 0.008), "#e9cf9a", gloss=160, feather=0.002)
    mirror_oval = Func(lambda P: np.hypot(P[:, 0] / (W - 0.029), P[:, 2] / (D - 0.021)) - 1.0 + np.maximum(P[:, 1] - H - 0.012, 0) * 50,
                       (-W, H - 0.02, -D), (W, H + 0.03, D))
    lid.paint(mirror_oval, "#c9d3da", gloss=255, feather=0.002)
    lid.paint(inter_prim(mirror_oval, blotch_prim(24, 0.3, seed=4)), "#9fb0ba", gloss=255, feather=0.06)
    lid.paint(inter_prim(mirror_oval, Ellipsoid((0.03, H, 0.02), (0.03, 0.05, 0.012), rot=(0, 35, 0))), "#eef3f6", gloss=255, feather=0.01)
    lfr = m.piece("lid_brass", color=BR, gloss=G_METAL, rigid="lid", lumps=0.0004, lump_freq=20, mottle=0.06, res=0.0016, decimate=700)
    lfr.add(Torus((0, H + 0.0045, 0), 1.0, 0.0028) if False else Func(
        lambda P: np.abs(np.hypot((P[:, 0]) / (W - 0.028), (P[:, 2]) / (D - 0.02)) - 1.0) * 0.08 - 0.0026 + np.maximum(np.abs(P[:, 1] - H - 0.0045) - 0.0016, 0),
        (-W, H - 0.01, -D), (W, H + 0.02, D)))
    lfr.add(Box((0, H + 0.0, D + 0.004), (0.012, 0.009, 0.0025), round=0.002), k=0.001)  # catch
    metal(lfr, BRD, None, r=0.005, tarnish=0.05, noise=0.01)
    for pc in (lid, lfr):
        pose_piece(pc, LID_ROT, (0, 0, 0), hinge)

    # the dancer (rigid to `dancer`): arms in a ring above her head, one leg raised behind, a frilly tutu
    dn = m.piece("dancer", color="#f0c8a8", gloss=90, rigid="dancer", lumps=0.0003, lump_freq=40, mottle=0.03, res=0.0011,
                 decimate=2000)
    b0 = plinth + (0, 0.001, 0)
    TUTU, SKIN, HAIR = "#f3a9bd", "#f0c8a8", "#4a2b1c"
    dn.add(Capsule(b0 + (0, 0.002, 0), b0 + (0, 0.008, 0), 0.0065, 0.004), color=BR, gloss=G_METAL)    # spindle cap
    dn.add(Capsule(b0 + (0, 0.004, 0), b0 + (0.001, 0.034, 0.0), 0.0022, 0.0032), k=0.002, color="#f6e7e4")   # standing leg (tights)
    dn.add(Capsule(b0 + (0.001, 0.034, 0), b0 + (-0.0, 0.03, -0.017), 0.003, 0.0022), k=0.002, color="#f6e7e4")   # raised leg
    dn.add(Capsule(b0 + (-0.0, 0.03, -0.017), b0 + (0.0, 0.037, -0.026), 0.0022, 0.0018), k=0.0015, color="#f6e7e4")
    dn.add(Ellipsoid(b0 + (0.001, 0.046, 0), (0.0055, 0.011, 0.0045)), k=0.003, color=TUTU)            # bodice
    dn.add(Ellipsoid(b0 + (0.001, 0.038, 0), (0.017, 0.0032, 0.017)), k=0.003, color=TUTU)              # tutu
    for i in range(14):
        a = i / 14 * TAU
        dn.add(Sphere(b0 + (np.cos(a) * 0.016, 0.0375 + 0.0012 * np.sin(a * 3), np.sin(a) * 0.016), 0.0034), k=0.002, color=TUTU)
    dn.add(Capsule(b0 + (0.001, 0.055, 0), b0 + (0.001, 0.06, 0.0), 0.0018), k=0.0015, color=SKIN)
    dn.add(Sphere(b0 + (0.001, 0.066, 0.001), 0.0058), k=0.0015, color=SKIN)
    dn.add(Sphere(b0 + (0.001, 0.071, -0.003), 0.0032), k=0.001, color=HAIR)                       # bun
    dn.add(Ellipsoid(b0 + (0.001, 0.068, -0.001), (0.0058, 0.0042, 0.0058)), k=0.0012, color=HAIR)
    for sx in (-1, 1):
        dn.add(Tube([b0 + (0.001 + sx * 0.004, 0.054, 0), b0 + (sx * 0.011, 0.066, 0.002), b0 + (sx * 0.008, 0.078, 0.003),
                     b0 + (sx * 0.002, 0.082, 0.003)], 0.0015, samples=4), k=0.0015, color=SKIN)
    dn.paint(Sphere(b0 + (0.001, 0.066, 0.0065), 0.0012), "#c64f5c", feather=0.0006)
    for sx in (-1, 1):
        dn.paint(Sphere(b0 + (0.001 + sx * 0.0022, 0.0675, 0.0058), 0.0009), "#2a1c18", feather=0.0005)

    for op in dn.ops:
        op.prim = Scaled(op.prim, 1.35, plinth)

    # wind-up key (rigid to `key`)
    ky = m.piece("key", color=BR, gloss=G_METAL, rigid="key", lumps=0.0005, lump_freq=20, mottle=0.06, res=0.0016, decimate=700)
    ky.add(Capsule(keyc - (0.004, 0, 0), keyc + (0.02, 0, 0), 0.0035))
    ky.add(Cylinder(keyc + (0.006, 0, 0), 0.007, 0.002, rot=(0, 0, 90), round=0.0015), k=0.002)
    for sy in (-1, 1):
        ky.add(Ellipsoid(keyc + (0.025, sy * 0.014, 0), (0.0032, 0.014, 0.011)), k=0.004)
        ky.sub(Ellipsoid(keyc + (0.025, sy * 0.016, 0), (0.006, 0.006, 0.0045)), k=0.002)
    metal(ky, BRD, "#d8aa4c", r=0.008, tarnish=0.05, wear=0.13, noise=0.01, light_gloss=215)
    m.socket("music", None, (0, 0.09, 0))
    return m


# ==============================================================================================================
# ship in a bottle — a little three-master on a putty sea, the bottle on a wooden cradle


def ship_in_bottle():
    m = Model("ship_in_bottle", res=0.003)
    AY = 0.123            # bottle axis height
    RB, RN = 0.084, 0.027  # body / neck outer radius
    WALL = 0.0065
    X0, XS, XN, XL = -0.22, 0.09, 0.19, 0.265   # base, shoulder start, neck start, lip

    def bottle(off):
        r_b, r_n = RB - off, RN - off
        parts = [Capsule((X0 + 0.03 + (0.06 if off > 0 else 0.0), AY, 0), (XS, AY, 0), r_b),
                 Capsule((XS, AY, 0), (XN, AY, 0), r_b, r_n),
                 Capsule((XN, AY, 0), (XL + (0.01 if off > 0 else 0.0), AY, 0), r_n)]
        return parts

    gl = m.piece("glass_clear", color="#d3e9e0", gloss=G_GLASS, lumps=0.0004, lump_freq=8, mottle=0.02, res=0.0028,
                 decimate=4200, ao=False)
    for q in bottle(0):
        gl.add(q, k=0.03)
    gl.inter(HalfSpace((X0, AY, 0), (-1, 0, 0)), k=0.012)
    gl.add(Torus((XL - 0.004, AY, 0), RN + 0.001, 0.0055, rot=(0, 0, 90)), k=0.004)
    inner_parts = bottle(WALL)

    def inner_f(P):
        d = inner_parts[0](P)
        for q in inner_parts[1:]:
            d = smin(d, q(P), 0.03)[0]
        return d
    gl.sub(Func(inner_f, (X0 - 0.01, AY - RB, -RB), (XL + 0.03, AY + RB, RB)), k=0.002)
    gl.sub(Ellipsoid((X0 + 0.004, AY, 0), (0.03, 0.05, 0.05)), k=0.01)   # the punt
    gl.paint(blotch_prim(10, 0.3, seed=2), "#c4e0d6", feather=0.1)

    ck = m.piece("cork", color=CP["cork"], gloss=30, lumps=0.0008, lump_freq=30, dents=6, dent_size=0.006, dent_depth=0.0008,
                 mottle=0.12, res=0.002, decimate=500)
    ck.add(Cylinder((XL + 0.006, AY, 0), RN - WALL + 0.0008, 0.022, rot=(0, 0, 90), round=0.003))
    ck.add(Cylinder((XL + 0.024, AY, 0), RN - WALL + 0.003, 0.009, rot=(0, 0, 90), round=0.004), k=0.002)
    ck.paint(blotch_prim(90, 0.3, seed=5), "#8a6238", feather=0.02)

    # cradle: two notched supports on a plank, a brass plaque
    cr = m.piece("cradle", color=CP["wood"], gloss=60, lumps=0.0012, lump_freq=12, dents=10, dent_size=0.014, dent_depth=0.0014,
                 mottle=0.08, res=0.003, decimate=1600)
    cr.add(Box((-0.04, 0.008, 0), (0.17, 0.008, 0.07), round=0.005))
    for x in (-0.14, 0.06):
        cr.add(Box((x, 0.04, 0), (0.016, 0.04, 0.06), round=0.006), k=0.004)
    cr.sub(Cylinder((0, AY, 0), RB + 0.001, 0.4, rot=(0, 0, 90)), k=0.003)
    cr.paint(grain_prim((1, 0, 0), freq=80, seed=4), CP["wood_dk"], feather=0.004)
    cr.add(Box((-0.04, 0.008, 0.0705), (0.035, 0.0055, 0.0015), round=0.0015), k=0.001, color=CP["brass"], gloss=G_METAL)
    grime(cr, CP["wood_dk"], r=0.006, thresh=0.1, noise=0.02, feather=0.05)

    # the putty sea filling the bottom of the bottle, with white wave crests
    sea = m.piece("sea", color="#2f6c88", gloss=150, lumps=0.0012, lump_freq=30, mottle=0.06, res=0.0022, decimate=1300)
    inner = Capsule((X0 + 0.03, AY, 0), (XS + 0.01, AY, 0), RB - WALL - 0.001)
    sea.add(inner)
    def wave_top(P):
        h = AY - 0.04 + 0.006 * np.sin(P[:, 0] * 70 + 1.2) + 0.004 * np.sin(P[:, 2] * 90 + P[:, 0] * 30)
        return P[:, 1] - h
    sea.inter(Func(wave_top, (-0.3, 0, -0.1), (0.2, 0.2, 0.1)), k=0.004)
    sea.inter(HalfSpace((X0 + 0.02, AY, 0), (-1, 0, 0)), k=0.004)
    sea.paint(func_prim(lambda P: -(P[:, 1] - (AY - 0.04 + 0.006 * np.sin(P[:, 0] * 70 + 1.2) + 0.004 * np.sin(P[:, 2] * 90 + P[:, 0] * 30)) + 0.0022)),
              "#f2f0ea", gloss=120, feather=0.0015)
    sea.paint(func_prim(lambda P: P[:, 1] - (AY - 0.05)), "#24506a", feather=0.008)

    # the ship: hull, deck, masts, bowsprit, sails, pennants
    sx, sy = -0.05, AY - 0.04          # midships on the water
    hull = m.piece("ship", color="#4a2c1b", gloss=90, lumps=0.0004, lump_freq=30, mottle=0.06, res=0.0013, decimate=2200)
    hull.add(Ellipsoid((sx, sy + 0.004, 0), (0.075, 0.017, 0.018)))
    hull.add(Box((sx - 0.062, sy + 0.012, 0), (0.012, 0.01, 0.0145), round=0.004), k=0.008)   # stern castle
    hull.add(Capsule((sx + 0.065, sy + 0.008, 0), (sx + 0.095, sy + 0.017, 0), 0.0045, 0.0015), k=0.004)  # bowsprit
    hull.inter(HalfSpace((0, sy + 0.017, 0), (0, 1, 0)) if False else Func(lambda P: P[:, 1] - (sy + 0.016 + 0.004 * ((P[:, 0] - sx) / 0.07) ** 2), (-1, -1, -1), (1, 1, 1)), k=0.002)
    hull.paint(func_prim(lambda P: np.abs(P[:, 1] - sy - 0.009) - 0.0022), "#e9d9a8", feather=0.0008)
    hull.paint(func_prim(lambda P: P[:, 1] - sy + 0.004), "#7a2e22", feather=0.0015)
    masts = [(sx + 0.035, 0.06), (sx - 0.002, 0.072), (sx - 0.04, 0.056)]
    for (mx, mh) in masts:
        hull.add(Capsule((mx, sy + 0.012, 0), (mx, sy + 0.016 + mh, 0), 0.0021, 0.0013), k=0.0015, color="#6b4a30")
        for f in (0.38, 0.66, 0.9):
            hull.add(Capsule((mx, sy + 0.016 + mh * f, -0.013 * (1.15 - f)), (mx, sy + 0.016 + mh * f, 0.013 * (1.15 - f)), 0.0011),
                     k=0.001, color="#6b4a30")
    sails = m.piece("sails", color="#efe5cc", gloss=40, lumps=0.0003, lump_freq=30, mottle=0.05, res=0.0011, decimate=1500)
    for (mx, mh) in masts:
        for (f0, f1) in ((0.38, 0.66), (0.66, 0.9)):
            w0, w1 = 0.013 * (1.15 - f0), 0.013 * (1.15 - f1)
            y0, y1 = sy + 0.016 + mh * f0 + 0.002, sy + 0.016 + mh * f1 - 0.001
            poly = closed_curve([(-w0, 0.0), (-w1, y1 - y0), (w1, y1 - y0), (w0, 0.0)], 2)
            sails.add(Pillow(poly, 0.0019, 0.0015, 0.004, o=(mx + 0.002, y0, 0), u=(0, 0, 1), v=(0, 1, 0),
                             offset=lambda p2: 0.0035 * (1 - (p2[:, 0] / 0.016) ** 2)), k=0.001)
        y0 = sy + 0.02
        y1 = sy + 0.016 + mh * 0.38
        poly = closed_curve([(-0.014, 0.0), (-0.012, y1 - y0), (0.012, y1 - y0), (0.014, 0.0)], 2)
        sails.add(Pillow(poly, 0.0019, 0.0015, 0.004, o=(mx + 0.002, y0, 0), u=(0, 0, 1), v=(0, 1, 0),
                         offset=lambda p2: 0.004 * (1 - (p2[:, 0] / 0.016) ** 2)), k=0.001)
    jib = closed_curve([(0.0, 0.0), (0.05, 0.0), (0.0, 0.05)], 2)
    sails.add(Pillow(jib, 0.0018, 0.0014, 0.004, o=(sx + 0.04, sy + 0.022, 0.0), u=(1, -0.12, 0), v=(0, 1, 0)), k=0.001)
    sails.paint(blotch_prim(60, 0.3, seed=7), "#ddd0b0", feather=0.04)
    flags = m.piece("flags", color="#c43a2e", gloss=60, lumps=0.0, mottle=0.04, res=0.0011, decimate=200)
    for (mx, mh) in masts:
        top = np.array([mx, sy + 0.016 + mh, 0])
        flags.add(Pillow(closed_curve([(0, 0), (0.016, -0.002), (0, -0.007)], 2), 0.0013, 0.001, 0.002, o=top + (0.0, -0.001, 0),
                         u=(-1, 0, 0), v=(0, 1, 0)))
    m.socket("cork", None, (XL + 0.034, AY, 0))
    return m


# ==============================================================================================================
# figurehead — a carved mermaid fragment: arms crossed, eyes closed, hair flowing, tail curling to a fluke;
# faded, chipped paint over weathered wood; a split, splintered back where she was torn from the bow


def figurehead():
    m = Model("figurehead", res=0.0045)
    WOOD, WOOD_D, RAW = "#8f6a45", "#5c4029", "#c9a26f"
    SKIN, CHEEK, BOD, TAIL, TAIL_D, HAIR, GOLD = "#e2c3a2", "#d9998a", "#6b8cae", "#5f9b93", "#3e6f6a", "#c99b55", "#d4aa48"
    CUT = 0.068     # the split back: everything behind z = -CUT is gone
    rng = np.random.default_rng(11)

    def back_cut(pc, seed):
        pc.inter(HalfSpace((0, 0, -CUT), (0, 0, -1)).lumpy(0.006, 16, seed), k=0.004)

    # --- body: torso, crossed arms, hip fin frill, scaled tail curling up to a fluke ---------------------------
    b = m.piece("body", color=WOOD, gloss=55, lumps=0.003, lump_freq=7, dents=26, dent_size=0.028, dent_depth=0.003,
                mottle=0.09, decimate=5600)
    b.add(Ellipsoid((0, 0.505, 0.012), (0.135, 0.058, 0.074)))
    b.add(Ellipsoid((0, 0.45, 0.03), (0.112, 0.085, 0.08)), k=0.05)
    b.add(Ellipsoid((0, 0.36, 0.018), (0.088, 0.08, 0.07)), k=0.05)
    b.add(Capsule((0, 0.53, 0.025), (0, 0.6, 0.05), 0.034, 0.03), k=0.03)
    for sx in (-1, 1):
        b.add(Sphere((sx * 0.06, 0.462, 0.083), 0.04), k=0.03)          # bust under the bodice
    tail = np.array([(0, 0.34, 0.015), (0, 0.24, 0.0), (0, 0.13, 0.002), (0, 0.055, 0.05), (0, 0.042, 0.13), (0, 0.062, 0.2),
                     (0, 0.102, 0.25), (0, 0.15, 0.268)])
    trad = [0.088, 0.086, 0.076, 0.058, 0.044, 0.034, 0.025, 0.019]
    b.add(Tube(tail, trad, samples=6), k=0.04)
    # arms crossed over the chest (right forearm on top)
    arms = [((0.128, 0.5, 0.015), (0.122, 0.405, 0.07), (-0.03, 0.47, 0.128), (-0.07, 0.474, 0.112)),
            ((-0.128, 0.5, 0.015), (-0.122, 0.398, 0.07), (0.03, 0.43, 0.13), (0.072, 0.432, 0.11))]
    for sh, el, wr, hd in arms:
        b.add(Capsule(sh, el, 0.032, 0.026), k=0.02)
        b.add(Capsule(el, wr, 0.026, 0.02), k=0.012)
        b.add(Ellipsoid(hd, (0.024, 0.016, 0.014), rot=(0, 0, 25 if hd[0] < 0 else -25)), k=0.01)
        for j in range(3):   # fingers scored into the hand
            off = np.array([0, (j - 1) * 0.008, 0.006])
            b.sub(Capsule(np.asarray(hd) + off + (0.012 * np.sign(hd[0]), 0, 0.006), np.asarray(hd) + off - (0.01 * np.sign(hd[0]), 0, -0.008), 0.0018), k=0.001)
    # hip frill: scalloped fin lobes where skin turns to tail
    for j, a in enumerate(np.linspace(-1.9, 1.9, 9)):
        d = np.array([np.sin(a), 0, np.cos(a)])
        o = np.array([0, 0.33, 0.012]) + d * 0.072
        outline = closed_curve([(-0.026, 0.0), (-0.022, -0.04), (0.0, -0.06), (0.022, -0.04), (0.026, 0.0)], 3)
        b.add(Pillow(outline, 0.008, 0.004, 0.012, o=o, u=np.cross([0, 1, 0], d), v=_n(np.array([0, 1.0, 0]) - d * 0.35),
                     offset=lambda p2: -0.012 * (p2[:, 1] / 0.06) ** 2), k=0.008)
    # fluke: two curling lobes
    tip = tail[-1]
    for sx in (-1, 1):
        outline = closed_curve([(0.0, -0.012), (0.03, 0.02), (0.075, 0.07), (0.1, 0.105), (0.07, 0.1), (0.03, 0.075), (0.0, 0.04)], 3)
        b.add(Pillow(outline * np.array([sx, 1]), 0.012, 0.005, 0.02, o=tip + (0, -0.01, 0.0), u=(1, 0, 0), v=(0, 1, 0.25),
                     offset=lambda p2: 0.25 * (p2[:, 0] ** 2) + 0.0 * p2[:, 1]), k=0.012)
        for f in (0.35, 0.6, 0.85):   # carved fluke ribs
            q0 = tip + (sx * 0.006, 0.0, 0.004)
            q1 = tip + (sx * 0.09 * f, 0.095 * f + 0.005, 0.03 * f + 0.008)
            b.sub(Capsule(q0, q1, 0.0035), k=0.002)
    # scale cups carved down the tail (hashed so a few hundred stay cheap)
    dense = smooth_curve(tail[:6], 8)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))]
    cups = []
    for row, sv in enumerate(np.arange(0.03, seg[-1] - 0.02, 0.021)):
        c = np.array([np.interp(sv, seg, dense[:, i]) for i in range(3)])
        i = min(np.searchsorted(seg, sv), len(dense) - 1)
        tng = _n(dense[min(i + 1, len(dense) - 1)] - dense[max(i - 1, 0)])
        rad = np.interp(sv / seg[-1], np.linspace(0, 1, 6), trad[:6])
        side = _n(np.cross(tng, [1, 0, 0]))
        side2 = np.cross(tng, side)
        n_around = max(6, int(TAU * rad / 0.024))
        for k in range(n_around):
            a = (k + 0.5 * (row % 2)) / n_around * TAU
            nn = np.cos(a) * side + np.sin(a) * side2
            cups.append(c + nn * (rad + 0.007) - tng * 0.004)
    b.sub(HashedSpheres(cups, 0.0125), k=0.003)
    back_cut(b, 3)
    # iron bolt stub and splinters on the split back
    for (x, y, l) in ((0.0, 0.43, 0.05), (0.0, 0.2, 0.035)):
        b.add(Capsule((x, y, -CUT + 0.01), (x + 0.004, y - 0.004, -CUT - l), 0.011), k=0.004, color="#4a3a32", gloss=60)
    for j in range(7):
        y = rng.uniform(0.08, 0.6)
        x = rng.uniform(-0.08, 0.08)
        b.add(Capsule((x, y, -CUT + 0.004), (x + rng.uniform(-0.01, 0.01), y + rng.uniform(-0.05, 0.05), -CUT - rng.uniform(0.012, 0.03)),
                      0.006, 0.0012), k=0.003)
    b.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.004)
    # paint: skin, faded blue bodice with gold trim, teal tail with darker scale cups, worn to raw wood
    b.paint(func_prim(lambda P: 0.36 - P[:, 1]), SKIN, gloss=70, feather=0.01)
    b.paint(inter_prim(func_prim(lambda P: np.abs(P[:, 1] - 0.43) - 0.065), func_prim(lambda P: 0.02 - P[:, 2])), WOOD, feather=0.01) if False else None
    bodice = Func(lambda P: np.maximum(np.abs(P[:, 1] - 0.43) - 0.058, -P[:, 2] - 0.02), (-1, -1, -1), (1, 1, 1))
    b.paint(bodice, BOD, gloss=60, feather=0.006)
    for sx, sh, el, wr, hd in [(1,) + arms[0], (-1,) + arms[1]]:
        b.paint(Capsule(el, wr, 0.03, 0.025), SKIN, gloss=70, feather=0.006)
        b.paint(Ellipsoid(hd, (0.028, 0.02, 0.018)), SKIN, gloss=70, feather=0.004)
        b.paint(Capsule(sh, el, 0.036, 0.03), SKIN, gloss=70, feather=0.006)
    b.paint(func_prim(lambda P: P[:, 1] - 0.355), TAIL, gloss=80, feather=0.012)
    b.paint(HashedSpheres(cups, 0.0165), TAIL_D, gloss=80, feather=0.004)
    b.paint(Tube([(-0.11, 0.49, 0.06), (-0.05, 0.5, 0.1), (0.0, 0.494, 0.112), (0.05, 0.5, 0.1), (0.11, 0.49, 0.06)], 0.007, samples=5), GOLD, gloss=170, feather=0.003)
    b.paint(func_prim(lambda P: np.abs(P[:, 1] - 0.302) - 0.009 + np.maximum(np.hypot(P[:, 0], P[:, 2] - 0.012) - 0.12, 0)), GOLD, gloss=170, feather=0.004)
    b.paint(Ellipsoid(tip + (0, 0.07, 0.03), (0.12, 0.085, 0.04)), TAIL, gloss=80, feather=0.01)
    b.paint(cavity_prim(b, 0.008, 0.12, True, noise=0.02), GOLD, gloss=170, feather=0.06)
    # wear: paint flaked off in patches and on proud edges, raw wood showing; split back pale and grainy
    b.paint(blotch_prim(9, 0.32, seed=4), WOOD, gloss=40, feather=0.04)
    b.paint(blotch_prim(22, 0.42, seed=5), RAW, gloss=30, feather=0.03)
    b.paint(cavity_prim(b, 0.014, 0.16, True, noise=0.03, seed=8), WOOD, gloss=40, feather=0.06)
    b.paint(grain_prim((0, 1, 0), freq=55, seed=6, thresh=0.7), WOOD_D, feather=0.006)
    b.paint(func_prim(lambda P: P[:, 2] + CUT - 0.008), RAW, gloss=25, feather=0.006)
    b.paint(inter_prim(func_prim(lambda P: P[:, 2] + CUT - 0.006), grain_prim((0, 1, 0), freq=90, seed=7, thresh=0.5)), "#9c7748", feather=0.003)
    grime(b, "#3e2c1c", r=0.012, thresh=0.12, noise=0.03, feather=0.06)
    b.paint(inter_prim(func_prim(lambda P: P[:, 1] - 0.07), blotch_prim(14, 0.0, seed=9)), "#55682f", gloss=70, feather=0.03)
    for (x, y, z, r) in ((0.04, 0.03, 0.13, 0.012), (0.055, 0.045, 0.1, 0.008), (-0.045, 0.035, 0.12, 0.01), (0.0, 0.11, 0.26, 0.007)):
        barnacle(b, (x, y, z), (np.sign(x) * 0.7 if x else 0.0, 0.4, 0.6), r)

    # --- head: serene face, eyes closed, chin lifted ----------------------------------------------------------
    hd = m.piece("head", color=SKIN, gloss=70, lumps=0.0015, lump_freq=10, dents=8, dent_size=0.016, dent_depth=0.0015,
                 mottle=0.07, res=0.0026, decimate=2200)
    H0 = np.array([0, 0.655, 0.052])
    hd.add(Ellipsoid(H0, (0.06, 0.074, 0.068), rot=(-10, 0, 0)))
    hd.add(Ellipsoid(H0 + (0, -0.035, 0.018), (0.046, 0.045, 0.052), rot=(-10, 0, 0)), k=0.03)
    hd.add(Capsule(H0 + (0, -0.09, -0.02), H0 + (0, -0.04, 0.0), 0.03), k=0.02)
    hd.add(Capsule(H0 + (0, 0.012, 0.063), H0 + (0, -0.008, 0.077), 0.008, 0.0105), k=0.008)   # nose
    hd.add(Sphere(H0 + (0, -0.011, 0.077), 0.0095), k=0.006)
    for sx in (-1, 1):
        e = H0 + (sx * 0.025, 0.014, 0.058)
        hd.sub(Sphere(e + (0, 0.004, 0.008), 0.014), k=0.008)                      # eye socket
        hd.add(Ellipsoid(e + (0, 0.0, 0.004), (0.014, 0.008, 0.008), rot=(-10, sx * 18, 0)), k=0.006)   # closed lid
        hd.add(Ellipsoid(H0 + (sx * 0.034, -0.02, 0.052), (0.016, 0.012, 0.01)), k=0.012)   # cheeks
        hd.add(Tube([e + (-sx * 0.012, 0.016, 0.004), e + (sx * 0.002, 0.021, 0.006), e + (sx * 0.016, 0.017, 0.0)], 0.0035, samples=4), k=0.005)  # brow
    hd.add(Ellipsoid(H0 + (0, -0.06, 0.05), (0.017, 0.012, 0.014)), k=0.01)   # chin
    back_cut(hd, 4)
    hd.paint(Sphere(H0 + (0.034, -0.02, 0.056), 0.016), CHEEK, feather=0.01)
    hd.paint(Sphere(H0 + (-0.034, -0.02, 0.056), 0.016), CHEEK, feather=0.01)
    hd.paint(blotch_prim(24, 0.42, seed=12), RAW, gloss=30, feather=0.03)
    hd.paint(cavity_prim(hd, 0.008, 0.2, True, noise=0.02, seed=3), WOOD, gloss=40, feather=0.05)
    hd.paint(func_prim(lambda P: P[:, 2] + CUT - 0.008), RAW, gloss=25, feather=0.006)
    grime(hd, "#7a5a40", r=0.008, thresh=0.12, noise=0.02, feather=0.05)
    fc = m.piece("face", color="#b7443c", gloss=120, lumps=0.0, mottle=0.04, res=0.0011, decimate=500, ao=False)
    fc.add(Ellipsoid(H0 + (0, -0.032, 0.07), (0.013, 0.0042, 0.006), rot=(-10, 0, 0)))
    fc.add(Ellipsoid(H0 + (0, -0.041, 0.067), (0.011, 0.0046, 0.006), rot=(-10, 0, 0)), k=0.002)
    fc.sub(Box(H0 + (0, -0.0365, 0.075), (0.02, 0.0007, 0.01), rot=(-10, 0, 0)), k=0.0005)
    for sx in (-1, 1):
        e = H0 + (sx * 0.025, 0.014, 0.058)
        fc.add(Tube([e + (-sx * 0.011, 0.002, 0.009), e + (sx * 0.0, -0.003, 0.0125), e + (sx * 0.012, 0.0005, 0.0085)], 0.0016, samples=4),
               k=0.001, color="#3a2a22", gloss=60)
        for t in (0.25, 0.55, 0.85):
            q = e + (sx * (-0.011 + 0.023 * t), -0.003 * np.sin(t * np.pi), 0.0115)
            fc.add(Capsule(q, q + (sx * 0.003, -0.005, 0.002), 0.0008), k=0.0005, color="#3a2a22", gloss=60)

    # --- hair: thick carved locks flowing back and over the shoulders, a ribbon band ---------------------------
    hr = m.piece("hair", color=HAIR, gloss=60, lumps=0.002, lump_freq=10, dents=10, dent_size=0.02, dent_depth=0.002,
                 mottle=0.08, res=0.0035, decimate=2200)
    hr.add(Ellipsoid(H0 + (0, 0.022, -0.012), (0.066, 0.064, 0.064), rot=(-10, 0, 0)))
    hr.sub(Ellipsoid(H0 + (0, -0.03, 0.07), (0.056, 0.07, 0.05), rot=(-25, 0, 0)), k=0.012)
    locks = []
    for sx in (-1, 1):
        locks.append(([H0 + (sx * 0.04, 0.05, 0.03), H0 + (sx * 0.066, 0.0, 0.02), H0 + (sx * 0.08, -0.07, 0.01), H0 + (sx * 0.1, -0.13, 0.03),
                       H0 + (sx * 0.108, -0.19, 0.06), H0 + (sx * 0.095, -0.235, 0.085)], [0.024, 0.026, 0.026, 0.023, 0.02, 0.013]))
        locks.append(([H0 + (sx * 0.02, 0.07, -0.02), H0 + (sx * 0.055, 0.02, -0.045), H0 + (sx * 0.07, -0.06, -0.05), H0 + (sx * 0.1, -0.14, -0.04),
                       H0 + (sx * 0.12, -0.21, -0.03), H0 + (sx * 0.125, -0.28, -0.02)], [0.026, 0.03, 0.03, 0.027, 0.023, 0.016]))
    locks.append(([H0 + (0, 0.07, -0.02), H0 + (0.0, 0.0, -0.06), H0 + (-0.01, -0.1, -0.06), H0 + (0.01, -0.2, -0.06), H0 + (-0.01, -0.27, -0.06)],
                  [0.03, 0.035, 0.034, 0.03, 0.022]))
    for pts, rr in locks:
        pts = np.array(pts)
        hr.add(Tube(pts, rr, samples=5), k=0.012)
        dense = smooth_curve(pts, 5)
        for off in (-0.45, 0.45):    # carved strand grooves along each lock
            g = []
            for i in range(1, len(dense) - 1):
                tng = _n(dense[i + 1] - dense[i - 1])
                sd = _n(np.cross(tng, [0, 0, 1]))
                r_here = np.interp(i / len(dense), np.linspace(0, 1, len(rr)), rr)
                g.append(dense[i] + sd * off * r_here + np.array([0, 0, 0.8]) * r_here * 0.7)
            hr.sub(Tube(np.array(g), 0.003, samples=2), k=0.002)
    hr.add(Torus(H0 + (0, 0.03, 0.004), 0.06, 0.0075, rot=(-28, 0, 0)), k=0.006, color=GOLD, gloss=170)   # hair ribbon
    back_cut(hr, 5)
    hr.paint(grain_prim((0, 1, 0), freq=80, seed=11, thresh=0.6), "#a77b3c", feather=0.004)
    hr.paint(blotch_prim(20, 0.38, seed=13), RAW, gloss=30, feather=0.03)
    hr.paint(cavity_prim(hr, 0.01, 0.16, True, noise=0.02, seed=4), WOOD, gloss=40, feather=0.05)
    hr.paint(func_prim(lambda P: P[:, 2] + CUT - 0.008), RAW, gloss=25, feather=0.006)
    grime(hr, "#5c4029", r=0.008, thresh=0.1, noise=0.02, feather=0.05)
    m.socket("top", None, (0, 0.75, 0.0))
    return m


MODELS = {
    "treasure/megalodon_tooth": megalodon_tooth,
    "treasure/porcelain_teapot": porcelain_teapot,
    "treasure/ship_lantern": ship_lantern,
    "treasure/grand_conch": grand_conch,
    "treasure/sunken_crown": sunken_crown,
    "treasure/treasure_chest": treasure_chest,
    "treasure/sextant": sextant,
    "treasure/music_box": music_box,
    "treasure/ship_in_bottle": ship_in_bottle,
    "treasure/figurehead": figurehead,
}
