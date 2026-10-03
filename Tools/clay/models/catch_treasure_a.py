"""
Deep-sea treasures, batch A (Docs/DESIGN.md §3 dredging, §5.4): sea_glass, message_bottle, ship_bell, brass_compass,
pearl, gold_doubloon, pocket_watch, spyglass, diving_helmet, ammonite. Bottom-centred (y = 0 at the bottom), front
toward +Z, 0.15-0.8 m, metallic clay = warm ochre-gold base, gloss, tarnish in crevices, worn bright edges.
"""
import numpy as np
from clay import *
from kit_catch import *

TAU = 2 * np.pi


# --------------------------------------------------------------------------------------------------------------
# local helpers


class Xf(Prim):
    """Rigidly transformed copy of a prim: world = R @ (local - pivot) + pivot + t."""

    def __init__(self, prim, rot=None, t=(0, 0, 0), pivot=(0, 0, 0)):
        super().__init__()
        self.p = prim
        self.R = euler(rot)
        self.t = np.asarray(t, float)
        self.pv = np.asarray(pivot, float)

    def sdf(self, P):
        return self.p(((P - self.pv - self.t) @ self.R) + self.pv)

    def bounds(self):
        lo, hi = self.p.bounds()
        C = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        W = (C - self.pv) @ self.R.T + self.pv + self.t
        return W.min(0), W.max(0)


class Revolve(Prim):
    """Surface of revolution about local +Y through c: closed 2D outline of (radius, y) points."""

    def __init__(self, outline, c=(0, 0, 0), rot=None, round=0.0, smooth=0):
        super().__init__()
        V = np.asarray(outline, float)
        if smooth:
            V = smooth_closed(V, smooth)
        self.V = V
        self.c = np.asarray(c, float)
        self.R = euler(rot)
        self.rd = round

    def sdf(self, P):
        q = (P - self.c) @ self.R
        p2 = np.column_stack([np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2), q[:, 1]])
        return poly_sdf(p2, self.V) - self.rd

    def bounds(self):
        r = np.max(np.abs(self.V[:, 0])) + self.rd
        y0, y1 = self.V[:, 1].min() - self.rd, self.V[:, 1].max() + self.rd
        C = np.array([[x, y, z] for x in (-r, r) for y in (y0, y1) for z in (-r, r)])
        W = C @ self.R.T + self.c
        return W.min(0), W.max(0)


class TModel(Model):
    """Model that is re-centred after meshing: bottom at y = 0, bounding box centred in x/z (bones/sockets follow)."""

    def build(self):
        parts = super().build()
        V = np.concatenate([v for p, v, n, c, f, sk in parts if not p.hidden])
        lo, hi = V.min(0), V.max(0)
        off = np.array([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2], np.float32)
        self.offset = off
        out = [(p, (v + off).astype(np.float32), n, c, f, sk) for p, v, n, c, f, sk in parts]
        self.bones = [(nm, pi, pos + off) for nm, pi, pos in self.bones]
        self.sockets = [(nm, bi, pos + off, q) for nm, bi, pos, q in self.sockets]
        self.size = hi - lo
        print(f"   size {self.size[0]:.3f} x {self.size[1]:.3f} x {self.size[2]:.3f} m")
        return out


def smooth_closed(V, n=4):
    V = np.asarray(V, float)
    P = np.vstack([V[-1], V, V[0], V[1]])
    out = []
    for i in range(1, len(P) - 2):
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * P[i]) + (-P[i - 1] + P[i + 1]) * t + (2 * P[i - 1] - 5 * P[i] + 4 * P[i + 1] - P[i + 2]) * t2
                              + (-P[i - 1] + 3 * P[i] - 3 * P[i + 1] + P[i + 2]) * t3))
    return np.array(out)


def barnacle(piece, p, n, r, k=None):
    """A little volcano barnacle pressed onto a surface at p with outward normal n."""
    p, n = np.asarray(p, float), np.asarray(n, float) / np.linalg.norm(n)
    piece.add(Capsule(p - n * r * 0.3, p + n * r * 0.75, r, r * 0.55), k=k if k is not None else r * 0.35)
    piece.sub(Capsule(p + n * r * 0.5, p + n * r * 1.4, r * 0.32, r * 0.42), k=r * 0.15)
    for a in range(0, 360, 72):
        t = np.cross(n, [0.3, 0.9, 0.1])
        t /= np.linalg.norm(t)
        b = np.cross(n, t)
        d = np.cos(np.radians(a)) * t + np.sin(np.radians(a)) * b
        piece.sub(Capsule(p + d * r * 1.05, p + d * r * 0.62 + n * r * 0.8, r * 0.09), k=r * 0.06)


# a tiny stroke font for engraving (unit box: x 0..0.7, y 0..1)
FONT = {
    "A": [[(0, 0), (0.35, 1), (0.7, 0)], [(0.15, 0.4), (0.55, 0.4)]],
    "B": [[(0, 0), (0, 1), (0.5, 1), (0.6, 0.85), (0.5, 0.55), (0, 0.55)], [(0.5, 0.55), (0.65, 0.35), (0.55, 0.05), (0, 0)]],
    "C": [[(0.65, 0.85), (0.45, 1), (0.15, 0.95), (0, 0.6), (0.05, 0.2), (0.3, 0), (0.6, 0.08)]],
    "D": [[(0, 0), (0, 1), (0.4, 0.95), (0.65, 0.6), (0.6, 0.25), (0.35, 0.02), (0, 0)]],
    "E": [[(0.65, 1), (0, 1), (0, 0), (0.65, 0)], [(0, 0.52), (0.5, 0.52)]],
    "G": [[(0.65, 0.85), (0.45, 1), (0.15, 0.95), (0, 0.6), (0.05, 0.2), (0.3, 0), (0.65, 0.1), (0.65, 0.45), (0.38, 0.45)]],
    "H": [[(0, 0), (0, 1)], [(0.65, 0), (0.65, 1)], [(0, 0.5), (0.65, 0.5)]],
    "I": [[(0.3, 0), (0.3, 1)]],
    "L": [[(0, 1), (0, 0), (0.6, 0)]],
    "M": [[(0, 0), (0, 1), (0.35, 0.45), (0.7, 1), (0.7, 0)]],
    "N": [[(0, 0), (0, 1), (0.65, 0), (0.65, 1)]],
    "O": [[(0.33, 1), (0.05, 0.8), (0, 0.4), (0.15, 0.05), (0.45, 0), (0.65, 0.3), (0.65, 0.7), (0.5, 0.97), (0.33, 1)]],
    "R": [[(0, 0), (0, 1), (0.5, 1), (0.62, 0.8), (0.5, 0.55), (0, 0.55)], [(0.3, 0.55), (0.65, 0)]],
    "S": [[(0.62, 0.88), (0.4, 1), (0.1, 0.92), (0.05, 0.68), (0.35, 0.5), (0.62, 0.3), (0.55, 0.06), (0.25, 0), (0.02, 0.12)]],
    "T": [[(0, 1), (0.7, 1)], [(0.35, 1), (0.35, 0)]],
    "U": [[(0, 1), (0, 0.25), (0.2, 0), (0.45, 0), (0.65, 0.25), (0.65, 1)]],
    "V": [[(0, 1), (0.35, 0), (0.7, 1)]],
    "W": [[(0, 1), (0.15, 0), (0.35, 0.6), (0.55, 0), (0.7, 1)]],
    "X": [[(0, 0), (0.65, 1)], [(0, 1), (0.65, 0)]],
    "Y": [[(0, 1), (0.35, 0.5), (0.7, 1)], [(0.35, 0.5), (0.35, 0)]],
    "1": [[(0.15, 0.8), (0.35, 1), (0.35, 0)]],
    "7": [[(0, 1), (0.65, 1), (0.25, 0)]],
    "8": [[(0.33, 0.55), (0.08, 0.75), (0.2, 0.97), (0.48, 0.97), (0.58, 0.75), (0.33, 0.55), (0.03, 0.3), (0.15, 0.02),
           (0.5, 0.02), (0.63, 0.3), (0.33, 0.55)]],
    "0": [[(0.33, 1), (0.05, 0.8), (0, 0.4), (0.15, 0.05), (0.45, 0), (0.65, 0.3), (0.65, 0.7), (0.5, 0.97), (0.33, 1)]],
    ".": [[(0.3, 0.0), (0.33, 0.06)]],
    " ": [],
}


def text_strokes(text, width_per=0.85):
    """List of polylines (u, v) for text, u advancing ~width_per per character."""
    out, x = [], 0.0
    for ch in text:
        for s in FONT.get(ch, []):
            out.append([(x + u, v) for u, v in s])
        x += width_per if ch != " " else width_per * 0.6
    return out, x


def lerp(a, b, t):
    return np.asarray(a, float) * (1 - t) + np.asarray(b, float) * t


# ==============================================================================================================
# ship bell — brass ship's bell found tipped back on a barnacled stone, clapper and lanyard spilling out


BELL_OUT = [(0.150, 0.000), (0.156, 0.016), (0.151, 0.042), (0.133, 0.085), (0.117, 0.140), (0.108, 0.200),
            (0.105, 0.250), (0.100, 0.280), (0.085, 0.300), (0.045, 0.309), (0.0, 0.311)]
BELL_RECESS = [(0.0, 0.07), (0.07, 0.062), (0.11, 0.04), (0.132, 0.016), (0.139, 0.0)]
BELL_IN = [(0.0, 0.282), (0.06, 0.278), (0.084, 0.262), (0.090, 0.205), (0.096, 0.145), (0.110, 0.090), (0.126, 0.048),
           (0.137, 0.016), (0.139, 0.0)]


def bell_r(y):
    a = np.array(BELL_OUT)
    return float(np.interp(y, a[:, 1], a[:, 0]))


