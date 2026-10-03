"""
Shared sculpting helpers for the catch: fish bodies (lofts), pressed-clay fins with scored rays, big glossy fish eyes,
pattern paints (spots, blotches, bars), scored grooves, metallic-clay wear (tarnish in crevices, worn bright edges),
rope/strand helpers and a common palette. Used by models/catch_*.py and models/boat_*.py.

Conventions (Docs/DESIGN.md §5): x right, y up, z forward, metres. Fish centred at the origin, head toward +Z.
Treasures/props bottom-centred. Gloss lives in vertex alpha (0 matte clay .. 255 wet/varnished/eyes).
"""
from __future__ import annotations

import numpy as np
from scipy.interpolate import PchipInterpolator

from clay import *

# --------------------------------------------------------------------------------------------------------------
# palette & gloss levels (sRGB) — dusty, saturated plasticine; metals are "metallic clay"

CP = dict(
    brass="#c39236", brass_lt="#ecd08a", brass_dk="#5e4318", gold="#dca52b", gold_lt="#f8e08a", gold_dk="#7f5512",
    silver="#c3c8cf", silver_dk="#6c727c", iron="#4b4b50", iron_dk="#2c2c31", rust="#9c4a22", rust_lt="#c46a33",
    copper="#b8673a", verdigris="#5f9c8a", wood="#8b5b34", wood_dk="#553620", wood_lt="#b98552", rope="#c9ad7a",
    rope_dk="#8d7449", paper="#ece0bf", cork="#b88a55", glass_g="#5f9d72", glass_b="#5f8fb0", glass_br="#8a5a2c",
    pearl="#f1ebe0", stone="#9c958a", kelp="#5b7a2e", kelp_dk="#3d5520", white="#efe9dc", black="#25262b",
    eye_white="#f4f1ea", pupil="#111114",
)
G_CLAY, G_SOFT, G_FIN, G_WET, G_METAL, G_EYE, G_GLASS = 35, 80, 150, 190, 170, 240, 255


