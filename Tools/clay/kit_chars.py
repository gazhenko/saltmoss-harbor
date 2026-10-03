"""
Shared helpers for the Saltmoss cast sculpts (walter, nell, marge, inkwell, shelby and the customers).

Built strictly on top of clay.py / kit.py (which stay untouched):
  * XPiece      - a Piece subclass with cheap procedural surface detail: tool-scored fur strokes, knit ribs,
                  colour patterns (stripes, tweed, spots). Detail is a tiny SDF displacement evaluated in one
                  vectorised pass, so hundreds of strokes cost about the same as one primitive.
  * Segs        - many short capsules in one primitive (KD-tree accelerated): stitching, whiskers, suckers, spots.
  * snap/onsurf - project guide points onto a piece's surface (place seams, buttons, lapels on curved clay).
  * face()      - eyes + brows + blush (+ replacement mouths) with sensible decimation budgets.
  * hats/scarves for customer accessory pieces.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from clay import *  # noqa: F401,F403
from clay import Piece, Prim, Capsule, Tube, Sphere, Ellipsoid, Torus, Box, Cylinder, HalfSpace, Func, gradient, catmull, euler, look_rot, rgb, shade, mix, vnoise, fbm
from kit import *  # noqa: F401,F403
from kit import eyes, brows, blush, mouths, PAL


# ----------------------------------------------------------------------------------------------------------------
# pieces with procedural detail


def _smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _gate(region, P, feather):
    if region is None:
        return 1.0
    return _smooth01(0.5 - region(P) / (2 * feather))


class XPiece(Piece):
    """Piece + displacement details (grooves/strokes) + procedural colour patterns."""

    def __init__(self, model, name, **kw):
        super().__init__(model, name, **kw)
        self.details = []   # (fn(P)->mask, depth, darken)
        self.patterns = []  # (fn(P)->weight 0..1, colour, gloss)

    def detail(self, fn, depth=0.002, darken=0.12):
        """Carve a procedural mask into the surface: mask 1 = groove of `depth`, negatives raise a lip."""
        self.details.append((fn, depth, darken))
        return self

    def pattern(self, fn, color, gloss=None):
        self.patterns.append((fn, rgb(color), gloss))
        return self

    def sdf(self, P):
        d = super().sdf(P)
        for fn, depth, _ in self.details:
            d = d + depth * fn(P)
        return d

    def attributes(self, P):
        col, gl, bone_d = super().attributes(P)
        for fn, c, g in self.patterns:
            w = np.clip(fn(P), 0, 1)
            col = col * (1 - w[:, None]) + c * w[:, None]
            if g is not None:
                gl = gl * (1 - w) + g * w
        for fn, _, dk in self.details:
            if dk:
                w = np.clip(fn(P), 0, 1)
                col = col * (1 - dk * w)[:, None]
        return col, gl, bone_d


def xpiece(m, name, **kw) -> XPiece:
    p = XPiece(m, name, **kw)
    m.pieces.append(p)
    return p


# ----------------------------------------------------------------------------------------------------------------
# detail masks


def _hash01(*ints, seed=0):
    h = np.int64(seed) * 2654435761 % (2 ** 32)
    acc = np.zeros_like(np.asarray(ints[0], dtype=np.int64)) + h
    for i, v in enumerate(ints):
        acc = acc ^ (np.asarray(v, dtype=np.int64) * [73856093, 19349663, 83492791, 2971215073][i % 4])
    acc = acc.astype(np.uint64) & np.uint64(0xFFFFFFFF)
    acc = (acc ^ (acc >> np.uint64(13))) * np.uint64(1274126177) & np.uint64(0xFFFFFFFF)
    acc = acc ^ (acc >> np.uint64(16))
    return (acc & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF)


def _cells(P, c, R, cells, flow, jitter, seed, cjit=0.35):
    """Cube-sphere cell frame for P: -> along, across (angle units, along = flow direction), hashes h1..h3."""
    q = (P - c) / R
    nq = np.linalg.norm(q, axis=1) + 1e-9
    p = q / nq[:, None]
    a = np.abs(p)
    f = np.argmax(a, axis=1)
    idx = np.arange(len(p))
    sgn = np.sign(p[idx, f])
    au, av = (f + 1) % 3, (f + 2) % 3
    mx = a[idx, f]
    u = p[idx, au] / mx
    v = p[idx, av] / mx
    iu = np.clip(np.floor((u + 1) * 0.5 * cells), 0, cells - 1)
    iv = np.clip(np.floor((v + 1) * 0.5 * cells), 0, cells - 1)
    face = (f * 2 + (sgn > 0)).astype(np.int64)
    h1 = _hash01(face, iu.astype(np.int64), iv.astype(np.int64), seed=seed)
    h2 = _hash01(face, iu.astype(np.int64), iv.astype(np.int64), seed=seed + 17)
    h3 = _hash01(face, iu.astype(np.int64), iv.astype(np.int64), seed=seed + 31)
    uc = (iu + 0.5 + (h2 - 0.5) * cjit) / cells * 2 - 1
    vc = (iv + 0.5 + (h3 - 0.5) * cjit) / cells * 2 - 1
    s = np.zeros_like(p)
    s[idx, f] = sgn
    s[idx, au] = uc
    s[idx, av] = vc
    s /= np.linalg.norm(s, axis=1, keepdims=True)
    F = flow(P) if callable(flow) else np.broadcast_to(np.asarray(flow, float), P.shape)
    F = F / R
    t = F - np.einsum("ij,ij->i", F, s)[:, None] * s
    tn = np.linalg.norm(t, axis=1)
    alt = np.cross(s, np.array([0.0, 0.0, 1.0]))
    alt_bad = np.linalg.norm(alt, axis=1) < 0.2
    alt[alt_bad] = np.cross(s[alt_bad], np.array([1.0, 0.0, 0.0]))
    alt /= np.linalg.norm(alt, axis=1, keepdims=True) + 1e-9
    t = np.where((tn > 1e-4)[:, None], t / (tn[:, None] + 1e-12), alt)
    ang = np.radians(jitter) * (h1 * 2 - 1)
    b0 = np.cross(s, t)
    tt = t * np.cos(ang)[:, None] + b0 * np.sin(ang)[:, None]
    bb = np.cross(s, tt)
    e = p - s
    return np.einsum("ij,ij->i", e, tt), np.einsum("ij,ij->i", e, bb), h1, h2, h3


def strokes(center, radii, cells=20, length=0.75, width=0.006, flow=(0, -1, 0), jitter=25.0, density=1.0,
            ridge=0.35, region=None, feather=0.02, seed=1):
    """Tool-scored fur/feather strokes over a roughly ellipsoidal form.

    Directions from `center` (scaled by `radii`) are mapped onto a cube-sphere; each of the cells x cells patches per
    cube face holds one short stroke aligned with `flow` (a vector or fn(P)->(N,3)) projected on the surface, rotated
    by +-jitter degrees. Returns mask(P): ~1 in the groove, small negative lip either side (pushed-up clay)."""
    c = np.asarray(center, float)
    R = np.asarray(radii, float)
    rbar = float(np.mean(R))
    cell_ang = (np.pi / 2) / cells
    hl0 = 0.5 * length * cell_ang

    def fn(P):
        al, ac, h1, h2, h3 = _cells(P, c, R, cells, flow, jitter, seed)
        hl = hl0 * (0.7 + 0.6 * h2)
        cl = np.clip(al, -hl, hl)
        dist = np.sqrt((al - cl) ** 2 + ac ** 2) * rbar
        taper = 1.0 - 0.55 * (cl / hl) ** 2
        tt_ = dist / (width * taper)
        mask = np.exp(-2.2 * tt_ * tt_) - ridge * np.exp(-5.0 * (tt_ - 1.45) ** 2)
        if density < 1.0:
            mask = mask * (h3 < density)
        return mask * _gate(region, P, feather)

    return fn


def feathers(center, radii, cells=14, width=0.005, flow=(0, -1, 0), jitter=10.0, size=0.62, region=None, feather=0.02,
             seed=1, step=0.6):
    """Overlapping feather scallops: a U-shaped scored edge per cell, opening up-stream of `flow`, plus a soft step
    (each feather sits a touch proud of the one below). Returns mask(P) (1 = groove)."""
    c = np.asarray(center, float)
    R = np.asarray(radii, float)
    rbar = float(np.mean(R))
    cell_ang = (np.pi / 2) / cells

    def fn(P):
        al, ac, h1, h2, h3 = _cells(P, c, R, cells, flow, jitter, seed, cjit=0.2)
        rho = size * cell_ang * (0.85 + 0.3 * h2)
        cy = -0.35 * rho
        rr = np.sqrt((al - cy) ** 2 + ac ** 2)
        d_arc = np.abs(rr - rho)
        # only the down-stream half of the circle (the feather tip)
        ex = np.sqrt((al - cy) ** 2 + (np.abs(ac) - rho) ** 2)
        d = np.where(al > cy, d_arc, ex) * rbar
        t = d / width
        groove = np.exp(-2.0 * t * t)
        inside = (rr < rho) & (al > cy)
        lift = -step * inside * np.clip((rho - rr) * rbar / (width * 2.0), 0, 1)
        return (groove + lift) * _gate(region, P, feather)

    return fn


def ribs(center, axis=(0, 1, 0), n=24, sharp=4.0, region=None, feather=0.01, phase=0.0):
    """Knit ribs / corduroy: n grooves around an axis through center. Returns mask(P) in 0..1."""
    c = np.asarray(center, float)
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    R = look_rot(a)
    x, z = R[:, 0], R[:, 2]

    def fn(P):
        q = P - c
        th = np.arctan2(q @ z, q @ x)
        m = (0.5 + 0.5 * np.cos(th * n + phase)) ** sharp
        return m * _gate(region, P, feather)

    return fn


def combed(center, axis=(0, 0, 1), n=60, sharp=2.5, wobble=0.25, wfreq=18.0, region=None, feather=0.01, seed=2,
           breakup=0.0):
    """Comb-tooth grooves radiating from an axis through `center` (e.g. a mustache combed out from under the nose,
    bristly brows). Angle is wobbled with noise so the lines meander like dragged clay; `breakup` (0..1) breaks the
    grooves into dashes."""
    c = np.asarray(center, float)
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    R = look_rot(a)
    x, z = R[:, 0], R[:, 2]

    def fn(P):
        q = P - c
        th = np.arctan2(q @ z, q @ x)
        th = th + wobble * (2 * np.pi / n) * vnoise(P * wfreq, seed)
        m = (0.5 + 0.5 * np.cos(th * n)) ** sharp
        if breakup > 0:
            m = m * np.clip((vnoise(P * wfreq * 3.0, seed + 5) + 1 - breakup * 1.4) * 3, 0, 1)
        return m * _gate(region, P, feather)

    return fn


def bands(normal=(0, 1, 0), period=0.05, width=0.5, offset=0.0, soft=0.12, region=None, feather=0.01):
    """Parallel stripes: weight 1 inside the band fraction `width` of each `period` along `normal`."""
    nrm = np.asarray(normal, float)
    nrm = nrm / np.linalg.norm(nrm)

    def fn(P):
        t = ((P @ nrm + offset) / period) % 1.0
        # band is t in [0, width): soft edges
        lo = _smooth01(t / soft)
        hi = _smooth01((width - t) / soft)
        w = np.minimum(lo, hi)
        return w * _gate(region, P, feather)

    return fn


def tweed(scale=0.012, region=None, feather=0.01, seed=5, axis_u=(1, 0, 0), axis_v=(0, 1, 0)):
    """Herringbone-ish tweed weight (0..1) for a darker yarn colour."""
    U = np.asarray(axis_u, float)
    V = np.asarray(axis_v, float)

    def fn(P):
        u = (P @ U) / scale
        v = (P @ V) / scale
        col = np.floor(u)
        fu = u - col
        zig = np.where(col % 2 == 0, fu, 1 - fu)
        t = (v + zig * 0.9) % 1.0
        w = _smooth01((t - 0.45) / 0.12) * _smooth01((0.95 - t) / 0.12)
        n = vnoise(P * 140.0, seed)
        w = np.clip(w * 0.75 + (n > 0.55) * 0.5, 0, 1)
        return w * _gate(region, P, feather)

    return fn


def specks(freq=90.0, thresh=0.6, region=None, feather=0.01, seed=3):
    """Random flecks (e.g. seal spots, speckled feathers) 0..1."""

    def fn(P):
        n = fbm(P * freq, 2, seed)
        return _smooth01((n - thresh) / 0.08) * _gate(region, P, feather)

    return fn


# ----------------------------------------------------------------------------------------------------------------
# many-capsule primitive


class Segs(Prim):
    """Union of many short round-cones a_i->b_i (radii ra_i, rb_i). KD-tree over midpoints keeps it fast."""

    def __init__(self, A, B, ra, rb=None, k=4):
        super().__init__()
        self.A = np.atleast_2d(np.asarray(A, float))
        self.B = np.atleast_2d(np.asarray(B, float))
        n = len(self.A)
        self.ra = np.broadcast_to(np.asarray(ra, float), (n,)).copy()
        self.rb = self.ra.copy() if rb is None else np.broadcast_to(np.asarray(rb, float), (n,)).copy()
        self.mid = (self.A + self.B) / 2
        half = np.linalg.norm(self.B - self.A, axis=1) / 2
        self.reach = float(np.max(half + np.maximum(self.ra, self.rb)))
        self.tree = cKDTree(self.mid)
        self.k = min(k, n)

    def sdf(self, P):
        out = np.empty(len(P))
        bound = self.reach + 0.06
        n = len(self.A)
        Ap = np.vstack([self.A, [[1e6, 1e6, 1e6]]])
        Bp = np.vstack([self.B, [[1e6, 1e6, 1e6]]])
        rap = np.append(self.ra, 0.0)
        rbp = np.append(self.rb, 0.0)
        for i0 in range(0, len(P), 400_000):
            Q = P[i0:i0 + 400_000]
            dist, idx = self.tree.query(Q, k=self.k, distance_upper_bound=bound, workers=-1)
            if self.k == 1:
                idx = idx[:, None]
            best = np.full(len(Q), np.inf)
            far = idx[:, 0] >= n
            if far.any():  # conservative distance for points out of reach (keeps the field usable deep inside)
                dfar, _ = self.tree.query(Q[far], k=1, workers=-1)
                best[far] = dfar - self.reach
            for j in range(self.k):
                ii = idx[:, j]
                ok = ii < n
                if not ok.any():
                    continue
                q = Q[ok]
                a, b = Ap[ii[ok]], Bp[ii[ok]]
                ba = b - a
                l2 = np.einsum("ij,ij->i", ba, ba) + 1e-12
                t = np.clip(np.einsum("ij,ij->i", q - a, ba) / l2, 0, 1)
                d = np.linalg.norm(q - (a + ba * t[:, None]), axis=1) - (rap[ii[ok]] * (1 - t) + rbp[ii[ok]] * t)
                best[ok] = np.minimum(best[ok], d)
            out[i0:i0 + 400_000] = best
        return out

    def bounds(self):
        r = max(self.ra.max(), self.rb.max())
        lo = np.minimum(self.A.min(0), self.B.min(0)) - r
        hi = np.maximum(self.A.max(0), self.B.max(0)) + r
        return lo, hi


class Poly2D(Prim):
    """A 2D polygon (points in the plane spanned by frame axes u,v) extruded infinitely along the frame's w axis.
    frame: 3x3 matrix whose columns are u, v, w (default: XY plane, extruded along Z). `round` grows it."""

    def __init__(self, pts, frame=None, origin=(0, 0, 0), round=0.0, depth=(-1.0, 1.0)):
        super().__init__()
        self.V = np.asarray(pts, float)
        self.F = np.eye(3) if frame is None else np.asarray(frame, float)
        self.o = np.asarray(origin, float)
        self.rd = round
        self.depth = depth

    def sdf(self, P):
        q = (P - self.o) @ self.F
        x, y = q[:, 0], q[:, 1]
        d2 = self._d2(x, y)
        w0, w1 = self.depth
        dz = np.abs(q[:, 2] - (w0 + w1) / 2) - (w1 - w0) / 2
        return np.maximum(d2, dz) - self.rd

    def _d2(self, x, y):
        V = self.V
        d = np.full(len(x), np.inf)
        s = np.ones(len(x))
        n = len(V)
        for i in range(n):
            a, b = V[i], V[(i + 1) % n]
            e = b - a
            wx, wy = x - a[0], y - a[1]
            t = np.clip((wx * e[0] + wy * e[1]) / (e @ e), 0, 1)
            dx, dy = wx - e[0] * t, wy - e[1] * t
            d = np.minimum(d, dx * dx + dy * dy)
            c1 = y >= a[1]
            c2 = y < b[1]
            c3 = e[0] * wy > e[1] * wx
            flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
            s = np.where(flip, -s, s)
        return s * np.sqrt(d)

    def bounds(self):
        lo2, hi2 = self.V.min(0) - self.rd, self.V.max(0) + self.rd
        corners = []
        for x in (lo2[0], hi2[0]):
            for y in (lo2[1], hi2[1]):
                for z in self.depth:
                    corners.append(self.o + self.F @ np.array([x, y, z]))
        corners = np.array(corners)
        return corners.min(0), corners.max(0)


class Shell(Prim):
    """A sheet of clay conforming to a base surface: base offsets in [t0, t1] (metres, outward), clipped by `region`
    (any Prim; e.g. a Poly2D outline). Gives garments, lapels, straps, aprons and flaps their rolled thickness."""

    def __init__(self, base, t0, t1, region, bounds_from=None, round=0.0):
        super().__init__()
        self.base, self.t0, self.t1, self.region, self.rd = base, t0, t1, region, round
        self.bf = bounds_from

    def sdf(self, P):
        r = self.region(P)
        k = max(self.rd, 1e-4)
        out = r.astype(float).copy()          # far from the region: its distance is a safe lower bound
        near = r < k + 0.025
        if near.any():
            Q = P[near]
            bb = self.base(Q)
            mid, half = (self.t0 + self.t1) / 2, (self.t1 - self.t0) / 2
            sh = np.abs(bb - mid) - half
            # rounded intersection so the cut edges are soft (rolled plasticine)
            out[near] = smax_np(sh, r[near], k)
        return out

    def bounds(self):
        src = self.bf if self.bf is not None else self.region
        lo, hi = src.bounds()
        return lo - self.t1, hi + self.t1


def smax_np(a, b, k):
    h = np.clip(0.5 - 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h + k * h * (1 - h)


def smin_np(a, b, k):
    h = np.clip(0.5 + 0.5 * (a - b) / k, 0.0, 1.0)
    return a * (1 - h) + b * h - k * h * (1 - h)


def union_sdf(prims, k):
    """Cheap smooth union of primitives as a callable (a base surface for Shell)."""

    def f(P):
        d = prims[0](P)
        for pr in prims[1:]:
            d = smin_np(d, pr(P), k)
        return d

    return f


# ----------------------------------------------------------------------------------------------------------------
# surface helpers


def snap(f, pts, iters=10, offset=0.0):
    """Project points onto the zero set of f (an sdf callable, e.g. piece._eval_shape or piece.sdf)."""
    pts = np.atleast_2d(np.array(pts, float))
    for _ in range(iters):
        d = f(pts) - offset
        g = gradient(f, pts)
        pts = pts - g * d[:, None]
    return pts


def surf_frame(n, up=(0, 1, 0)):
    """Rotation with local z = outward normal n, local x = right (tangent), local y = up (tangent)."""
    z = np.asarray(n, float)
    z = z / np.linalg.norm(z)
    x = np.cross(np.asarray(up, float), z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def onsurf(f, pts, offset=0.0):
    """-> (points on surface, outward normals)."""
    p = snap(f, pts, offset=offset)
    return p, gradient(f, p)


def plane_ring(f, origin, normal, n=32, offset=0.0, a0=0.0, a1=2 * np.pi, ref=(0, 0, 1), rmax=1.0):
    """Points where the plane (origin, normal) cuts the surface of f (offset outward), swept by angle a0..a1 around
    `origin` (which must be inside the shape). Angle 0 points along `ref` projected into the plane."""
    o = np.asarray(origin, float)
    nn = np.asarray(normal, float)
    nn = nn / np.linalg.norm(nn)
    u = np.asarray(ref, float) - nn * (np.asarray(ref, float) @ nn)
    u /= np.linalg.norm(u)
    v = np.cross(nn, u)
    out = []
    for a in np.linspace(a0, a1, n):
        d = u * np.cos(a) + v * np.sin(a)
        lo, hi = 0.0, rmax
        for _ in range(40):
            mid = (lo + hi) / 2
            if f((o + d * mid)[None])[0] - offset < 0:
                lo = mid
            else:
                hi = mid
        out.append(o + d * lo)
    return np.array(out)


def curve(pts, n=40):
    """Catmull-Rom resample of guide points -> (n,3) evenly-ish spaced."""
    pts = np.asarray(pts, float)
    P, _ = catmull(pts, np.zeros(len(pts)), max(2, n // (len(pts) - 1)))
    # arc-length resample
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, i]) for i in range(3)], axis=1)


def surface_curve(f, guide, n=40, offset=0.0):
    return snap(f, curve(guide, n), offset=offset)


def stitches(path, n, length=0.012, r=0.0028, across=False, normal_f=None):
    """Short dashes along a (surface) path: along-path dashes, or `across` the path (needs normal_f sdf)."""
    P = curve(path, max(n * 4, 8))
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    ts = np.linspace(s[-1] / (2 * n), s[-1] - s[-1] / (2 * n), n)
    C = np.stack([np.interp(ts, s, P[:, i]) for i in range(3)], axis=1)
    T = np.stack([np.interp(ts + 1e-3, s, P[:, i]) - np.interp(ts - 1e-3, s, P[:, i]) for i in range(3)], axis=1)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    if across and normal_f is not None:
        N = gradient(normal_f, C)
        T = np.cross(N, T)
        T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    return Segs(C - T * length / 2, C + T * length / 2, r)


def budget(m, targets):
    """Per-piece triangle targets: {exact name or prefix*: tris}."""
    for p in m.pieces:
        for k, v in targets.items():
            if (k.endswith("*") and p.name.startswith(k[:-1])) or p.name == k:
                p.decimate = v


class Scaled(Prim):
    """Uniformly scale a primitive about a centre (exact for SDFs)."""

    def __init__(self, prim, c, s):
        super().__init__()
        self.p, self.c, self.s = prim, np.asarray(c, float), float(s)

    def sdf(self, P):
        return self.s * self.p(self.c + (P - self.c) / self.s)

    def bounds(self):
        lo, hi = self.p.bounds()
        return self.c + (lo - self.c) * self.s, self.c + (hi - self.c) * self.s


class Squash(Prim):
    """Non-uniform scale of a primitive about c by per-axis factors s (in the frame R, default world). Approximate
    SDF (scaled by the smallest factor) - fine for gentle flattening of tails, paws, bills."""

    def __init__(self, prim, c, s, R=None):
        super().__init__()
        self.p, self.c, self.s = prim, np.asarray(c, float), np.asarray(s, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)

    def sdf(self, P):
        q = ((P - self.c) @ self.R) / self.s
        return self.p(self.c + q @ self.R.T) * float(self.s.min())

    def bounds(self):
        lo, hi = self.p.bounds()
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        q = ((corners - self.c) @ self.R) * self.s
        w = self.c + q @ self.R.T
        return w.min(0), w.max(0)


def scale_pieces(m, names, centres, s):
    """Scale every op of the named pieces about centres[name] (e.g. puff replacement lids out over big pupils)."""
    for p in m.pieces:
        if p.name in names:
            c = centres[p.name]
            for op in p.ops:
                op.prim = Scaled(op.prim, c, s)


def pupil_dir(look, toe_in, sx):
    """Gaze direction of one eye exactly as kit.eyes computes it (sx = -1 left, +1 right): toed IN by toe_in deg."""
    d = np.asarray(look, float)
    d = d / np.linalg.norm(d)
    ang = np.radians(toe_in) * sx * -1
    return np.array([d[0] * np.cos(ang) + d[2] * np.sin(ang), d[1], -d[0] * np.sin(ang) + d[2] * np.cos(ang)])


def pupil_pivots(m, eye_c, eye_r, look=(0, 0, 1), toe_in=12.0, pupil_frac=0.55):
    """Move the pupil_L/R bones from the eye centre to the pupil's own centre on the eyeball surface.

    Rigid pieces scale about their bone's rest position, and the runtime scales pupils 0.78-1.1: about the eye centre
    that buries the whole pupil inside the eyeball at 0.78 (blank 'surprised' eyes) and floats it off at 1.1. Pivoting
    at the pupil itself makes the scale a dilation in place; the +-11 mm look offset is unchanged."""
    ex, ey, ez = eye_c
    pr = eye_r * pupil_frac
    for sx, s in ((-1, "L"), (1, "R")):
        c = np.array([sx * ex, ey, ez])
        pc = c + pupil_dir(look, toe_in, sx) * (eye_r - pr * 0.45)
        i = m.bone_index(f"pupil_{s}")
        name, parent, _ = m.bones[i]
        m.bones[i] = (name, parent, pc)


def face(m, eye_c, eye_r, lid, brow_col, look=(0, 0, 1), pupil_frac=0.55, ring=None, toe_in=12.0, brow_kw=None,
         blush_c=None, blush_r=None, blush_n=(0.6, 0, 0.8), mouth=None, eye_budget=1400, sclera=PAL["eye_white"],
         blush_on=None, lid_scale=None):
    """Standard expressive face set. mouth = dict(c=..., w=..., lip=..., normal=..., bone=...) or None.
    blush_on: an sdf callable (e.g. head._eval_shape) to press the blush discs onto the cheek surface.
    Replacement lids are puffed out so the pupil's catch-light bead never pokes through a closed lid."""
    eyes(m, eye_c, eye_r, lid_color=lid, look=look, pupil_frac=pupil_frac, ring=ring, toe_in=toe_in, sclera=sclera)
    pupil_pivots(m, eye_c, eye_r, look=look, toe_in=toe_in, pupil_frac=pupil_frac)
    s = lid_scale or max(1.0, (1.0 + 0.21 * pupil_frac) / 1.1 + 0.025)
    ex, ey, ez = eye_c
    # happy eyes = a closed, lid-coloured bulge with the smiling crease on it (reads the same whether or not the
    # game hides the eyeball/pupil underneath)
    for p in m.pieces:
        if p.name.startswith("eyehappy_"):
            sx = -1.0 if p.name.endswith("_L") else 1.0
            c = np.array([sx * ex, ey, ez])
            p.add(Ellipsoid(c + np.array([0, -eye_r * 0.04, 0]), (eye_r * 1.08, eye_r * 1.04, eye_r * 1.08)), k=eye_r * 0.06, color=lid, gloss=40)
    cen = {}
    for sx, side in ((-1, "L"), (1, "R")):
        for nm in ("lidhalf", "lidclosed", "eyehappy"):
            cen[f"{nm}_{side}"] = np.array([sx * ex, ey, ez])
    scale_pieces(m, set(cen), cen, s)
    if brow_kw is not False:
        brows(m, eye_c, eye_r, color=brow_col, **(brow_kw or {}))
    if blush_c is not None:
        bc = np.asarray(blush_c, float)
        bn = blush_n
        if blush_on is not None:
            p, n = onsurf(blush_on, [bc])
            bc = p[0] + n[0] * 0.002
            bn = n[0] * np.array([1, 1, 1])
        blush(m, bc, blush_r or eye_r * 0.7, normal=bn)
    if mouth:
        mouths(m, **mouth)
    budget(m, {"eyeball_*": eye_budget, "lidhalf_*": eye_budget, "lidclosed_*": eye_budget, "eyehappy_*": 900,
               "pupil_*": 900, "brow_*": 900, "blush_*": 400, "mouth_*": 1200})