def brass_finish(piece, base=None, dark=None, light=None, r=0.006, tarnish=0.07, wear=0.15, noise=0.015, verd=None,
                 seed=5, feather=0.03):
    """Metallic clay: tarnish into crevices (mean-SDF cavity < -tarnish), polish on edges (> wear), optional verdigris
    deeper in the crevices. Thin parts (rods, rings) are convex everywhere, so give them a higher `wear`."""
    base = base or CP["brass"]
    piece.paint(cavity_prim(piece, r, tarnish, False, noise=noise, seed=seed), dark or shade(base, 0.42), gloss=70,
                feather=feather)
    piece.paint(cavity_prim(piece, r, wear, True, noise=noise, seed=seed + 1), light or CP["brass_lt"], gloss=225,
                feather=feather)
    if verd:
        piece.paint(cavity_prim(piece, r * 1.3, verd, False, noise=noise, seed=seed + 7), "#5e9a86", gloss=35,
                    feather=feather)


def wood_grain(piece, axis, freq=60.0, seed=2, color=None, amount=0.18):
    """Dark grain streaks along `axis` (0=x,1=y,2=z) painted into a wooden piece."""
    st = [1.0, 1.0, 1.0]
    st[axis] = 0.08
    piece.paint(blotch_prim(freq, amount, seed=seed, stretch=st, octaves=2), color or CP["wood_dk"], feather=0.004)


def ship_bell():
    m = TModel("ship_bell", res=0.003)
    lift = 0.175  # lip height above the table (hangs from its bracket)

    def X(p):
        return Xf(p, None, t=(0, lift, 0))

    bell = m.piece("bell", color="#bd8a2e", gloss=G_METAL, lumps=0.0007, lump_freq=12, dents=9, dent_size=0.03,
                   dent_depth=0.0015, mottle=0.04, decimate=5600, merge="bell")
    # solid casting with a shallow mouth recess (the inside is never seen from the display angles)
    bell.add(X(Revolve(BELL_OUT + BELL_RECESS, round=0.0015)))
    bands = m.piece("bands", color="#c4912f", gloss=G_METAL, lumps=0.0004, lump_freq=20, mottle=0.04, res=0.0022,
                    decimate=1200, merge="bell")
    for y, rr in ((0.03, 0.0056), (0.118, 0.0042), (0.212, 0.0042), (0.262, 0.005)):
        bands.add(X(Torus((0, y, 0), bell_r(y) + 0.0005, rr)), k=0.0)
    bands.paint(func_prim(lambda P: P[:, 1] - (lift + 0.031)), "#9a6d22", feather=0.004)
    bell.add(X(Cylinder((0, 0.318, 0), 0.042, 0.012, round=0.006)), k=0.008)
    bell.add(X(Torus((0, 0.36, 0), 0.032, 0.012, rot=(90, 0, 0))), k=0.008)
    bell.add(X(Ellipsoid((0, 0.334, 0), (0.03, 0.012, 0.022))), k=0.01)

    def engrave(text, y0, hgt, phi_c, rr):
        strokes, wtot = text_strokes(text)
        for st in strokes:
            dense = [st[0]]
            for i in range(1, len(st)):
                for t in np.linspace(0, 1, 4)[1:]:
                    dense.append(tuple(lerp(st[i - 1], st[i], t)))
            P3 = []
            for u, v in dense:
                y = y0 + v * hgt
                R0 = bell_r(y)
                phi = phi_c - (u - wtot / 2) * hgt / R0  # +x is the viewer's left seen from the front
                P3.append((R0 * np.sin(phi), y, R0 * np.cos(phi)))
            P3 = np.array(P3)
            if len(P3) == 1:
                P3 = np.vstack([P3, P3 + (0, 0.001, 0)])
            bell.sub(X(Tube(P3, rr)), k=rr * 0.5)
    engrave("GREY GULL", 0.16, 0.038, 0.0, 0.0024)
    engrave("1887", 0.127, 0.024, 0.0, 0.0021)
    for a, y in ((1.2, 0.06), (-1.9, 0.2), (2.6, 0.1)):
        r0 = bell_r(y)
        bell.sub(X(Sphere((r0 * np.sin(a) * 1.02, y, r0 * np.cos(a) * 1.02), 0.008)), k=0.005)
    bell.paint(X(Revolve(BELL_RECESS + [(0.0, 0.0)], round=0.004)), shade(CP["brass"], 0.4), gloss=90, feather=0.006)
    brass_finish(bell, tarnish=0.08, wear=0.2, verd=0.16, light="#e3b85e", feather=0.05)
    # a patch of verdigris and weed where it lay on the seabed (back-left)
    bell.paint(X(blotch_prim(12.0, 0.1, seed=4, region=Sphere((-0.09, 0.06, -0.08), 0.1))), "#5e9a86", gloss=35, feather=0.004)

    # clapper hangs plumb; its ball peeks just below the lip, the lanyard dangles from its eye
    cl = m.piece("clapper", color=CP["iron"], gloss=110, lumps=0.0008, mottle=0.08, res=0.0022, decimate=500)
    top, ball = np.array([0, lift + 0.062, 0]), np.array([0, lift - 0.006, 0])
    cl.add(Capsule(top, ball, 0.0065, 0.009))
    cl.add(Sphere(ball, 0.028), k=0.01)
    eye = ball + (0, -0.04, 0)
    cl.add(Capsule(ball, eye + (0, 0.008, 0), 0.007), k=0.004)
    cl.add(Torus(eye, 0.011, 0.0045, rot=(90, 0, 0)), k=0.003)
    cl.paint(blotch_prim(30, 0.15, seed=3), CP["rust"], gloss=40, feather=0.004)

    # the lanyard hangs from the clapper eye and curls along the plank, ending in a Turk's head knot and fringe
    ly = m.piece("lanyard", color="#e0d3ad", gloss=30, lumps=0.0006, mottle=0.08, res=0.002, decimate=1200)
    pts = [eye + (0, -0.006, 0), eye + (0.0, -0.05, 0.006), (0.004, 0.052, 0.018), (0.02, 0.042, 0.06), (0.05, 0.042, 0.1)]
    rope(ly, pts, 0.0095, groove="#a8946a")
    knot = np.array(pts[-1]) + (0.014, 0.0, 0.026)
    ly.add(Ellipsoid(knot, (0.019, 0.017, 0.021), rot=(0, -30, 0)), k=0.006)
    for a in range(0, 360, 45):
        dd = np.array([np.cos(np.radians(a)), np.sin(np.radians(a)), 0.0])
        dd = euler((0, -30, 0)) @ dd
        ly.sub(Capsule(knot + dd * 0.02 + euler((0, -30, 0)) @ np.array([0, 0, 0.014]), knot + dd * 0.02 - euler((0, -30, 0)) @ np.array([0, 0, 0.014]), 0.0026), k=0.002)
    fwd = euler((0, -30, 0)) @ np.array([0, 0, 1.0])
    side = np.cross([0, 1.0, 0], fwd)
    for i in range(9):
        t = (i - 4) / 4
        tip = knot + fwd * (0.05 + 0.008 * np.cos(i * 1.7)) + side * t * 0.026 + (0, -0.012 + 0.003 * abs(t), 0)
        ly.add(Capsule(knot + fwd * 0.012 + side * t * 0.008, tip, 0.0042, 0.003), k=0.003)
    ly.paint(Ellipsoid(knot, (0.022, 0.02, 0.023), rot=(0, -30, 0)), "#c84a35", feather=0.003)  # red Turk's head

    # display stand: driftwood plank + post at the back, a scrolled brass bracket arm, shackle through the crown loop
    wd = m.piece("stand", color="#76624d", gloss=25, lumps=0.001, lump_freq=10, dents=10, dent_size=0.02, dent_depth=0.0016,
                 mottle=0.08, res=0.0045, decimate=1700)
    wd.add(Box((0, 0.016, -0.02), (0.15, 0.016, 0.2), round=0.012).lumpy(0.0012, 9, 3))
    wd.add(Box((0, 0.3, -0.172), (0.024, 0.3, 0.022), round=0.01).lumpy(0.001, 10, 5), k=0.012)
    wood_grain(wd, 2, seed=2)
    wd.paint(blotch_prim(55, 0.25, seed=6, stretch=(1, 0.08, 1)), "#6c4f35", feather=0.004)
    for z in (-0.11, 0.0, 0.1):
        score(wd, [(-0.14, 0.032, z), (0.0, 0.0325, z + 0.004), (0.14, 0.032, z - 0.003)], 0.0012)
    br = m.piece("bracket", color="#bd8a2e", gloss=G_METAL, lumps=0.0005, mottle=0.04, res=0.0024, decimate=1000)
    arm = [(0, 0.55, -0.165), (0, 0.585, -0.12), (0, 0.6, -0.05), (0, 0.6, 0.0), (0, 0.585, 0.02)]
    br.add(Tube(arm, 0.0105, samples=5))
    br.add(Tube([(0, 0.55, -0.15), (0, 0.5, -0.145), (0, 0.48, -0.11), (0, 0.5, -0.085), (0, 0.53, -0.095)], 0.006, samples=5), k=0.004)
    br.add(Cylinder((0, 0.57, -0.152), 0.03, 0.006, rot=(90, 0, 0), round=0.003), k=0.004)  # wall rose plate
    for dx, dy in ((-0.016, 0.0), (0.016, 0.0), (0.0, 0.017)):
        br.add(Sphere((dx, 0.57 + dy - 0.006, -0.145), 0.0045), k=0.002)
    br.add(Torus((0, 0.567, 0.0), 0.02, 0.0055, rot=(0, 0, 90)), k=0.002)  # shackle through the crown loop
    brass_finish(br, r=0.004, tarnish=0.05, wear=0.24, seed=9)

    cr = m.piece("crust", color="#ddd5c2", gloss=40, lumps=0.0005, mottle=0.08, res=0.002, decimate=500)
    for phi, y, r in ((-2.2, 0.25, 0.011), (-2.5, 0.225, 0.008), (1.9, 0.07, 0.009), (-1.7, 0.19, 0.006)):
        r0 = bell_r(y)
        barnacle(cr, (r0 * np.sin(phi), y + lift, r0 * np.cos(phi)), (np.sin(phi), 0.25, np.cos(phi)), r)
    return m