def _n(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


# --------------------------------------------------------------------------------------------------------------
# Loft: a fish body. Elliptical cross-sections along z with half-width w(z), half-heights above/below the centre line
# (ht, hb), centre line cy(z) and a lateral bend cx(z). Profiles are PCHIP-smoothed between control points.


class Loft(Prim):
    def __init__(self, z, w, ht, hb=None, cy=0.0, cx=0.0, n=1024, squarish=0.0, scales=None):
        """z: increasing control z's (tail .. nose). w/ht/hb/cy/cx: scalars or per-control arrays.
        squarish: 0 = ellipse .. ~0.6 = rounded-rectangle cross-section (superellipse-ish).
        scales: dict(size, depth, z=(z0,z1), th=(t0,t1), width=0.13) — scored scale arcs pressed into the skin."""
        super().__init__()
        z = np.asarray(z, float)
        L = len(z)

        def arr(a):
            return np.broadcast_to(np.asarray(a, float), (L,)).copy()

        self.z0, self.z1 = float(z[0]), float(z[-1])
        self.Z = np.linspace(self.z0, self.z1, n)
        self.tab = {}
        for k, a in (("w", w), ("ht", ht), ("hb", ht if hb is None else hb), ("cy", cy), ("cx", cx)):
            self.tab[k] = PchipInterpolator(z, arr(a))(self.Z)
        for k in ("w", "ht", "hb"):
            self.tab[k] = np.maximum(self.tab[k], 1e-3)
        dZ = self.Z[1] - self.Z[0]
        slope = np.zeros(n)
        for k in self.tab:
            slope = np.maximum(slope, np.abs(np.gradient(self.tab[k], dZ)))
        self.tab["L"] = np.sqrt(1 + np.minimum(slope, 8.0) ** 2)
        self.sq = squarish
        self.scales = scales

    def at(self, z, key):
        return np.interp(z, self.Z, self.tab[key])

    def sdf(self, P):
        z = P[:, 2]
        zc = np.clip(z, self.z0, self.z1)
        w, ht, hb = self.at(zc, "w"), self.at(zc, "ht"), self.at(zc, "hb")
        x = P[:, 0] - self.at(zc, "cx")
        y = P[:, 1] - self.at(zc, "cy")
        h = np.where(y > 0, ht, hb)
        if self.sq:
            # squash toward a superellipse by measuring with a p-norm
            p = 2.0 + self.sq * 4.0
            ax, ay = np.abs(x) / w, np.abs(y) / h
            k0 = (ax ** p + ay ** p) ** (1 / p)
            d2 = (k0 - 1.0) * np.minimum(w, h)
        else:
            k0 = np.sqrt((x / w) ** 2 + (y / h) ** 2)
            k1 = np.sqrt((x / (w * w)) ** 2 + (y / (h * h)) ** 2)
            d2 = k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        d2 = d2 / self.at(zc, "L")
        dz = np.abs(z - zc)
        d = np.where(dz > 0, np.sqrt(np.maximum(d2, 0) ** 2 + dz ** 2), d2)
        if self.scales:
            d = d + self._scale_groove(P, zc, x, y, w, h)
        return d

    def _scale_groove(self, P, z, x, y, w, h):
        s = self.scales
        size, depth = s["size"], s["depth"]
        z0, z1 = s.get("z", (self.z0, self.z1))
        t0, t1 = s.get("th", (0.15, 2.9))
        th = np.arctan2(x / w, y / h)  # 0 dorsal, +-pi ventral, +pi/2 at +x flank
        ath = np.abs(th)
        r = 0.5 * (w + h)
        u = z
        v = ath * r
        row = np.floor(v / size)
        u2 = u + (row % 2) * size * 0.5
        lu = (u2 / size - np.floor(u2 / size)) * size
        lv = (v / size - row - 0.5) * size
        R = size * 0.78
        dist = np.abs(np.hypot(lu - size, lv) - R)
        g = depth * np.exp(-(dist / (size * s.get("width", 0.13))) ** 2) * (lu < size)
        fade = np.clip((z - z0) / (size * 1.5), 0, 1) * np.clip((z1 - z) / (size * 1.5), 0, 1)
        fade = fade * np.clip((ath - t0) / 0.25, 0, 1) * np.clip((t1 - ath) / 0.25, 0, 1)
        return g * fade

    def area(self):
        """Approximate surface area (Ramanujan ellipse perimeters integrated along z)."""
        w = self.tab["w"]
        h = 0.5 * (self.tab["ht"] + self.tab["hb"])
        hh = ((w - h) / (w + h)) ** 2
        per = np.pi * (w + h) * (1 + 3 * hh / (10 + np.sqrt(4 - 3 * hh)))
        dz = self.Z[1] - self.Z[0]
        return float(np.sum(per * np.sqrt(1 + (self.tab["L"] ** 2 - 1) * 0.5)) * dz)

    def scale_prim(self, thresh=0.45):
        """Negative along the scored scale arcs (paint them a shade darker so they read up close)."""
        def f(P):
            z = np.clip(P[:, 2], self.z0, self.z1)
            w, ht, hb = self.at(z, "w"), self.at(z, "ht"), self.at(z, "hb")
            x = P[:, 0] - self.at(z, "cx")
            y = P[:, 1] - self.at(z, "cy")
            h = np.where(y > 0, ht, hb)
            g = self._scale_groove(P, z, x, y, w, h) / self.scales["depth"]
            return (thresh - g) * 0.01
        return Func(f, (-9, -9, -9), (9, 9, 9))

    def bounds(self):
        cx, cy = self.tab["cx"], self.tab["cy"]
        w, ht, hb = self.tab["w"], self.tab["ht"], self.tab["hb"]
        lo = np.array([np.min(cx - w), np.min(cy - hb), self.z0])
        hi = np.array([np.max(cx + w), np.max(cy + ht), self.z1])
        return lo - 0.002, hi + 0.002

    # placement helpers ------------------------------------------------------------------------------------------
    def surf(self, z, th, off=0.0):
        """Surface point at z, angle th (0 = top/dorsal, pi/2 = +x flank, pi = belly), pushed `off` along the normal."""
        w, ht, hb = self.at(z, "w"), self.at(z, "ht"), self.at(z, "hb")
        c, s = np.cos(th), np.sin(th)
        h = ht if c > 0 else hb
        p = np.array([self.at(z, "cx") + s * w, self.at(z, "cy") + c * h, z])
        n = _n([s / w, c / h, 0.0])
        return p + n * off

    def normal(self, z, th):
        w, ht, hb = self.at(z, "w"), self.at(z, "ht"), self.at(z, "hb")
        c, s = np.cos(th), np.sin(th)
        h = ht if c > 0 else hb
        return _n([s / w, c / h, 0.0])

    def top(self, z, off=0.0):
        return self.surf(z, 0.0, off)

    def bottom(self, z, off=0.0):
        return self.surf(z, np.pi, off)

    def line(self, zs, th, off=0.0):
        """Polyline of surface points (for scored grooves / lateral lines)."""
        ths = np.broadcast_to(np.asarray(th, float), (len(zs),))
        return np.array([self.surf(z, t, off) for z, t in zip(zs, ths)])


# --------------------------------------------------------------------------------------------------------------
# 2D helpers


def poly_sdf(p, V):
    """Signed distance from points p (N,2) to closed polygon V (M,2); negative inside."""
    d = np.sum((p - V[0]) ** 2, axis=1)
    s = np.ones(len(p))
    M = len(V)
    for i in range(M):
        j = i - 1
        e = V[j] - V[i]
        w = p - V[i]
        b = w - np.outer(np.clip((w @ e) / max(e @ e, 1e-12), 0, 1), e)
        d = np.minimum(d, np.sum(b * b, axis=1))
        c1 = p[:, 1] >= V[i, 1]
        c2 = p[:, 1] < V[j, 1]
        c3 = e[0] * w[:, 1] > e[1] * w[:, 0]
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


def seg_dist2(p, A, B):
    """Distance from points p (N,2) to the nearest of segments A[i]->B[i] (K,2)."""
    d = np.full(len(p), 1e9)
    for a, b in zip(A, B):
        e = b - a
        w = p - a
        t = np.clip((w @ e) / max(e @ e, 1e-12), 0, 1)
        q = w - np.outer(t, e)
        d = np.minimum(d, np.sqrt(np.sum(q * q, axis=1)))
    return d


def smooth_curve(pts, n=5):
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts
    out, _ = catmull(pts, np.zeros(len(pts)), n)
    return out


# --------------------------------------------------------------------------------------------------------------
# Fin: a thin sheet of pressed clay. Base line root_a->root_b (bury it in the body), outline through `tips`
# (ordered from the root_a side to the root_b side), scalloped between ray tips, rays raised as ribs.


class Fin(Prim):
    def __init__(self, root_a, root_b, tips, normal, thick=0.004, edge=0.0016, scallop=0.22, ribs=0.0008,
                 rib_w=None, wave=(0.0, 0.05), ray_from=None, smooth=4, nrays=None):
        """normal: fin plane normal. thick: half-thickness at the root, edge: half-thickness at the rim.
        ribs: extra half-thickness along each ray. wave: (amplitude, wavelength) ripple of the sheet.
        ray_from: optional 3D point all rays fan out from (pectoral/caudal fans); default = spread along the root.
        nrays: number of rays (default: one per tip; extra rays are interpolated along the outline)."""
        super().__init__()
        self.o = np.asarray(root_a, float)
        n = _n(normal)
        e1 = np.asarray(root_b, float) - self.o
        e1 = _n(e1 - n * (e1 @ n))
        e2 = np.cross(n, e1)
        self.n, self.e1, self.e2 = n, e1, e2
        to2 = lambda q: np.array([(np.asarray(q, float) - self.o) @ e1, (np.asarray(q, float) - self.o) @ e2])
        ra, rb = to2(root_a), to2(root_b)
        T = np.array([to2(t) for t in tips])
        if len(T) > 1 and np.linalg.norm(T[0] - ra) > np.linalg.norm(T[0] - rb):
            T = T[::-1]  # order tips from the root_a side
        # make the tips lie on the +e2 side
        if np.mean(T[:, 1]) < 0:
            self.e2 = -self.e2
            e2 = self.e2
            T[:, 1] *= -1
            ra[1] *= -1
            rb[1] *= -1
        # outline with scallops between tips
        chain = [ra]
        for i, t in enumerate(T):
            chain.append(t)
            if i < len(T) - 1:
                m = 0.5 * (t + T[i + 1])
                # pull toward the fin's root centre
                rc = 0.5 * (ra + rb)
                dirc = rc - m
                gap = np.linalg.norm(T[i + 1] - t)
                chain.append(m + _n(np.append(dirc, 0))[:2] * gap * scallop)
        chain.append(rb)
        chain = np.array(chain)
        edge_curve = smooth_curve(chain[1:-1], smooth) if len(chain) > 3 else chain[1:-1]
        self.poly = np.vstack([ra, edge_curve, rb])
        # rays
        K = nrays or len(T)
        if K == len(T):
            RT = T
        else:
            # resample tips along the edge curve
            seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(edge_curve, axis=0), axis=1))]
            ss = np.linspace(seg[-1] * 0.03, seg[-1] * 0.97, K)
            RT = np.column_stack([np.interp(ss, seg, edge_curve[:, 0]), np.interp(ss, seg, edge_curve[:, 1])])
        if ray_from is not None:
            RA = np.tile(to2(ray_from) * np.array([1, 1 if np.mean(T[:, 1]) >= 0 else -1]), (K, 1))
        else:
            f = np.linspace(0.08, 0.92, K)
            RA = ra[None] * (1 - f[:, None]) + rb[None] * f[:, None]
        self.RA = RA + (RT - RA) * 0.06
        self.RT = RT - (RT - RA) * 0.03
        self.thick, self.edge, self.ribs = thick, edge, ribs
        self.rib_w = rib_w if rib_w is not None else max(edge * 1.1, 0.0012)
        self.wave = wave
        self.root_mid = 0.5 * (ra + rb)
        self.reach = max(np.max(np.linalg.norm(self.poly - self.root_mid, axis=1)), 1e-3)
        pts3 = np.array([self.o + q[0] * e1 + q[1] * e2 for q in self.poly])
        pad = thick + ribs + abs(wave[0]) + 0.004
        self._lo, self._hi = pts3.min(0) - pad, pts3.max(0) + pad

    def _local(self, P):
        q = P - self.o
        return np.column_stack([q @ self.e1, q @ self.e2]), q @ self.n

    def _thick(self, p2):
        root_d = np.abs(p2[:, 1] - 0.0) if False else np.linalg.norm(p2 - self.root_mid, axis=1)
        s = np.clip(root_d / self.reach, 0, 1)
        t = self.thick * (1 - s) + self.edge * s
        if self.ribs:
            rd = seg_dist2(p2, self.RA, self.RT)
            t = t + self.ribs * np.exp(-(rd / self.rib_w) ** 2) * (0.4 + 0.6 * (1 - s))
        return t

    def sdf(self, P):
        p2, c = self._local(P)
        amp, wl = self.wave
        if amp:
            c = c - amp * np.sin(p2[:, 0] / wl * 2 * np.pi) * np.clip(np.linalg.norm(p2 - self.root_mid, axis=1) / self.reach, 0, 1)
        ds = poly_sdf(p2, self.poly)
        t = self._thick(p2)
        rr = self.edge * 0.6
        wx = ds + rr
        wy = np.abs(c) - np.maximum(t - rr, 2e-4)
        return np.minimum(np.maximum(wx, wy), 0) + np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wy, 0) ** 2) - rr

    def bounds(self):
        return self._lo, self._hi

    def rays(self, width=None):
        """A prim that is negative along the rays (paint darker/lighter ray lines)."""
        wdt = width or self.rib_w * 0.7

        def f(P):
            p2, c = self._local(P)
            return np.maximum(seg_dist2(p2, self.RA, self.RT) - wdt, self._offplane(p2, c))
        return Func(f, self._lo, self._hi)

    def rim(self, width):
        """Negative within `width` of the fin's outer edge (paint a dark/pale fin margin)."""
        def f(P):
            p2, c = self._local(P)
            ds = poly_sdf(p2, self.poly)
            rootish = np.linalg.norm(p2 - self.root_mid, axis=1) / self.reach
            return np.maximum(np.where(rootish > 0.45, -ds - width, 1.0), self._offplane(p2, c))
        return Func(f, self._lo, self._hi)

    def zone(self, s0, s1=1.01):
        """Negative where the normalised distance from the fin root is within [s0, s1]."""
        def f(P):
            p2, c = self._local(P)
            s = np.linalg.norm(p2 - self.root_mid, axis=1) / self.reach
            return np.maximum(np.maximum(s0 - s, s - s1) * self.reach, self._offplane(p2, c))
        return Func(f, self._lo, self._hi)

    def _offplane(self, p2, c):
        """Positive away from this fin's sheet (so paints on one fin don't leak onto others)."""
        amp, wl = self.wave
        if amp:
            c = c - amp * np.sin(p2[:, 0] / wl * 2 * np.pi) * np.clip(np.linalg.norm(p2 - self.root_mid, axis=1) / self.reach, 0, 1)
        slab = np.abs(c) - (self.thick + self.ribs + 0.0015)
        return np.maximum(slab, poly_sdf(p2, self.poly) - 0.002)


