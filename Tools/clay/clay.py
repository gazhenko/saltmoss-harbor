"""
Clay sculpting toolkit: signed-distance primitives, smooth unions, paint, hand-made imperfection, skinning,
marching-cubes meshing and the .claymesh writer (see Docs/DESIGN.md §5.2).

Coordinates are Unity's: x right, y up, z forward, metres. Characters face +Z with feet at the origin.

    from clay import *
    m = Model("pip")
    m.bone("root"); m.bone("hips", "root", (0, .3, 0)); ...
    body = m.piece("body", color="#22252b", bone="chest", lumps=.004)
    body.add(Ellipsoid((0, .42, 0), (.22, .28, .2)), bone="chest")
    body.paint(Ellipsoid((0, .38, .12), (.16, .22, .12)), "#f1ece0")
    m.save("Game/Assets/Saltmoss/Models/chars/pip.claymesh")
"""
from __future__ import annotations

import math
import os
import struct
import numpy as np
from skimage.measure import marching_cubes

try:
    import pyfqmr
except ImportError:  # decimation optional
    pyfqmr = None

# ----------------------------------------------------------------------------------------------------------------
# colour helpers


def rgb(c):
    """'#rrggbb' | (r,g,b) 0-255 | (r,g,b) 0-1 floats -> np.array float 0-1 (sRGB)."""
    if isinstance(c, str):
        c = c.lstrip("#")
        return np.array([int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    c = np.asarray(c, dtype=float)
    return c / 255.0 if c.max() > 1.0 else c


def shade(c, f):
    """Darken (f<1) or lighten (f>1) a colour."""
    c = rgb(c)
    return np.clip(c * f if f <= 1 else c + (1 - c) * (f - 1), 0, 1)


def mix(a, b, t):
    return rgb(a) * (1 - t) + rgb(b) * t


# ----------------------------------------------------------------------------------------------------------------
# noise (vectorised value noise, deterministic)

_M = np.uint64(0xFFFFFFFF)


def _hash(ix, iy, iz, seed):
    h = (ix.astype(np.int64) * 73856093) ^ (iy.astype(np.int64) * 19349663) ^ (iz.astype(np.int64) * 83492791) ^ (seed * 2654435761)
    h = h.astype(np.uint64) & _M
    h = (h ^ (h >> np.uint64(13))) * np.uint64(1274126177) & _M
    h = h ^ (h >> np.uint64(16))
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF) * 2.0 - 1.0


def vnoise(P, seed=0):
    """Smooth 3D value noise in [-1, 1]. P (N,3)."""
    P = np.asarray(P, dtype=np.float64)
    i = np.floor(P).astype(np.int64)
    f = P - i
    u = f * f * (3 - 2 * f)
    x, y, z = i[:, 0], i[:, 1], i[:, 2]
    out = 0.0
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                out = out + wx * wy * wz * _hash(x + dx, y + dy, z + dz, seed)
    return out


def fbm(P, octaves=3, seed=0, lac=2.03, gain=0.5):
    s, a, norm = 0.0, 1.0, 0.0
    Q = np.asarray(P, dtype=np.float64)
    for o in range(octaves):
        s = s + a * vnoise(Q, seed + o * 101)
        norm += a
        Q = Q * lac + 17.17
        a *= gain
    return s / norm


# ----------------------------------------------------------------------------------------------------------------
# rotation


def euler(deg):
    """Euler degrees (x, y, z) applied in Unity order (z, then x, then y) -> 3x3 local->world matrix."""
    if deg is None:
        return np.eye(3)
    if np.asarray(deg).shape == (3, 3):
        return np.asarray(deg, dtype=float)
    ax, ay, az = [math.radians(v) for v in deg]
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


def look_rot(direction, up=(0, 1, 0)):
    """Rotation whose local +Y points along `direction` (useful for capsules)."""
    d = np.asarray(direction, float)
    d = d / (np.linalg.norm(d) + 1e-12)
    u = np.asarray(up, float)
    if abs(np.dot(d, u)) > 0.95:
        u = np.array([1.0, 0, 0])
    x = np.cross(u, d)
    x /= np.linalg.norm(x)
    z = np.cross(x, d)
    return np.stack([x, d, z], axis=1)


def quat_from_matrix(R):
    R = np.asarray(R, float)
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x, y, z = (R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x, y, z = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x, y, z = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s
    return (x, y, z, w)


# ----------------------------------------------------------------------------------------------------------------
# primitives — each has sdf(P) and bounds() -> (lo, hi)


class Prim:
    def __init__(self):
        self.lumps = None  # optional per-primitive displacement (amp, freq)

    def sdf(self, P):
        raise NotImplementedError

    def bounds(self):
        raise NotImplementedError

    def __call__(self, P):
        d = self.sdf(P)
        if self.lumps:
            amp, freq, seed = self.lumps
            d = d + amp * fbm(P * freq, 2, seed)
        return d

    def lumpy(self, amp, freq=12.0, seed=7):
        self.lumps = (amp, freq, seed)
        return self


class _Xf(Prim):
    def __init__(self, c, rot):
        super().__init__()
        self.c = np.asarray(c, float)
        self.R = euler(rot)

    def local(self, P):
        return (P - self.c) @ self.R


class Sphere(Prim):
    def __init__(self, c, r):
        super().__init__()
        self.c, self.r = np.asarray(c, float), float(r)

    def sdf(self, P):
        return np.linalg.norm(P - self.c, axis=1) - self.r

    def bounds(self):
        return self.c - self.r, self.c + self.r


class Ellipsoid(_Xf):
    def __init__(self, c, radii, rot=None):
        super().__init__(c, rot)
        self.r = np.asarray(radii, float)

    def sdf(self, P):
        q = self.local(P)
        k0 = np.linalg.norm(q / self.r, axis=1)
        k1 = np.linalg.norm(q / (self.r * self.r), axis=1)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)

    def bounds(self):
        e = np.abs(self.R) @ self.r
        return self.c - e, self.c + e


class Capsule(Prim):
    """Round cone from a (radius ra) to b (radius rb)."""

    def __init__(self, a, b, ra, rb=None):
        super().__init__()
        self.a, self.b = np.asarray(a, float), np.asarray(b, float)
        self.ra, self.rb = float(ra), float(ra if rb is None else rb)

    def sdf(self, P):
        a, b, r1, r2 = self.a, self.b, self.ra, self.rb
        ba = b - a
        l2 = float(ba @ ba)
        if l2 < 1e-12:
            return np.linalg.norm(P - a, axis=1) - max(r1, r2)
        rr = r1 - r2
        a2 = l2 - rr * rr
        il2 = 1.0 / l2
        pa = P - a
        y = pa @ ba
        z = y - l2
        xv = pa * l2 - np.outer(y, ba)
        x2 = np.einsum("ij,ij->i", xv, xv)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d = np.empty(len(P))
        m1 = np.sign(z) * a2 * z2 > k
        m2 = np.sign(y) * a2 * y2 < k
        d[m1] = np.sqrt(x2[m1] + z2[m1]) * il2 - r2
        m2 &= ~m1
        d[m2] = np.sqrt(x2[m2] + y2[m2]) * il2 - r1
        m3 = ~(m1 | m2)
        d[m3] = (np.sqrt(x2[m3] * a2 * il2) + y[m3] * rr) * il2 - r1
        return d

    def bounds(self):
        r = max(self.ra, self.rb)
        return np.minimum(self.a, self.b) - r, np.maximum(self.a, self.b) + r


class Box(_Xf):
    """Rounded box: half extents `half`, corner radius `round`."""

    def __init__(self, c, half, rot=None, round=0.0):
        super().__init__(c, rot)
        self.h = np.asarray(half, float)
        self.rd = float(round)

    def sdf(self, P):
        q = np.abs(self.local(P)) - (self.h - self.rd)
        return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(axis=1), 0) - self.rd

    def bounds(self):
        e = np.abs(self.R) @ self.h
        return self.c - e, self.c + e


