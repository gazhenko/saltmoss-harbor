"""
The 16 catchable fish of Saltmoss Harbor (Docs/DESIGN.md §3, §5.4). Centred at the origin, head toward +Z, real-ish
lengths. Each: loft body (one lump of clay, colours painted/pressed in), separate pressed fin sheets with raised
rays and scalloped rims, big glossy eyes seated in clay rims, scored gill covers and mouth, sockets `mouth`, `belly`.
"""
import numpy as np
from clay import *
from kit_catch import *

TAU = 2 * np.pi


class Fish:
    """Small builder that keeps the per-species code about shapes and colours."""

    def __init__(self, name, res=0.003, fin_res=None):
        self.m = Model(name, res=res)
        self.res = res
        self.fin_res = fin_res or res * 0.7
        self.body = None
        self.fins = None
        self.loft = None

    def make_body(self, loft, color, gloss=G_WET, lumps=None, dents=14, dent_size=None, mottle=0.05, res=None,
                  lump_freq=None, decimate=None, tris=None):
        """tris: uniform (undecimated) body mesh with about this many triangles — crisp painted patterns."""
        self.loft = loft
        L = loft.z1 - loft.z0
        self.L = L
        if tris:
            res = float(np.sqrt(2.8 * loft.area() / tris))
            decimate = 10 ** 9
        self.body = self.m.piece("body", color=color, gloss=gloss, lumps=lumps if lumps is not None else L * 0.006,
                                 lump_freq=lump_freq or 3.0 / L, dents=dents, dent_size=dent_size or L * 0.05,
                                 dent_depth=L * 0.004, mottle=mottle, res=res or self.res, decimate=decimate)
        self.body.add(loft)
        return self.body

    def make_fins(self, color, gloss=G_FIN, res=None, mottle=0.04, decimate=None):
        self.fins = self.m.piece("fins", color=color, gloss=gloss, lumps=self.L * 0.0006, lump_freq=5.0 / self.L,
                                 mottle=mottle, res=res or self.fin_res, decimate=decimate or getattr(self, "fin_decimate", None))
        return self.fins

    def fin(self, root_a, root_b, tips, normal, thick, edge=None, color=None, ray_color=None, rim_color=None, rim_w=None,
            k=None, **kw):
        kw.setdefault("scallop", 0.12)
        sep = kw.pop("separate", False)
        f = Fin(root_a, root_b, tips, normal, thick=thick, edge=edge or thick * 0.45, **kw)
        tgt = self.fins
        if sep:  # its own small grid, concatenated into "fins" (fast for very long fish)
            base = self.fins
            tgt = self.m.piece(f"fin{len(self.m.pieces)}", color=base.color, gloss=base.gloss, lumps=base.lumps, lump_freq=base.lump_freq,
                               mottle=base.mottle, res=base.res, merge="fins", decimate=sep if sep is not True else None)
            tgt.ops.extend([o for o in base.ops if o.kind == "paint"])
        tgt.add(f, k=k if k is not None else thick * 0.8)
        fin_paint(tgt, f, color, ray_color, rim_color, rim_w or self.L * 0.012, ray_w=f.rib_w * 0.45)
        self.last_fin_piece = tgt
        return f

    def lips(self, pts, r, color=None, k=None):
        """A rolled lip of clay along the mouth (gives the face its expression)."""
        ridge(self.body, pts, r, k=k if k is not None else r * 0.7, color=color)

    def scale_paint(self, back, belly, frac=0.3, thresh=0.45):
        """Darken the scored scale arcs: `back` shade above the line at frac, `belly` below."""
        sp = self.loft.scale_prim(thresh)
        self.body.paint(inter_prim(sp, above_prim(self.loft, frac)), back, feather=0.0015)
        self.body.paint(inter_prim(sp, below_prim(self.loft, frac)), belly, feather=0.0015)

    def pair(self, fn):
        """Call fn(sx) for the right (+1) and left (-1) side."""
        fn(1.0)
        fn(-1.0)

    # fin conveniences ---------------------------------------------------------------------------------------------
    def dorsal(self, z0, z1, hs, thick, lean=0.0, bury=None, th=0.0, normal=(1, 0, 0), zs=None, **kw):
        """Median fin along the top (th=0) or bottom (th=pi): heights hs spread from z0 (rear) to z1 (front);
        lean sweeps the tips back by lean*h."""
        lo = self.loft
        bury = bury if bury is not None else thick * 1.6
        zs = np.linspace(z0, z1, len(hs)) if zs is None else zs
        tips = [lo.surf(z, th, h) + (0, 0, -lean * h) for z, h in zip(zs, hs)]
        return self.fin(lo.surf(z0, th, -bury), lo.surf(z1, th, -bury), tips, normal, thick, **kw)

    def caudal(self, zp, outline, thick, hp=None, bend=0.0, **kw):
        """Tail fin hung off the peduncle at zp. outline: [(dz_back, dy), ...] from the top lobe round to the bottom;
        bend: sideways x drift per metre back (follows a flopping body)."""
        lo = self.loft
        c = np.array([lo.at(zp, "cx"), lo.at(zp, "cy"), zp])
        hp = hp or (lo.at(zp, "ht") + lo.at(zp, "hb")) * 0.5
        tips = [c + (bend * dz, dy, -dz) for dz, dy in outline]
        return self.fin(c + (0, hp * 0.9, hp * 0.8), c + (0, -hp * 0.9, hp * 0.8), tips, (1, 0, -bend), thick,
                        ray_from=c + (0, 0, hp * 1.6), **kw)

    def long_fin(self, z0, z1, hfn, thick, th=0.0, nseg=6, lean=0.15, rays_per=4, **kw):
        """A long continuous median fin on a bent body, built from short planar segments that follow the bend.
        hfn(z) -> fin height at z."""
        lo = self.loft
        zb = np.linspace(z0, z1, nseg + 1)
        bury = thick * 1.6
        out = []
        for a, b in zip(zb[:-1], zb[1:]):
            zm = 0.5 * (a + b)
            dcx = (lo.at(b, "cx") - lo.at(a, "cx")) / (b - a)
            nrm = np.array([1.0, 0.0, -dcx])
            pad = (b - a) * 0.06
            zs = np.linspace(a - pad, b + pad, 4)
            tips = [lo.surf(z, th, hfn(z)) + (0, 0, -lean * hfn(z)) for z in zs]
            out.append(self.fin(lo.surf(a - pad, th, -bury), lo.surf(b + pad, th, -bury), tips, nrm, thick, nrays=rays_per, **kw))
        return out

    def paired(self, z, th, offs, thick, normal, spread=0.006, ray_from=True, **kw):
        """Pectoral/pelvic fins on both flanks. offs: tip offsets (dx_out, dy, dz) for the RIGHT fin relative to the
        root; normal: plane normal for the right fin (mirrored for the left)."""
        lo = self.loft
        out = []
        for sx in (1.0, -1.0):
            a = lo.surf(z - spread * 0.5, th * sx, -thick * 1.5)
            b = lo.surf(z + spread * 0.5, th * sx, -thick * 1.5)
            mid = 0.5 * (a + b)
            tips = [mid + np.array([dx * sx, dy, dz]) for dx, dy, dz in offs]
            nrm = np.array([normal[0] * sx, normal[1], normal[2]])
            out.append(self.fin(a, b, tips, nrm, thick, ray_from=mid if ray_from else None, **kw))
        return out

    def eyes(self, z, th, r, iris, ring=None, pupil_frac=0.6, sink=0.45, rim=0.2, rim_color=None, toe=0.3, up=0.05, **kw):
        lo = self.loft
        for sx, s in ((1, "R"), (-1, "L")):
            p = lo.surf(z, th * sx)
            nrm = lo.normal(z, th * sx)
            c = p - nrm * r * sink
            eye_socket(self.body, c, r, nrm, rim=rim, rim_color=rim_color)
            fish_eye(self.m, c, r, nrm, iris=iris, ring=ring, pupil_frac=pupil_frac, side=s, toe=toe, up=up, **kw)

    def gill(self, z, r=None, th0=0.5, th1=2.6, bulge=0.0, depth=None, color=None, curve=0.25):
        """Scored operculum arc on both flanks at z (curving back toward the tail at mid-height)."""
        lo = self.loft
        r = r or self.L * 0.006
        for sx in (1, -1):
            ths = np.linspace(th0, th1, 9) * sx
            zs = z - curve * self.L * 0.08 * np.sin(np.linspace(0, np.pi, 9))
            pts = np.array([lo.surf(zz, t, r * 0.2) for zz, t in zip(zs, ths)])
            score(self.body, pts, r, color=color)

    def sockets(self, mouth, belly):
        self.m.socket("mouth", None, mouth)
        self.m.socket("belly", None, belly)
        # drop pieces that ended up with no clay (e.g. a fins piece whose fins were all meshed separately)
        self.m.pieces = [p for p in self.m.pieces if any(o.kind == "add" for o in p.ops)]


# ==============================================================================================================
# shared pattern helpers


def bars_prim(lo, period, duty, z0, z1, ymin_frac=0.1, lean=0.3, wav=0.004, wl=0.02, seed=1, noise=0.25):
    """Wavy vertical bars over the back (mackerel tiger stripes): `duty` = bar fraction of each period.
    Negative inside a bar."""
    def f(P):
        z = np.clip(P[:, 2], lo.z0, lo.z1)
        cy, ht = lo.at(z, "cy"), lo.at(z, "ht")
        yy = P[:, 1] - cy
        u = P[:, 2] + lean * yy + wav * np.sin(yy / wl * TAU + P[:, 2] * 40) + noise * period * fbm(P * (6 / period), 2, seed)
        ph = u / period - np.floor(u / period)
        dt = duty * (1 + 0.3 * fbm(P * (4 / period), 2, seed + 3))
        d = np.maximum(-ph, ph - dt) * period
        d = np.maximum(d, ymin_frac * ht - yy)
        d = np.maximum(d, np.maximum(z0 - P[:, 2], P[:, 2] - z1))
        return d
    return func_prim(f)


def spines(F, pairs, r0, r1, color=None, k=None):
    """Sharp fin spines (round cones) standing out of a spiny fin: pairs of (base, tip)."""
    for a, b in pairs:
        F.fins.add(Capsule(np.asarray(a, float), np.asarray(b, float), r0, r1), k=k if k is not None else r0 * 0.5, color=color)


def teeth(F, pts, size, color="#f3eedf", toward=(0, -1, 0)):
    """Little cone teeth pressed along a jaw (merged into the eyes piece so they stay crisp)."""
    t = F.m.piece("teeth", color=color, gloss=200, lumps=0.0, mottle=0.03, res=max(float(np.min(size)) * 0.22, 0.0012), ao=False, merge="eyes",
                  decimate=max(60, 40 * len(pts)))
    d = np.asarray(toward, float)
    for p, sz in zip(pts, np.broadcast_to(size, (len(pts),))):
        p = np.asarray(p, float)
        t.add(Capsule(p - d * sz * 0.6, p + d * sz, sz * 0.38, sz * 0.06), k=sz * 0.1)
    return t


def mouth_line(F, pts, r, color="#3a2629", gloss=110):
    """Score the gape along pts and paint it dark."""
    pts = np.asarray(pts, float)
    score(F.body, pts, r, k=r * 0.5)
    F.body.paint(Tube(pts, r * 1.6, samples=4 if len(pts) >= 3 else None), color, gloss=gloss, feather=r * 0.6)


# ==============================================================================================================
# herring — slim, silver, blue-green back, deep-forked tail, single mid dorsal, upturned jaw