def fin_paint(piece, fin, color=None, ray_color=None, rim_color=None, rim_w=0.004, ray_w=None, gloss=None):
    if color is not None:
        piece.paint(fin, color, gloss=gloss, feather=0.002)
    if ray_color is not None:
        piece.paint(fin.rays(ray_w), ray_color, feather=0.0012)
    if rim_color is not None:
        piece.paint(fin.rim(rim_w), rim_color, feather=0.002)


# --------------------------------------------------------------------------------------------------------------
# eyes


def fish_eye(m: Model, c, r, out, iris="#e3b64c", ring=None, pupil_frac=0.6, side="R", res=None, merge="eyes",
             toe=0.25, up=0.05, pupil_shape=(1.0, 1.0), gloss=G_EYE, name=None, catch=True):
    """A big glossy fish eye: iris ball + domed black pupil + white catch-light bead. `out` = outward direction of the
    eye (e.g. (1,0,0) for the right flank); toe swings the gaze forward (+z), up tilts it up."""
    c = np.asarray(c, float)
    d = _n(np.asarray(out, float) + np.array([0, up, toe]))
    res = res or max(0.0018, min(0.004, r * 0.12))
    nm = name or f"eye_{side}"
    ball = m.piece(nm, color=iris, gloss=gloss - 30, lumps=r * 0.008, mottle=0.03, res=res, merge=merge, ao=False, decimate=360)
    ball.add(Sphere(c, r))
    if ring is not None:
        ball.paint(Sphere(c + d * r * 0.55, r * 0.78), ring, feather=r * 0.12)
    pr = r * pupil_frac
    pc = c + d * (r - pr * 0.42)
    pu = m.piece(nm + "_pupil", color=CP["pupil"], gloss=gloss, lumps=0.0, mottle=0.0, res=res, merge=merge, ao=False, decimate=300)
    pu.add(Ellipsoid(pc, (pr * pupil_shape[0], pr * pupil_shape[1], pr * 0.5), rot=look_rot(d) @ euler((90, 0, 0))))
    if catch:
        upv = np.array([0, 1.0, 0])
        sidev = _n(np.cross(upv, d))
        hl = pc + d * pr * 0.4 + upv * pr * 0.38 + sidev * pr * 0.28 * (1 if side == "R" else -1)
        pu.add(Sphere(hl, pr * 0.22), k=pr * 0.04, color="#ffffff", gloss=255)
        pu.add(Sphere(pc + d * pr * 0.42 - upv * pr * 0.35 - sidev * pr * 0.25 * (1 if side == "R" else -1), pr * 0.09),
               k=pr * 0.02, color="#f4f4f4", gloss=255)
    return d