class Cylinder(_Xf):
    """Capped cylinder along local Y: radius r, half-height hh, edge rounding."""

    def __init__(self, c, r, hh, rot=None, round=0.0):
        super().__init__(c, rot)
        self.r, self.hh, self.rd = float(r), float(hh), float(round)

    def sdf(self, P):
        q = self.local(P)
        dx = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - (self.r - self.rd)
        dy = np.abs(q[:, 1]) - (self.hh - self.rd)
        return np.minimum(np.maximum(dx, dy), 0) + np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2) - self.rd

    def bounds(self):
        e = np.abs(self.R) @ np.array([self.r, self.hh, self.r])
        return self.c - e, self.c + e


class Torus(_Xf):
    """Torus in local XZ plane: major R, minor r."""

    def __init__(self, c, R, r, rot=None):
        super().__init__(c, rot)
        self.Rm, self.rm = float(R), float(r)

    def sdf(self, P):
        q = self.local(P)
        qx = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - self.Rm
        return np.sqrt(qx * qx + q[:, 1] ** 2) - self.rm

    def bounds(self):
        e = np.abs(self.R) @ np.array([self.Rm + self.rm, self.rm, self.Rm + self.rm])
        return self.c - e, self.c + e


class Tube(Prim):
    """A sausage of clay along a polyline/curve (Catmull-Rom smoothed); radii per control point."""

    def __init__(self, pts, radii, samples=None):
        super().__init__()
        pts = np.asarray(pts, float)
        radii = np.broadcast_to(np.asarray(radii, float), (len(pts),)).copy()
        if samples and len(pts) >= 3:
            pts, radii = catmull(pts, radii, samples)
        self.segs = [Capsule(pts[i], pts[i + 1], radii[i], radii[i + 1]) for i in range(len(pts) - 1)]

    def sdf(self, P):
        d = self.segs[0].sdf(P)
        for s in self.segs[1:]:
            d = np.minimum(d, s.sdf(P))
        return d

    def bounds(self):
        lo = np.min([s.bounds()[0] for s in self.segs], axis=0)
        hi = np.max([s.bounds()[1] for s in self.segs], axis=0)
        return lo, hi