def herring():
    F = Fish("herring", res=0.0026, fin_res=0.0014)
    BACK, FLANK, BELLY, FIN = "#2d5f78", "#c3ccd2", "#eef0ec", "#a9b8bd"
    z = [-0.112, -0.09, -0.05, 0.0, 0.05, 0.09, 0.118, 0.136, 0.148, 0.154]
    w = [0.0058, 0.0082, 0.0158, 0.021, 0.0215, 0.0195, 0.0158, 0.0112, 0.0066, 0.0024]
    ht = [0.0085, 0.0128, 0.027, 0.0365, 0.0368, 0.0322, 0.0255, 0.018, 0.0098, 0.0034]
    hb = [0.0085, 0.0128, 0.027, 0.0385, 0.0378, 0.032, 0.0236, 0.0152, 0.0082, 0.003]
    cy = [0.0, 0.0, 0.0, -0.001, -0.001, 0.0, 0.0005, 0.0012, 0.0022, 0.0032]
    cx = [-0.007, -0.0045, -0.0012, 0.0, 0.0005, 0.0005, 0.0, 0.0, 0.0, 0.0]  # a gentle flop to the side
    lo = Loft(z, w, ht, hb, cy, cx, scales=dict(size=0.019, depth=0.0006, width=0.16, z=(-0.08, 0.092), th=(0.4, 2.7)))
    b = F.make_body(lo, FLANK, tris=5800)
    b.paint(above_prim(lo, 0.35, wobble=0.002, freq=60), BACK, feather=0.006)
    b.paint(above_prim(lo, 0.65, wobble=0.0015, freq=60), shade(BACK, 0.72), feather=0.004)
    b.paint(below_prim(lo, -0.45, wobble=0.002), BELLY, feather=0.008)
    b.paint(inter_prim(above_prim(lo, 0.12), below_prim(lo, 0.32)), "#a3bfc9", feather=0.004)
    F.scale_paint(shade(BACK, 0.78), "#a7b2b8", frac=0.3)
    b.add(Ellipsoid((0, -0.005, 0.146), (0.0062, 0.0045, 0.01), rot=(-28, 0, 0)), k=0.003)  # jutting chin
    mouth_line(F, [(-0.0066, -0.0026, 0.138), (0, 0.0012, 0.1548), (0.0066, -0.0026, 0.138)], 0.0009)
    F.lips([(-0.0068, -0.0008, 0.137), (-0.0035, 0.0014, 0.148), (0, 0.0026, 0.1535), (0.0035, 0.0014, 0.148), (0.0068, -0.0008, 0.137)], 0.0011)
    F.gill(0.103, r=0.0013, th0=0.45, th1=2.55, curve=0.6)
    F.gill(0.111, r=0.0009, th0=0.9, th1=2.3, curve=0.4)
    F.eyes(0.124, 1.3, 0.0114, iris="#d9c27a", ring="#efe4c0", pupil_frac=0.66, rim=0.18, rim_color="#8fa5ae")
    F.make_fins(FIN)
    RAY, RAY2 = "#8297a0", "#8a9ca3"
    F.dorsal(-0.016, 0.036, [0.006, 0.013, 0.021, 0.029, 0.033], 0.0027, lean=0.3, ray_color=RAY, nrays=8, wave=(0.0006, 0.014))
    F.caudal(-0.106, [(0.056, 0.05), (0.047, 0.034), (0.032, 0.015), (0.024, 0.0), (0.032, -0.015), (0.047, -0.034), (0.056, -0.05)],
             0.003, bend=-0.08, ray_color="#71878f", nrays=13, wave=(0.0012, 0.03), rim_color="#4d6a78", rim_w=0.0045)
    F.dorsal(-0.07, -0.034, [0.007, 0.011, 0.011, 0.007], 0.0023, th=np.pi, lean=0.3, ray_color=RAY2, nrays=7)
    F.paired(0.014, np.pi * 0.86, [(0.006, -0.012, -0.014), (0.006, -0.015, -0.006), (0.004, -0.01, 0.0)], 0.0021,
             (1, 0.35, 0), spread=0.016, ray_color=RAY2, nrays=5)
    F.paired(0.095, np.pi * 0.68, [(0.011, 0.003, -0.028), (0.012, -0.004, -0.031), (0.01, -0.013, -0.02)], 0.0021,
             (0.3, -1, 0), spread=0.008, ray_color=RAY2, nrays=6)
    F.sockets(mouth=(0, 0.001, 0.155), belly=(0, -0.038, 0.0))
    return F.m


# ==============================================================================================================
# mackerel — torpedo, pointed snout, black wavy tiger bars on an iridescent blue-green back, finlets, forked tail


def mackerel():
    F = Fish("mackerel", res=0.0034, fin_res=0.0018)
    BACK, FLANK, BELLY, BAR, FIN = "#2b7a86", "#bccbcd", "#f0efe8", "#14212a", "#8a9ea2"
    z = [-0.138, -0.12, -0.08, -0.03, 0.03, 0.08, 0.12, 0.15, 0.172, 0.185, 0.191]
    w = [0.0048, 0.0066, 0.014, 0.0235, 0.0275, 0.026, 0.021, 0.016, 0.0104, 0.0055, 0.002]
    ht = [0.0062, 0.0086, 0.018, 0.0295, 0.0338, 0.0318, 0.0265, 0.02, 0.0132, 0.007, 0.0025]
    hb = [0.0062, 0.0086, 0.0172, 0.0282, 0.0318, 0.029, 0.023, 0.0164, 0.0098, 0.005, 0.002]
    cy = [0, 0, 0, 0, 0, 0, 0, -0.0008, -0.0016, -0.002, -0.002]
    cx = [0.008, 0.006, 0.002, 0.0, -0.0005, 0, 0, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx)
    b = F.make_body(lo, FLANK, tris=6400)
    b.paint(above_prim(lo, 0.08, wobble=0.002, freq=50), BACK, feather=0.005)
    b.paint(above_prim(lo, 0.8, wobble=0.002, freq=50), shade(BACK, 0.7), feather=0.005)
    b.paint(below_prim(lo, -0.3, wobble=0.003), BELLY, feather=0.01)
    b.paint(inter_prim(above_prim(lo, -0.12), below_prim(lo, 0.08)), "#cdbf93", feather=0.006)  # faint bronze sheen
    b.paint(bars_prim(lo, 0.023, 0.42, -0.122, 0.127, ymin_frac=0.18, lean=0.3, wav=0.0035, wl=0.014, noise=0.12), BAR, feather=0.0016)
    b.paint(inter_prim(above_prim(lo, 0.3), func_prim(lambda P: 0.13 - P[:, 2])), shade(BACK, 0.6), feather=0.004)
    mouth_line(F, [(-0.009, -0.0032, 0.162), (-0.0042, -0.0024, 0.181), (0, -0.0019, 0.1905), (0.0042, -0.0024, 0.181), (0.009, -0.0032, 0.162)], 0.0011)
    F.lips([(-0.0092, -0.0012, 0.161), (-0.0045, -0.0005, 0.181), (0, -0.0004, 0.19), (0.0045, -0.0005, 0.181), (0.0092, -0.0012, 0.161)], 0.0011)
    F.gill(0.136, r=0.0014, th0=0.4, th1=2.6, curve=0.7)
    F.eyes(0.157, 1.25, 0.0122, iris="#d6cfae", ring="#f1ead2", pupil_frac=0.66, rim=0.2, rim_color="#a9b9bb")
    for sx in (1, -1):
        b.add(Ellipsoid(lo.surf(-0.123, sx * np.pi / 2, -0.001), (0.0017, 0.0017, 0.011)), k=0.002)  # peduncle keels
    F.make_fins(FIN)
    RAY = "#5d7277"
    F.dorsal(0.05, 0.095, [0.004, 0.013, 0.021, 0.027], 0.0025, lean=0.45, ray_color=RAY, nrays=9, scallop=0.3, wave=(0.0006, 0.012))
    F.dorsal(-0.03, -0.006, [0.005, 0.011, 0.012], 0.0023, lean=0.4, ray_color=RAY, nrays=6)
    F.dorsal(-0.03, -0.006, [0.005, 0.01, 0.011], 0.0023, th=np.pi, lean=0.4, ray_color=RAY, nrays=6)
    for i, zf in enumerate(np.linspace(-0.046, -0.112, 5)):
        hh = 0.0064 - i * 0.0006
        for th in (0.0, np.pi):
            F.fin(lo.surf(zf - 0.004, th, -0.0025), lo.surf(zf + 0.004, th, -0.0025),
                  [lo.surf(zf - 0.006, th, hh), lo.surf(zf - 0.001, th, hh * 0.6)], (1, 0, 0), 0.0019, nrays=2, scallop=0.0)
    F.caudal(-0.134, [(0.07, 0.068), (0.058, 0.05), (0.038, 0.022), (0.029, 0.0), (0.038, -0.022), (0.058, -0.05), (0.07, -0.068)],
             0.0029, bend=0.18, ray_color=RAY, nrays=15, scallop=0.08, wave=(0.001, 0.03), rim_color="#3d4f55", rim_w=0.004)
    F.paired(0.124, np.pi * 0.6, [(0.009, 0.006, -0.032), (0.01, 0.0, -0.035), (0.008, -0.008, -0.024)], 0.0021,
             (0.3, -1, 0), spread=0.008, ray_color=RAY, nrays=7)
    F.paired(0.082, np.pi * 0.9, [(0.004, -0.01, -0.014), (0.004, -0.012, -0.006)], 0.0019, (1, 0.35, 0), spread=0.008, nrays=4)
    F.sockets(mouth=(0, -0.002, 0.191), belly=(0, -0.032, 0.0))
    return F.m


# ==============================================================================================================
# smelt — little slender silver fish, olive back, bright silver side stripe, adipose fin, big eye, jutting jaw


def smelt():
    F = Fish("smelt", res=0.0021, fin_res=0.0013)
    BACK, FLANK, BELLY, STRIPE, FIN = "#7a9560", "#cdd3cb", "#f2f0e6", "#eef2f4", "#c8cfc3"
    z = [-0.09, -0.072, -0.035, 0.015, 0.058, 0.088, 0.106, 0.118, 0.125]
    w = [0.0042, 0.006, 0.0102, 0.0134, 0.013, 0.0108, 0.0084, 0.0052, 0.002]
    ht = [0.006, 0.0082, 0.0148, 0.0196, 0.019, 0.016, 0.0122, 0.0074, 0.0027]
    hb = [0.006, 0.0082, 0.0148, 0.02, 0.019, 0.0154, 0.0106, 0.0062, 0.0023]
    cy = [0, 0, 0, 0, 0, 0.0004, 0.001, 0.0017, 0.0025]
    cx = [-0.005, -0.0035, -0.001, 0, 0, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx, scales=dict(size=0.013, depth=0.0005, width=0.16, z=(-0.06, 0.07), th=(0.45, 2.6)))
    b = F.make_body(lo, FLANK, mottle=0.04, tris=5800)
    b.paint(above_prim(lo, 0.3, wobble=0.0015, freq=70), BACK, feather=0.004)
    b.paint(above_prim(lo, 0.7), shade(BACK, 0.72), feather=0.004)
    b.paint(below_prim(lo, -0.4), BELLY, feather=0.006)
    F.scale_paint(shade(BACK, 0.8), "#b3bab0", frac=0.3)
    # the bright silver stripe with a violet-blue sheen above it
    b.paint(inter_prim(above_prim(lo, -0.08, zrange=(-0.078, 0.09)), below_prim(lo, 0.18)), STRIPE, gloss=235, feather=0.0016)
    b.paint(inter_prim(above_prim(lo, 0.18, zrange=(-0.07, 0.085)), below_prim(lo, 0.25)), "#a7a9cf", feather=0.0014)
    b.add(Ellipsoid((0, -0.0034, 0.119), (0.0048, 0.0032, 0.0085), rot=(-25, 0, 0)), k=0.002)
    mouth_line(F, [(-0.006, -0.0012, 0.104), (-0.003, 0.0006, 0.118), (0, 0.0018, 0.1262), (0.003, 0.0006, 0.118), (0.006, -0.0012, 0.104)], 0.0008)
    F.lips([(-0.0062, 0.0004, 0.104), (-0.003, 0.0019, 0.118), (0, 0.003, 0.125), (0.003, 0.0019, 0.118), (0.0062, 0.0004, 0.104)], 0.0009)
    F.gill(0.088, r=0.0011, th0=0.45, th1=2.55, curve=0.55)
    F.eyes(0.1, 1.3, 0.0096, iris="#d8d4bf", ring="#f3efdc", pupil_frac=0.68, rim=0.17, rim_color="#a7b39b")
    F.make_fins(FIN, gloss=120)
    RAY = "#9aa793"
    F.dorsal(-0.004, 0.024, [0.004, 0.009, 0.015, 0.019], 0.002, lean=0.3, ray_color=RAY, nrays=7, wave=(0.0005, 0.012))
    F.dorsal(-0.062, -0.052, [0.0034, 0.0044], 0.002, lean=0.6, nrays=2, scallop=0.0, ribs=0.0)  # adipose nub
    F.dorsal(-0.064, -0.03, [0.006, 0.009, 0.009, 0.006], 0.0019, th=np.pi, lean=0.3, ray_color=RAY, nrays=7)
    F.caudal(-0.087, [(0.046, 0.039), (0.039, 0.027), (0.027, 0.012), (0.02, 0.0), (0.027, -0.012), (0.039, -0.027), (0.046, -0.039)],
             0.0021, bend=-0.07, ray_color=RAY, nrays=11, scallop=0.08, wave=(0.0008, 0.024), rim_color="#8f9b88", rim_w=0.003)
    F.paired(0.008, np.pi * 0.86, [(0.005, -0.01, -0.012), (0.005, -0.012, -0.004)], 0.0017, (1, 0.35, 0), spread=0.01, ray_color=RAY, nrays=4)
    F.paired(0.082, np.pi * 0.68, [(0.009, 0.002, -0.022), (0.01, -0.004, -0.024), (0.008, -0.01, -0.015)], 0.0017,
             (0.3, -1, 0), spread=0.007, ray_color=RAY, nrays=5)
    F.sockets(mouth=(0, 0.0018, 0.126), belly=(0, -0.02, 0.0))
    return F.m