# ----------------------------------------------------------------------------------------------------------------
# small parts


def button(p, c, n, r, color, holes=4, gloss=170, bone=None, rim=True, hole_col=None):
    """A pressed-on button facing normal n at surface point c (added to piece p)."""
    n = np.asarray(n, float)
    n = n / np.linalg.norm(n)
    R = look_rot(n)
    p.add(Cylinder(c + n * r * 0.15, r, r * 0.28, rot=R, round=r * 0.22), k=0.003, color=color, gloss=gloss, bone=bone)
    if rim:
        p.add(Torus(c + n * r * 0.42, r * 0.82, r * 0.14, rot=R), k=0.002, color=color, gloss=gloss, bone=bone)
    x, z = R[:, 0], R[:, 2]
    if holes:
        for i in range(holes):
            a = np.pi / 4 + i * 2 * np.pi / holes
            hc = c + n * r * 0.45 + (x * np.cos(a) + z * np.sin(a)) * r * 0.32
            p.sub(Capsule(hc - n * r * 0.3, hc + n * r * 0.6, r * 0.11), k=0.001, color=hole_col if hole_col is not None else shade(color, 0.5))


# ----------------------------------------------------------------------------------------------------------------
# accessories (customers): hidden, rigid to `hat` (hats) or skinned to neck/chest (scarves)