class Extrude(Prim):
    """A flat 2D polygon (in the plane through c with normal n; u axis = `uaxis`) extruded +-hh, edge rounded."""

    def __init__(self, poly, c, n=(0, 1, 0), uaxis=(1, 0, 0), hh=0.001, round=0.0):
        super().__init__()
        self.V = np.asarray(poly, float)
        self.c = np.asarray(c, float)
        n = np.asarray(n, float) / np.linalg.norm(n)
        u = np.asarray(uaxis, float)
        u = u - n * (u @ n)
        u /= np.linalg.norm(u)
        self.n, self.u, self.v = n, u, np.cross(n, u)
        self.hh, self.rd = hh, round

    def sdf(self, P):
        q = P - self.c
        p2 = np.column_stack([q @ self.u, q @ self.v])
        wx = poly_sdf(p2, self.V) + self.rd
        wy = np.abs(q @ self.n) - (self.hh - self.rd)
        return np.minimum(np.maximum(wx, wy), 0) + np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wy, 0) ** 2) - self.rd

    def bounds(self):
        r = np.max(np.linalg.norm(self.V, axis=1)) + self.hh
        return self.c - r, self.c + r


def strokes_3d(strokes, origin, uvec, vvec, size, flip_u=False):
    """Map unit-box font strokes onto a plane: origin = text centre-bottom."""
    out = []
    width = max([max(u for u, _ in s) for s in strokes] + [0.0])
    for s in strokes:
        pts = []
        for u, v in s:
            uu = (u - width / 2) * size
            pts.append(np.asarray(origin) + np.asarray(uvec) * (-uu if flip_u else uu) + np.asarray(vvec) * v * size)
        pts = np.array(pts)
        if len(pts) == 1:
            pts = np.vstack([pts, pts + np.asarray(vvec) * 0.001])
        out.append(pts)
    return out


# ==============================================================================================================
# brass compass — open-lid pocket compass, painted rose with a red north, spinning needle, anchor engraved in the lid


def brass_compass():
    m = TModel("brass_compass", res=0.0022)
    m.bone("root")
    R0, H = 0.085, 0.042
    hinge = np.array([0, H - 0.004, -R0 - 0.006])
    m.bone("needle", "root", (0, 0.0325, 0))
    BR = "#bd8a2e"

    case = m.piece("case", color=BR, gloss=G_METAL, lumps=0.0005, lump_freq=25, dents=8, dent_size=0.012, dent_depth=0.0009,
                   mottle=0.04, decimate=3200)
    case.add(Cylinder((0, H / 2, 0), R0, H / 2, round=0.012))
    case.add(Torus((0, H - 0.002, 0), R0 - 0.007, 0.0065), k=0.004)                         # bezel
    case.sub(Cylinder((0, H, 0), R0 - 0.014, 0.02, round=0.002), k=0.002)                    # dial recess (floor 0.022)
    case.add(Torus((0, 0.016, 0), R0 + 0.0005, 0.003), k=0.002)                              # milled base band
    for i in range(48):
        a = i / 48 * TAU
        case.sub(Capsule((np.sin(a) * (R0 + 0.003), 0.011, np.cos(a) * (R0 + 0.003)),
                         (np.sin(a) * (R0 + 0.003), 0.021, np.cos(a) * (R0 + 0.003)), 0.0013), k=0.0008)
    # hinge knuckles at the back, thumb catch at the front
    case.add(Cylinder(hinge + (0.0, 0, 0.0), 0.0065, 0.018, rot=(0, 0, 90), round=0.003), k=0.004)
    case.add(Box((0, H - 0.008, R0 + 0.002), (0.012, 0.005, 0.006), round=0.003), k=0.004)
    brass_finish(case, base=BR, r=0.004, tarnish=0.08, wear=0.3, verd=0.2, light="#e8c070")

    # dial: cream enamel under glass (high gloss), compass rose pressed on as thin clay shapes
    dial = m.piece("dial", color="#efe6cf", gloss=175, lumps=0.0, mottle=0.03, res=0.0012, decimate=4400)
    top = 0.027
    dial.add(Ellipsoid((0, top - 0.004, 0), (R0 - 0.0145, 0.006, R0 - 0.0145)))
    dial.inter(HalfSpace((0, top, 0), (0, 1, 0)), k=0.0008)
    star4, star8 = [], []
    for i in range(8):
        a = i / 8 * TAU
        rr = 0.058 if i % 2 == 0 else 0.015
        star4.append((np.sin(a) * rr, np.cos(a) * rr))
    for i in range(16):
        a = i / 16 * TAU + TAU / 16
        rr = 0.043 if i % 2 == 0 else 0.012
        star8.append((np.sin(a) * rr, np.cos(a) * rr))
    # uv: u = +x, v = +z (north at +z = toward the viewer's front... rotate the rose so N points to the back/up the dial)
    dial.add(Extrude(star8, (0, top, 0), (0, 1, 0), (1, 0, 0), hh=0.0012, round=0.0004), k=0.0006)
    dial.add(Extrude(star4, (0, top + 0.0006, 0), (0, 1, 0), (1, 0, 0), hh=0.0014, round=0.0004), k=0.0006)
    dial.paint(Extrude(star8, (0, top, 0), (0, 1, 0), (1, 0, 0), hh=0.004), "#c99a46", gloss=200, feather=0.0006)
    dial.paint(Extrude(star4, (0, top + 0.0006, 0), (0, 1, 0), (1, 0, 0), hh=0.004), "#26324f", gloss=210, feather=0.0006)
    # light halves of the main points (classic two-tone rose)
    for i in range(4):
        a = i / 4 * TAU
        tip = (np.sin(a) * 0.058, np.cos(a) * 0.058)
        b2 = (np.sin(a + TAU / 8) * 0.015, np.cos(a + TAU / 8) * 0.015)
        dial.paint(Extrude([(0, 0), tip, b2], (0, top + 0.0006, 0), (0, 1, 0), (1, 0, 0), hh=0.004), "#e9dcc0", gloss=210,
                   feather=0.0005)
    # north point: red (the dial's north faces the back, toward the hinge, so it reads "up" in the open view)
    northV = [(0, 0), (0.0095 * np.sin(-TAU / 8), -0.0095 * np.cos(TAU / 8)), (0, -0.058), (0.0095 * np.sin(TAU / 8), -0.0095 * np.cos(TAU / 8))]
    dial.paint(Extrude([(0.0, 0.0), (-0.0106, 0.0106), (0, 0.059), (0.0106, 0.0106)], (0, top + 0.0006, 0), (0, 1, 0), (1, 0, 0),
                       hh=0.004), "#c7352c", gloss=220, feather=0.0005)
    # a pressed ridge down every point keeps the two-tone split crisp
    for i in range(8):
        a = i / 8 * TAU
        rr = 0.056 if i % 2 == 0 else 0.041
        hgt = top + (0.0021 if i % 2 == 0 else 0.0013)
        dial.add(Capsule((0, hgt, 0), (np.sin(a) * rr, hgt - 0.0006, np.cos(a) * rr), 0.0011, 0.0005), k=0.0008)
    # degree ring + ticks
    dial.add(Torus((0, top - 0.0004, 0), 0.0635, 0.0009), k=0.0004)
    for i in range(36):
        a = i / 36 * TAU
        r1 = 0.0655 if i % 9 else 0.067
        dial.add(Capsule((np.sin(a) * 0.0615, top - 0.0004, np.cos(a) * 0.0615), (np.sin(a) * r1, top - 0.0004, np.cos(a) * r1), 0.0007),
                 k=0.0003)
    dial.paint(func_prim(lambda P: np.abs(np.hypot(P[:, 0], P[:, 2]) - 0.0645) - 0.0035), "#3b3530", gloss=200, feather=0.0006)
    # N E S W letters (N at -z, toward the hinge; read from the front)
    for ch, a in (("N", np.pi), ("E", -np.pi / 2), ("S", 0.0), ("W", np.pi / 2)):
        st, _ = text_strokes(ch)
        cpos = np.array([np.sin(a) * 0.05, top + 0.0003, np.cos(a) * 0.05])
        for pts in strokes_3d(st, cpos + np.array([0, 0, 0.0055]), (-1, 0, 0), (0, 0, -1), 0.011):
            dial.add(Tube(pts, 0.0008), k=0.0003, color="#c7352c" if ch == "N" else "#2b2b30")

    # needle (spins on bone `needle`): red north half, blued-steel south half, brass pivot cap
    nd = m.piece("needle", color="#3a4150", gloss=200, rigid="needle", lumps=0.0, mottle=0.02, res=0.0011, decimate=900)
    ang = np.radians(14)
    nd.add(Extrude([(0, 0.052), (0.0065, 0), (0, -0.046), (-0.0065, 0)], (0, 0.0325, 0), (0, 1, 0), (np.cos(ang), 0, np.sin(ang)),
                   hh=0.0013, round=0.0005))
    nvec = np.array([-np.sin(ang), 0, -np.cos(ang)])  # needle points back-ish (north) with a little swing
    nd.paint(HalfSpace((0, 0, 0), -nvec), "#cc3a2e", gloss=220, feather=0.0008)
    nd.add(Capsule((0, 0.026, 0), (0, 0.0335, 0), 0.0016), k=0.001)
    nd.add(Sphere((0, 0.0345, 0), 0.0052), k=0.001, color="#d6a640", gloss=230)

    # lid: open past upright, the inside polished with an engraved anchor
    def L(pr):
        return Xf(pr, (-104, 0, 0), pivot=hinge)
    lid = m.piece("lid", color=BR, gloss=G_METAL, lumps=0.0005, lump_freq=25, dents=6, dent_size=0.012, dent_depth=0.0009,
                  mottle=0.04, decimate=2700)
    lc = np.array([0, H + 0.006, 0])
    lid.add(L(Cylinder(lc, R0 + 0.001, 0.008, round=0.007)))
    lid.add(L(Ellipsoid(lc + (0, 0.004, 0), (R0 - 0.01, 0.009, R0 - 0.01))), k=0.01)
    lid.sub(L(Cylinder(lc - (0, 0.006, 0), R0 - 0.008, 0.005, round=0.002)), k=0.002)
    lid.add(L(Cylinder(hinge, 0.0062, 0.032, rot=(0, 0, 90), round=0.003)), k=0.003)
    lid.add(L(Torus(lc - (0, 0.0015, 0), R0 - 0.022, 0.0012)), k=0.0006)
    # anchor engraving on the lid's inside (faces the viewer once open)
    anchor = [[(0.35, 0.95), (0.35, 0.12)], [(0.12, 0.78), (0.58, 0.78)], [(0.0, 0.32), (0.08, 0.14), (0.35, 0.02), (0.62, 0.14), (0.7, 0.32)],
              [(0.0, 0.32), (0.07, 0.26)], [(0.7, 0.32), (0.63, 0.26)]]
    for pts in strokes_3d(anchor, lc - (0, 0.0011, 0.03), (-1, 0, 0), (0, 0, 1), 0.06):
        lid.sub(L(Tube(pts, 0.0019)), k=0.0008)
    lid.sub(L(Torus(lc - (0, 0.0011, -0.034), 0.0048, 0.0016)), k=0.0008)
    brass_finish(lid, base=BR, r=0.004, tarnish=0.08, wear=0.3, verd=0.2, light="#e8c070", seed=12)
    cr = m.piece("crust", color="#ddd5c2", gloss=40, lumps=0.0004, mottle=0.08, res=0.0016, decimate=500)
    barnacle(cr, (0.062, 0.02, -0.058), (0.7, 0.2, -0.65), 0.008)
    barnacle(cr, (0.072, 0.03, -0.035), (0.9, 0.3, -0.3), 0.0055)
    return m