# ==============================================================================================================
# salmon — silver sea-run coho: dark blue-green back peppered with bold black spots, rosy blush, adipose fin, kype


def salmon():
    F = Fish("salmon", res=0.0055, fin_res=0.0032)
    F.fin_decimate = 3800
    BACK, FLANK, BELLY, BLUSH, SPOT, FIN = "#30536a", "#c9d0d4", "#f2f0ea", "#cfa3a3", "#16181d", "#74858c"
    z = [-0.29, -0.255, -0.17, -0.06, 0.06, 0.17, 0.25, 0.31, 0.355, 0.385, 0.402]
    w = [0.012, 0.016, 0.031, 0.049, 0.056, 0.053, 0.045, 0.034, 0.023, 0.013, 0.004]
    ht = [0.017, 0.024, 0.05, 0.079, 0.088, 0.079, 0.063, 0.046, 0.031, 0.018, 0.006]
    hb = [0.017, 0.024, 0.047, 0.072, 0.079, 0.07, 0.054, 0.037, 0.024, 0.013, 0.004]
    cy = [0, 0, 0, 0, 0, 0, 0, -0.002, -0.004, -0.007, -0.009]
    cx = [-0.016, -0.012, -0.004, 0, 0.001, 0.001, 0, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx, scales=dict(size=0.032, depth=0.001, width=0.16, z=(-0.2, 0.22), th=(0.5, 2.5)))
    b = F.make_body(lo, FLANK, tris=6300)
    b.paint(above_prim(lo, 0.28, wobble=0.004, freq=25), BACK, feather=0.014)
    b.paint(above_prim(lo, 0.75), shade(BACK, 0.72), feather=0.01)
    b.paint(inter_prim(above_prim(lo, -0.55, wobble=0.008, freq=18), below_prim(lo, 0.05, wobble=0.008, freq=18)), BLUSH, feather=0.03)
    b.paint(below_prim(lo, -0.6), BELLY, feather=0.02)
    F.scale_paint(shade(BACK, 0.82), "#b2b9bf", frac=0.28, thresh=0.5)
    C, R = surface_spots(lo, 40, (-0.27, 0.33), (0.0, 1.05), 0.0098, seed=4, jitter=0.3)
    b.paint(spots_prim(C, R), SPOT, feather=0.002)
    # snout: hooked kype, gape back to below the eye
    b.add(Ellipsoid((0, -0.013, 0.382), (0.012, 0.0075, 0.019), rot=(-20, 0, 0)), k=0.008)
    b.add(Capsule((0, -0.004, 0.392), (0, -0.012, 0.404), 0.0075, 0.005), k=0.006)
    mouth_line(F, [(-0.021, -0.014, 0.335), (-0.012, -0.011, 0.375), (0, -0.0095, 0.4), (0.012, -0.011, 0.375), (0.021, -0.014, 0.335)], 0.0022)
    F.lips([(-0.0215, -0.0105, 0.334), (-0.0125, -0.0075, 0.375), (0, -0.0055, 0.398), (0.0125, -0.0075, 0.375), (0.0215, -0.0105, 0.334)], 0.0024)
    F.gill(0.29, r=0.0028, th0=0.45, th1=2.6, curve=0.7)
    F.gill(0.305, r=0.002, th0=0.9, th1=2.25, curve=0.45)
    F.eyes(0.345, 1.3, 0.0225, iris="#d9c27a", ring="#f0e5c4", pupil_frac=0.64, rim=0.2, rim_color="#8c9aa3")
    F.make_fins(FIN)
    RAY = "#5b6a71"
    F.dorsal(-0.01, 0.1, [0.012, 0.032, 0.052, 0.07, 0.075], 0.0048, lean=0.35, ray_color=RAY, nrays=10, wave=(0.0015, 0.03))
    F.dorsal(-0.21, -0.18, [0.012, 0.017], 0.0042, lean=0.7, nrays=2, scallop=0.0, ribs=0.0)  # adipose
    F.dorsal(-0.175, -0.1, [0.016, 0.031, 0.037, 0.023], 0.0042, th=np.pi, lean=0.35, ray_color=RAY, nrays=8)
    F.caudal(-0.285, [(0.145, 0.115), (0.128, 0.083), (0.103, 0.041), (0.093, 0.0), (0.103, -0.041), (0.128, -0.083), (0.145, -0.115)],
             0.0055, bend=-0.12, ray_color=RAY, nrays=15, scallop=0.08, wave=(0.002, 0.06), rim_color="#3c4a52", rim_w=0.008)
    rng = np.random.default_rng(3)
    tc = [np.array([lo.at(-0.29, "cx") - 0.12 * dz, dy, -0.285 - dz]) for dz, dy in zip(rng.uniform(0.03, 0.13, 22), rng.uniform(-0.09, 0.09, 22))]
    F.fins.paint(spots_prim(tc, 0.0078), SPOT, feather=0.0015)
    dc = [lo.top(zz, hh) for zz, hh in zip(rng.uniform(0.0, 0.085, 8), rng.uniform(0.012, 0.05, 8))]
    F.fins.paint(spots_prim(dc, 0.0072), SPOT, feather=0.0015)
    F.paired(-0.03, np.pi * 0.85, [(0.012, -0.03, -0.035), (0.012, -0.036, -0.012), (0.008, -0.022, 0.0)], 0.0036,
             (1, 0.35, 0), spread=0.03, ray_color=RAY, nrays=6)
    F.paired(0.265, np.pi * 0.72, [(0.02, 0.0, -0.06), (0.024, -0.012, -0.064), (0.018, -0.03, -0.042)], 0.0036,
             (0.3, -1, 0), spread=0.016, ray_color=RAY, nrays=8)
    F.sockets(mouth=(0, -0.009, 0.402), belly=(0, -0.079, 0.0))
    return F.m


# ==============================================================================================================
# cod — heavy olive-tan body freckled with leopard spots, pale arched lateral line, three dorsals, chin barbel


def cod():
    F = Fish("cod", res=0.008, fin_res=0.0052)
    BASE, BACK, SPOT, BELLY, LINE, FIN = "#ad9d6c", "#7f7548", "#5a4d2e", "#eee7d4", "#f3efe2", "#a39466"
    z = [-0.315, -0.28, -0.2, -0.08, 0.05, 0.16, 0.25, 0.32, 0.37, 0.405, 0.428]
    w = [0.014, 0.019, 0.037, 0.06, 0.07, 0.07, 0.066, 0.057, 0.043, 0.027, 0.01]
    ht = [0.02, 0.029, 0.06, 0.092, 0.104, 0.1, 0.091, 0.075, 0.055, 0.035, 0.012]
    hb = [0.02, 0.027, 0.052, 0.084, 0.098, 0.096, 0.088, 0.075, 0.059, 0.038, 0.014]
    cy = [0, 0, 0, 0, -0.002, -0.004, -0.006, -0.008, -0.01, -0.012, -0.014]
    cx = [0.022, 0.017, 0.007, 0.001, 0, 0, 0, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx)
    b = F.make_body(lo, BASE, tris=6400)
    b.paint(above_prim(lo, 0.2, wobble=0.01, freq=12), BACK, feather=0.02)
    b.paint(below_prim(lo, -0.45, wobble=0.006, freq=14), BELLY, feather=0.018)
    C, R = surface_spots(lo, 120, (-0.3, 0.4), (0.0, 1.75), 0.0085, seed=11, jitter=0.4)
    b.paint(spots_prim(C, R), SPOT, feather=0.003)
    # pale lateral line arching high over the pectoral
    zs = np.linspace(-0.3, 0.3, 14)
    ths = np.interp(zs, [-0.3, -0.05, 0.15, 0.3], [1.55, 1.3, 1.0, 1.05])
    for sx in (1, -1):
        b.paint(Tube(lo.line(zs, ths * sx), 0.0042, samples=3), LINE, feather=0.002)
    # head: overbite snout, gape, chin barbel
    b.add(Ellipsoid((0, 0.002, 0.41), (0.026, 0.02, 0.026)), k=0.012)
    mouth_line(F, [(-0.032, -0.03, 0.365), (-0.02, -0.024, 0.405), (0, -0.021, 0.422), (0.02, -0.024, 0.405), (0.032, -0.03, 0.365)], 0.0035)
    F.lips([(-0.033, -0.022, 0.364), (-0.021, -0.015, 0.405), (0, -0.012, 0.424), (0.021, -0.015, 0.405), (0.033, -0.022, 0.364)], 0.0038)
    ridge(b, [(0, -0.05, 0.392), (0.002, -0.068, 0.38), (0.006, -0.08, 0.37)], [0.0042, 0.0034, 0.0022], k=0.003, color="#d8cfae")  # barbel
    F.gill(0.29, r=0.004, th0=0.4, th1=2.6, curve=0.7)
    F.gill(0.31, r=0.0028, th0=0.85, th1=2.3, curve=0.45)
    F.eyes(0.335, 1.12, 0.024, iris="#d8b25a", ring="#efdba2", pupil_frac=0.62, rim=0.2, rim_color=shade(BACK, 0.9))
    F.make_fins(FIN)
    RAY = "#7a6c45"
    for (z0, z1, hs) in ((0.07, 0.18, [0.02, 0.05, 0.07, 0.072, 0.05]), (-0.075, 0.05, [0.018, 0.045, 0.055, 0.05, 0.03]),
                         (-0.245, -0.1, [0.016, 0.04, 0.05, 0.045, 0.025])):
        f = F.dorsal(z0, z1, hs, 0.0058, lean=0.25, ray_color=RAY, nrays=10, wave=(0.002, 0.04))
        F.fins.paint(f.rim(0.0035), "#c9be95", feather=0.002)
    for (z0, z1, hs) in ((-0.07, 0.05, [0.016, 0.04, 0.046, 0.04, 0.022]), (-0.245, -0.1, [0.016, 0.038, 0.044, 0.036, 0.02])):
        F.dorsal(z0, z1, hs, 0.0055, th=np.pi, lean=0.25, ray_color=RAY, nrays=10, wave=(0.002, 0.04))
    rng = np.random.default_rng(5)
    F.fins.paint(spots_prim([lo.top(zz, hh) for zz, hh in zip(rng.uniform(-0.24, 0.17, 30), rng.uniform(0.01, 0.05, 30))], 0.006), SPOT, feather=0.002)
    F.caudal(-0.31, [(0.115, 0.105), (0.12, 0.065), (0.112, 0.025), (0.108, 0.0), (0.112, -0.025), (0.12, -0.065), (0.115, -0.105)],
             0.0065, bend=0.15, ray_color=RAY, nrays=15, scallop=0.06, wave=(0.002, 0.07), rim_color="#c9be95", rim_w=0.004)
    F.paired(0.215, np.pi * 0.62, [(0.026, 0.03, -0.06), (0.03, 0.005, -0.08), (0.028, -0.025, -0.07), (0.02, -0.04, -0.045)], 0.0048,
             (0.3, -1, 0), spread=0.03, ray_color=RAY, nrays=10)
    F.paired(0.26, np.pi * 0.9, [(0.012, -0.045, -0.03), (0.01, -0.06, -0.012), (0.006, -0.03, 0.0)], 0.004,
             (1, 0.35, 0), spread=0.022, ray_color=RAY, nrays=6)
    F.sockets(mouth=(0, -0.021, 0.425), belly=(0, -0.098, 0.05))
    return F.m