def catmull(pts, radii, n):
    pts = np.asarray(pts, float)
    P = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    R = np.concatenate([[radii[0]], radii, [radii[-1]]])
    out, rad = [], []
    for i in range(1, len(P) - 2):
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            p = 0.5 * ((2 * P[i]) + (-P[i - 1] + P[i + 1]) * t + (2 * P[i - 1] - 5 * P[i] + 4 * P[i + 1] - P[i + 2]) * t2 + (-P[i - 1] + 3 * P[i] - 3 * P[i + 1] + P[i + 2]) * t3)
            out.append(p)
            rad.append(R[i] * (1 - t) + R[i + 1] * t)
    out.append(pts[-1])
    rad.append(radii[-1])
    return np.array(out), np.array(rad)


class HalfSpace(Prim):
    """Everything on the -normal side of a plane through c (use with sub/intersect to slice)."""

    def __init__(self, c, normal):
        super().__init__()
        self.c = np.asarray(c, float)
        n = np.asarray(normal, float)
        self.n = n / np.linalg.norm(n)

    def sdf(self, P):
        return (P - self.c) @ self.n

    def bounds(self):
        return self.c - 100, self.c + 100


class Func(Prim):
    """Arbitrary SDF: f(P)->d with explicit bounds."""

    def __init__(self, f, lo, hi):
        super().__init__()
        self.f, self.lo, self.hi = f, np.asarray(lo, float), np.asarray(hi, float)

    def sdf(self, P):
        return self.f(P)

    def bounds(self):
        return self.lo, self.hi


# ----------------------------------------------------------------------------------------------------------------
# a piece of clay


class Op:
    __slots__ = ("kind", "prim", "k", "color", "gloss", "bone", "feather")

    def __init__(self, kind, prim, k=0.0, color=None, gloss=None, bone=None, feather=0.004):
        self.kind, self.prim, self.k = kind, prim, k
        self.color = None if color is None else rgb(color)
        self.gloss, self.bone, self.feather = gloss, bone, feather