def acc_beanie(m, name, top, r, color, cuff=None, pom=None, tilt=(0, 0, 0), bone="hat", stripe=None, res=0.006):
    """Knitted beanie sitting on a head whose crown centre is `top` (point on head top), head radius ~r."""
    top = np.asarray(top, float)
    Rt = euler(tilt)
    c = top + Rt @ np.array([0, -r * 0.55, 0])
    up = Rt @ np.array([0, 1, 0])
    p = xpiece(m, name, color=color, rigid=bone, hidden=True, lumps=0.0018, dents=6, dent_size=r * 0.15, dent_depth=0.0015, res=res)
    p.add(Ellipsoid(c + up * r * 0.25, (r * 1.04, r * 0.95, r * 1.04), rot=Rt))
    p.inter(HalfSpace(c - up * r * 0.05, -up), k=r * 0.08)
    p.sub(Ellipsoid(c - up * r * 0.1, (r * 0.96, r * 0.95, r * 0.96), rot=Rt), k=r * 0.05)
    # folded cuff band
    p.add(Torus(c + up * r * 0.07, r * 0.98, r * 0.17, rot=Rt), k=r * 0.05, color=cuff or shade(color, 0.92))
    p.detail(ribs(c, up, n=34, sharp=3, region=Ellipsoid(c + up * r * 0.6, (r * 1.4, r * 1.2, r * 1.4), rot=Rt)), depth=r * 0.035, darken=0.1)
    if stripe is not None:
        p.pattern(bands(up, period=r * 0.5, width=0.4, offset=-(c @ up) + r * 0.05, soft=0.08,
                        region=HalfSpace(c + up * r * 0.25, up)), stripe)
    if pom is not None:
        pc = c + up * r * 1.23
        p.add(Sphere(pc, r * 0.32).lumpy(r * 0.04, 1.0 / (r * 0.12), 3), k=r * 0.08, color=pom)
    return p