# ==============================================================================================================
# pearl — a giant glossy pearl in an open oyster: rough lamellate outside, iridescent nacre inside


def _oyster_valve(c, rad, inner_off, inner_rad, rim_y, upper, hinge_z, ridge=0.0028, period=0.016, seed=1):
    """One oyster valve as a Func: an ellipsoidal cup with stepped growth lamellae and a ruffled rim."""
    c, rad, inner_off, inner_rad = (np.asarray(v, float) for v in (c, rad, inner_off, inner_rad))
    outer = Ellipsoid(c, rad)
    inner = Ellipsoid(c + inner_off, inner_rad)
    sgn = 1.0 if upper else -1.0

    def f(P):
        d = outer.sdf(P)
        rho = np.hypot(P[:, 0] - c[0], (P[:, 2] - hinge_z) * 0.9)
        saw = (rho / period) % 1.0
        d = d + ridge * saw ** 2 * np.clip(rho / 0.04, 0, 1)
        d = d + 0.003 * fbm(P * 30.0, 2, seed)
        d = np.maximum(d, -inner.sdf(P))
        th = np.arctan2(P[:, 0] - c[0], P[:, 2] - c[2])
        rim = rim_y + 0.006 * np.sin(th * 7 + seed) + 0.003 * np.sin(th * 13 + 2 * seed)
        d = np.maximum(d, sgn * (rim - P[:, 1]))
        return d
    lo = c - rad - 0.01
    hi = c + rad + 0.01
    return Func(f, lo, hi)


def pearl():
    m = TModel("pearl", res=0.0028)
    hz = -0.115
    hinge = np.array([0, 0.062, hz])
    OUT, NAC = "#857868", "#ebe5dc"
    sh = m.piece("shell", color=OUT, gloss=45, lumps=0.0015, lump_freq=12, dents=8, dent_size=0.02, dent_depth=0.002,
                 mottle=0.12, decimate=4200)
    lower = _oyster_valve((0, 0.06, 0.0), (0.13, 0.06, 0.14), (0, 0.012, 0.006), (0.112, 0.05, 0.12), 0.066, False, hz, seed=1)
    sh.add(lower)
    sh.add(Ellipsoid((0, 0.06, hz + 0.01), (0.035, 0.012, 0.02)), k=0.012)  # hinge boss
    inner_lo = Ellipsoid((0, 0.072, 0.006), (0.114, 0.052, 0.122))
    sh.paint(inner_lo, NAC, gloss=215, feather=0.004)
    sh.paint(inter_prim(Ellipsoid((0, 0.072, 0.006), (0.12, 0.058, 0.128)), not_prim(inner_lo)), "#5c4752", gloss=90, feather=0.003)
    for col, seed, fr in (("#efcfd6", 2, 22), ("#d4d6ee", 3, 18), ("#cfe6e2", 4, 26)):
        sh.paint(inter_prim(inner_lo, blotch_prim(fr, 0.15, seed=seed)), col, gloss=220, feather=0.004)
    # growth bands (darker rings) + greenish weed on the outside
    bands = func_prim(lambda P: np.abs(((np.hypot(P[:, 0], (P[:, 2] - hz) * 0.9) / 0.016) % 1.0) - 0.15) - 0.1)
    sh.paint(inter_prim(bands, not_prim(Ellipsoid((0, 0.072, 0.006), (0.12, 0.058, 0.128)))), "#6a5d50", feather=0.004)
    sh.paint(blotch_prim(14, 0.2, seed=5, region=not_prim(inner_lo)), "#617040", gloss=40, feather=0.004)
    # upper valve, flatter, flipped open on the hinge
    up = m.piece("lid", color=OUT, gloss=45, lumps=0.0015, lump_freq=12, dents=8, dent_size=0.02, dent_depth=0.002,
                 mottle=0.12, decimate=3600)
    upper = _oyster_valve((0, 0.066, 0.0), (0.122, 0.034, 0.132), (0, -0.01, 0.006), (0.106, 0.026, 0.115), 0.064, True, hz,
                          seed=4)
    ang = -72

    def U(pr):
        return Xf(pr, (ang, 0, 0), pivot=hinge)
    up.add(U(upper))
    inner_up = Ellipsoid((0, 0.056, 0.006), (0.108, 0.028, 0.117))
    up.paint(U(inner_up), NAC, gloss=215, feather=0.004)
    up.paint(U(inter_prim(Ellipsoid((0, 0.056, 0.006), (0.114, 0.033, 0.123)), not_prim(inner_up))), "#5c4752", gloss=90, feather=0.003)
    for col, seed, fr in (("#efcfd6", 7, 22), ("#d4d6ee", 8, 18), ("#cfe6e2", 9, 26)):
        up.paint(U(inter_prim(inner_up, blotch_prim(fr, 0.15, seed=seed))), col, gloss=220, feather=0.004)
    up.paint(U(inter_prim(bands, not_prim(Ellipsoid((0, 0.056, 0.006), (0.114, 0.033, 0.123))))), "#6a5d50", feather=0.004)
    # the pearl: big, round, wet-glossy, faint pink and blue lustre
    pc = np.array([0.0, 0.098, 0.018])
    pr = 0.054
    pe = m.piece("pearl", color="#f3eee5", gloss=255, lumps=0.0003, lump_freq=10, mottle=0.015, res=0.0022, decimate=1600, ao=False)
    pe.add(Sphere(pc, pr))
    pe.paint(Sphere(pc + (-0.03, -0.035, 0.02), 0.05), "#f2dadd", gloss=255, feather=0.02)
    pe.paint(Sphere(pc + (0.035, 0.03, -0.01), 0.045), "#e1e8f3", gloss=255, feather=0.02)
    pe.paint(Sphere(pc + (0.0, 0.05, 0.03), 0.02), "#fbfaf6", gloss=255, feather=0.012)
    cr = m.piece("crust", color="#ddd5c2", gloss=40, lumps=0.0004, mottle=0.08, res=0.0018, decimate=600)
    barnacle(cr, (0.09, 0.03, -0.06), (0.8, 0.1, -0.5), 0.011)
    barnacle(cr, (-0.1, 0.035, 0.03), (-0.9, 0.2, 0.2), 0.008)
    return m


# ==============================================================================================================
# gold doubloon — a little stack and spill of hand-struck gold cobs: cross, castles-and-lions dots, worn rims


def _coin(piece, c, rot, r=0.03, hh=0.0036, seed=0):
    R = euler(rot)
    n = R @ np.array([0, 1.0, 0])
    u = R @ np.array([1.0, 0, 0])
    w = R @ np.array([0, 0, 1.0])
    rng = np.random.default_rng(seed)
    piece.add(Cylinder(c, r, hh, rot=rot, round=0.0022).lumpy(0.0012, 55, seed), k=0.0012)
    for side in (1, -1):
        f = np.asarray(c) + n * hh * side
        a = rng.uniform(0, np.pi)
        ua = u * np.cos(a) + w * np.sin(a)
        wa = np.cross(n, ua)
        piece.add(Capsule(f - ua * r * 0.55, f + ua * r * 0.55, 0.0028), k=0.001)
        piece.add(Capsule(f - wa * r * 0.55, f + wa * r * 0.55, 0.0028), k=0.001)
        for q in range(4):
            qa = (ua * np.cos(q * np.pi / 2 + np.pi / 4) + wa * np.sin(q * np.pi / 2 + np.pi / 4)) * r * 0.42
            piece.add(Sphere(f + qa, 0.0032), k=0.001)
        piece.add(Torus(f - n * 0.0006 * side, r * 0.83, 0.0012, rot=look_rot(n)), k=0.0006)
        for b in range(14):
            ba = b / 14 * TAU
            piece.sub(Sphere(f + (u * np.cos(ba) + w * np.sin(ba)) * r * 0.92, 0.0016), k=0.0006)


def gold_doubloon():
    m = TModel("gold_doubloon", res=0.0016)
    co = m.piece("coins", color="#d19a24", gloss=185, lumps=0.0004, lump_freq=30, dents=14, dent_size=0.008, dent_depth=0.0008,
                 mottle=0.05, decimate=8600)
    rng = np.random.default_rng(7)
    y = 0.0036
    base = np.array([-0.025, 0, -0.015])
    for i in range(6):
        off = rng.uniform(-0.006, 0.006, 3) * (1, 0, 1)
        _coin(co, base + off + (0, y, 0), (rng.uniform(-3, 3), rng.uniform(0, 90), rng.uniform(-3, 3)), seed=i)
        y += 0.0074
    # one coin leaning on the stack, the rest spilled
    _coin(co, (0.022, 0.025, -0.006), (0, 20, 62), seed=11)
    spill = [((0.045, 0.0036, 0.035), (2, 10, 0)), ((0.0, 0.0036, 0.05), (0, 40, 0)), ((-0.055, 0.0036, 0.035), (0, 70, 2)),
             ((0.07, 0.0036, -0.025), (0, 5, 0)), ((0.035, 0.009, 0.06), (0, 80, -9)), ((-0.07, 0.0036, -0.03), (0, 25, 0))]
    for i, (c, rot) in enumerate(spill):
        _coin(co, c, rot, seed=20 + i)
    brass_finish(co, base="#d19a24", dark="#6e4510", light="#f4d27a", r=0.0035, tarnish=0.08, wear=0.32, seed=3)
    return m