# ==============================================================================================================
# rockfish (yelloweye) — deep orange-red body, big gold-yellow eye, tall spiny dorsal, head spines, black-edged fins


def rockfish():
    F = Fish("rockfish", res=0.005, fin_res=0.0034)
    F.fin_decimate = 4300
    BASE, BACK, BELLY, FIN, EDGE = "#e2643c", "#c8452c", "#f2b98f", "#ec7d42", "#6a2c22"
    z = [-0.175, -0.15, -0.09, 0.0, 0.07, 0.13, 0.18, 0.215, 0.238, 0.25]
    w = [0.011, 0.015, 0.031, 0.047, 0.052, 0.05, 0.043, 0.032, 0.019, 0.007]
    ht = [0.019, 0.028, 0.062, 0.094, 0.1, 0.092, 0.073, 0.052, 0.032, 0.011]
    hb = [0.019, 0.026, 0.054, 0.08, 0.086, 0.078, 0.062, 0.045, 0.029, 0.011]
    cy = [0, 0, 0, 0, 0, -0.003, -0.006, -0.009, -0.011, -0.012]
    cx = [-0.012, -0.009, -0.003, 0, 0, 0, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx, scales=dict(size=0.022, depth=0.0009, width=0.17, z=(-0.14, 0.15), th=(0.35, 2.7)))
    b = F.make_body(lo, BASE, tris=5700)
    b.paint(above_prim(lo, 0.4, wobble=0.006, freq=20), BACK, feather=0.012)
    b.paint(below_prim(lo, -0.45, wobble=0.006, freq=20), BELLY, feather=0.014)
    F.scale_paint(shade(BACK, 0.82), shade(BASE, 0.86), frac=0.4, thresh=0.5)
    # big jutting lower jaw and gape
    b.add(Ellipsoid((0, -0.03, 0.235), (0.02, 0.014, 0.024), rot=(-18, 0, 0)), k=0.008)
    mouth_line(F, [(-0.027, -0.012, 0.2), (-0.016, -0.009, 0.236), (0, -0.007, 0.253), (0.016, -0.009, 0.236), (0.027, -0.012, 0.2)], 0.0032)
    F.lips([(-0.028, -0.005, 0.2), (-0.017, -0.002, 0.236), (0, 0.0, 0.251), (0.017, -0.002, 0.236), (0.028, -0.005, 0.2)], 0.0034, color=shade(BACK, 0.9))
    F.gill(0.165, r=0.0034, th0=0.4, th1=2.6, curve=0.7)
    F.gill(0.18, r=0.0024, th0=0.8, th1=2.3, curve=0.45)
    F.eyes(0.2, 1.0, 0.026, iris="#f4cf2e", ring="#fbe68a", pupil_frac=0.56, rim=0.24, rim_color=shade(BACK, 0.85), sink=0.4)
    F.make_fins(FIN)
    # head spines: little cones over the eyes and on the gill cover
    for sx in (1, -1):
        for zz, th, ln in ((0.215, 0.55, 0.012), (0.19, 0.5, 0.011), (0.168, 0.48, 0.01), (0.15, 1.35, 0.014), (0.152, 1.75, 0.012)):
            p0 = lo.surf(zz, th * sx, -0.002)
            nrm = lo.normal(zz, th * sx)
            F.fins.add(Capsule(p0, p0 + nrm * ln + np.array([0, 0, -ln * 0.8]), 0.0035, 0.0007), k=0.002, color=shade(BACK, 0.9))
    # spiny dorsal: 12 spines, membranes notched deep between them, then the rounded soft dorsal
    zs = np.linspace(-0.01, 0.15, 12)
    hs = np.array([0.04, 0.052, 0.06, 0.062, 0.061, 0.058, 0.055, 0.05, 0.046, 0.04, 0.032, 0.022])[::-1][::-1]
    hs = np.interp(zs, [-0.01, 0.03, 0.09, 0.15], [0.036, 0.06, 0.06, 0.03])
    f = F.dorsal(-0.012, 0.155, list(hs), 0.0042, zs=zs, lean=0.25, nrays=12, scallop=0.42, wave=(0.0015, 0.03), ribs=0.0012)
    F.fins.paint(f.rim(0.0035), EDGE, feather=0.002)
    spines(F, [(lo.top(zz, -0.004), lo.top(zz, hh * 1.12) + (0, 0, -hh * 0.3)) for zz, hh in zip(zs, hs)], 0.0032, 0.0007, color="#f08a52")
    f = F.dorsal(-0.12, -0.012, [0.03, 0.05, 0.058, 0.055, 0.04], 0.0042, lean=0.25, ray_color="#c95a30", nrays=10, wave=(0.0015, 0.03))
    F.fins.paint(f.rim(0.0035), EDGE, feather=0.002)
    f = F.dorsal(-0.12, -0.03, [0.025, 0.05, 0.058, 0.04], 0.004, th=np.pi, lean=0.2, ray_color="#c95a30", nrays=8)
    F.fins.paint(f.rim(0.0035), EDGE, feather=0.002)
    spines(F, [(lo.bottom(zz, -0.004), lo.bottom(zz, hh) + (0, 0, -hh * 0.25)) for zz, hh in ((-0.03, 0.03), (-0.04, 0.045), (-0.05, 0.055))], 0.003, 0.0007, color="#f08a52")
    f = F.caudal(-0.17, [(0.075, 0.075), (0.085, 0.05), (0.085, 0.018), (0.083, 0.0), (0.085, -0.018), (0.085, -0.05), (0.075, -0.075)],
                 0.0048, bend=-0.12, ray_color="#c95a30", nrays=13, scallop=0.06, wave=(0.0015, 0.05))
    F.fins.paint(f.rim(0.004), EDGE, feather=0.002)
    for f in F.paired(0.135, np.pi * 0.62, [(0.02, 0.025, -0.05), (0.024, 0.0, -0.068), (0.022, -0.03, -0.06), (0.016, -0.045, -0.035)], 0.0042,
                      (0.3, -1, 0), spread=0.03, ray_color="#c95a30", nrays=11):
        F.fins.paint(f.rim(0.0035), EDGE, feather=0.002)
    for f in F.paired(0.09, np.pi * 0.9, [(0.012, -0.045, -0.03), (0.01, -0.052, -0.012), (0.006, -0.03, 0.0)], 0.0038,
                      (1, 0.35, 0), spread=0.022, ray_color="#c95a30", nrays=6):
        F.fins.paint(f.rim(0.0035), EDGE, feather=0.002)
    F.sockets(mouth=(0, -0.007, 0.253), belly=(0, -0.086, 0.07))
    return F.m


# ==============================================================================================================
# lingcod — long, big-headed ambush hunter: huge toothy jaw, mottled brown-green with copper blotches, fan pectorals


def lingcod():
    F = Fish("lingcod", res=0.009, fin_res=0.0058)
    BASE, DARK, COPPER, BELLY, FIN = "#8f8a64", "#3f3a29", "#c27b3b", "#e6dfc8", "#7c7552"
    z = [-0.39, -0.35, -0.25, -0.1, 0.05, 0.18, 0.28, 0.36, 0.42, 0.47, 0.5]
    w = [0.015, 0.021, 0.041, 0.064, 0.077, 0.086, 0.088, 0.081, 0.067, 0.044, 0.014]
    ht = [0.021, 0.029, 0.056, 0.079, 0.088, 0.092, 0.088, 0.077, 0.06, 0.038, 0.012]
    hb = [0.021, 0.028, 0.052, 0.073, 0.082, 0.088, 0.088, 0.081, 0.067, 0.045, 0.018]
    cy = [0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.002, 0.004]
    cx = [-0.04, -0.03, -0.012, 0.0, 0.004, 0.003, 0.001, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx)
    b = F.make_body(lo, BASE, tris=6300)
    reg = above_prim(lo, -0.5)
    b.paint(blotch_prim(8.0, -0.06, seed=3, region=reg), DARK, feather=0.0040)
    b.paint(blotch_prim(15.0, 0.22, seed=8, region=reg), COPPER, feather=0.0032)
    b.paint(below_prim(lo, -0.55, wobble=0.012, freq=9), BELLY, feather=0.025)
    # huge mouth: lower jaw jutting, rows of little fangs
    b.add(Ellipsoid((0, -0.036, 0.474), (0.036, 0.02, 0.042), rot=(-12, 0, 0)), k=0.012)
    gape = [(-0.055, -0.024, 0.36), (-0.04, -0.014, 0.44), (0, -0.006, 0.507), (0.04, -0.014, 0.44), (0.055, -0.024, 0.36)]
    mouth_line(F, gape, 0.0055)
    F.lips([(-0.056, -0.013, 0.36), (-0.041, -0.004, 0.44), (0, 0.004, 0.502), (0.041, -0.004, 0.44), (0.056, -0.013, 0.36)], 0.0058, color=shade(BASE, 0.8))
    F.lips([(-0.054, -0.034, 0.36), (-0.04, -0.024, 0.445), (0, -0.016, 0.512), (0.04, -0.024, 0.445), (0.054, -0.034, 0.36)], 0.0058, color=shade(BELLY, 0.9))
    tp = smooth_curve(np.array(gape), 3)
    tp = tp[(tp[:, 2] > 0.4)]
    teeth(F, [p + np.array([0, -0.004, 0.004]) + np.array([np.sign(p[0]) * 0.003, 0, 0]) for p in tp[::2]], 0.012, toward=(0, 1, 0.15))
    F.gill(0.35, r=0.0055, th0=0.4, th1=2.6, curve=0.8)
    F.eyes(0.43, 0.72, 0.026, iris="#cfa64e", ring="#ead6a0", pupil_frac=0.62, rim=0.26, rim_color=DARK, toe=0.35, up=0.25)
    F.make_fins(FIN)
    RAY = "#4f4a35"
    f = F.dorsal(-0.02, 0.29, list(np.interp(np.linspace(0, 1, 11), [0, 0.15, 0.7, 1], [0.025, 0.052, 0.048, 0.022])), 0.0065, lean=0.2,
                 nrays=11, scallop=0.35, ray_color=RAY, wave=(0.002, 0.05))
    F.fins.paint(blotch_prim(12.0, -0.05, seed=4, region=f), DARK, feather=0.0030)
    f = F.dorsal(-0.33, -0.03, [0.03, 0.062, 0.072, 0.07, 0.052, 0.03], 0.0066, lean=0.15, nrays=18, ray_color=RAY, wave=(0.002, 0.06))
    F.fins.paint(blotch_prim(12.0, -0.05, seed=5, region=f), DARK, feather=0.0030)
    F.dorsal(-0.32, -0.02, [0.025, 0.045, 0.054, 0.052, 0.04, 0.02], 0.0064, th=np.pi, lean=0.15, nrays=16, ray_color=RAY)
    f = F.caudal(-0.385, [(0.08, 0.08), (0.1, 0.058), (0.112, 0.027), (0.115, 0.0), (0.112, -0.027), (0.1, -0.058), (0.08, -0.08)],
                 0.007, bend=-0.25, ray_color=RAY, nrays=13, scallop=0.06, wave=(0.002, 0.06))
    F.fins.paint(blotch_prim(12.0, 0.0, seed=6, region=f), DARK, feather=0.0030)
    for f in F.paired(0.31, np.pi * 0.66, [(0.04, 0.05, -0.07), (0.05, 0.015, -0.115), (0.045, -0.035, -0.11), (0.03, -0.07, -0.062)], 0.0065,
                      (0.35, -1, 0), spread=0.05, ray_color=RAY, nrays=14):
        F.fins.paint(blotch_prim(12.0, 0.0, seed=7, region=f), DARK, feather=0.0030)
    F.paired(0.33, np.pi * 0.92, [(0.012, -0.04, -0.03), (0.01, -0.048, -0.01)], 0.0055, (1, 0.35, 0), spread=0.02, ray_color=RAY, nrays=5)
    F.sockets(mouth=(0, -0.006, 0.507), belly=(0, -0.088, 0.15))
    return F.m