def eye_socket(body: Piece, c, r, out, rim=0.2, rim_color=None, k=None):
    """Seat an eye in the body: a recess plus a pressed rim of body clay (the eyelid ring)."""
    d = _n(out)
    body.sub(Sphere(np.asarray(c), r * 1.03), k=k or r * 0.15)
    body.add(Torus(np.asarray(c) + d * r * 0.25, r * 1.02, r * rim, rot=look_rot(d)), k=k or r * 0.2, color=rim_color)


# --------------------------------------------------------------------------------------------------------------
# pattern prims (for paint())


def spots_prim(centres, radii):
    C = np.asarray(centres, float)
    R = np.broadcast_to(np.asarray(radii, float), (len(C),))
    lo, hi = C.min(0) - R.max(), C.max(0) + R.max()

    def f(P):
        d = np.full(len(P), 1e9)
        for c, r in zip(C, R):
            d = np.minimum(d, np.linalg.norm(P - c, axis=1) - r)
        return d
    return Func(f, lo, hi)


def blotch_prim(freq=20.0, thresh=0.1, seed=1, region=None, octaves=3, stretch=(1, 1, 1)):
    """Negative where fbm noise exceeds `thresh` (mottled patches); optionally limited to `region` (a prim)."""
    st = np.asarray(stretch, float)

    def f(P):
        v = thresh - fbm(P * freq * st, octaves, seed)
        if region is not None:
            v = np.maximum(v, region(P))
        return v * 0.05
    return Func(f, (-9, -9, -9), (9, 9, 9))