def acc_flatcap(m, name, top, r, color, tilt=(0, 0, 0), bone="hat", yarn=None, fwd=(0, 0, 1), res=0.006):
    """Tweed flat cap: flat crown sloping forward to a short stiff peak."""
    top = np.asarray(top, float)
    Rt = euler(tilt)
    up = Rt @ np.array([0, 1, 0])
    f = Rt @ np.asarray(fwd, float)
    c = top - up * r * 0.12
    p = xpiece(m, name, color=color, rigid=bone, hidden=True, lumps=0.0015, dents=5, dent_size=r * 0.15, dent_depth=0.0012, res=res)
    p.add(Ellipsoid(c + f * r * 0.12, (r * 1.08, r * 0.36, r * 1.18), rot=Rt @ euler((-8, 0, 0))))
    p.add(Ellipsoid(c + f * r * 0.62 - up * r * 0.02, (r * 0.92, r * 0.22, r * 0.62), rot=Rt @ euler((10, 0, 0))), k=r * 0.2)
    p.sub(Ellipsoid(c - up * r * 0.33, (r * 1.0, r * 0.42, r * 1.05), rot=Rt), k=r * 0.06)
    # peak
    p.add(Ellipsoid(c + f * r * 1.05 - up * r * 0.14, (r * 0.78, r * 0.06, r * 0.4), rot=Rt @ euler((14, 0, 0))), k=r * 0.08)
    p.add(Sphere(c + up * r * 0.32 + f * r * 0.15, r * 0.09), k=r * 0.05)  # button on top
    p.sub(Tube([c + f * r * 0.75 - up * r * 0.05 + Rt @ np.array([-r * 0.85, 0, 0]), c + f * r * 0.92 + up * r * 0.0,
                c + f * r * 0.75 - up * r * 0.05 + Rt @ np.array([r * 0.85, 0, 0])], r * 0.025, samples=6), k=0.002)
    p.pattern(tweed(r * 0.12), yarn or shade(color, 0.72))
    return p