# ==============================================================================================================
# sablefish (black cod) — sleek slate-black torpedo, two well-separated dorsals, big eye, pale belly


def sablefish():
    F = Fish("sablefish", res=0.007, fin_res=0.0036)
    BACK, FLANK, BELLY, FIN = "#2f343c", "#5e6670", "#aab0b6", "#363b43"
    z = [-0.31, -0.27, -0.18, -0.05, 0.08, 0.2, 0.28, 0.34, 0.378, 0.398]
    w = [0.011, 0.015, 0.031, 0.047, 0.054, 0.052, 0.045, 0.034, 0.02, 0.007]
    ht = [0.015, 0.021, 0.044, 0.064, 0.07, 0.066, 0.055, 0.04, 0.024, 0.008]
    hb = [0.015, 0.02, 0.042, 0.062, 0.067, 0.061, 0.049, 0.035, 0.02, 0.007]
    cy = [0, 0, 0, 0, 0, 0, -0.001, -0.002, -0.003, -0.004]
    cx = [0.022, 0.017, 0.007, 0.001, 0, 0, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx)
    b = F.make_body(lo, FLANK, gloss=150, tris=6200)
    b.paint(above_prim(lo, 0.1, wobble=0.006, freq=16), BACK, feather=0.02)
    b.paint(below_prim(lo, -0.5, wobble=0.006, freq=16), BELLY, feather=0.02)
    b.paint(blotch_prim(18.0, 0.32, seed=12, region=above_prim(lo, -0.2)), "#4a525c", feather=0.0040)  # faint velvety mottling
    zs = np.linspace(-0.28, 0.27, 12)
    for sx in (1, -1):
        b.paint(Tube(lo.line(zs, np.interp(zs, [-0.28, 0.27], [1.45, 1.05]) * sx), 0.0028, samples=3), "#8b939c", feather=0.002)
    mouth_line(F, [(-0.022, -0.012, 0.35), (-0.012, -0.007, 0.383), (0, -0.0045, 0.398), (0.012, -0.007, 0.383), (0.022, -0.012, 0.35)], 0.0028)
    F.lips([(-0.023, -0.006, 0.35), (-0.013, -0.002, 0.383), (0, 0.0, 0.396), (0.013, -0.002, 0.383), (0.023, -0.006, 0.35)], 0.003, color="#3c424a")
    F.gill(0.3, r=0.0034, th0=0.4, th1=2.6, curve=0.7)
    F.eyes(0.35, 1.15, 0.022, iris="#9aa7ad", ring="#d9e1e3", pupil_frac=0.66, rim=0.2, rim_color="#2a2f36")
    F.make_fins(FIN, gloss=120)
    RAY = "#1f2328"
    F.dorsal(0.08, 0.2, [0.02, 0.045, 0.05, 0.04, 0.02], 0.005, lean=0.3, nrays=10, scallop=0.25, ray_color=RAY, wave=(0.0015, 0.04))
    F.dorsal(-0.16, -0.06, [0.02, 0.042, 0.045, 0.035, 0.018], 0.005, lean=0.25, nrays=10, ray_color=RAY, wave=(0.0015, 0.04))
    F.dorsal(-0.16, -0.06, [0.02, 0.04, 0.042, 0.032, 0.016], 0.005, th=np.pi, lean=0.25, nrays=10, ray_color=RAY)
    F.caudal(-0.305, [(0.12, 0.1), (0.108, 0.07), (0.092, 0.035), (0.086, 0.0), (0.092, -0.035), (0.108, -0.07), (0.12, -0.1)],
             0.0055, bend=0.15, ray_color=RAY, nrays=15, scallop=0.06, wave=(0.002, 0.06))
    F.paired(0.27, np.pi * 0.66, [(0.02, 0.012, -0.06), (0.024, -0.005, -0.068), (0.02, -0.025, -0.05)], 0.0042,
             (0.3, -1, 0), spread=0.022, ray_color=RAY, nrays=9)
    F.paired(0.17, np.pi * 0.9, [(0.01, -0.03, -0.03), (0.01, -0.036, -0.01)], 0.004, (1, 0.35, 0), spread=0.02, ray_color=RAY, nrays=5)
    F.sockets(mouth=(0, -0.0045, 0.398), belly=(0, -0.067, 0.08))
    return F.m


# ==============================================================================================================
# flatfish (lying eyed-side up, head +Z): the body loft's "w" is the disc half-width in x, ht/hb the thickness


def flat_fringe(F, side, z0, z1, width_fn, thick, nseg=4, y=None, **kw):
    """Dorsal/anal fin fringe along the left (side=-1) or right (+1) rim of a flatfish disc, in the horizontal plane."""
    lo = F.loft
    zb = np.linspace(z0, z1, nseg + 1)
    out = []
    for a, b in zip(zb[:-1], zb[1:]):
        pad = (b - a) * 0.08
        zs = np.linspace(a - pad, b + pad, 4)
        rim = lambda z: np.array([lo.at(z, "cx") + side * lo.at(z, "w") * 0.94, lo.at(z, "cy") if y is None else y, z])
        tips = [rim(z) + np.array([side * width_fn(z), 0, -width_fn(z) * 0.18]) for z in zs]
        ra = rim(a - pad) - np.array([side * thick * 3, 0, 0])
        rb = rim(b + pad) - np.array([side * thick * 3, 0, 0])
        out.append(F.fin(ra, rb, tips, (0, 1, 0), thick, nrays=5, **kw))
    return out


def flat_eye(F, c, r, iris, ring, lean=(0, 0, 0), turret_color=None, side="R"):
    """A flatfish eye perched on a little turret on the top side."""
    c = np.asarray(c, float)
    out = np.array([0.0, 1.0, 0.0]) + np.asarray(lean, float)
    F.body.add(Capsule(c - (0, r * 1.2, 0), c - (0, r * 0.2, 0), r * 1.15, r * 1.05), k=r * 0.6, color=turret_color)
    eye_socket(F.body, c, r, out, rim=0.22, rim_color=turret_color)
    fish_eye(F.m, c, r, out, iris=iris, ring=ring, pupil_frac=0.6, side=side, toe=0.35, up=0.0)


def flounder():
    F = Fish("flounder", res=0.003, fin_res=0.0019)
    TOP, MOTTLE, PALE, BELLY, FIN, BAR, BAR2 = "#4f4a35", "#2c2819", "#93875f", "#efeadc", "#e0a457", "#1d1b19", "#f1e4c4"
    z = [-0.128, -0.112, -0.07, -0.01, 0.05, 0.1, 0.135, 0.158, 0.172, 0.178]
    w = [0.008, 0.014, 0.052, 0.076, 0.078, 0.066, 0.05, 0.032, 0.016, 0.006]
    ht = [0.004, 0.006, 0.014, 0.019, 0.019, 0.018, 0.017, 0.014, 0.009, 0.004]
    hb = [0.004, 0.005, 0.01, 0.013, 0.013, 0.012, 0.011, 0.009, 0.006, 0.003]
    cx = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.002, 0.004, 0.006, 0.007]  # head twisted a touch
    lo = Loft(z, w, ht, hb, 0.0, cx)
    b = F.make_body(lo, TOP, tris=5200, gloss=70)
    b.paint(blotch_prim(26.0, 0.02, seed=2), MOTTLE, feather=0.0025)
    b.paint(blotch_prim(40.0, 0.3, seed=6), PALE, feather=0.0025)
    rng = np.random.default_rng(7)
    stars = [lo.surf(zz, th, 0.0) for zz, th in zip(rng.uniform(-0.09, 0.14, 26), rng.uniform(-1.2, 1.2, 26))]
    b.paint(spots_prim(stars, 0.0042), "#2e2a20", feather=0.0015)
    for p in stars[::2]:
        b.add(Sphere(p, 0.0028), k=0.002)  # the starry flounder's rough star plates
    b.paint(func_prim(lambda P: P[:, 1] + 0.004), BELLY, feather=0.004)
    # lateral line arching over the pectoral
    b.paint(Tube([lo.top(zz, 0.0) for zz in np.linspace(-0.1, 0.1, 9)], 0.0018, samples=3), "#d8cfae", feather=0.001)
    zs = np.linspace(0.1, 0.135, 6)
    b.paint(Tube([lo.surf(zz, 0.6 * (zz - 0.1) / 0.035, 0.0) for zz in zs], 0.0018, samples=3), "#d8cfae", feather=0.001)
    # little twisted mouth at the tip
    mouth_line(F, [(0.0, 0.0, 0.176), (0.008, 0.002, 0.172), (0.014, 0.002, 0.165)], 0.0012)
    F.lips([(-0.002, 0.003, 0.176), (0.008, 0.005, 0.171), (0.015, 0.004, 0.163)], 0.0016, color=shade(TOP, 1.15))
    flat_eye(F, (0.016, 0.022, 0.14), 0.0105, "#d7b85e", "#efe0a8", lean=(0.6, 0, 0.35), turret_color=shade(TOP, 1.1), side="R")
    flat_eye(F, (-0.012, 0.023, 0.124), 0.0105, "#d7b85e", "#efe0a8", lean=(-0.6, 0, 0.35), turret_color=shade(TOP, 1.1), side="L")
    F.make_fins(FIN, gloss=120, decimate=4400)
    wf = lambda z: 0.028 * np.clip(np.sin(np.clip((z + 0.11) / 0.27, 0, 1) * np.pi) ** 0.6, 0.25, 1)
    fins = flat_fringe(F, 1, -0.105, 0.15, wf, 0.0024, nseg=4, ray_color="#b07a3a", scallop=0.1)
    fins += flat_fringe(F, -1, -0.105, 0.12, wf, 0.0024, nseg=4, ray_color="#b07a3a", scallop=0.1)
    bars = func_prim(lambda P: np.where((P[:, 2] / 0.03 - np.floor(P[:, 2] / 0.03)) < 0.5, -1.0, 1.0) * 0.01)
    for f in fins:
        F.fins.paint(inter_prim(f.zone(0.0), bars), BAR, feather=0.002)
        F.fins.paint(inter_prim(f.zone(0.0), not_prim(bars), func_prim(lambda P: P[:, 1] + 0.004)), BAR2, feather=0.002)
    F.caudal(-0.124, [(0.04, 0.0), (0.05, 0.0), (0.055, 0.0)], 0.0026) if False else None
    tail = F.fin((0.006, 0, -0.118), (-0.006, 0, -0.118),
                 [(0.034, 0, -0.15), (0.03, 0, -0.17), (0.016, 0, -0.183), (0.0, 0, -0.187), (-0.016, 0, -0.183), (-0.03, 0, -0.17), (-0.034, 0, -0.15)],
                 (0, 1, 0), 0.0026, nrays=11, ray_from=(0, 0, -0.112), ray_color="#b07a3a", scallop=0.08)
    F.fins.paint(inter_prim(tail.zone(0.55), bars), BAR, feather=0.002)
    F.paired(0.118, 0.9, [(0.02, 0.006, -0.02), (0.022, 0.004, -0.012)], 0.0018, (0.2, 1, 0), spread=0.008, ray_color="#8a6a3a", nrays=4)
    F.sockets(mouth=(0.008, 0.003, 0.176), belly=(0, -0.013, 0.0))
    return F.m