class Piece:
    def __init__(self, model, name, color="#bbbbbb", gloss=40, bone=None, rigid=None, mat=0, hidden=False,
                 lumps=0.0035, lump_freq=9.0, dents=0, dent_size=0.018, dent_depth=0.0035, mottle=0.06, seed=None,
                 res=None, decimate=None, smooth=0.0, ao=True, merge=None):
        self.model, self.name = model, name
        self.color, self.gloss = rgb(color), gloss
        self.bone = bone            # default bone for skinned add-ops
        self.rigid = rigid          # bone name for rigid pieces
        self.mat, self.hidden = mat, hidden
        self.lumps, self.lump_freq = lumps, lump_freq
        self.dents, self.dent_size, self.dent_depth = dents, dent_size, dent_depth
        self.mottle = mottle
        self.seed = seed if seed is not None else (abs(hash(model.name + name)) % 100000)
        self.res, self.decimate, self.smooth, self.ao = res, decimate, smooth, ao
        self.merge = merge          # output name: pieces sharing it are meshed separately, then concatenated
        self.ops: list[Op] = []
        self._dent_centres = None

    # building ------------------------------------------------------------------------------------------------
    def add(self, prim, k=0.02, color=None, gloss=None, bone=None):
        self.ops.append(Op("add", prim, k, color, gloss, bone or self.bone))
        return self

    def sub(self, prim, k=0.01, color=None, gloss=None):
        """Carve away; `color` paints the carved walls (e.g. a dark mouth)."""
        self.ops.append(Op("sub", prim, k, color, gloss))
        return self

    def inter(self, prim, k=0.0):
        self.ops.append(Op("inter", prim, k))
        return self

    def paint(self, prim, color, gloss=None, feather=0.004):
        """Recolour where `prim` < 0 without changing the shape (stripes, bellies, patches)."""
        self.ops.append(Op("paint", prim, 0.0, color, gloss, None, feather))
        return self

    def mirror(self, fn):
        """Call fn(sx, side) for both sides. Characters face +Z, so their right ('R') is +X and left ('L') is -X."""
        fn(-1.0, "L")
        fn(1.0, "R")
        return self

    # evaluation ----------------------------------------------------------------------------------------------
    def bounds(self):
        los, his = [], []
        for op in self.ops:
            if op.kind == "add":
                lo, hi = op.prim.bounds()
                los.append(lo)
                his.append(hi)
        lo, hi = np.min(los, axis=0), np.max(his, axis=0)
        pad = 0.02 + self.lumps * 3 + max([op.k for op in self.ops] + [0])
        return lo - pad, hi + pad

    def _dents_d(self, P):
        if not self.dents:
            return 0.0
        if self._dent_centres is None:
            rng = np.random.default_rng(self.seed + 3)
            lo, hi = self.bounds()
            C = rng.uniform(lo, hi, size=(self.dents * 6, 3))
            d = self._eval_shape(C)
            # keep candidates near the surface
            self._dent_centres = C[np.abs(d) < self.dent_size * 0.8][: self.dents]
            self._dent_sizes = rng.uniform(0.6, 1.3, len(self._dent_centres)) * self.dent_size
        out = np.zeros(len(P))
        for c, s in zip(self._dent_centres, self._dent_sizes):
            r2 = np.einsum("ij,ij->i", P - c, P - c) / (s * s)
            m = r2 < 4.0
            out[m] += self.dent_depth * np.exp(-r2[m] * 1.6)
        return out

    def _eval_shape(self, P):
        d = None
        for op in self.ops:
            if op.kind == "add":
                b = op.prim(P)
                d = b if d is None else smin(d, b, op.k)[0]
            elif op.kind == "sub":
                d = smax(d, -op.prim(P), op.k)
            elif op.kind == "inter":
                d = smax(d, op.prim(P), op.k)
        return d

    def sdf(self, P):
        d = self._eval_shape(P)
        if self.lumps:
            d = d + self.lumps * fbm(P * self.lump_freq, 3, self.seed)
        if self.dents:
            d = d + self._dents_d(P)
        return d

    def attributes(self, P):
        """Colour (N,3), gloss (N,), and per-bone raw distances {bone: (N,)} at points P."""
        n = len(P)
        col = np.tile(self.color, (n, 1))
        gl = np.full(n, float(self.gloss))
        d = None
        bone_d = {}
        for op in self.ops:
            if op.kind == "add":
                b = op.prim(P)
                if d is None:
                    d, h = b, np.zeros(n)
                    if op.color is not None:
                        col[:] = op.color
                    if op.gloss is not None:
                        gl[:] = op.gloss
                else:
                    d, h = smin(d, b, op.k)  # h=1 -> new primitive dominates
                    if op.color is not None:
                        col = col * (1 - h[:, None]) + op.color * h[:, None]
                    if op.gloss is not None:
                        gl = gl * (1 - h) + op.gloss * h
                if op.bone:
                    bone_d[op.bone] = np.minimum(bone_d[op.bone], b) if op.bone in bone_d else b
            elif op.kind == "sub":
                b = op.prim(P)
                if op.color is not None or op.gloss is not None:
                    w = np.clip(1.0 - np.maximum(-b, 0) / max(op.k * 1.5 + 0.004, 1e-4), 0, 1)
                    w = w * (np.abs(b) < op.k * 2 + 0.01)
                    if op.color is not None:
                        col = col * (1 - w[:, None]) + op.color * w[:, None]
                    if op.gloss is not None:
                        gl = gl * (1 - w) + op.gloss * w
                d = smax(d, -b, op.k)
            elif op.kind == "inter":
                d = smax(d, op.prim(P), op.k)
            elif op.kind == "paint":
                r = op.prim(P)
                w = np.clip(0.5 - r / (2 * op.feather), 0, 1)
                w = w * w * (3 - 2 * w)
                col = col * (1 - w[:, None]) + op.color * w[:, None]
                if op.gloss is not None:
                    gl = gl * (1 - w) + op.gloss * w
        return col, gl, bone_d