def acc_bowler(m, name, top, r, color, tilt=(0, 0, 0), bone="hat", band=None, res=0.006):
    top = np.asarray(top, float)
    Rt = euler(tilt)
    up = Rt @ np.array([0, 1, 0])
    c = top - up * r * 0.25
    p = xpiece(m, name, color=color, rigid=bone, hidden=True, gloss=90, lumps=0.0012, dents=4, dent_size=r * 0.15, dent_depth=0.0012, res=res)
    p.add(Ellipsoid(c + up * r * 0.45, (r * 0.86, r * 0.78, r * 0.9), rot=Rt))
    p.inter(HalfSpace(c - up * r * 0.0, -up), k=r * 0.05)
    p.add(Ellipsoid(c, (r * 1.28, r * 0.07, r * 1.35), rot=Rt), k=r * 0.1)
    p.add(Torus(c + up * r * 0.02, r * 1.22, r * 0.07, rot=Rt @ euler((0, 0, 0))), k=r * 0.05)  # rolled brim edge
    p.add(Torus(c + up * r * 0.14, r * 0.87, r * 0.085, rot=Rt), k=r * 0.03, color=band or shade(color, 0.6))
    p.sub(Ellipsoid(c - up * r * 0.2, (r * 0.8, r * 0.3, r * 0.84), rot=Rt), k=r * 0.04)
    return p