def halibut():
    F = Fish("halibut", res=0.012, fin_res=0.0075)
    TOP, MOTTLE, PALE, BELLY, FIN = "#4b4935", "#2b2b22", "#857f5e", "#efece2", "#454431"
    z = [-0.55, -0.5, -0.38, -0.2, 0.0, 0.2, 0.36, 0.48, 0.56, 0.6]
    w = [0.03, 0.045, 0.13, 0.215, 0.245, 0.235, 0.19, 0.13, 0.07, 0.02]
    ht = [0.018, 0.024, 0.05, 0.072, 0.08, 0.077, 0.07, 0.058, 0.04, 0.014]
    hb = [0.014, 0.018, 0.036, 0.05, 0.055, 0.052, 0.046, 0.038, 0.026, 0.01]
    cx = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.004, 0.01, 0.016, 0.02]
    lo = Loft(z, w, ht, hb, 0.0, cx)
    b = F.make_body(lo, TOP, tris=6400, gloss=70)
    b.paint(blotch_prim(6.0, 0.0, seed=4), MOTTLE, feather=0.0050)
    b.paint(blotch_prim(11.0, 0.26, seed=9), PALE, feather=0.0050)
    b.paint(func_prim(lambda P: P[:, 1] + 0.012), BELLY, feather=0.012)
    # lateral line with its high arch over the pectoral
    for sx in (1, -1):
        pass
    b.paint(Tube([lo.top(zz, 0.0) for zz in np.linspace(-0.48, 0.28, 10)], 0.006, samples=3), "#cfc8a8", feather=0.003)
    b.paint(Tube([lo.surf(0.28 + t * 0.14, 0.75 * np.sin(t * np.pi), 0.0) for t in np.linspace(0, 1, 7)], 0.006, samples=3), "#cfc8a8", feather=0.003)
    mouth_line(F, [(-0.035, 0.0, 0.565), (-0.01, 0.006, 0.598), (0.02, 0.006, 0.6), (0.05, 0.0, 0.57)], 0.0055)
    F.lips([(-0.036, 0.012, 0.562), (-0.01, 0.018, 0.594), (0.02, 0.018, 0.596), (0.052, 0.012, 0.565)], 0.0065, color=shade(TOP, 1.12))
    flat_eye(F, (0.045, 0.075, 0.47), 0.03, "#cfb46a", "#ecdca8", lean=(0.6, 0, 0.35), turret_color=shade(TOP, 1.08), side="R")
    flat_eye(F, (-0.035, 0.078, 0.43), 0.03, "#cfb46a", "#ecdca8", lean=(-0.6, 0, 0.35), turret_color=shade(TOP, 1.08), side="L")
    F.gill(0.39, r=0.007, th0=-1.3, th1=1.3, curve=-0.5)
    F.make_fins(FIN, gloss=110)
    wf = lambda z: 0.075 * np.clip(np.sin(np.clip((z + 0.5) / 0.95, 0, 1) * np.pi) ** 0.7, 0.25, 1)
    for side, z1 in ((1, 0.45), (-1, 0.38)):
        for f in flat_fringe(F, side, -0.47, z1, wf, 0.0075, nseg=5, ray_color="#3c3b2c", scallop=0.08):
            F.fins.paint(blotch_prim(8.0, 0.1, seed=5, region=f), "#3c3b2c", feather=0.0050)
    # crescent tail
    F.fin((0.022, 0, -0.53), (-0.022, 0, -0.53),
          [(0.17, 0, -0.69), (0.13, 0, -0.67), (0.07, 0, -0.64), (0.0, 0, -0.625), (-0.07, 0, -0.64), (-0.13, 0, -0.67), (-0.17, 0, -0.69)],
          (0, 1, 0), 0.0085, nrays=15, ray_from=(0, 0, -0.5), ray_color="#3c3b2c", scallop=0.06, wave=(0.003, 0.12))
    F.paired(0.36, 1.0, [(0.07, 0.01, -0.06), (0.08, 0.005, -0.03)], 0.006, (0.2, 1, 0), spread=0.03, ray_color="#3c3b2c", nrays=6)
    F.sockets(mouth=(0.01, 0.006, 0.6), belly=(0, -0.055, 0.0))
    return F.m


# ==============================================================================================================
# wolf eel — long grey-brown eel spotted with pale-ringed dark spots, huge lumpy grumpy-sweet face, buck fangs


def wolf_eel():
    F = Fish("wolf_eel", res=0.012, fin_res=0.007)
    BASE, SPOT, RING, BELLY, FIN = "#8a8475", "#4a443e", "#d4ccb6", "#bdb5a0", "#77715f"
    z = np.linspace(-0.78, 0.8, 17)
    zk = [-0.78, -0.62, -0.3, 0.2, 0.5, 0.6, 0.7, 0.76, 0.795, 0.81]
    prof_h = np.interp(z, zk, [0.01, 0.045, 0.076, 0.094, 0.106, 0.14, 0.142, 0.118, 0.075, 0.022])
    prof_w = np.interp(z, zk, [0.008, 0.032, 0.056, 0.07, 0.082, 0.118, 0.122, 0.1, 0.066, 0.022])
    cx = 0.15 * np.sin((z + 0.78) / 1.58 * np.pi * 1.7 + 0.4) * np.clip((0.6 - z) / 0.35, 0, 1)
    lo = Loft(z, prof_w, prof_h, prof_h * 0.92, 0.0, cx)
    b = F.make_body(lo, BASE, tris=5600, gloss=135)
    b.paint(below_prim(lo, -0.55, wobble=0.01, freq=8), BELLY, feather=0.03)
    C, R = surface_spots(lo, 40, (-0.62, 0.58), (0.0, 1.85), 0.026, seed=21, jitter=0.3)
    b.paint(spots_prim(C, np.array(R) * 1.32), RING, feather=0.006)
    b.paint(spots_prim(C, R), SPOT, feather=0.004)
    # the face: lumpy jowls, heavy brow, thick lips, two buck fangs
    for sx in (1, -1):
        b.add(Ellipsoid(lo.surf(0.7, sx * 1.95, -0.012), (0.04, 0.034, 0.05)), k=0.025)   # jowls
        b.add(Ellipsoid(lo.surf(0.61, sx * 1.6, -0.016), (0.034, 0.04, 0.05)), k=0.025)  # cheek lumps
        b.add(Ellipsoid(lo.surf(0.735, sx * 0.72, -0.01), (0.028, 0.02, 0.034)), k=0.015)  # brow lumps
        b.add(Ellipsoid(lo.surf(0.65, sx * 1.15, -0.008), (0.02, 0.022, 0.028)), k=0.012)  # wart
    b.add(Ellipsoid(lo.top(0.66, -0.014), (0.045, 0.03, 0.06)), k=0.03)  # forehead hump
    b.add(Ellipsoid((lo.at(0.79, "cx"), -0.014, 0.795), (0.05, 0.038, 0.035)), k=0.025)  # thick snout
    mx = lo.at(0.79, "cx")
    gape = [(mx - 0.062, -0.036, 0.72), (mx - 0.046, -0.028, 0.785), (mx, -0.022, 0.828), (mx + 0.046, -0.028, 0.785), (mx + 0.062, -0.036, 0.72)]
    mouth_line(F, gape, 0.006)
    F.lips([(p[0] * 1.02, p[1] + 0.011, p[2] - 0.002) for p in gape], 0.0085, color="#a29c8c")
    F.lips([(p[0] * 1.02, p[1] - 0.012, p[2] - 0.004) for p in gape], 0.0095, color="#a29c8c")
    teeth(F, [(mx - 0.016, -0.026, 0.826), (mx + 0.016, -0.026, 0.826)], 0.022, toward=(0, -1, 0.35))
    teeth(F, [(mx - 0.036, -0.032, 0.806), (mx + 0.036, -0.032, 0.806)], 0.013, toward=(0, 1, 0.2))
    F.eyes(0.715, 0.9, 0.031, iris="#c9a45a", ring="#e8d6a2", pupil_frac=0.62, rim=0.3, rim_color="#76705f", sink=0.35, toe=0.4, up=0.15)
    b.paint(blotch_prim(20.0, 0.25, seed=9, region=func_prim(lambda P: 0.5 - P[:, 2])), "#9c9686", feather=0.0040)
    F.make_fins(FIN, gloss=140, decimate=3300)
    F.long_fin(-0.76, 0.56, lambda zz: 0.05 * np.clip((zz + 0.8) / 0.25, 0.2, 1) * np.clip((0.6 - zz) / 0.12, 0.3, 1), 0.0075, nseg=9,
               rays_per=6, ray_color="#5f5a4e", wave=(0.003, 0.1))
    F.long_fin(-0.76, -0.05, lambda zz: 0.042 * np.clip((zz + 0.8) / 0.2, 0.2, 1) * np.clip((0.0 - zz) / 0.12, 0.3, 1), 0.0072, th=np.pi,
               nseg=6, rays_per=6, ray_color="#5f5a4e")
    nrm = lo.normal(0.55, np.pi * 0.6)
    F.paired(0.55, np.pi * 0.62, [(0.04, 0.04, -0.06), (0.05, 0.0, -0.085), (0.04, -0.045, -0.07)], 0.0068, (0.35, -1, 0), spread=0.04,
             ray_color="#5f5a4e", nrays=10)
    F.sockets(mouth=(mx, -0.022, 0.828), belly=(lo.at(0.2, "cx"), -0.09, 0.2))
    return F.m


# ==============================================================================================================
# lumpsucker — a round little green ball of a fish, rows of knobbly tubercles, a crest, sucker disc, pursed lips