# ==============================================================================================================
# pocket watch — gold hunter-case watch leaning back on its open lid, enamel dial, blued hands, draped chain


def chain(piece, pts, link=0.0095, wire=0.0022, samples=6, phase=0.0):
    """Interlocking oval links along a curve (alternating 90 degrees)."""
    dense = smooth_curve(np.asarray(pts, float), samples)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))]
    step = link * 1.45
    ss = np.arange(step * 0.5, seg[-1], step)
    P = np.column_stack([np.interp(ss, seg, dense[:, i]) for i in range(3)])
    for i, p in enumerate(P):
        j0, j1 = max(i - 1, 0), min(i + 1, len(P) - 1)
        t = P[j1] - P[j0]
        t /= np.linalg.norm(t) + 1e-12
        a = np.cross(t, [0.0, 1.0, 0.0])
        if np.linalg.norm(a) < 0.2:
            a = np.cross(t, [1.0, 0, 0])
        a /= np.linalg.norm(a)
        b = np.cross(t, a)
        ang = phase + (np.pi / 2 if i % 2 else 0.0)
        nrm = np.cos(ang) * a + np.sin(ang) * b  # link plane normal
        # oval link = two half-tori joined: approximate with a stretched torus via a capsule loop
        side = np.cross(nrm, t)
        q = [p - t * link * 0.55, p - t * link * 0.3 + side * link * 0.42, p + t * link * 0.3 + side * link * 0.42,
             p + t * link * 0.55, p + t * link * 0.3 - side * link * 0.42, p - t * link * 0.3 - side * link * 0.42,
             p - t * link * 0.55]
        piece.add(Tube(q, wire, samples=3), k=wire * 0.3)
    return P


def pocket_watch():
    m = TModel("pocket_watch", res=0.0016)
    r, th = 0.068, 0.011
    GOLD = "#cf9a2a"
    lean = -22.0
    Rl = euler((lean, 0, 0))
    lift = np.array([0, r * np.cos(np.radians(lean)) + th * 0.6, 0])

    def X(p):
        return Xf(p, (lean, 0, 0), t=lift)

    def W(q):
        return Rl @ np.asarray(q, float) + lift

    case = m.piece("case", color=GOLD, gloss=185, lumps=0.0004, lump_freq=30, dents=8, dent_size=0.01, dent_depth=0.0008,
                   mottle=0.04, decimate=3400)
    case.add(X(Ellipsoid((0, 0, -0.004), (r, r, th * 1.15))))
    case.add(X(Torus((0, 0, th * 0.55), r - 0.006, 0.0058, rot=(90, 0, 0))), k=0.003)      # front bezel
    case.sub(X(Cylinder((0, 0, th * 0.75), r - 0.011, 0.006, rot=(90, 0, 0), round=0.001)), k=0.0015)
    # pendant, crown (knurled) and bow at 12
    case.add(X(Capsule((0, r - 0.006, 0), (0, r + 0.012, 0), 0.0065, 0.0055)), k=0.003)
    case.add(X(Cylinder((0, r + 0.017, 0), 0.0085, 0.0055, round=0.002)), k=0.002)
    for i in range(14):
        a = i / 14 * TAU
        case.sub(X(Capsule((np.sin(a) * 0.0088, r + 0.0125, np.cos(a) * 0.0088), (np.sin(a) * 0.0088, r + 0.0215, np.cos(a) * 0.0088), 0.0011)),
                 k=0.0006)
    case.add(X(Torus((0, r + 0.02, 0), 0.019, 0.0028, rot=(90, 0, 0))), k=0.002)            # the bow
    case.add(X(Cylinder((r + 0.002, 0, 0.0), 0.004, 0.016, round=0.002)), k=0.002)            # hinge knuckle at 9
    brass_finish(case, base=GOLD, dark="#6e4510", light="#f4d27a", r=0.0035, tarnish=0.08, wear=0.3, seed=2)

    dial = m.piece("dial", color="#f3efe4", gloss=170, lumps=0.0, mottle=0.02, res=0.0011, decimate=3000)
    dz = th * 0.75 - 0.006
    fz = dz + 0.0015
    # flat enamel front, domed back (a perfectly flat back face stalls the decimator)
    dial.add(X(Ellipsoid((0, 0, fz - 0.003), (r - 0.0105, r - 0.0105, 0.0058))))
    dial.inter(X(HalfSpace((0, 0, fz), (0, 0, 1))), k=0.0008)
    # chapter ring and roman numerals (XII, III, VI, IX) + minute ticks
    dial.add(X(Torus((0, 0, fz), r - 0.016, 0.0006, rot=(90, 0, 0))), k=0.0003, color="#2c2a2e")
    dial.add(X(Torus((0, 0, fz), r - 0.03, 0.0006, rot=(90, 0, 0))), k=0.0003, color="#2c2a2e")
    for i in range(12):
        a = i / 12 * TAU
        if i % 3 == 0:
            continue
        c = np.array([-np.sin(a), np.cos(a), 0]) * (r - 0.023)
        u = np.array([np.cos(a), np.sin(a), 0]) * -1
        for pts in strokes_3d([[(0.35, 0.0), (0.35, 1.0)]], c + (0, 0, fz) - np.array([-np.sin(a), np.cos(a), 0]) * 0.0045,
                              u, np.array([-np.sin(a), np.cos(a), 0]), 0.009):
            dial.add(X(Tube(pts, 0.0011)), k=0.0003, color="#2c2a2e")
    for txt, a in (("XII", 0.0), ("III", -np.pi / 2), ("VI", np.pi), ("IX", np.pi / 2)):
        st, _ = text_strokes(txt, 0.75)
        c = np.array([-np.sin(a), np.cos(a), 0]) * (r - 0.0235)
        for pts in strokes_3d(st, c + (0, -0.0055, fz), (-1, 0, 0), (0, 1, 0), 0.0105):
            dial.add(X(Tube(pts, 0.0011)), k=0.0003, color="#2c2a2e")
    # sub-seconds at 6
    dial.sub(X(Cylinder((0, -0.026, fz), 0.011, 0.0012, rot=(90, 0, 0), round=0.0005)), k=0.0005, color="#d9d2c0")
    dial.add(X(Torus((0, -0.026, fz - 0.0008), 0.011, 0.0005, rot=(90, 0, 0))), k=0.0002, color="#2c2a2e")
    # hands: blued steel, spade hour hand at ~10, minute hand at ~2
    hands = m.piece("hands", color="#26304a", gloss=230, lumps=0.0, mottle=0.02, res=0.0009, decimate=900)
    hz = fz + 0.0018
    ha, ma = np.radians(55), np.radians(-62)
    hd = np.array([-np.sin(ha), np.cos(ha), 0])
    md = np.array([-np.sin(ma), np.cos(ma), 0])
    hands.add(X(Capsule((0, 0, hz), tuple(hd * 0.026 + (0, 0, hz)), 0.0012, 0.0009)))
    hands.add(X(Ellipsoid(tuple(hd * 0.026 + (0, 0, hz)), (0.0045, 0.0045, 0.0008))), k=0.0008)
    hands.sub(X(Sphere(tuple(hd * 0.0265 + (0, 0, hz)), 0.0018)), k=0.0004)
    hands.add(X(Capsule((0, 0, hz + 0.0012), tuple(md * 0.041 + (0, 0, hz + 0.0012)), 0.0011, 0.0006)), k=0.0008)
    hands.add(X(Cylinder((0, 0, hz + 0.0008), 0.0028, 0.0022, rot=(90, 0, 0), round=0.001)), k=0.0008, color="#d6a640")
    hands.add(X(Capsule((0, -0.026, hz - 0.001), (0.006, -0.0335, hz - 0.001), 0.0006)), k=0.0004)

    # hunter lid swung open about the 9 o'clock hinge, standing behind as a kickstand; engraved monogram inside
    hinge = np.array([r + 0.002, 0, 0.0])
    lid = m.piece("lid", color=GOLD, gloss=185, lumps=0.0004, lump_freq=30, dents=6, dent_size=0.01, dent_depth=0.0008,
                  mottle=0.04, decimate=2600)

    def L(p):
        return X(Xf(p, (0, -138, 0), pivot=hinge))
    lc = np.array([0, 0, th * 0.9])
    lid.add(L(Ellipsoid(lc + (0, 0, 0.002), (r + 0.0005, r + 0.0005, 0.0075))))
    lid.sub(L(Ellipsoid(lc + (0, 0, -0.0035), (r - 0.004, r - 0.004, 0.0062))), k=0.002)
    lid.inter(L(HalfSpace(lc + (0, 0, -0.0035), (0, 0, -1))), k=0.0015)
    for rr in (0.045, 0.05):
        lid.sub(L(Torus(lc + (0, 0, 0.0088), rr, 0.0008, rot=(90, 0, 0))), k=0.0004)
    # scrolling engraving on the outside of the cover
    for i in range(8):
        a0 = i / 8 * TAU
        pts = [lc + (np.cos(a0 + t * 0.7) * (0.012 + t * 0.03), np.sin(a0 + t * 0.7) * (0.012 + t * 0.03), 0.0092 - t * 0.0012)
               for t in np.linspace(0, 1, 6)]
        lid.sub(L(Tube(pts, 0.0008)), k=0.0004)
    brass_finish(lid, base=GOLD, dark="#6e4510", light="#f4d27a", r=0.0035, tarnish=0.08, wear=0.3, seed=7)

    # chain: from the bow, down the right side to the table, curling forward, ending in a T-bar
    ch = m.piece("chain", color=GOLD, gloss=200, lumps=0.0, mottle=0.04, res=0.0011, decimate=3000)
    b0 = W((0, r + 0.02 + 0.019, 0))
    pts = [b0, W((-0.03, r + 0.04, -0.004)), W((-0.065, r + 0.01, -0.006)), W((-0.085, -0.03, 0.0)),
           (-0.095, 0.003, 0.03), (-0.07, 0.003, 0.075), (-0.02, 0.003, 0.085), (0.03, 0.003, 0.07)]
    P = chain(ch, pts, link=0.0085, wire=0.0019)
    tb = P[-1]
    tdir = P[-1] - P[-2]
    tdir /= np.linalg.norm(tdir)
    tside = np.cross([0, 1.0, 0], tdir)
    ch.add(Capsule(tb + tdir * 0.006 - tside * 0.016, tb + tdir * 0.006 + tside * 0.016, 0.0028), k=0.002)
    for sgn in (-1, 1):
        ch.add(Sphere(tb + tdir * 0.006 + tside * 0.017 * sgn, 0.0038), k=0.0015)
    brass_finish(ch, base=GOLD, dark="#6e4510", light="#f4d27a", r=0.0025, tarnish=0.12, wear=0.45, seed=9)
    return m