def func_prim(f):
    return Func(f, (-9, -9, -9), (9, 9, 9))


def above_prim(loft: Loft, frac=0.0, wobble=0.0, freq=14.0, seed=3, zrange=None):
    """Negative above the line cy(z) + frac*ht (countershading: dark back). frac<0 reaches down the flank."""
    def f(P):
        z = np.clip(P[:, 2], loft.z0, loft.z1)
        lim = loft.at(z, "cy") + frac * np.where(frac >= 0, loft.at(z, "ht"), loft.at(z, "hb"))
        if wobble:
            lim = lim + wobble * fbm(P * freq, 2, seed)
        v = lim - P[:, 1]
        if zrange is not None:
            v = np.maximum(v, np.maximum(zrange[0] - P[:, 2], P[:, 2] - zrange[1]))
        return v
    return Func(f, (-9, -9, -9), (9, 9, 9))


def below_prim(loft: Loft, frac=0.0, wobble=0.0, freq=14.0, seed=4):
    a = above_prim(loft, frac, wobble, freq, seed)
    return Func(lambda P: -a.f(P), (-9, -9, -9), (9, 9, 9))


def union_prim(*prims):
    def f(P):
        d = prims[0](P)
        for q in prims[1:]:
            d = np.minimum(d, q(P))
        return d
    return Func(f, (-9, -9, -9), (9, 9, 9))