def acc_souwester(m, name, top, r, color, tilt=(0, 0, 0), bone="hat", res=0.006):
    top = np.asarray(top, float)
    Rt = euler(tilt)
    up = Rt @ np.array([0, 1, 0])
    c = top - up * r * 0.3
    p = xpiece(m, name, color=color, rigid=bone, hidden=True, gloss=150, lumps=0.002, dents=6, dent_size=r * 0.2, dent_depth=0.002, res=res)
    p.add(Ellipsoid(c + up * r * 0.35, (r * 0.92, r * 0.62, r * 0.92), rot=Rt))
    p.add(Ellipsoid(c - up * r * 0.08 + Rt @ np.array([0, 0, -r * 0.4]), (r * 1.4, r * 0.15, r * 1.75), rot=Rt @ euler((-22, 0, 0))), k=r * 0.25)
    p.add(Ellipsoid(c + up * r * 0.04 + Rt @ np.array([0, 0, r * 0.45]), (r * 1.25, r * 0.12, r * 0.8), rot=Rt @ euler((-14, 0, 0))), k=r * 0.22)
    p.sub(Ellipsoid(c - up * r * 0.38, (r * 0.95, r * 0.6, r * 0.95), rot=Rt), k=r * 0.06)
    p.add(Torus(c + up * r * 0.14, r * 0.9, r * 0.07, rot=Rt), k=r * 0.05)
    return p


def acc_scarf(m, name, neck_c, R, thick, color, stripe=None, bone_ring="neck", bone_tail="chest", tail_side=1.0,
              drop=0.18, fwd=(0, 0, 1), res=0.006, tilt=10.0):
    """Knitted scarf ring + one dangling end (skinned, hidden)."""
    c = np.asarray(neck_c, float)
    p = xpiece(m, name, color=color, bone=bone_ring, hidden=True, lumps=0.002, dents=5, dent_size=thick * 0.5, dent_depth=0.0015, res=res)
    p.add(Torus(c, R, thick, rot=(tilt, 0, 0)), bone=bone_ring)
    s = tail_side
    k0 = c + np.array([s * R * 0.55, -thick * 0.3, R * 0.85])
    p.add(Ellipsoid(k0, (thick * 1.25, thick * 1.1, thick * 0.85)), k=thick * 0.5, bone=bone_ring)
    tail = [k0, k0 + np.array([s * thick * 0.6, -drop * 0.35, thick * 0.9]), k0 + np.array([s * thick * 0.9, -drop * 0.7, thick * 1.0]),
            k0 + np.array([s * thick * 0.9, -drop, thick * 0.8])]
    p.add(Tube(tail, [thick * 0.85, thick * 0.8, thick * 0.78, thick * 0.75], samples=6), k=thick * 0.6, bone=bone_tail)
    p.detail(ribs(c, (0, 1, 0), n=40, sharp=3, region=Sphere(c, R + thick * 1.2)), depth=thick * 0.07, darken=0.1)
    if stripe is not None:
        p.pattern(bands((0, 1, 0), period=drop * 0.33, width=0.35, offset=-(c[1] - drop), soft=0.08,
                        region=HalfSpace(c - np.array([0, thick * 1.4, 0]), (0, 1, 0))), stripe)
    # fringe
    fe = tail[-1]
    for i in range(5):
        x = (i - 2) * thick * 0.32
        p.add(Capsule(fe + np.array([x, -thick * 0.2, 0]), fe + np.array([x * 1.2, -thick * 1.4, 0.0]), thick * 0.14, thick * 0.1), k=thick * 0.15, bone=bone_tail)
    return p


def acc_bowtie(m, name, c, w, color, dots=None, bone="chest", rigid=True, normal=(0, 0, 1), res=0.004):
    c = np.asarray(c, float)
    n = np.asarray(normal, float)
    n /= np.linalg.norm(n)
    Rn = look_rot(n) @ euler((90, 0, 0))   # local z -> n, local x -> right
    X = Rn[:, 0]
    Y = Rn[:, 1]
    kw = dict(rigid=bone) if rigid else dict(bone=bone)
    p = xpiece(m, name, color=color, hidden=True, gloss=60, lumps=0.0008, res=res, **kw)
    for s in (-1, 1):
        p.add(Ellipsoid(c + X * s * w * 0.5, (w * 0.5, w * 0.36, w * 0.16), rot=Rn @ euler((0, 0, s * 8))), k=w * 0.08)
        p.sub(Capsule(c + X * s * w * 0.55 + Y * w * 0.12 + n * w * 0.16, c + X * s * w * 0.9 + Y * w * 0.2 + n * w * 0.12, w * 0.03), k=0.002)
        p.sub(Capsule(c + X * s * w * 0.55 - Y * w * 0.12 + n * w * 0.16, c + X * s * w * 0.9 - Y * w * 0.2 + n * w * 0.12, w * 0.03), k=0.002)
    p.add(Ellipsoid(c + n * w * 0.08, (w * 0.18, w * 0.24, w * 0.16), rot=Rn), k=w * 0.05)
    if dots is not None:
        p.pattern(specks(1.0 / (w * 0.18), 0.35), dots)
    return p