# ==============================================================================================================
# spyglass — brass telescope with draw tubes pulled out, leather-wrapped barrel, lens and caps, resting on a pebble


def spyglass():
    m = TModel("spyglass", res=0.0026)
    BR = "#bd8a2e"
    rot = (0, 0, -90)  # local +y (tube axis) -> world +x

    def X(p, x0=0.0):
        return Xf(p, rot, t=(0, 0.04, 0))
    # profile along the axis (radius, y): objective sunshade at y=-0.25, eyepiece at y=+0.25
    br = m.piece("brass", color=BR, gloss=G_METAL, lumps=0.0006, lump_freq=18, dents=10, dent_size=0.015, dent_depth=0.0012,
                 mottle=0.04, decimate=4600)
    out = [(0.0, -0.262), (0.031, -0.262), (0.0375, -0.258), (0.0375, -0.205), (0.034, -0.2), (0.034, -0.19),
           (0.0305, -0.185), (0.0305, 0.03), (0.0335, 0.033), (0.0335, 0.05), (0.025, 0.054), (0.0245, 0.14),
           (0.0275, 0.143), (0.0275, 0.156), (0.019, 0.16), (0.0185, 0.228), (0.021, 0.231), (0.021, 0.244),
           (0.015, 0.247), (0.015, 0.262), (0.0, 0.262)]
    br.add(X(Revolve(out, round=0.001)))
    br.sub(X(Cylinder((0, -0.262, 0), 0.026, 0.008, round=0.002)), k=0.002)               # objective recess
    for y in (-0.232, -0.215, 0.041, 0.149, 0.237):
        rr = np.interp(y, [p[1] for p in out], [p[0] for p in out])
        br.add(X(Torus((0, y, 0), rr, 0.0016)), k=0.001)
    # draw-tube seams scored
    for y in (0.09, 0.19):
        rr = np.interp(y, [p[1] for p in out], [p[0] for p in out])
        br.sub(X(Torus((0, y, 0), rr + 0.0003, 0.0009)), k=0.0005)
    brass_finish(br, base=BR, r=0.004, tarnish=0.08, wear=0.28, verd=0.2, light="#e8c070", seed=4)
    br.paint(X(blotch_prim(16, 0.18, seed=6, region=Sphere((0, -0.23, -0.02), 0.04))), "#5e9a86", gloss=35, feather=0.004)

    # leather wrap over the main barrel with a stitched seam and spiral wrap grooves
    le = m.piece("leather", color="#6e3f25", gloss=55, lumps=0.0008, lump_freq=30, dents=12, dent_size=0.012, dent_depth=0.0012,
                 mottle=0.1, res=0.0022, decimate=2600)
    le.add(X(Cylinder((0, -0.077, 0), 0.0335, 0.1, round=0.003)))
    for i in range(10):
        y0 = -0.17 + i * 0.019
        pts = [(np.sin(t) * 0.0338, y0 + t / TAU * 0.019, np.cos(t) * 0.0338) for t in np.linspace(0, TAU, 14)]
        le.sub(X(Tube(pts, 0.0011, samples=None)), k=0.0006)
    for y in np.arange(-0.17, 0.02, 0.008):
        le.add(X(Capsule((0.0, y, 0.0336), (0.0, y + 0.004, 0.0336), 0.0009)), k=0.0004, color="#d9c7a0")
    le.paint(blotch_prim(26, 0.2, seed=3), "#4f2c19", feather=0.004)

    # lens: dark glossy glass in the objective, a brass cap pressed on the eyepiece
    gl = m.piece("lens", color="#1d3a45", gloss=250, lumps=0.0, mottle=0.03, res=0.0018, decimate=500, ao=False)
    gl.add(X(Ellipsoid((0, -0.255, 0), (0.026, 0.004, 0.026))))
    gl.paint(X(Sphere((0.01, -0.26, 0.012), 0.008)), "#7fb7c4", gloss=255, feather=0.004)
    cap = m.piece("cap", color="#a77b2b", gloss=G_METAL, lumps=0.0004, mottle=0.04, res=0.0018, decimate=700)
    cap.add(X(Cylinder((0, 0.262, 0), 0.0165, 0.006, round=0.0025)))
    cap.add(X(Torus((0, 0.267, 0), 0.0095, 0.0012)), k=0.0008)

    # pebble under the draw tubes keeps it level; a barnacle and a strand of weed
    st = m.piece("pebble", color="#86817a", gloss=25, lumps=0.003, lump_freq=30, dents=6, dent_size=0.012, mottle=0.12,
                 res=0.0025, decimate=700)
    st.add(Ellipsoid((0.17, 0.008, 0.0), (0.035, 0.016, 0.03), rot=(0, 30, 0)))
    st.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.003)
    cr = m.piece("crust", color="#ddd5c2", gloss=40, lumps=0.0004, mottle=0.08, res=0.0018, decimate=500)
    barnacle(cr, (-0.12, 0.072, 0.012), (0.0, 1.0, 0.3), 0.008)
    barnacle(cr, (-0.1, 0.07, 0.02), (0.0, 0.9, 0.5), 0.0055)
    wd = m.piece("weed", color=CP["kelp"], gloss=120, lumps=0.0006, mottle=0.1, res=0.0018, decimate=700)
    wd.add(Tube([(-0.215, 0.083, -0.01), (-0.21, 0.08, 0.02), (-0.2, 0.06, 0.04), (-0.19, 0.03, 0.05), (-0.17, 0.004, 0.06),
                 (-0.13, 0.002, 0.07)], [0.003, 0.004, 0.0045, 0.004, 0.0035, 0.002], samples=5))
    return m


# ==============================================================================================================
# sea glass — a little heap of frosted, sea-worn glass: greens, blues, amber, white, a cobalt rarity, a bottle lip


def sea_glass():
    m = TModel("sea_glass", res=0.0014)
    rng = np.random.default_rng(5)
    items = [
        # colour, centre, half-size (x, thickness, z), yaw, tilt(x, z), corners
        ("#6faa7d", (0.0, 0.0065, 0.0), (0.036, 0.0062, 0.027), 20, (0, 0), 5),
        ("#86c3cf", (0.047, 0.0058, 0.02), (0.027, 0.0055, 0.021), -30, (0, 0), 4),
        ("#b07a3e", (-0.044, 0.006, 0.018), (0.026, 0.006, 0.02), 60, (0, 0), 5),
        ("#e3e9e5", (0.012, 0.0055, 0.048), (0.022, 0.005, 0.016), 5, (0, 0), 4),
        ("#4f72bf", (-0.008, 0.0165, -0.004), (0.02, 0.0055, 0.016), 75, (7, -9), 5),
        ("#a6dccb", (0.033, 0.0155, -0.014), (0.019, 0.005, 0.014), -50, (-6, 10), 4),
        ("#9fae62", (-0.038, 0.0058, -0.032), (0.022, 0.0055, 0.017), 40, (0, 0), 5),
        ("#7fbf95", (0.006, 0.019, 0.018), (0.015, 0.0048, 0.012), 120, (5, 6), 4),
    ]
    for i, (col, c, rad, yaw, tilt, nc) in enumerate(items):
        pc = m.piece(f"pebble_{i}", color=col, gloss=34, lumps=0.0006, lump_freq=60, dents=9, dent_size=0.004, dent_depth=0.0005,
                     mottle=0.05, seed=40 + i, merge="glass", decimate=850)
        rot = (tilt[0], yaw, tilt[1])
        poly = []
        for k in range(nc):
            a = k / nc * TAU + rng.uniform(-0.3, 0.3)
            poly.append((np.cos(a) * rad[0] * rng.uniform(0.8, 1.05), np.sin(a) * rad[2] * rng.uniform(0.8, 1.05)))
        R = euler(rot)
        pc.add(Extrude(smooth_closed(poly, 2), c, R @ np.array([0, 1.0, 0]), R @ np.array([1.0, 0, 0]), hh=rad[1],
                       round=rad[1] * 0.85))
        # frosting: milky paler rims, a slightly clearer, deeper-toned core
        pc.paint(cavity_prim(pc, 0.003, 0.14, True, noise=0.02, seed=i), mix(col, "#ffffff", 0.38), gloss=22, feather=0.06)
        pc.paint(Ellipsoid(c, (rad[0] * 0.5, rad[1] * 3, rad[2] * 0.5), rot=rot), shade(col, 0.86), gloss=48, feather=0.008)
    sh = m.piece("shard", color="#8cc0a2", gloss=34, lumps=0.0006, lump_freq=60, dents=6, dent_size=0.004, dent_depth=0.0005,
                 mottle=0.05, merge="glass", decimate=900)
    sc = np.array([-0.062, -0.05, 0.062])
    sh.add(Sphere(sc, 0.068))
    sh.sub(Sphere(sc, 0.061), k=0.002)
    sh.inter(Ellipsoid((-0.05, 0.012, 0.055), (0.026, 0.03, 0.022), rot=(0, 35, 0)), k=0.004)
    sh.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.002)
    sh.paint(cavity_prim(sh, 0.003, 0.14, True, noise=0.02, seed=9), mix("#8cc0a2", "#ffffff", 0.4), gloss=22, feather=0.06)
    lp = m.piece("lip", color="#5f9474", gloss=40, lumps=0.0006, lump_freq=60, mottle=0.05, merge="glass", decimate=900)
    lc = np.array([0.03, 0.026, 0.006])
    lp.add(Torus(lc, 0.0125, 0.005, rot=(18, 0, 10)))
    lp.add(Torus(lc + (0, 0.0065, 0), 0.0112, 0.0038, rot=(18, 0, 10)), k=0.003)
    lp.inter(HalfSpace(lc + (0.0, 0, 0.002), (-0.4, 0, -1)), k=0.002)
    lp.paint(cavity_prim(lp, 0.003, 0.16, True, noise=0.02, seed=4), "#a9cdb8", gloss=24, feather=0.06)
    return m