def inter_prim(*prims):
    def f(P):
        d = prims[0](P)
        for q in prims[1:]:
            d = np.maximum(d, q(P))
        return d
    return Func(f, (-9, -9, -9), (9, 9, 9))


def not_prim(p):
    return Func(lambda P: -p(P), (-9, -9, -9), (9, 9, 9))


def surface_spots(loft: Loft, n, zr, thr, rad, seed=0, off=0.0, jitter=0.25):
    """Random spot centres on a loft surface between z range zr and angle range thr (both flanks)."""
    rng = np.random.default_rng(seed)
    C, R = [], []
    for _ in range(n):
        z = rng.uniform(*zr)
        th = rng.uniform(*thr) * rng.choice([-1, 1])
        C.append(loft.surf(z, th, off))
        R.append(rad * (1 + rng.uniform(-jitter, jitter)))
    return C, R


# --------------------------------------------------------------------------------------------------------------
# carving: scored lines, thumb dents, pressed beads


def score(piece: Piece, pts, r=0.0015, k=None, color=None, samples=4, gloss=None):
    """Score a groove along a polyline of surface points (tool line)."""
    piece.sub(Tube(np.asarray(pts, float), r, samples=samples if len(pts) >= 3 else None), k=k if k is not None else r * 0.6,
              color=color, gloss=gloss)


def ridge(piece: Piece, pts, r=0.0015, k=None, color=None, samples=4, gloss=None):
    """A rolled sausage of clay pressed along a polyline."""
    piece.add(Tube(np.asarray(pts, float), r, samples=samples if len(pts) >= 3 else None), k=k if k is not None else r * 0.8,
              color=color, gloss=gloss)


def arc_pts(c, u, v, r, a0, a1, n=8):
    """Points on a circular arc centred at c in the plane spanned by unit vectors u, v (angles in degrees)."""
    c, u, v = np.asarray(c, float), _n(u), _n(v)
    a = np.radians(np.linspace(a0, a1, n))
    return c[None] + r * (np.cos(a)[:, None] * u[None] + np.sin(a)[:, None] * v[None])