def bushy_brows(m, eye_c, eye_r, color, scale=1.3, lift=1.75, fwd=0.25, droop=1.0, res=0.0042, seed=3):
    """Shaggy clay brows (three overlapping tufts, combed), rigid to brow_L/R. droop>0 lowers the outer ends (kind),
    droop<0 lifts them (stern/surprised)."""
    ex, ey, ez = eye_c
    r = eye_r * scale
    for sx, side in ((-1, "L"), (1, "R")):
        b = xpiece(m, f"brow_{side}", color=color, gloss=35, rigid=f"brow_{side}", res=res, lumps=0.0012 * scale, lump_freq=30, mottle=0.05)
        base = np.array([sx * (ex + eye_r * 0.15), ey + eye_r * lift, ez + eye_r * fwd])
        dr = droop
        b.add(Tube([base + (-sx * r * 1.15, r * 0.1 * dr, r * 0.1), base + (0, r * 0.25, r * 0.2), base + (sx * r * 1.3, -r * 0.3 * dr, -r * 0.4)],
                   [r * 0.36, r * 0.46, r * 0.3], samples=6))
        b.add(Tube([base + (-sx * r * 0.7, r * 0.45, -r * 0.05), base + (sx * r * 0.5, r * 0.5, -r * 0.05), base + (sx * r * 1.7, r * (0.5 - 0.4 * dr), -r * 0.7)],
                   [r * 0.3, r * 0.32, r * 0.12], samples=6), k=r * 0.15)
        b.add(Tube([base + (sx * r * 0.3, -r * 0.05, r * 0.1), base + (sx * r * 1.2, -r * 0.35 * dr, -r * 0.25), base + (sx * r * 1.8, -r * 0.75 * dr, -r * 0.75)],
                   [r * 0.27, r * 0.24, r * 0.1], samples=6), k=r * 0.15)
        b.detail(combed(base + (-sx * r * 1.6, -r * 1.6, 0), (0, 0, 1), n=70, sharp=2.5, wobble=0.4, wfreq=60 / scale, seed=seed if sx > 0 else seed + 1),
                 depth=0.0024 * scale / 1.3, darken=0.2)


# ----------------------------------------------------------------------------------------------------------------
# crustaceans (shelby, cust_crab): stalked eyes, jointed legs, claws; flat 2D shapes (stickers)


def stalk_face_bones(m, eye_c, eye_r, stalk_base, parent="head", brow_up=1.3, mouth_c=None, hat_c=None):
    """Eyes on stalks: stalk_L/R (pivot at the stalk base) > eye_L/R > pupil_L/R, brow_L/R under the stalk.
    eye_c / stalk_base are the RIGHT side (x > 0)."""
    ex, ey, ez = eye_c
    bx, by, bz = stalk_base
    for sx, s in ((-1, "L"), (1, "R")):
        m.bone(f"stalk_{s}", parent, (sx * bx, by, bz))
        m.bone(f"eye_{s}", f"stalk_{s}", (sx * ex, ey, ez))
        m.bone(f"pupil_{s}", f"eye_{s}", (sx * ex, ey, ez))
        m.bone(f"brow_{s}", f"stalk_{s}", (sx * ex, ey + eye_r * brow_up, ez + eye_r * 0.2))
    if mouth_c is not None:
        m.bone("mouth", parent, mouth_c)
    if hat_c is not None:
        m.bone("hat", parent, hat_c)


def jointed(p, pts, radii, bones=None, color=None, band=None, band_w=0.35, tip=None, tip_len=0.25, bristles=0, bristle_col=None,
            seed=0, k=0.006, pinch=0.82):
    """A jointed crustacean limb: one capsule per segment (pts[i] -> pts[i+1]), pinched at the joints with a pale band,
    an optional dark tip on the last segment and a few short bristles. bones[i] skins segment i (None = piece default)."""
    pts = [np.asarray(q, float) for q in pts]
    rng = np.random.default_rng(seed)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ra, rb = radii[i], radii[i + 1]
        bone = bones[i] if bones else None
        mid = a + (b - a) * 0.5
        # each segment slightly barrel-shaped: fatter in the middle, pinched at the joints
        p.add(Tube([a, mid + np.cross(b - a, (0, 1, 0)) * 0.02, b], [ra * pinch, (ra + rb) * 0.5, rb * pinch], samples=5), k=k, bone=bone,
              color=color)
        if band is not None and i > 0:
            d = (b - a) / (np.linalg.norm(b - a) + 1e-9)
            p.paint(Capsule(a - d * ra * band_w, a + d * ra * band_w, ra * 1.3), band, feather=ra * 0.25)
        if bristles:
            d = (b - a) / (np.linalg.norm(b - a) + 1e-9)
            side = np.cross(d, (0, 1, 0))
            if np.linalg.norm(side) < 1e-3:
                side = np.array([1.0, 0, 0])
            side /= np.linalg.norm(side)
            up = np.cross(side, d)
            A, B = [], []
            for j in range(bristles):
                t = rng.uniform(0.15, 0.85)
                ang = rng.uniform(-1.3, 1.3)
                nrm = up * np.cos(ang) + side * np.sin(ang)
                r = ra * (1 - t) + rb * t
                q = a + (b - a) * t + nrm * r * 0.8
                A.append(q)
                B.append(q + nrm * r * rng.uniform(0.25, 0.5) + d * r * 0.45)
            p.add(Segs(np.array(A), np.array(B), r * 0.1, r * 0.045), k=0.001, color=bristle_col, bone=bone)
    if tip is not None:
        a, b = pts[-2], pts[-1]
        d = (b - a) / (np.linalg.norm(b - a) + 1e-9)
        L = np.linalg.norm(b - a)
        p.paint(Capsule(b - d * L * tip_len, b + d * radii[-1] * 3, radii[-1] * 3.0), tip, feather=radii[-1] * 0.8)