# ==============================================================================================================
# message in a bottle — green glass bottle on its side (hollow `glass_clear`), waxed cork, scroll tied with red twine


BOTTLE = [(0.0, 0.0), (0.047, 0.0), (0.0545, 0.007), (0.056, 0.03), (0.0555, 0.2), (0.051, 0.228), (0.034, 0.253),
          (0.0215, 0.27), (0.019, 0.285), (0.019, 0.312), (0.0235, 0.315), (0.024, 0.323), (0.0195, 0.328),
          (0.0148, 0.328), (0.0148, 0.286), (0.017, 0.27), (0.029, 0.254), (0.0465, 0.23), (0.0515, 0.2),
          (0.0518, 0.03), (0.05, 0.011), (0.04, 0.007), (0.012, 0.016), (0.0, 0.018)]


def message_bottle():
    m = TModel("message_bottle", res=0.002)
    rot = (0, 0, 90)  # bottle axis (local +y) -> world -x: neck to the viewer's right in a front view
    y0 = 0.0565

    def X(p):
        return Xf(p, rot, t=(0.16, y0, 0))

    def W(q):
        return euler(rot) @ np.asarray(q, float) + np.array([0.16, y0, 0])
    g = m.piece("glass_clear", color="#9cc7a6", gloss=255, lumps=0.0006, lump_freq=25, dents=5, dent_size=0.02, dent_depth=0.0008,
                mottle=0.03, decimate=4200, ao=False)
    g.add(X(Revolve(BOTTLE, round=0.0006)))
    # frosted sea-worn patches + a seam line
    g.paint(X(blotch_prim(18, 0.22, seed=2)), "#bcd8c2", gloss=150, feather=0.004)
    # the cork, pulled, lies on the table beside the neck (sealing wax still on its top)
    ck = m.piece("cork", color=CP["cork"], gloss=30, lumps=0.0008, lump_freq=40, dents=10, dent_size=0.004, dent_depth=0.0007,
                 mottle=0.15, res=0.0013, decimate=900)
    cc = np.array([-0.235, 0.0155, 0.05])
    ck.add(Capsule(cc + (0.0, 0, -0.02), cc + (0.0, 0, 0.02), 0.0145, 0.0158))
    ck.add(Ellipsoid(cc + (0, 0.0, 0.0235), (0.019, 0.019, 0.006)), k=0.003, color="#b0352b", gloss=200)
    for a_ in (0.4, 2.2, 4.1):
        ck.add(Capsule(cc + (np.sin(a_) * 0.016, np.cos(a_) * 0.016, 0.022), cc + (np.sin(a_) * 0.0175, np.cos(a_) * 0.0175, 0.012),
                       0.003, 0.0024), k=0.002, color="#b0352b", gloss=200)
    ck.paint(inter_prim(blotch_prim(70, 0.3, seed=5), HalfSpace(cc + (0, 0, 0.016), (0, 0, 1))), "#7f5a34", feather=0.004)
    # the scroll: a tight roll of parchment from the bottom of the bottle out through the neck, tied with red twine
    sc = m.piece("scroll", color=CP["paper"], gloss=25, lumps=0.0005, lump_freq=30, dents=8, dent_size=0.01, dent_depth=0.0007,
                 mottle=0.08, res=0.0013, decimate=2200)
    sr = 0.0115
    a0 = W((0.0, 0.05, 0.0)) + np.array([0, -0.0515 + sr + 0.002, 0])
    a1 = W((0.0, 0.26, 0.0)) + np.array([0, -0.0148 + sr + 0.0015, 0])
    a2 = W((0.0, 0.372, 0.0)) + np.array([0, -0.004, 0])
    sc.add(Tube([a0, a0 + (a1 - a0) * 0.7, a1, a2], sr, samples=5))
    # the outer end flares open in a curl, with the spiral of the roll scored into the end
    sc.add(Ellipsoid(a2 + (-0.006, 0.0, 0), (0.009, 0.016, 0.016)), k=0.004)
    sc.add(Tube([a2 + (0.0, 0.012, 0.0), a2 + (-0.016, 0.02, 0.004), a2 + (-0.024, 0.012, 0.006)], 0.0032, samples=4), k=0.003)
    pts = [a2 + (-0.0145, np.cos(t) * (0.002 + t * 0.0018), np.sin(t) * (0.002 + t * 0.0018)) for t in np.linspace(0, 6.0, 20)]
    sc.sub(Tube(pts, 0.0008), k=0.0005)
    sc.paint(func_prim(lambda P: P[:, 0] - (a2[0] + 0.006)), "#d8c18f", feather=0.004)    # browned outer end
    sc.add(Torus(a2 + (0.008, 0, 0), sr + 0.0008, 0.0017, rot=(0, 0, 90)), k=0.001, color="#c94b3a")
    sc.add(Torus(a2 + (0.0115, 0, 0), sr + 0.0008, 0.0017, rot=(0, 0, 90)), k=0.001, color="#c94b3a")
    kn = a2 + (0.0095, 0.0, sr + 0.002)
    sc.add(Sphere(kn, 0.003), k=0.0012, color="#c94b3a")
    sc.add(Tube([kn, kn + (-0.006, -0.012, 0.008), kn + (0.002, -0.022, 0.016), kn + (-0.004, -0.03, 0.024)], 0.0014, samples=4),
           k=0.001, color="#c94b3a")
    sc.add(Tube([kn, kn + (0.008, -0.01, 0.006), kn + (0.014, -0.02, 0.016), kn + (0.02, -0.024, 0.026)], 0.0014, samples=4),
           k=0.001, color="#c94b3a")
    cr = m.piece("crust", color="#ddd5c2", gloss=40, lumps=0.0004, mottle=0.08, res=0.0016, decimate=500)
    barnacle(cr, W((0.02, 0.08, 0.05)), W((0.36, 0, 0.93)) - W((0, 0, 0)), 0.0075)
    barnacle(cr, W((0.035, 0.1, 0.035)), W((0.7, 0, 0.7)) - W((0, 0, 0)), 0.005)
    return m


# ==============================================================================================================
# diving helmet — copper Mark-V style bonnet on a bolted breastplate, brass port rings, grilles, verdigris