def thumbprints(piece: Piece, pts, r, depth_frac=0.25):
    """Shallow thumb presses at the given surface points."""
    for p in pts:
        piece.sub(Sphere(np.asarray(p, float), r), k=r * 0.6)


# --------------------------------------------------------------------------------------------------------------
# metallic clay: tarnish in crevices, bright worn edges (curvature from the piece's own SDF)


def cavity_prim(piece: Piece, r=0.006, thresh=0.12, convex=False, n_dirs=14, noise=0.0, seed=5):
    """Negative where the surface is concave (crevice) — or convex (edge) when convex=True. Measured as the mean SDF
    on a shell of radius r around the point (concave -> negative mean)."""
    rng = np.random.default_rng(seed)
    D = rng.normal(size=(n_dirs, 3))
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    D = np.vstack([D, -D])

    def f(P):
        s = np.zeros(len(P))
        for d in D:
            s += piece._eval_shape(P + d * r)
        s = s / len(D) - piece._eval_shape(P)
        s = s / r
        if noise:
            s = s + noise * fbm(P * 40.0, 2, seed)
        return (s + thresh) if not convex else (thresh - s)
    return Func(f, (-9, -9, -9), (9, 9, 9))


def metal(piece: Piece, dark=None, light=None, r=0.006, tarnish=0.06, wear=0.09, dark_gloss=90, light_gloss=220,
          noise=0.25, seed=5):
    """Paint tarnish into crevices and polish onto edges (call after the shape is complete)."""
    if dark is not None:
        piece.paint(cavity_prim(piece, r, tarnish, False, noise=noise, seed=seed), dark, gloss=dark_gloss, feather=0.06)
    if light is not None:
        piece.paint(cavity_prim(piece, r, wear, True, noise=noise, seed=seed + 1), light, gloss=light_gloss, feather=0.06)


def grime(piece: Piece, color, r=0.008, thresh=0.05, gloss=None, noise=0.3, seed=9, feather=0.08):
    """Dirt/algae settled into crevices."""
    piece.paint(cavity_prim(piece, r, thresh, False, noise=noise, seed=seed), color, gloss=gloss, feather=feather)


# --------------------------------------------------------------------------------------------------------------
# rope / strands


def rope(piece: Piece, pts, r, twist=True, samples=5, k=None, color=None, groove=None):
    """A rolled clay rope; optional spiral twist scored into it."""
    pts = np.asarray(pts, float)
    piece.add(Tube(pts, r, samples=samples if len(pts) >= 3 else None), k=k if k is not None else r * 0.5, color=color)
    if twist:
        dense = smooth_curve(pts, samples) if len(pts) >= 3 else np.linspace(pts[0], pts[-1], 12)
        seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))]
        length = seg[-1]
        step = r * 2.2
        ss = np.arange(step * 0.5, length, step)
        P = np.column_stack([np.interp(ss, seg, dense[:, i]) for i in range(3)])
        T = np.gradient(P, axis=0)
        for i, (p, t) in enumerate(zip(P, T)):
            t = _n(t)
            a = _n(np.cross(t, [0.31, 0.93, 0.17]))
            b = np.cross(t, a)
            ang = i * 1.1
            dvec = np.cos(ang) * a + np.sin(ang) * b
            q0 = p + dvec * r - t * r * 0.7
            q1 = p - dvec * r + t * r * 0.7
            piece.sub(Capsule(q0, q1, r * 0.16), k=r * 0.12, color=groove)


def coil(c, r0, r1, turns, y_step, n_per_turn=14, phase=0.0):
    """Points of a flat spiral / stacked coil (rope coils on deck)."""
    c = np.asarray(c, float)
    N = int(turns * n_per_turn)
    t = np.linspace(0, 1, N)
    a = phase + t * turns * 2 * np.pi
    rr = r0 + (r1 - r0) * t
    return np.column_stack([c[0] + np.cos(a) * rr, c[1] + t * y_step * turns, c[2] + np.sin(a) * rr])


def finish(m: Model, budget=12000, verbose=True):
    """Return m; budget is informational (build prints tri counts)."""
    m._budget = budget
    return m