def claw(p, base, fwd, up, length, height, thick, color, tip_col, bone_hand=None, bone_finger=None, gape=12.0, teeth=5,
         tubercles=0, tub_col=None, seed=0, finger_col=None):
    """A crab claw (propodus 'palm' + fixed finger + movable finger) on piece p.
    base: wrist joint, fwd: palm/finger direction, up: the movable finger's side. Returns the finger pivot point."""
    f = np.asarray(fwd, float)
    f /= np.linalg.norm(f)
    u = np.asarray(up, float)
    u = u - f * (u @ f)
    u /= np.linalg.norm(u)
    s = np.cross(u, f)
    R = np.stack([s, u, f], axis=1)          # local x = side (thickness), y = up, z = forward
    base = np.asarray(base, float)

    def L(x, y, z):
        return base + R @ np.array([x, y, z])

    palm_c = L(0, 0, length * 0.33)
    p.add(Ellipsoid(palm_c, (thick * 0.5, height * 0.5, length * 0.36), rot=R), k=thick * 0.25, bone=bone_hand)
    p.add(Ellipsoid(L(0, -height * 0.05, length * 0.06), (thick * 0.36, height * 0.34, length * 0.14), rot=R), k=thick * 0.3, bone=bone_hand)
    # fixed finger (lower), tapering and curving up at the tip
    pivot = L(0, height * 0.18, length * 0.62)
    fc = finger_col if finger_col is not None else color
    ff = [L(0, -height * 0.12, length * 0.55), L(0, -height * 0.16, length * 0.78), L(0, -height * 0.08, length * 0.97), L(0, height * 0.02, length * 1.06)]
    p.add(Tube(ff, [height * 0.22, height * 0.17, height * 0.1, height * 0.04], samples=5), k=thick * 0.2, color=fc, bone=bone_hand)
    # movable finger (dactyl), hinged at the top of the palm, opened by `gape`
    g = np.radians(gape)
    Rg = R @ np.array([[1, 0, 0], [0, np.cos(g), np.sin(g)], [0, -np.sin(g), np.cos(g)]])

    def G(y, z):
        return pivot + Rg @ np.array([0, y, z])
    df = [G(0, 0), G(height * 0.02, length * 0.18), G(-height * 0.02, length * 0.36), G(-height * 0.14, length * 0.47)]
    p.add(Tube(df, [height * 0.19, height * 0.15, height * 0.09, height * 0.035], samples=5), k=thick * 0.15, color=fc, bone=bone_finger or bone_hand)
    # rounded teeth along both cutting edges
    for i in range(teeth):
        t = (i + 0.5) / teeth
        q = L(0, -height * 0.02 + 0.03 * height * np.sin(t * 9), length * (0.6 + 0.36 * t))
        p.add(Sphere(q, height * 0.045 * (1.2 - t * 0.5)), k=height * 0.02, color="#f1e2c6", bone=bone_hand)
        q2 = G(-height * 0.13, length * (0.06 + 0.33 * t))
        p.add(Sphere(q2, height * 0.04 * (1.2 - t * 0.5)), k=height * 0.02, color="#f1e2c6", bone=bone_finger or bone_hand)
    # dark tips
    p.paint(Sphere(ff[-1], height * 0.12), tip_col, feather=height * 0.05)
    p.paint(Sphere(df[-1], height * 0.12), tip_col, feather=height * 0.05)
    # tubercles: little raised bumps over the palm
    if tubercles:
        rng = np.random.default_rng(seed)
        A, rr = [], []
        for _ in range(tubercles):
            th = rng.uniform(0, 2 * np.pi)
            z = rng.uniform(-0.6, 0.75)
            q = palm_c + R @ np.array([np.cos(th) * thick * 0.5, np.sin(th) * height * 0.5, z * length * 0.36]) * np.sqrt(max(0.0, 1 - z * z) + 0.08)
            A.append(q)
            rr.append(height * rng.uniform(0.03, 0.055))
        A = np.array(A)
        p.add(Segs(A, A, np.array(rr)), k=height * 0.02, color=tub_col, bone=bone_hand)
    return pivot


def star_pts(r, n=5, inner=0.45, rot=90.0):
    return [(np.cos(np.radians(rot + i * 180.0 / n)) * (r if i % 2 == 0 else r * inner),
             np.sin(np.radians(rot + i * 180.0 / n)) * (r if i % 2 == 0 else r * inner)) for i in range(2 * n)]


def heart_pts(r, n=28):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    return list(zip(x * r / 17.0, (y + 2.5) * r / 17.0))


def circle_pts(r, n=24, rx=1.0, ry=1.0):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return list(zip(np.cos(t) * r * rx, np.sin(t) * r * ry))


def flower_pts(r, petals=5, n=50):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rr = r * (0.62 + 0.38 * np.abs(np.cos(t * petals / 2)))
    return list(zip(np.cos(t) * rr, np.sin(t) * rr))


def bolt_pts(r):
    return [(0.15 * r, r), (-0.55 * r, -0.05 * r), (-0.05 * r, -0.05 * r), (-0.25 * r, -r), (0.6 * r, 0.2 * r), (0.08 * r, 0.2 * r)]


def sticker(m, name, base_f, at, shapes, rigid, spin=0.0, res=0.0022, proud=0.0018, border="#f7f3ea", border_w=0.004, merge="stickers"):
    """A paper sticker pressed onto a curved clay surface: a white backing sheet with a printed shape on top.
    base_f: sdf of the surface; at: a point near it; shapes: [(pts2d, colour, extra_proud)] in a tangent frame
    (x right, y up, z out). The first shape also defines the backing outline."""
    p0, n0 = onsurf(base_f, [at])
    p0, n0 = p0[0], n0[0]
    F = surf_frame(n0) @ euler((0, 0, spin))
    pc = xpiece(m, name, color=border, gloss=110, rigid=rigid, res=res, lumps=0.0, mottle=0.03, ao=False, merge=merge)
    outline = shapes[0][0]
    pc.add(Shell(base_f, -0.001, proud * 0.6, Poly2D(outline, frame=F, origin=p0, round=border_w, depth=(-0.03, 0.03)), round=0.0008))
    for pts, col, extra in shapes:
        pc.add(Shell(base_f, -0.001, proud + extra, Poly2D(pts, frame=F, origin=p0, depth=(-0.03, 0.03)), round=0.0006), k=0.0006, color=col, gloss=150)
    return pc, p0, n0, F


def neck_fit(f, c, normal=(0, 1, 0), n=24):
    """Measure a neck: (mean, max) distance from c to the surface of sdf f in the plane through c (scarf sizing)."""
    pts = plane_ring(f, np.asarray(c, float), normal, n)
    d = np.linalg.norm(pts - np.asarray(c, float), axis=1)
    return float(d.mean()), float(d.max())