def lumpsucker():
    F = Fish("lumpsucker", res=0.003, fin_res=0.0022)
    BASE, DARK, KNOB, BELLY, FIN = "#7c9a4c", "#4d6a30", "#c5d283", "#e8bf80", "#93ad5c"
    z = [-0.115, -0.1, -0.06, 0.0, 0.055, 0.095, 0.125, 0.145, 0.155]
    w = [0.01, 0.019, 0.056, 0.078, 0.076, 0.064, 0.048, 0.03, 0.01]
    ht = [0.012, 0.026, 0.068, 0.088, 0.085, 0.072, 0.054, 0.034, 0.012]
    hb = [0.01, 0.022, 0.058, 0.074, 0.07, 0.058, 0.042, 0.028, 0.01]
    lo = Loft(z, w, ht, hb, 0.0, [-0.008, -0.006, -0.002, 0, 0, 0, 0, 0, 0])
    b = F.make_body(lo, BASE, tris=5600, gloss=160, dents=20)
    b.paint(blotch_prim(30.0, 0.12, seed=3, region=above_prim(lo, -0.3)), DARK, feather=0.0025)
    b.paint(below_prim(lo, -0.55, wobble=0.004, freq=30), BELLY, feather=0.01)
    # knobbly tubercles: a crest and three rows per flank
    knobs = []
    for th, z0, z1, n, sz in ((0.0, -0.05, 0.09, 6, 0.011), (0.85, -0.07, 0.1, 7, 0.0085), (1.55, -0.075, 0.1, 8, 0.0075), (2.25, -0.06, 0.07, 6, 0.007)):
        for sx in ((1,) if th == 0.0 else (1, -1)):
            for i, zz in enumerate(np.linspace(z0, z1, n)):
                sj = sz * (0.85 + 0.3 * ((i * 7) % 5) / 4)
                p = lo.surf(zz, th * sx, -sj * 0.2)
                nr = lo.normal(zz, th * sx)
                b.add(Capsule(p, p + nr * sj * 0.9, sj, sj * 0.35), k=sj * 0.5)
                knobs.append(p + nr * sj * 0.6)
    b.paint(spots_prim(knobs, 0.0065), KNOB, feather=0.003)
    # pursed little mouth
    b.add(Torus((0, -0.004, 0.152), 0.0075, 0.0035, rot=(90, 0, 0)), k=0.004, color="#d98f6e")
    b.sub(Sphere((0, -0.004, 0.158), 0.0045), k=0.002)
    b.paint(Sphere((0, -0.004, 0.157), 0.0045), "#4a2a28", feather=0.0015)
    F.eyes(0.1, 1.15, 0.016, iris="#e3c45a", ring="#f3e3a6", pupil_frac=0.66, rim=0.22, rim_color=DARK, toe=0.35, up=0.1)
    F.gill(0.07, r=0.0016, th0=0.7, th1=2.3, curve=0.4)
    F.make_fins(FIN, gloss=150)
    F.dorsal(-0.09, -0.04, [0.012, 0.022, 0.024, 0.014], 0.0028, lean=0.25, ray_color=DARK, nrays=6)
    F.dorsal(-0.09, -0.045, [0.01, 0.018, 0.018, 0.01], 0.0026, th=np.pi, lean=0.25, ray_color=DARK, nrays=6)
    F.caudal(-0.11, [(0.035, 0.03), (0.042, 0.018), (0.045, 0.0), (0.042, -0.018), (0.035, -0.03)], 0.0028, bend=-0.1,
             ray_color=DARK, nrays=9, scallop=0.12)
    F.paired(0.06, np.pi * 0.62, [(0.012, 0.022, -0.028), (0.016, 0.0, -0.038), (0.012, -0.022, -0.03)], 0.0026, (0.4, -1, 0),
             spread=0.03, ray_color=DARK, nrays=8)
    # sucker disc underneath
    sd = F.m.piece("sucker", color="#e9a888", gloss=170, lumps=0.0006, res=0.0022, decimate=500)
    sd.add(Torus((0, -0.066, 0.035), 0.022, 0.006, rot=(0, 0, 0)))
    sd.add(Cylinder((0, -0.067, 0.035), 0.022, 0.003), k=0.004)
    F.sockets(mouth=(0, -0.004, 0.158), belly=(0, -0.074, 0.02))
    return F.m


# ==============================================================================================================
# ratfish — big-eyed "rabbit fish": huge emerald eyes, buck tooth-plates, wing-like pectorals, tall spined dorsal,
# bronze-silver body freckled white tapering into a whip tail


def ratfish():
    F = Fish("ratfish", res=0.004, fin_res=0.0028)
    BASE, BACK, BELLY, SPOT, FIN = "#a79a86", "#7a6656", "#e2dfd6", "#f4f0e4", "#8e8070"
    z = [-0.4, -0.3, -0.16, -0.04, 0.06, 0.15, 0.22, 0.27, 0.305, 0.325]
    w = [0.002, 0.006, 0.018, 0.034, 0.047, 0.051, 0.048, 0.04, 0.028, 0.012]
    ht = [0.002, 0.007, 0.024, 0.043, 0.058, 0.062, 0.058, 0.047, 0.033, 0.013]
    hb = [0.002, 0.006, 0.02, 0.038, 0.05, 0.054, 0.05, 0.042, 0.03, 0.013]
    cy = [0.012, 0.004, 0.0, 0, 0, 0, 0, -0.002, -0.005, -0.008]
    cx = [0.06, 0.03, 0.008, 0, 0, 0, 0, 0, 0, 0]
    lo = Loft(z, w, ht, hb, cy, cx)
    b = F.make_body(lo, BASE, tris=5600, gloss=200)
    b.paint(above_prim(lo, 0.35, wobble=0.004, freq=30), BACK, feather=0.012)
    b.paint(below_prim(lo, -0.35, wobble=0.004, freq=30), BELLY, feather=0.012)
    b.paint(inter_prim(above_prim(lo, -0.2), below_prim(lo, 0.25)), "#b9b3c4", feather=0.01)  # iridescent sheen
    C, R = surface_spots(lo, 45, (-0.2, 0.25), (0.0, 1.7), 0.0055, seed=31, jitter=0.4)
    b.paint(spots_prim(C, R), SPOT, feather=0.0018)
    # blunt rabbit snout, little mouth with buck tooth-plates
    b.add(Ellipsoid((0, -0.012, 0.31), (0.026, 0.024, 0.022)), k=0.012)
    mouth_line(F, [(-0.014, -0.034, 0.3), (0, -0.031, 0.315), (0.014, -0.034, 0.3)], 0.0022)
    tp = F.m.piece("teeth", color="#f5f1e6", gloss=210, lumps=0.0, res=0.0015, merge="eyes", ao=False, decimate=160)
    for sx in (1, -1):
        tp.add(Box((sx * 0.0042, -0.034, 0.316), (0.0038, 0.0055, 0.0018), rot=(18, 0, 0), round=0.0012))
    F.lips([(-0.015, -0.028, 0.298), (0, -0.025, 0.314), (0.015, -0.028, 0.298)], 0.0026, color=shade(BASE, 1.08))
    # lateral-line canals on the head (ratfish have a lovely scrolled pattern)
    for sx in (1, -1):
        b.paint(Tube(lo.line(np.linspace(0.18, 0.3, 6), np.array([1.3, 1.25, 1.35, 1.55, 1.8, 2.0]) * sx), 0.0016, samples=3), "#5e5048", feather=0.001)
        b.paint(Tube(lo.line(np.linspace(-0.2, 0.2, 9), 1.25 * sx), 0.0016, samples=3), "#6e6052", feather=0.001)
    F.eyes(0.235, 1.12, 0.032, iris="#2fae84", ring="#9af2c9", pupil_frac=0.52, rim=0.2, rim_color=BACK, sink=0.38, toe=0.25)
    F.make_fins(FIN, gloss=150, decimate=3400)
    RAY = "#5e5248"
    # tall first dorsal with its venom spine at the front
    F.dorsal(0.12, 0.19, [0.02, 0.05, 0.075, 0.085], 0.0036, lean=0.35, ray_color=RAY, nrays=6, scallop=0.15)
    spines(F, [(lo.top(0.188, -0.004), lo.top(0.17, 0.092))], 0.0042, 0.0012, color="#f2ead6")
    # long low second dorsal running down the tail, and the ventral fin under the tail
    F.long_fin(-0.36, 0.1, lambda zz: 0.02 * np.clip((zz + 0.38) / 0.12, 0.15, 1) * np.clip((0.12 - zz) / 0.06, 0.3, 1), 0.0026, nseg=5,
               rays_per=6, ray_color=RAY)
    F.long_fin(-0.37, -0.1, lambda zz: 0.016 * np.clip((zz + 0.38) / 0.1, 0.2, 1) * np.clip((-0.08 - zz) / 0.06, 0.3, 1), 0.0024, th=np.pi,
               nseg=3, rays_per=6, ray_color=RAY)
    # big wing pectorals
    F.paired(0.165, np.pi * 0.6, [(0.06, -0.03, -0.035), (0.12, -0.075, -0.11), (0.1, -0.075, -0.165), (0.045, -0.04, -0.13)], 0.0036,
             (0.57, 0.82, 0.0), spread=0.05, ray_color=RAY, nrays=12, wave=(0.002, 0.05))
    F.paired(0.02, np.pi * 0.85, [(0.03, -0.03, -0.03), (0.035, -0.035, -0.06)], 0.003, (0.5, -1, 0), spread=0.03, ray_color=RAY, nrays=6)
    F.sockets(mouth=(0, -0.032, 0.318), belly=(0, -0.054, 0.12))
    return F.m


# ==============================================================================================================
# anglerfish — deep-sea humpback angler: round inky body, enormous upturned toothy grin, a glowing lure on a rod


def anglerfish():
    F = Fish("anglerfish", res=0.0045, fin_res=0.003)
    BASE, DARK, BELLY, FIN, INNER = "#3a2f33", "#231c20", "#4d4046", "#2e2529", "#1a0f12"
    z = [-0.2, -0.18, -0.12, -0.04, 0.05, 0.12, 0.17, 0.205, 0.225]
    w = [0.012, 0.026, 0.074, 0.104, 0.112, 0.106, 0.092, 0.072, 0.04]
    ht = [0.016, 0.034, 0.088, 0.12, 0.128, 0.114, 0.092, 0.065, 0.03]
    hb = [0.013, 0.028, 0.08, 0.112, 0.12, 0.114, 0.104, 0.09, 0.062]
    lo = Loft(z, w, ht, hb, 0.0, [-0.01, -0.008, -0.003, 0, 0, 0, 0, 0, 0])
    b = F.make_body(lo, BASE, tris=4300, gloss=200, dents=24)
    b.paint(blotch_prim(18.0, 0.15, seed=4), DARK, feather=0.0025)
    b.paint(below_prim(lo, -0.5), BELLY, feather=0.02)
    # the huge upturned mouth: a bucket lower jaw thrust forward, gape carved deep and dark, jaws ringed with fangs
    b.add(Ellipsoid((0, -0.05, 0.19), (0.098, 0.062, 0.075), rot=(-35, 0, 0)), k=0.02)
    cav = Ellipsoid((0, 0.004, 0.205), (0.088, 0.042, 0.088), rot=(-38, 0, 0))
    b.sub(cav, k=0.006)
    b.paint(Ellipsoid((0, 0.004, 0.205), (0.093, 0.047, 0.093), rot=(-38, 0, 0)), INNER, gloss=210, feather=0.004)
    b.paint(Ellipsoid((0, -0.02, 0.18), (0.05, 0.02, 0.05), rot=(-38, 0, 0)), "#7a3a44", gloss=220, feather=0.006)  # tongue
    lower = smooth_curve(np.array([(-0.088, -0.006, 0.12), (-0.075, -0.026, 0.19), (-0.042, -0.04, 0.245), (0, -0.046, 0.262),
                                   (0.042, -0.04, 0.245), (0.075, -0.026, 0.19), (0.088, -0.006, 0.12)]), 3)
    upper = smooth_curve(np.array([(-0.086, 0.016, 0.115), (-0.075, 0.03, 0.17), (-0.045, 0.046, 0.205), (0, 0.052, 0.218),
                                   (0.045, 0.046, 0.205), (0.075, 0.03, 0.17), (0.086, 0.016, 0.115)]), 3)
    F.lips(lower, 0.0075, color="#4a3c42")
    F.lips(upper, 0.0065, color="#4a3c42")
    lt = lower[1:-1:2]
    teeth(F, [p + (0, 0.004, -0.004) for p in lt], np.array([0.02, 0.026, 0.032, 0.03, 0.034, 0.03, 0.032, 0.026, 0.02, 0.022][:len(lt)]),
          toward=(0, 1, -0.35), color="#ece6dc")
    ut = upper[2:-2:2]
    teeth(F, [p + (0, -0.004, -0.004) for p in ut], 0.022, toward=(0, -1, -0.2), color="#ece6dc")
    # sparse little skin papillae
    rng = np.random.default_rng(2)
    for _ in range(26):
        zz, th = rng.uniform(-0.12, 0.15), rng.uniform(-2.6, 2.6)
        p = lo.surf(zz, th, -0.001)
        b.add(Capsule(p, p + lo.normal(zz, th) * 0.008, 0.0035, 0.0015), k=0.003)
    F.eyes(0.15, 0.9, 0.019, iris="#7fb9c9", ring="#cbe8ee", pupil_frac=0.6, rim=0.25, rim_color=DARK, toe=0.3, up=0.1)
    F.make_fins(FIN, gloss=170)
    RAY = "#16101a"
    F.dorsal(-0.16, -0.08, [0.02, 0.035, 0.038, 0.025], 0.0032, lean=0.3, ray_color=RAY, nrays=7)
    F.dorsal(-0.16, -0.09, [0.018, 0.03, 0.03, 0.02], 0.003, th=np.pi, lean=0.3, ray_color=RAY, nrays=6)
    F.caudal(-0.19, [(0.05, 0.05), (0.065, 0.03), (0.07, 0.0), (0.065, -0.03), (0.05, -0.05)], 0.0034, bend=-0.1, ray_color=RAY, nrays=9)
    F.paired(0.0, np.pi * 0.62, [(0.02, 0.02, -0.04), (0.025, -0.005, -0.05), (0.02, -0.03, -0.04)], 0.003, (0.4, -1, 0), spread=0.03,
             ray_color=RAY, nrays=7)
    # the illicium (fishing rod) springs from the brow and arcs forward; the esca glows
    rod = [lo.top(0.13, -0.006), lo.top(0.15, 0.06), (0, 0.2, 0.25), (0, 0.18, 0.3), (0, 0.15, 0.315)]
    F.fins.add(Tube(np.array(rod, float), [0.0055, 0.0045, 0.0035, 0.003, 0.003], samples=5), k=0.004, color="#4a3c42")
    tip = np.array([0, 0.135, 0.318])
    lure = F.m.piece("lure", color="#b8ffe6", gloss=230, mat=1, lumps=0.0008, res=0.0018, ao=False, decimate=700)
    lure.add(Sphere(tip, 0.017))
    lure.add(Ellipsoid(tip + (0, -0.012, 0.004), (0.008, 0.012, 0.008)), k=0.006)
    for a in (-40, 0, 40):
        r = np.radians(a)
        lure.add(Capsule(tip + (0, -0.016, 0), tip + (np.sin(r) * 0.012, -0.03, np.cos(r) * 0.006), 0.003, 0.0015), k=0.003)
    lure.paint(Sphere(tip + (0, 0.004, 0.008), 0.009), "#f6fff4")
    F.m.socket("lure", None, tuple(tip))
    F.sockets(mouth=(0, 0.004, 0.235), belly=(0, -0.12, 0.05))
    return F.m