def smin(a, b, k):
    """Polynomial smooth min. Returns (d, h) where h is the weight of b."""
    if k <= 0:
        h = (b < a).astype(float)
        return np.minimum(a, b), h
    h = np.clip(0.5 + 0.5 * (a - b) / k, 0.0, 1.0)
    return a * (1 - h) + b * h - k * h * (1 - h), h


def smax(a, b, k):
    if k <= 0:
        return np.maximum(a, b)
    h = np.clip(0.5 - 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h + k * h * (1 - h)


# ----------------------------------------------------------------------------------------------------------------
# model


class Model:
    def __init__(self, name, res=0.012):
        self.name = name
        self.res = res
        self.bones: list[tuple[str, int, np.ndarray]] = []
        self.pieces: list[Piece] = []
        self.sockets: list[tuple[str, int, np.ndarray, tuple]] = []
        self.weight_softness = 0.03
        self.decimate_ratio = 0.3   # pieces above decimate_min tris are reduced to this fraction (QEM)
        self.decimate_min = 3000

    # rig
    def bone(self, name, parent=None, pos=(0, 0, 0)):
        pi = -1 if parent is None else self.bone_index(parent)
        self.bones.append((name, pi, np.asarray(pos, float)))
        return name

    def bone_index(self, name):
        for i, b in enumerate(self.bones):
            if b[0] == name:
                return i
        raise KeyError(f"bone {name} not defined in {self.name}")

    def bone_pos(self, name):
        return self.bones[self.bone_index(name)][2]

    def socket(self, name, bone=None, pos=(0, 0, 0), rot=None):
        bi = -1 if bone is None else self.bone_index(bone)
        self.sockets.append((name, bi, np.asarray(pos, float), quat_from_matrix(euler(rot))))

    def piece(self, name, **kw) -> Piece:
        p = Piece(self, name, **kw)
        self.pieces.append(p)
        return p

    # meshing
    def _mesh_piece(self, p: Piece):
        h = p.res or self.res
        lo, hi = p.bounds()
        n = np.ceil((hi - lo) / h).astype(int) + 1
        if np.prod(n) > 60_000_000:
            raise ValueError(f"{self.name}/{p.name}: grid {n} too large; raise res")
        xs, ys, zs = (lo[i] + np.arange(n[i]) * h for i in range(3))
        vol = np.empty((n[0], n[1], n[2]), dtype=np.float32)
        # evaluate in x-slabs to bound memory
        Y, Z = np.meshgrid(ys, zs, indexing="ij")
        yz = np.stack([Y.ravel(), Z.ravel()], axis=1)
        slab = max(1, int(4_000_000 // len(yz)))
        for i0 in range(0, n[0], slab):
            i1 = min(n[0], i0 + slab)
            X = np.repeat(xs[i0:i1], len(yz))
            P = np.column_stack([X, np.tile(yz, (i1 - i0, 1))])
            vol[i0:i1] = p.sdf(P).reshape(i1 - i0, n[1], n[2])
        if vol.min() > 0 or vol.max() < 0:
            raise ValueError(f"{self.name}/{p.name}: no surface")
        verts, faces, _, _ = marching_cubes(vol, level=0.0, spacing=(h, h, h))
        verts = verts + lo
        # skimage winding: cross(B-A, C-A) points outward, which is Unity's front face numerically
        target = p.decimate
        if target is None and len(faces) > self.decimate_min:
            target = max(self.decimate_min, int(len(faces) * self.decimate_ratio))
        if target and pyfqmr is not None and len(faces) > target:
            s = pyfqmr.Simplify()
            s.setMesh(verts.astype(np.float64), faces.astype(np.int32))
            s.simplify_mesh(target_count=int(target), aggressiveness=6, preserve_border=True, verbose=False)
            verts, faces, _ = s.getMesh()
            verts = project(p, verts, 3)
        return verts, faces

    def build(self):
        out = []
        for p in self.pieces:
            v, f = self._mesh_piece(p)
            out.append((p, v, f))
        visible = [p for p in self.pieces if not p.hidden]
        vb = {id(p): p.bounds() for p in visible}

        def scene_sdf_near(p):
            lo, hi = p.bounds()
            reach = 0.08
            near = [q for q in visible if np.all(vb[id(q)][0] <= hi + reach) and np.all(vb[id(q)][1] >= lo - reach)]

            def f(P):
                d = np.full(len(P), 1e9)
                for q in near:
                    d = np.minimum(d, q.sdf(P))
                return d
            return f

        result = []
        for p, v, f in out:
            nrm = gradient(p.sdf, v)
            col, gl, bone_d = p.attributes(v)
            # hand-made colour: mottling, faint smudges, dust specks
            seed = p.seed
            mott = fbm(v * 22.0, 3, seed + 11) * p.mottle + fbm(v * 5.0, 2, seed + 12) * p.mottle * 0.6
            col = np.clip(col * (1.0 + mott[:, None]), 0, 1)
            if p.mat == 0:
                specks = vnoise(v * 260.0, seed + 13)
                col = col * np.where(specks > 0.93, 0.82, 1.0)[:, None]
            if p.ao and p.mat == 0:
                ao = bake_ao(scene_sdf_near(p), v, nrm)
                col = col * (0.55 + 0.45 * ao)[:, None]
            rgba = np.concatenate([np.clip(col * 255 + 0.5, 0, 255), np.clip(gl, 0, 255)[:, None]], axis=1).astype(np.uint8)
            skin = None
            if p.rigid is None and self.bones and bone_d:
                skin = self._weights(v, bone_d)
            result.append((p, v.astype(np.float32), nrm.astype(np.float32), rgba, f.astype(np.uint32), skin))
        return self._merge(result)

    def _merge(self, result):
        """Concatenate pieces that share a `merge` name (rigid/static only)."""
        merged, groups, order = [], {}, []
        for r in result:
            p = r[0]
            if p.merge is None:
                order.append(("one", r))
                continue
            if p.merge not in groups:
                groups[p.merge] = []
                order.append(("grp", p.merge))
            groups[p.merge].append(r)
        for kind, item in order:
            if kind == "one":
                merged.append(item)
                continue
            rs = groups[item]
            first = rs[0][0]
            vs, ns, cs, fs, base = [], [], [], [], 0
            for p, v, n, c, f, skin in rs:
                vs.append(v); ns.append(n); cs.append(c); fs.append(f + base)
                base += len(v)
            proxy = Piece(self, item, mat=first.mat, hidden=first.hidden, rigid=first.rigid)
            merged.append((proxy, np.concatenate(vs), np.concatenate(ns), np.concatenate(cs), np.concatenate(fs).astype(np.uint32), None))
        return merged

    def _weights(self, v, bone_d):
        names = list(bone_d.keys())
        D = np.stack([np.maximum(bone_d[n], 0.0) for n in names], axis=1)  # outside distance per bone
        D = D - D.min(axis=1, keepdims=True)
        W = np.exp(-D / self.weight_softness)
        order = np.argsort(-W, axis=1)[:, :4]
        Wt = np.take_along_axis(W, order, axis=1)
        Wt[Wt < 0.02] = 0.0
        Wt = Wt / Wt.sum(axis=1, keepdims=True)
        idx = np.vectorize(lambda j: self.bone_index(names[j]))(order).astype(np.uint8)
        if len(names) < 4:
            idx = np.concatenate([idx, np.zeros((len(v), 4 - idx.shape[1]), np.uint8)], axis=1)
            Wt = np.concatenate([Wt, np.zeros((len(v), 4 - Wt.shape[1]))], axis=1)
        return idx, Wt.astype(np.float32)

    # output
    def save(self, path, preview=True):
        parts = self.build()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_claymesh(path, self, parts)
        tris = sum(len(f) for _, _, _, _, f, _ in parts)
        print(f"[clay] {self.name}: {len(parts)} pieces, {tris} tris -> {path}")
        return parts


def gradient(f, P, eps=1e-3):
    e = np.eye(3) * eps
    g = np.stack([(f(P + e[i]) - f(P - e[i])) for i in range(3)], axis=1)
    return g / (np.linalg.norm(g, axis=1, keepdims=True) + 1e-12)


def project(p, v, iters=3):
    for _ in range(iters):
        d = p.sdf(v)
        g = gradient(p.sdf, v)
        v = v - g * d[:, None]
    return v


def bake_ao(f, P, N, steps=5, delta=0.012, strength=0.9):
    occ = np.zeros(len(P))
    w = 1.0
    for i in range(1, steps + 1):
        dist = i * delta
        occ += w * np.maximum(dist - f(P + N * dist), 0) / dist
        w *= 0.6
    return np.clip(1.0 - strength * occ / 2.2, 0.0, 1.0)


# ----------------------------------------------------------------------------------------------------------------
# writer


def _str(s):
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


def write_claymesh(path, model: Model, parts):
    out = bytearray(b"CLAY" + struct.pack("<I", 2))
    out += struct.pack("<I", len(model.bones))
    for name, parent, pos in model.bones:
        out += _str(name) + struct.pack("<i3f", parent, *pos)
    out += struct.pack("<I", len(parts))
    for p, v, n, c, f, skin in parts:
        flags = (1 if p.hidden else 0) | (2 if skin is not None else 0)
        rb = model.bone_index(p.rigid) if p.rigid else -1
        out += _str(p.name) + struct.pack("<BBi", p.mat, flags, rb)
        out += struct.pack("<II", len(v), f.size)
        out += v.astype("<f4").tobytes() + n.astype("<f4").tobytes() + c.astype(np.uint8).tobytes()
        if skin is not None:
            out += skin[0].astype(np.uint8).tobytes() + skin[1].astype("<f4").tobytes()
        out += f.astype("<u4").ravel().tobytes()
    out += struct.pack("<I", len(model.sockets))
    for name, bi, pos, q in model.sockets:
        out += _str(name) + struct.pack("<i3f4f", bi, *pos, *q)
    with open(path, "wb") as fh:
        fh.write(out)


def read_claymesh(path):
    """Parser (used by previews/tests) -> dict."""
    data = open(path, "rb").read()
    o = 0

    def rd(fmt):
        nonlocal o
        v = struct.unpack_from(fmt, data, o)
        o += struct.calcsize(fmt)
        return v

    def rs():
        nonlocal o
        (n,) = rd("<H")
        s = data[o:o + n].decode()
        o += n
        return s

    assert data[:4] == b"CLAY"
    o = 4
    (ver,) = rd("<I")
    (nb,) = rd("<I")
    bones = []
    for _ in range(nb):
        name = rs()
        parent, x, y, z = rd("<i3f")
        bones.append((name, parent, (x, y, z)))
    (npc,) = rd("<I")
    pieces = []
    for _ in range(npc):
        name = rs()
        mat, flags, rb = rd("<BBi")
        vc, ic = rd("<II")
        v = np.frombuffer(data, "<f4", vc * 3, o).reshape(-1, 3); o += vc * 12
        n = np.frombuffer(data, "<f4", vc * 3, o).reshape(-1, 3); o += vc * 12
        c = np.frombuffer(data, np.uint8, vc * 4, o).reshape(-1, 4); o += vc * 4
        skin = None
        if flags & 2:
            bi = np.frombuffer(data, np.uint8, vc * 4, o).reshape(-1, 4); o += vc * 4
            bw = np.frombuffer(data, "<f4", vc * 4, o).reshape(-1, 4); o += vc * 16
            skin = (bi, bw)
        f = np.frombuffer(data, "<u4", ic, o).reshape(-1, 3); o += ic * 4
        pieces.append(dict(name=name, mat=mat, hidden=bool(flags & 1), rigid=rb, v=v, n=n, c=c, f=f, skin=skin))
    (ns,) = rd("<I")
    sockets = []
    for _ in range(ns):
        name = rs()
        vals = rd("<i3f4f")
        sockets.append((name, vals[0], vals[1:4], vals[4:8]))
    return dict(version=ver, bones=bones, pieces=pieces, sockets=sockets)