def diving_helmet():
    m = TModel("diving_helmet", res=0.004)
    CU, BR = "#b06a3c", "#bd8a2e"
    hc = np.array([0, 0.305, 0.0])
    hr = 0.158
    he = m.piece("helmet", color=CU, gloss=165, lumps=0.0016, lump_freq=8, dents=16, dent_size=0.035, dent_depth=0.003,
                 mottle=0.06, decimate=4800)
    he.add(Sphere(hc, hr))
    # breastplate: broad shoulders sloping down from the neck ring, flat flange at the bottom
    he.add(Ellipsoid((0, 0.0, 0.0), (0.238, 0.178, 0.196)), k=0.035)
    he.inter(HalfSpace((0, 0.016, 0), (0, -1, 0)), k=0.004)
    he.add(Ellipsoid((0, 0.013, 0.0), (0.25, 0.013, 0.206)), k=0.004)
    he.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.002)
    # recesses for the ports
    fp = hc + np.array([0, 0.0, hr - 0.01])
    he.sub(Cylinder(fp + (0, 0, 0.02), 0.062, 0.03, rot=(90, 0, 0)), k=0.005)
    for sx in (1, -1):
        sp = hc + np.array([sx * (hr - 0.01), 0.01, 0.0])
        he.sub(Cylinder(sp + (sx * 0.02, 0, 0), 0.045, 0.03, rot=(0, 0, 90)), k=0.005)
    tp = hc + np.array([0, hr * 0.8, hr * 0.55])
    he.sub(Sphere(tp + (0, 0.02, 0.012), 0.03), k=0.005)
    he.paint(blotch_prim(9, 0.22, seed=3), "#8d4e2c", gloss=110, feather=0.004)
    brass_finish(he, base=CU, dark="#4a2a18", light="#e0a070", r=0.008, tarnish=0.06, wear=0.12, verd=0.12, seed=2)
    he.paint(blotch_prim(10, 0.42, seed=8), "#5e9a86", gloss=35, feather=0.004)

    fi = m.piece("fittings", color=BR, gloss=G_METAL, lumps=0.0006, lump_freq=20, dents=10, dent_size=0.015, dent_depth=0.0012,
                 mottle=0.04, res=0.0028, decimate=5000)
    # neck ring with lugs
    fi.add(Torus((0, 0.17, 0), 0.118, 0.013))
    for i in range(6):
        a = i / 6 * TAU + 0.3
        fi.add(Box((np.sin(a) * 0.13, 0.17, np.cos(a) * 0.13), (0.012, 0.014, 0.01), rot=(0, np.degrees(a), 0), round=0.004), k=0.004)
    # face port: thick ring, 8 bolts
    fi.add(Torus(fp + (0, 0, 0.012), 0.062, 0.012, rot=(90, 0, 0)), k=0.004)
    for i in range(8):
        a = i / 8 * TAU
        fi.add(Cylinder(fp + (np.cos(a) * 0.062, np.sin(a) * 0.062, 0.024), 0.0055, 0.004, rot=(90, 0, 0), round=0.002), k=0.002)
    # side ports with grilles
    for sx in (1, -1):
        sp = hc + np.array([sx * (hr - 0.01), 0.01, 0.0])
        fi.add(Torus(sp + (sx * 0.01, 0, 0), 0.046, 0.0095, rot=(0, 0, 90)), k=0.004)
        for k_ in (-1, 0, 1):
            fi.add(Capsule(sp + (sx * 0.02, -0.042, k_ * 0.018), sp + (sx * 0.02, 0.042, k_ * 0.018), 0.0042), k=0.003)
        for i in range(6):
            a = i / 6 * TAU
            fi.add(Sphere(sp + (sx * 0.016, np.cos(a) * 0.046, np.sin(a) * 0.046), 0.0055), k=0.002)
    # top port with two bars
    tn = np.array([0, 0.8, 0.55]) / np.linalg.norm([0, 0.8, 0.55])
    fi.add(Torus(tp + tn * 0.004, 0.03, 0.0075, rot=look_rot(tn)), k=0.003)
    for k_ in (-1, 1):
        fi.add(Capsule(tp + tn * 0.012 + (k_ * 0.01, -0.02, 0.02), tp + tn * 0.012 + (k_ * 0.01, 0.02, -0.01), 0.0032), k=0.002)
    # breastplate rim bolts and the front/back brails with wing nuts
    for i in range(14):
        a = i / 14 * TAU
        fi.add(Cylinder((np.sin(a) * 0.215, 0.032, np.cos(a) * 0.175), 0.008, 0.006, round=0.003), k=0.002)
    for sz in (1, -1):
        fi.add(Box((0, 0.045, sz * 0.18), (0.11, 0.009, 0.012), rot=(sz * -18, 0, 0), round=0.004), k=0.003)
        for sx in (-1, 1):
            wn = np.array([sx * 0.075, 0.06, sz * 0.18])
            fi.add(Cylinder(wn, 0.009, 0.008, round=0.003), k=0.002)
            fi.add(Ellipsoid(wn + (0, 0.012, 0), (0.017, 0.007, 0.004)), k=0.002)
    # air inlet goose-neck on the back, exhaust valve on the right
    gn = hc + np.array([-0.07, 0.035, -hr * 0.9])
    fi.add(Tube([gn - (0, 0, -0.02), gn + (-0.005, 0.012, -0.03), gn + (-0.01, 0.0, -0.065), gn + (-0.012, -0.03, -0.075)],
                0.0125, samples=5), k=0.006)
    fi.add(Cylinder(gn + (-0.012, -0.036, -0.075), 0.018, 0.01, round=0.004), k=0.004)
    fi.add(Cylinder(gn + (0, 0, 0.004), 0.022, 0.006, rot=(90, 0, 0), round=0.003), k=0.004)
    ev = hc + np.array([-hr * 0.72, -0.07, hr * 0.62])
    fi.add(Cylinder(ev, 0.02, 0.016, rot=(90, 45, 0), round=0.005), k=0.006)
    fi.add(Sphere(ev + np.array([-0.012, 0, 0.012]), 0.011), k=0.004)
    brass_finish(fi, base=BR, r=0.005, tarnish=0.08, wear=0.28, verd=0.14, light="#e8c070", seed=6)

    gl = m.piece("port_glass", color="#21424a", gloss=250, lumps=0.0, mottle=0.03, res=0.0025, decimate=1000, ao=False)
    gl.add(Ellipsoid(fp + (0, 0, 0.004), (0.054, 0.054, 0.012)))
    for sx in (1, -1):
        sp = hc + np.array([sx * (hr - 0.01), 0.01, 0.0])
        gl.add(Ellipsoid(sp + (sx * 0.006, 0, 0), (0.01, 0.04, 0.04)))
    gl.add(Ellipsoid(tp + tn * 0.0, (0.026, 0.026, 0.026)))
    gl.paint(Sphere(fp + (0.02, 0.022, 0.014), 0.012), "#9fd0d6", gloss=255, feather=0.006)
    cr = m.piece("crust", color="#ddd5c2", gloss=40, lumps=0.0004, mottle=0.08, res=0.0022, decimate=900)
    for p, n, r_ in (((0.09, 0.4, 0.06), (0.6, 0.7, 0.4), 0.012), ((0.11, 0.38, 0.04), (0.7, 0.6, 0.3), 0.008),
                     ((-0.17, 0.08, 0.06), (-0.7, 0.5, 0.3), 0.011), ((0.0, 0.452, -0.03), (0, 1, -0.2), 0.009)):
        barnacle(cr, p, n, r_)
    return m


# ==============================================================================================================
# ammonite — a ribbed spiral fossil weathering out of a chunk of sandstone


class Ammonite(Prim):
    def __init__(self, c, normal, a=0.0042, growth=2.15, turns=4.2, tube=0.31, flat=0.72, ribs=22, rib_amp=0.07):
        super().__init__()
        self.c = np.asarray(c, float)
        w = np.asarray(normal, float)
        self.w = w / np.linalg.norm(w)
        u = np.cross([0, 1.0, 0], self.w)
        if np.linalg.norm(u) < 0.1:
            u = np.array([1.0, 0, 0])
        self.u = u / np.linalg.norm(u)
        self.v = np.cross(self.w, self.u)
        self.a, self.b = a, np.log(growth) / TAU
        self.phi_end = turns * TAU
        self.tube, self.flat, self.ribs, self.rib_amp = tube, flat, ribs, rib_amp
        self.Rmax = a * np.exp(self.b * self.phi_end) * (1 + tube) + 0.01

    def field(self, P):
        q = P - self.c
        x, y, z = q @ self.u, q @ self.v, q @ self.w
        r = np.hypot(x, y)
        th = np.arctan2(y, x) % TAU
        best = np.full(len(P), 1e9)
        bphi = np.zeros(len(P))
        for k in range(int(self.phi_end / TAU) + 2):
            phi = th + TAU * k
            ok = phi <= self.phi_end
            R = self.a * np.exp(self.b * phi)
            rho = self.tube * R * (1 + self.rib_amp * np.maximum(np.cos(self.ribs * phi), 0) ** 3)
            d = (np.sqrt(((r - R) / rho) ** 2 + (z / (rho * self.flat)) ** 2) - 1.0) * rho * self.flat
            d = np.where(ok, d, 1e9)
            sel = d < best
            best = np.where(sel, d, best)
            bphi = np.where(sel, phi, bphi)
        return best, bphi

    def sdf(self, P):
        return self.field(P)[0]

    def bounds(self):
        e = self.Rmax
        return self.c - e, self.c + e


def ammonite():
    m = TModel("ammonite", res=0.0028)
    tilt = 24.0
    Rt = euler((tilt, 0, 0))
    nrm = Rt @ np.array([0, 1.0, 0])
    bc, bh = np.array([0, 0.07, 0.0]), np.array([0.185, 0.07, 0.17])
    topc = bc + Rt @ np.array([0, bh[1], 0])
    ac = topc - nrm * 0.006
    am = Ammonite(ac, nrm, a=0.0041, growth=2.2, turns=4.1, tube=0.32, flat=0.7, ribs=20, rib_amp=0.09)
    st = m.piece("stone", color="#9e9079", gloss=22, lumps=0.005, lump_freq=9, dents=22, dent_size=0.03, dent_depth=0.004,
                 mottle=0.12, decimate=3800)
    st.add(Box(bc, bh, rot=(tilt, 0, 0), round=0.04).lumpy(0.007, 7, 2))
    st.add(Ellipsoid(bc + (-0.12, -0.02, -0.08), (0.09, 0.07, 0.08)), k=0.04)
    for c, n in (((0.18, 0.08, 0.06), (1, 0.3, 0.5)), ((-0.17, 0.1, 0.1), (-0.6, 0.7, 0.5)), ((0.08, 0.16, -0.12), (0.3, 1, -0.6))):
        st.inter(HalfSpace(c, n), k=0.012)
    st.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.006)
    st.sub(Ellipsoid(ac + nrm * 0.012, (0.15, 0.022, 0.15), rot=Rt), k=0.02)
    st.paint(blotch_prim(10, 0.15, seed=4), "#8a7c66", feather=0.004)
    st.paint(blotch_prim(30, 0.35, seed=5), "#bfb196", feather=0.004)
    grime(st, "#6a5d4a", r=0.01, thresh=0.1, seed=2, feather=0.04)
    fo = m.piece("fossil", color="#dcbb88", gloss=80, lumps=0.0007, lump_freq=25, dents=8, dent_size=0.012, dent_depth=0.001,
                 mottle=0.08, decimate=6000, res=0.002)
    fo.add(am)
    fo.inter(HalfSpace(ac - nrm * 0.004, -nrm), k=0.004)   # only the top half has weathered out
    fo.paint(Func(lambda P: (np.cos(am.ribs * am.field(P)[1]) + 0.75) * 0.01, am.c - 0.2, am.c + 0.2), "#7a5636", gloss=50,
             feather=0.0015)
    fo.paint(Func(lambda P: np.linalg.norm(P - ac, axis=1) - 0.035, ac - 0.1, ac + 0.1), "#9c7046", feather=0.015)
    fo.paint(cavity_prim(fo, 0.006, 0.1, False, noise=0.0), "#6a4a2c", gloss=40, feather=0.04)
    fo.paint(cavity_prim(fo, 0.005, 0.25, True, noise=0.0, seed=7), "#f0dcb4", gloss=110, feather=0.04)
    return m


# ==============================================================================================================


MODELS = {
    "treasure/ship_bell": ship_bell,
    "treasure/brass_compass": brass_compass,
    "treasure/pearl": pearl,
    "treasure/gold_doubloon": gold_doubloon,
    "treasure/pocket_watch": pocket_watch,
    "treasure/spyglass": spyglass,
    "treasure/sea_glass": sea_glass,
    "treasure/message_bottle": message_bottle,
    "treasure/diving_helmet": diving_helmet,
    "treasure/ammonite": ammonite,
}