# ==============================================================================================================
# oarfish (legendary) — a 3 m silver ribbon undulating, blue-grey dashes, scarlet crest plume, ribbon dorsal, oar fins


def oarfish():
    F = Fish("oarfish", res=0.011, fin_res=0.0055)
    BASE, DASH, BELLY, RED, HEAD = "#cfd5da", "#6f8193", "#e9ecee", "#d83a35", "#9fb3c6"
    z = np.linspace(-1.6, 1.42, 19)
    h = np.interp(z, [-1.6, -1.3, -0.9, 0.0, 0.9, 1.2, 1.32, 1.4, 1.42], [0.008, 0.055, 0.095, 0.118, 0.122, 0.112, 0.09, 0.045, 0.012])
    wd = np.interp(z, [-1.6, -1.3, -0.9, 0.0, 0.9, 1.2, 1.32, 1.4, 1.42], [0.004, 0.014, 0.022, 0.026, 0.028, 0.03, 0.028, 0.018, 0.006])
    cx = 0.2 * np.sin((z + 1.6) / 3.0 * np.pi * 2.2) * np.clip((1.3 - z) / 0.6, 0, 1)
    cy = 0.035 * np.sin((z + 1.6) / 3.0 * np.pi * 1.1)
    lo = Loft(z, wd, h, h * 0.95, cy, cx)
    b = F.make_body(lo, BASE, res=0.0085, decimate=5200, gloss=230)
    b.paint(below_prim(lo, -0.4), BELLY, feather=0.03)
    # rows of blue-grey dashes and spots along the silver flank
    rng = np.random.default_rng(3)
    dashes = []
    for zz in np.arange(-1.3, 1.1, 0.075):
        for th in (0.7, 1.15, 1.6, 2.0):
            for sx in (1, -1):
                if rng.uniform() < 0.75:
                    dashes.append(lo.surf(zz + rng.uniform(-0.02, 0.02), sx * (th + rng.uniform(-0.1, 0.1)), 0.0))
    b.paint(spots_prim(dashes, 0.011), DASH, feather=0.004)
    b.paint(func_prim(lambda P: P[:, 2] - 1.27), HEAD, feather=0.03)
    mouth_line(F, [(lo.at(1.38, "cx") - 0.012, -0.01, 1.38), (lo.at(1.42, "cx"), -0.004, 1.422), (lo.at(1.38, "cx") + 0.012, -0.01, 1.38)], 0.003)
    F.lips([(lo.at(1.38, "cx") - 0.013, -0.004, 1.38), (lo.at(1.42, "cx"), 0.002, 1.418), (lo.at(1.38, "cx") + 0.013, -0.004, 1.38)], 0.0035, color="#b9c9d6")
    F.gill(1.3, r=0.004, th0=0.5, th1=2.6, curve=0.5)
    F.eyes(1.36, 1.2, 0.024, iris="#d9dde2", ring="#f6f7f8", pupil_frac=0.62, rim=0.25, rim_color="#8aa0b6", sink=0.5, toe=0.3)
    F.make_fins(RED, gloss=170, res=0.0055)
    RAY = "#9e211f"
    # scarlet ribbon dorsal the whole length (separate small pieces so the long fin meshes fast)
    F.long_fin(-1.52, 1.22, lambda zz: 0.075 * np.clip((zz + 1.58) / 0.3, 0.2, 1), 0.0062, nseg=10, rays_per=9, ray_color=RAY,
               wave=(0.004, 0.09), separate=360)
    # the crest: a plume of long red rays springing from the head
    hz = 1.24
    crest = F.m.piece("crest", color=RED, gloss=170, lumps=0.0008, res=0.004, merge="fins", decimate=1300)
    for i, (ln, ang) in enumerate(((0.36, 62), (0.42, 52), (0.38, 42), (0.3, 32), (0.24, 24), (0.18, 16))):
        base = lo.top(hz - i * 0.02, -0.008)
        a = np.radians(ang)
        d = np.array([0.0, np.sin(a), np.cos(a) * -1.0])
        mid = base + d * ln * 0.5 + np.array([0.02 * (i % 2 - 0.5), 0.04, 0.05])
        tipp = base + d * ln + np.array([0.03 * (i % 2 - 0.5), -0.02, 0.0])
        crest.add(Tube(np.array([base, mid, tipp]), [0.007, 0.005, 0.0035], samples=5), k=0.004)
        crest.add(Ellipsoid(tipp, (0.006, 0.014, 0.01), rot=(ang, 0, 0)), k=0.004)  # little paddle tips
    # long pelvic "oars" trailing below
    for sx in (1, -1):
        base = lo.surf(1.2, sx * np.pi * 0.9, -0.006)
        pts = np.array([base, base + (sx * 0.03, -0.12, -0.08), base + (sx * 0.05, -0.2, -0.22), base + (sx * 0.06, -0.24, -0.36)])
        crest.add(Tube(pts, [0.0055, 0.0045, 0.0035, 0.003], samples=5), k=0.004)
        crest.add(Ellipsoid(pts[-1] + (0, -0.006, -0.02), (0.006, 0.016, 0.034), rot=(20, 0, 0)), k=0.004)
    F.m.socket("crest", None, tuple(lo.top(hz, 0.3)))
    F.sockets(mouth=(lo.at(1.42, "cx"), -0.004, 1.422), belly=(lo.at(0.0, "cx"), -0.1, 0.0))
    return F.m


# ==============================================================================================================
# ocean sunfish (mola mola) — a huge silvery disc of a fish: tall dorsal & anal sails, frilly clavus, pouty mouth


def sunfish():
    F = Fish("sunfish", res=0.022, fin_res=0.011)
    BASE, BACK, BELLY, PALE, FIN = "#9aa4aa", "#6f7a82", "#d7dbd9", "#c4cbcd", "#7f8a91"
    z = [-0.44, -0.4, -0.3, -0.15, 0.0, 0.15, 0.3, 0.42, 0.5, 0.54]
    w = [0.05, 0.07, 0.095, 0.112, 0.12, 0.116, 0.1, 0.078, 0.052, 0.022]
    ht = [0.26, 0.33, 0.39, 0.425, 0.43, 0.405, 0.34, 0.25, 0.15, 0.05]
    hb = [0.26, 0.33, 0.39, 0.42, 0.42, 0.39, 0.32, 0.23, 0.13, 0.045]
    lo = Loft(z, w, ht, hb, 0.0, 0.0)
    b = F.make_body(lo, BASE, tris=6300, gloss=150, dents=30)
    b.add(Ellipsoid((0, 0, -0.43), (0.05, 0.26, 0.04)), k=0.04)  # round off the truncated rear
    b.paint(above_prim(lo, 0.4, wobble=0.03, freq=4), BACK, feather=0.05)
    b.paint(below_prim(lo, -0.45, wobble=0.03, freq=4), BELLY, feather=0.05)
    b.paint(blotch_prim(5.0, 0.25, seed=8), PALE, feather=0.0050)
    # pouty round mouth
    b.add(Torus((0, -0.01, 0.54), 0.024, 0.012, rot=(90, 0, 0)), k=0.012, color="#b8c0c4")
    b.sub(Sphere((0, -0.01, 0.555), 0.016), k=0.006)
    b.paint(Sphere((0, -0.01, 0.552), 0.016), "#3c3236", feather=0.004)
    F.gill(0.33, r=0.008, th0=1.0, th1=2.1, curve=0.3)
    F.eyes(0.4, 1.22, 0.05, iris="#a7b4bb", ring="#e3e9eb", pupil_frac=0.64, rim=0.24, rim_color=BACK, sink=0.4, toe=0.25)
    F.make_fins(FIN, gloss=140)
    RAY = "#59646c"
    # tall dorsal and anal sails swept back
    F.fin(lo.top(-0.33, -0.02), lo.top(-0.12, -0.02), [lo.top(-0.36, 0.05), lo.top(-0.42, 0.3), lo.top(-0.42, 0.42), lo.top(-0.34, 0.44), lo.top(-0.22, 0.2), lo.top(-0.12, 0.02)],
          (1, 0, 0), 0.012, ray_color=RAY, nrays=9, scallop=0.06, wave=(0.006, 0.25))
    F.fin(lo.bottom(-0.33, -0.02), lo.bottom(-0.12, -0.02), [lo.bottom(-0.36, 0.05), lo.bottom(-0.42, 0.28), lo.bottom(-0.41, 0.4), lo.bottom(-0.33, 0.42), lo.bottom(-0.22, 0.2), lo.bottom(-0.12, 0.02)],
          (1, 0, 0), 0.012, ray_color=RAY, nrays=9, scallop=0.06, wave=(0.006, 0.25))
    # clavus: the scalloped frill that stands in for a tail
    angs = np.radians(np.linspace(62, -62, 9))
    tips = [np.array([0, np.sin(a) * 0.36, -0.44 - np.cos(a) * 0.1]) for a in angs]
    F.fin((0, 0.32, -0.36), (0, -0.32, -0.36), tips, (1, 0, 0), 0.012, ray_color=RAY, nrays=13, scallop=0.35, ray_from=(0, 0, -0.2),
          wave=(0.004, 0.2), rim_color="#c9d0d3", rim_w=0.012)
    F.paired(0.22, np.pi * 0.5, [(0.03, 0.05, -0.08), (0.04, 0.0, -0.11), (0.03, -0.05, -0.08)], 0.008, (0.3, 0, -1), spread=0.06,
             ray_color=RAY, nrays=8)
    F.sockets(mouth=(0, -0.01, 0.556), belly=(0, -0.42, 0.0))
    return F.m


MODELS = {
    "fish/herring": herring,
    "fish/mackerel": mackerel,
    "fish/smelt": smelt,
    "fish/salmon": salmon,
    "fish/cod": cod,
    "fish/rockfish": rockfish,
    "fish/lingcod": lingcod,
    "fish/sablefish": sablefish,
    "fish/flounder": flounder,
    "fish/halibut": halibut,
    "fish/wolf_eel": wolf_eel,
    "fish/lumpsucker": lumpsucker,
    "fish/ratfish": ratfish,
    "fish/anglerfish": anglerfish,
    "fish/oarfish": oarfish,
    "fish/sunfish": sunfish,
}
