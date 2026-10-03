"""
Saltmoss Harbor set-building kit: weathered planks, corrugated tin, shakes, pilings, windows, doors, railings and
the budgeted TownModel. Everything is clay SDF (Tools/clay/clay.py); boards are meshed one by one and merged into a
handful of output pieces (merge="walls", "roof", ...), so big sets stay inside the grid limit and the tri budget.

Conventions (Unity): x right, y up, z forward, metres. Buildings face +Z (front door / counter side), origin at the
centre of the floor footprint, y = 0 at the walkable floor surface. Kit pieces: origin at the deck-top centre.
"""
from __future__ import annotations

import math
import zlib

import numpy as np
from clay import *  # noqa: F401,F403
from clay import Model, Piece, Prim, Func, Box, Sphere, Ellipsoid, Capsule, Cylinder, Tube, Torus, HalfSpace
from clay import euler, look_rot, rgb, shade, mix, fbm, vnoise, project

try:
    import pyfqmr
except ImportError:
    pyfqmr = None

# ----------------------------------------------------------------------------------------------------------------
# palette: dusty, sea-faded plasticine

TP = dict(
    # weathered timber
    wood="#8a8276", wood_lt="#9e968a", wood_dk="#6c655c", wood_br="#85725f", wood_silver="#a49e94", wood_wet="#5b554d",
    wood_new="#b08d61", wood_new2="#9c7650", wood_tar="#4a443e",
    # faded paint
    teal="#5b8a86", teal_dk="#4a7471", red="#9a5246", red_dk="#7f4136", mustard="#c8a04c", cream="#ddd2b6",
    navy="#4a5b72", sage="#839c80", ochre="#b98045", slate="#6f8698", rose="#b8796f", white="#e7e1d2",
    # metal
    tin="#7f8487", tin_dk="#6a6f73", tin_lt="#939799", rust="#95522f", rust_lt="#ad6a3d", rust_dk="#6e3b24",
    iron="#3e3c3b", brass="#c39b48", copper="#a8673f",
    # sea things
    algae="#4f6a36", algae_lt="#6c8a45", slime="#3c472d", barnacle="#d4ccb8", barnacle_dk="#b3aa96", mussel="#2e3340",
    rope="#b59c70", rope_dk="#8f7a55", net_green="#5f7d66", net_orange="#c46f3a", net_blue="#56708c",
    # glass (matClass 1 multiplies its vertex colour by the warm glow colour at night)
    glass="#5f6e70", lamp="#f2cf86",
    # ground
    stone="#8e8b84", stone_dk="#75736d", stone_lt="#a39f95", sand="#c8b48f", grass="#7c9257", grass_dk="#5f7743",
    moss="#6f8a4a", ice="#dfeef2",
)

# ----------------------------------------------------------------------------------------------------------------


def crc(s):
    return zlib.crc32(s.encode()) & 0x7FFFFFFF


class TownModel(Model):
    """Model with a total triangle budget: every piece is meshed raw, then decimated in proportion to its raw
    complexity (x `detail`), water-filling so small pieces keep what they need."""

    def __init__(self, name, budget=60000, res=0.02, seed=None):
        super().__init__(name, res=res)
        self.budget = budget
        self.rng = np.random.default_rng(crc(name) if seed is None else seed)
        self._n = 0
        self._cache = {}
        self.min_tris = 24
        self.peel_seed = int(self.rng.integers(10 ** 5))

    def piece(self, name=None, detail=1.0, **kw) -> Piece:
        self._n += 1
        if name is None:
            name = f"p{self._n}"
        kw.setdefault("seed", (crc(self.name) + self._n * 7919) % 100000)
        p = Piece(self, name, **kw)
        p.detail = detail
        self.pieces.append(p)
        return p

    def _raw(self, p):
        keep = p.decimate
        p.decimate = 10 ** 12
        try:
            v, f = Model._mesh_piece(self, p)
        finally:
            p.decimate = keep
        return v, f

    def build(self):
        raws = {}
        for p in list(self.pieces):
            try:
                raws[id(p)] = self._raw(p)
            except ValueError as e:
                if "no surface" not in str(e):
                    raise
                print(f"[town] {self.name}: dropping empty piece {p.name} ({p.merge})")
                self.pieces.remove(p)
        live = [p for p in self.pieces if not p.hidden]
        fixed = {id(p): p.decimate for p in self.pieces if p.decimate}
        B = float(self.budget) - sum(min(fixed[id(p)], len(raws[id(p)][1])) for p in live if id(p) in fixed)
        pool = [p for p in live if id(p) not in fixed]
        alloc = {}
        for _ in range(60):
            W = sum(len(raws[id(p)][1]) * p.detail for p in pool)
            if not pool or W <= 0:
                break
            changed = False
            for p in list(pool):
                n = len(raws[id(p)][1])
                a = B * n * p.detail / W
                lo = min(self.min_tris, n)
                if a >= n or a < lo:
                    alloc[id(p)] = n if a >= n else lo
                    B -= alloc[id(p)]
                    pool.remove(p)
                    changed = True
            if not changed:
                for p in pool:
                    alloc[id(p)] = max(self.min_tris, int(B * len(raws[id(p)][1]) * p.detail / W))
                break
        for p in self.pieces:
            v, f = raws[id(p)]
            t = fixed.get(id(p)) or alloc.get(id(p)) or len(f)
            if p.hidden and not fixed.get(id(p)):
                t = min(len(f), 3000)
            if pyfqmr is not None and len(f) > t:
                for it in range(3):
                    s = pyfqmr.Simplify()
                    s.setMesh(v.astype(np.float64), f.astype(np.int32))
                    s.simplify_mesh(target_count=int(t), aggressiveness=5 + it * 2, preserve_border=True, verbose=False, max_iterations=400)
                    v, f, _ = s.getMesh()
                    if len(f) <= t * 1.08:
                        break
                v = project(p, v, 2)
            self._cache[id(p)] = (v, f)
        tot = sum(len(self._cache[id(p)][1]) for p in live)
        if tot > self.budget * 1.05:
            print(f"[town] {self.name}: {tot} tris vs budget {self.budget}")
            over = sorted(((len(self._cache[id(p)][1]) - (fixed.get(id(p)) or alloc.get(id(p)) or 0), p.name, p.merge,
                            len(raws[id(p)][1])) for p in live), reverse=True)[:6]
            print("   worst (excess, piece, merge, raw):", over)
        return Model.build(self)

    def _mesh_piece(self, p):
        if id(p) in self._cache:
            return self._cache[id(p)]
        return Model._mesh_piece(self, p)


# ----------------------------------------------------------------------------------------------------------------
# frames & transforms


def frame(xdir, ydir):
    """Rotation matrix (columns = local X, Y, Z in world) with local X along xdir and local Y as close to ydir."""
    X = np.asarray(xdir, float)
    X = X / np.linalg.norm(X)
    Y = np.asarray(ydir, float)
    Y = Y - X * (Y @ X)
    n = np.linalg.norm(Y)
    if n < 1e-6:
        Y = np.array([0, 1.0, 0]) if abs(X[1]) < 0.9 else np.array([1.0, 0, 0])
        Y = Y - X * (Y @ X)
        n = np.linalg.norm(Y)
    Y = Y / n
    Z = np.cross(X, Y)
    return np.stack([X, Y, Z], axis=1)


def rot_axis(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * (K @ K)


class T:
    """Placement: world = pos + Ry(yaw) @ (s * local). Compose with .sub(pos, yaw)."""

    def __init__(self, pos=(0, 0, 0), yaw=0.0, s=1.0, R=None):
        self.o = np.asarray(pos, float)
        self.R = euler((0, yaw, 0)) if R is None else np.asarray(R, float)
        self.s = s

    def p(self, x, y=0.0, z=0.0):
        if np.ndim(x):
            x, y, z = x
        return self.o + self.R @ (np.array([x, y, z], float) * self.s)

    def v(self, d):
        return self.R @ np.asarray(d, float)

    def r(self, rot=None):
        return self.R @ euler(rot)

    def sub(self, pos=(0, 0, 0), yaw=0.0, s=1.0):
        return T(self.p(pos), R=self.R @ euler((0, yaw, 0)), s=self.s * s)


# ----------------------------------------------------------------------------------------------------------------
# primitives


def _aabb(c, R, half):
    e = np.abs(R) @ np.asarray(half, float)
    return c - e, c + e


class Plank(Prim):
    """A hand-cut board. Local X = length (half hl), Y = thickness (half ht, the face normal), Z = width (half hw).
    bow sags the middle toward -Y, sweep bends it toward -Z, twist (deg) winds the ends, taper/wob vary the width,
    grooves = [(z fraction, phase)] tool-scored grain lines, ends = (slant+, slant-) angled saw cuts (m)."""

    def __init__(self, c, half, rot=None, round=None, bow=0.0, sweep=0.0, twist=0.0, taper=0.0, wob=0.04,
                 grooves=(), gdepth=0.004, gwidth=0.0075, ends=(0.0, 0.0), seed=0):
        super().__init__()
        self.c = np.asarray(c, float)
        self.R = euler(rot)
        self.h = np.asarray(half, float)
        self.rd = min(self.h[1] * 0.7, self.h[2] * 0.5) if round is None else round
        self.bow, self.sweep, self.twist, self.taper, self.wob = bow, sweep, math.radians(twist), taper, wob
        self.grooves, self.gdepth, self.gwidth = list(grooves), gdepth, gwidth
        self.ends = ends
        self.ph = (seed % 997) * 0.37

    def sdf(self, P):
        q = (P - self.c) @ self.R
        hl, ht, hw = self.h
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        u = np.clip(x / hl, -1, 1)
        b = 1 - u * u
        y = y + self.bow * b
        z = z + self.sweep * b
        if self.twist:
            a = self.twist * u
            ca, sa = np.cos(a), np.sin(a)
            y, z = ca * y - sa * z, sa * y + ca * z
        ph = self.ph
        hwe = hw * (1 + self.taper * u + self.wob * np.sin(u * 2.7 + ph))
        hte = ht * (1 + 0.6 * self.wob * np.sin(u * 3.9 + ph * 1.7))
        e0, e1 = self.ends
        hle = hl + np.where(x > 0, e0, e1) * np.clip(z / hw, -1, 1)
        r = self.rd
        qa = np.stack([np.abs(x) - (hle - r), np.abs(y) - (hte - r), np.abs(z) - (hwe - r)], axis=1)
        d = np.linalg.norm(np.maximum(qa, 0), axis=1) + np.minimum(qa.max(axis=1), 0) - r
        for gz, gp in self.grooves:
            zc = gz * hw + 0.18 * hw * np.sin(x * 1.1 + gp) + 0.05 * hw * np.sin(x * 4.3 + gp * 2)
            d = d + self.gdepth * np.exp(-((z - zc) / self.gwidth) ** 2)
        return d

    def bounds(self):
        hl, ht, hw = self.h
        half = (hl + max(abs(self.ends[0]), abs(self.ends[1])) + 0.01,
                ht * 1.3 + abs(self.bow) + hw * abs(math.sin(self.twist)) + 0.01,
                hw * (1 + abs(self.taper) + self.wob) + abs(self.sweep) + ht * abs(math.sin(self.twist)) + 0.01)
        return _aabb(self.c, self.R, half)


class Corrugated(Prim):
    """Corrugated tin sheet. Local X across the sheet (corrugation), Z along the ridges, Y = normal.
    sag dishes the middle, curl lifts the +Z edge, dent = list of (x, z, r, depth)."""

    def __init__(self, c, half_xz, rot=None, amp=0.014, period=0.09, t=0.0085, sag=0.0, curl=0.0, ripple=0.004,
                 seed=0, dents=()):
        super().__init__()
        self.c = np.asarray(c, float)
        self.R = euler(rot)
        self.hx, self.hz = half_xz
        self.amp, self.per, self.t, self.sag, self.curl, self.rip = amp, period, t, sag, curl, ripple
        self.k = 1.0 / math.sqrt(1 + (amp * 2 * math.pi / period) ** 2)
        self.ph = (seed % 991) * 0.53
        self.dents = list(dents)

    def sdf(self, P):
        q = (P - self.c) @ self.R
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        u = np.clip(x / self.hx, -1.2, 1.2)
        v = np.clip(z / self.hz, -1.2, 1.2)
        off = self.amp * np.sin(2 * np.pi * x / self.per + self.ph)
        off = off - self.sag * (1 - v * v) * (1 - 0.4 * u * u)
        off = off + self.curl * np.maximum(v, 0) ** 3
        off = off + self.rip * np.sin(z * 3.1 + self.ph) * np.sin(x * 2.3 + self.ph * 0.7)
        for dx, dz, r, dd in self.dents:
            off = off - dd * np.exp(-((x - dx) ** 2 + (z - dz) ** 2) / (r * r))
        d = (np.abs(y - off) - self.t) * self.k
        de = np.maximum(np.abs(x) - self.hx, np.abs(z) - self.hz)
        return np.maximum(d, de)

    def bounds(self):
        return _aabb(self.c, self.R, (self.hx + 0.01, self.amp + self.t + self.sag + self.curl + self.rip + 0.03, self.hz + 0.01))


def _h2(a, b, s):
    """Deterministic hash of integer arrays -> [0,1)."""
    h = (a.astype(np.int64) * 374761393 + b.astype(np.int64) * 668265263 + s * 2246822519) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65536.0


class Shingles(Prim):
    """A roof slope of overlapping wooden shakes. Local X along the ridge (half hx), Z down-slope from the ridge
    (z=0) to the eave (z=L), Y = outward normal. Each shake has its own thickness, butt line and gap."""

    def __init__(self, c, hx, L, rot=None, row=0.2, width=0.17, t0=0.02, tw=0.028, gap=0.012, seed=0, sag=0.0):
        super().__init__()
        self.c = np.asarray(c, float)
        self.R = euler(rot)
        self.hx, self.L, self.row, self.w, self.t0, self.tw, self.gap, self.seed, self.sag = hx, L, row, width, t0, tw, gap, seed, sag

    def cells(self, q):
        x, z = q[:, 0], q[:, 2]
        s = (self.L - z) / self.row
        r = np.floor(s)
        off = _h2(r, r * 0 + 3, self.seed) * self.w
        cx = (x + off) / self.w
        col = np.floor(cx)
        return s, r, cx, col

    def sdf(self, P):
        q = (P - self.c) @ self.R
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        u = np.clip(x / self.hx, -1, 1)
        y = y + self.sag * (1 - u * u) * np.clip(z / self.L, 0, 1)
        s, r, cx, col = self.cells(q)
        j = _h2(r, col, self.seed)
        j2 = _h2(col, r, self.seed + 7)
        f = s - r + (j - 0.5) * 0.22
        f = np.where(f < 0, f + 1, f)
        top = self.t0 + self.tw * np.clip(1 - f, 0, 1) + (j2 - 0.5) * 0.012
        g = np.minimum(cx - col, 1 - (cx - col)) * self.w
        top = top - 0.018 * np.exp(-(g / self.gap) ** 2)
        d = np.maximum(y - top, -y - 0.01) * 0.6
        de = np.maximum(np.abs(x) - self.hx, np.maximum(z - self.L, -z))
        return np.maximum(d, de)

    def bounds(self):
        c = self.c + self.R @ np.array([0, 0, self.L / 2])
        return _aabb(c, self.R, (self.hx + 0.02, self.t0 + self.tw + self.sag + 0.03, self.L / 2 + 0.02))


def patches(scale, thr, seed=0, octaves=2, stretch=(1, 1, 1)):
    """Paint mask: negative where low-frequency noise exceeds thr (peeling paint, rust, moss, lichen)."""
    st = np.asarray(stretch, float)
    return Func(lambda P: (thr - fbm(P * st * scale, octaves, seed)) * 0.06, (-1e4,) * 3, (1e4,) * 3)


def band(y0, y1, wob=0.0, freq=1.5, seed=0):
    """Paint mask: horizontal band y0 < y < y1 (wobbly edges)."""
    def f(P):
        w = wob * fbm(P * freq, 2, seed) if wob else 0.0
        return np.maximum(y0 + w - P[:, 1], P[:, 1] - y1 - w)
    return Func(f, (-1e4,) * 3, (1e4,) * 3)


def below(y, wob=0.0, freq=1.5, seed=0):
    return band(-1e4, y, wob, freq, seed)


# ----------------------------------------------------------------------------------------------------------------
# boards


def board(m: TownModel, merge, a, b, w, t, up, color, *, res=None, bow=None, sweep=None, twist=None, grooves=None,
          nails=0, nail_inset=0.05, rust=0.6, paint=None, peel=0.18, knot=0.25, ends=None, detail=1.0, gloss=30,
          lumps=0.0022, dents=2, jitter=1.0, round=None, rot_jit=None):
    """Board with centreline a->b, face normal ~up, width w, thickness t. Hand-made by default: bowed, swept,
    twisted, uneven width, saw-cut ends slanted, a couple of tool-scored grain lines, maybe a knot.
    paint: paint colour over the wood with patches peeled back to the wood (peel = fraction-ish)."""
    rng = m.rng
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    R = frame(b - a, up)
    if rot_jit is None:
        rot_jit = jitter
    if rot_jit:
        R = rot_axis(R[:, 1], rng.normal() * 0.8 * rot_jit) @ rot_axis(R[:, 2], rng.normal() * 0.5 * rot_jit) @ R
    c = (a + b) / 2
    if bow is None:
        bow = rng.uniform(-0.2, 1.0) * L * 0.006 * jitter
    if sweep is None:
        sweep = rng.normal() * L * 0.004 * jitter
    if twist is None:
        twist = rng.normal() * 1.6 * jitter * min(1.0, L)
    if grooves is None:
        ng = rng.integers(1, 3) if w > 0.09 else rng.integers(0, 2)
        grooves = [(rng.uniform(-0.6, 0.6), rng.uniform(0, 6)) for _ in range(ng)]
    if ends is None:
        ends = (rng.normal() * 0.008 * jitter, rng.normal() * 0.008 * jitter)
    if res is None:
        res = float(np.clip(t / 3.2, 0.007, 0.016))
    base = paint if paint is not None else color
    p = m.piece(color=base, gloss=gloss, merge=merge, res=res, lumps=lumps, lump_freq=7.0, dents=dents,
                dent_size=0.03, dent_depth=0.003, mottle=0.08, detail=detail)
    p.add(Plank(c, (L / 2, t / 2, w / 2), R, round=round, bow=bow, sweep=sweep, twist=twist, taper=rng.normal() * 0.04 * jitter,
                wob=0.035 * jitter, grooves=grooves, gdepth=min(0.0045, t * 0.15), gwidth=max(0.006, res * 0.55), ends=ends,
                seed=int(rng.integers(0, 10 ** 6))))
    X, Y, Z = R[:, 0], R[:, 1], R[:, 2]
    if paint is not None and peel > 0:
        # world-coherent weathering: big patches shared by neighbouring boards + worn bottoms on uprights
        p.paint(patches(2.4, 0.34 - peel * 0.7, m.peel_seed, stretch=(1.0, 0.7, 1.0)), color, feather=0.003)
        p.paint(patches(5.5, 0.42 - peel * 0.5, m.peel_seed + 1), mix(color, base, 0.35), feather=0.003)
        if abs(X[1]) > 0.7:
            p.paint(below(min(a[1], b[1]) + rng.uniform(0.1, 0.3) * (0.5 + peel * 2), 0.06, 5, m.peel_seed), color, feather=0.01)
    if knot and rng.random() < knot and L > 0.4:
        kc = c + X * rng.uniform(-0.35, 0.35) * L + Z * rng.uniform(-0.25, 0.25) * w + Y * t / 2
        p.sub(Ellipsoid(kc, (0.024, 0.008, 0.018), frame(X, Y)), k=0.004, color=shade(color, 0.75))
    for e in (-1, 1):
        for i in range(nails):
            pos = c + X * e * (L / 2 - nail_inset) + Z * (((i + 0.5) / nails - 0.5) * w * 0.9) + Y * t / 2
            pos = pos + rng.normal(size=3) * 0.004
            p.add(Ellipsoid(pos, (0.011, 0.006, 0.011), frame(X, Y)), k=0.003, color=TP["iron"], gloss=60)
            if rust and rng.random() < rust:
                ln = rng.uniform(0.04, 0.16)
                p.paint(Capsule(pos + Y * 0.004, pos + np.array([0, -ln, 0]) + Y * 0.004, 0.012, 0.004), mix(TP["rust"], base, 0.45), feather=0.006)
    return p


def post(m, merge, a, b, r, color, *, res=None, square=True, detail=1.0, lumps=0.003, rot=0.0):
    """A timber post or beam from a to b (square section by default, slightly irregular)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    up = np.array([0, 0, 1.0]) if abs((b - a)[1]) > 0.9 * np.linalg.norm(b - a) else np.array([0, 1.0, 0])
    R = frame(b - a, up)
    if rot:
        R = rot_axis(R[:, 0], rot) @ R
    if square:
        return board(m, merge, a, b, r * 2, r * 2 * m.rng.uniform(0.85, 1.0), R[:, 1], color, res=res or float(np.clip(r / 3, 0.008, 0.02)),
                     detail=detail, lumps=lumps, grooves=[(m.rng.uniform(-0.5, 0.5), m.rng.uniform(0, 6))], round=r * 0.35,
                     bow=m.rng.normal() * 0.01, twist=m.rng.normal() * 2)
    p = m.piece(color=color, merge=merge, res=res or float(np.clip(r / 3, 0.008, 0.025)), lumps=lumps, lump_freq=6, detail=detail, mottle=0.08)
    p.add(Capsule(a, b, r, r * m.rng.uniform(0.88, 1.0)))
    return p


def piling(m, merge, top, bottom_y, r, *, lean=(0.0, 0.0), sea_y=0.0, color=None, barnacles=14, res=None, detail=1.0, cap=True,
           algae=True):
    """Round timber piling from `top` down to bottom_y, leaning a little; wet dark below the tide line, green algae
    band and barnacle crust at the waterline (sea_y in the same frame)."""
    rng = m.rng
    top = np.asarray(top, float)
    bot = np.array([top[0] + lean[0], bottom_y, top[2] + lean[1]])
    color = color or rng.choice([TP["wood"], TP["wood_dk"], TP["wood_br"], TP["wood_lt"]])
    p = m.piece(color=color, merge=merge, res=res or float(np.clip(r / 3.2, 0.012, 0.03)), lumps=0.006, lump_freq=5, dents=3,
                dent_size=0.05, dent_depth=0.006, mottle=0.1, detail=detail)
    mid = (top + bot) / 2 + np.array([rng.normal() * 0.02, 0, rng.normal() * 0.02])
    p.add(Tube([top, mid, bot], [r, r * 1.04, r * 1.08], samples=3))
    if cap:
        p.add(Cylinder(top + np.array([0, -0.01, 0]), r * 1.02, 0.02, round=0.012), k=0.02)
        p.paint(Cylinder(top, r * 1.3, 0.06), shade(color, 0.85))
    # vertical splits / grain
    for i in range(3):
        ang = rng.uniform(0, 2 * np.pi)
        d = np.array([np.cos(ang), 0, np.sin(ang)])
        y0 = rng.uniform(sea_y + 0.2, top[1] - 0.1)
        p.sub(Capsule(top + d * r + np.array([0, y0 - top[1], 0]), top + d * r + np.array([0, y0 - top[1] - rng.uniform(0.3, 0.9), 0]), 0.008), k=0.004,
              color=shade(color, 0.6))
    if algae:
        p.paint(below(sea_y - 0.05, 0.08, 3.0, rng.integers(99)), TP["wood_wet"], gloss=110, feather=0.03)
        p.paint(band(sea_y - 0.55, sea_y + 0.28, 0.12, 3.0, rng.integers(99)), TP["algae"], gloss=120, feather=0.03)
        p.paint(band(sea_y + 0.1, sea_y + 0.42, 0.1, 4.0, rng.integers(99)), TP["slime"], gloss=90, feather=0.03)
        p.paint(band(sea_y - 0.2, sea_y + 0.15, 0.08, 5.0, rng.integers(99)), TP["algae_lt"], gloss=120, feather=0.02)
        # barnacles: little volcano cones pressed on around the tide line
        for i in range(barnacles):
            ang = rng.uniform(0, 2 * np.pi)
            yy = sea_y + rng.uniform(-0.35, 0.3)
            t = (top[1] - yy) / max(top[1] - bottom_y, 1e-3)
            axis = top + (bot - top) * t
            d = np.array([np.cos(ang), 0, np.sin(ang)])
            br = rng.uniform(0.014, 0.03)
            c = axis + d * (r * 1.02)
            p.add(Ellipsoid(c, (br, br, br * 0.7), frame(np.cross(d, [0, 1, 0]), d)), k=0.006, color=rng.choice([TP["barnacle"], TP["barnacle_dk"]]), gloss=60)
            p.sub(Sphere(c + d * br * 0.75, br * 0.35), k=0.003, color=TP["slime"])
        # mussels clumped low
        for i in range(rng.integers(2, 6)):
            ang = rng.uniform(0, 2 * np.pi)
            yy = sea_y + rng.uniform(-0.45, -0.1)
            t = (top[1] - yy) / max(top[1] - bottom_y, 1e-3)
            axis = top + (bot - top) * t
            d = np.array([np.cos(ang), 0, np.sin(ang)])
            c = axis + d * r
            p.add(Ellipsoid(c, (0.018, 0.035, 0.012), frame([0, 1, 0], d) @ euler((0, 0, rng.normal() * 25))), k=0.004, color=TP["mussel"], gloss=170)
    return p


def rope(m, merge, pts, r=0.018, color=None, samples=6, res=None, detail=1.0):
    color = color or TP["rope"]
    p = m.piece(color=color, merge=merge, res=res or max(0.006, r / 2.2), lumps=0.0015, lump_freq=20, mottle=0.08, detail=detail)
    p.add(Tube(pts, r, samples=samples))
    # twisted lay: diagonal stripes painted darker
    pts = np.asarray(pts, float)
    lo, hi = pts.min(0) - r * 2, pts.max(0) + r * 2

    def stripes(P):
        s = np.sin((P[:, 0] + P[:, 1] * 1.3 + P[:, 2] * 0.7) / (r * 0.9))
        return (0.55 - s) * 0.01
    p.paint(Func(stripes, lo, hi), shade(color, 0.75), feather=0.002)
    return p


# ----------------------------------------------------------------------------------------------------------------
# walls


def _split_span(lo, hi, holes):
    """Split interval [lo,hi] removing holes [(a,b)]."""
    spans = [(lo, hi)]
    for a, b in holes:
        out = []
        for s0, s1 in spans:
            if b <= s0 or a >= s1:
                out.append((s0, s1))
                continue
            if a > s0:
                out.append((s0, a))
            if b < s1:
                out.append((b, s1))
        spans = out
    return [(s0, s1) for s0, s1 in spans if s1 - s0 > 0.04]


def vboard_wall(m, merge, p0, p1, y0, top, out, colors, *, bw=(0.2, 0.28), t=0.045, openings=(), paint=None, peel=0.2,
                replace=0.08, battens=True, batten_color=None, nails=1, detail=1.0, gap=0.008, lean=0.0):
    """Vertical board wall along the base line p0->p1 (x,z; y0 = bottom), boards from y0 to top(s) where s in [0,L]
    (top may be a number). `out` = outward normal. openings = [(s0, s1, yb, yt)] holes for windows/doors.
    Returns list of pieces."""
    rng = m.rng
    p0 = np.array([p0[0], y0, p0[1]], float)
    p1 = np.array([p1[0], y0, p1[1]], float)
    L = np.linalg.norm(p1 - p0)
    dirv = (p1 - p0) / L
    out = np.asarray(out, float)
    topf = top if callable(top) else (lambda s, _t=top: _t)
    s = 0.0
    pieces = []
    edges = []
    while s < L - 0.03:
        w = rng.uniform(*bw)
        if L - (s + w) < bw[0] * 0.6:
            w = L - s
        sc = s + w / 2
        col = colors[int(rng.integers(len(colors)))] if isinstance(colors, (list, tuple)) else colors
        pnt = paint
        if rng.random() < replace:
            col = rng.choice([TP["wood_new"], TP["wood_new2"], TP["wood_lt"]])
            pnt = None
        ytop = topf(sc) + rng.normal() * 0.012
        ybot = y0 - rng.uniform(0.0, 0.05)
        holes = [(yb, yt) for (a, b, yb, yt) in openings if sc + w / 2 > a and sc - w / 2 < b]
        spans = _split_span(ybot, ytop, holes)
        base = p0 + dirv * sc + out * (t / 2 + rng.normal() * 0.004)
        lean_v = dirv * (lean + rng.normal() * 0.006)
        for (ya, yb_) in spans:
            a = base + np.array([0, ya - y0, 0]) - lean_v * (ya - y0)
            b = base + np.array([0, yb_ - y0, 0]) + lean_v * 0  # lean the top a touch
            b = b + lean_v * (yb_ - ya) * 0.5
            pieces.append(board(m, merge, a, b, w - gap, t, out, col, paint=pnt, peel=peel, nails=nails, detail=detail))
        edges.append(s + w)
        s += w
    if battens:
        bc = batten_color or (colors[0] if isinstance(colors, (list, tuple)) else colors)
        for e in edges[:-1]:
            if rng.random() < 0.75:
                sc = e
                holes = [(yb, yt) for (a, b, yb, yt) in openings if sc + 0.04 > a and sc - 0.04 < b]
                for ya, yb_ in _split_span(y0 + 0.02, topf(sc) - 0.02, holes):
                    base = p0 + dirv * sc + out * (t + 0.012)
                    pieces.append(board(m, merge, base + np.array([0, ya - y0, 0]), base + np.array([0, yb_ - y0, 0]), 0.06, 0.025, out, bc,
                                        paint=paint, peel=peel * 1.2, nails=0, detail=detail * 0.7, grooves=[], knot=0))
    return pieces


def hboard_wall(m, merge, p0, p1, y0, top, out, colors, *, bh=(0.17, 0.22), t=0.04, openings=(), paint=None, peel=0.22,
                replace=0.06, lap=7.0, nails=1, detail=1.0, ext=0.03):
    """Clapboard (horizontal lapped) wall; top(s) may describe a gable. Board ends are trimmed to the gable."""
    rng = m.rng
    p0 = np.array([p0[0], y0, p0[1]], float)
    p1 = np.array([p1[0], y0, p1[1]], float)
    L = np.linalg.norm(p1 - p0)
    dirv = (p1 - p0) / L
    out = np.asarray(out, float)
    topf = top if callable(top) else (lambda s, _t=top: _t)
    peak = max(topf(s) for s in np.linspace(0, L, 41))
    y = y0
    pieces = []
    while y < peak - 0.05:
        h = rng.uniform(*bh)
        yc = y + h / 2
        # horizontal extent at this height (gable): where topf(s) > y + h*0.5
        ss = np.linspace(-ext, L + ext, 161)
        ok = np.array([topf(min(max(s_, 0), L)) > yc for s_ in ss])
        if not ok.any():
            break
        s0, s1 = ss[ok].min(), ss[ok].max()
        col = colors[int(rng.integers(len(colors)))] if isinstance(colors, (list, tuple)) else colors
        pnt = paint
        if rng.random() < replace:
            col, pnt = rng.choice([TP["wood_new"], TP["wood_new2"], TP["wood_lt"]]), None
        holes = [(a, b) for (a, b, yb, yt) in openings if yc + h * 0.3 > yb and yc - h * 0.3 < yt]
        for sa, sb in _split_span(s0, s1, holes):
            # lapped: rotate around the board length so the bottom edge kicks out
            up = np.array([0, 1.0, 0]) * math.cos(math.radians(lap)) - out * math.sin(math.radians(lap))
            nrm = np.cross(up, dirv)
            if nrm @ out < 0:
                nrm = -nrm
            base = p0 + out * (t / 2 + 0.006) + np.array([0, yc - y0, 0])
            a = base + dirv * sa
            b = base + dirv * sb
            pieces.append(board(m, merge, a, b, h + 0.03, t, nrm, col, paint=pnt, peel=peel, nails=nails, detail=detail,
                                bow=rng.normal() * 0.006, sweep=rng.uniform(-0.004, 0.012)))
        y += h
    return pieces


def deck(m, merge, x0, x1, z0, z1, y, *, along="x", pw=(0.17, 0.24), t=0.05, colors=None, gap=0.012, replace=0.08,
         nails=2, detail=1.0, overhang=0.04, missing=0.0, T_=None):
    """Floor/deck planks covering [x0,x1]x[z0,z1] with top at y. along = plank length direction ('x' or 'z')."""
    rng = m.rng
    T_ = T_ or T()
    colors = colors or [TP["wood"], TP["wood_lt"], TP["wood_dk"], TP["wood_br"], TP["wood_silver"]]
    pieces = []
    if along == "x":
        s, s_end = z0, z1
    else:
        s, s_end = x0, x1
    while s < s_end - 0.02:
        w = rng.uniform(*pw)
        if s_end - (s + w) < pw[0] * 0.5:
            w = s_end - s
        c = s + w / 2
        col = colors[int(rng.integers(len(colors)))]
        if rng.random() < replace:
            col = rng.choice([TP["wood_new"], TP["wood_new2"]])
        if rng.random() < missing:
            s += w
            continue
        e0 = rng.uniform(-overhang, overhang * 1.5)
        e1 = rng.uniform(-overhang, overhang * 1.5)
        dy = rng.normal() * 0.004
        if along == "x":
            a, b = (x0 - e0, y - t / 2 + dy, c), (x1 + e1, y - t / 2 + dy, c)
        else:
            a, b = (c, y - t / 2 + dy, z0 - e0), (c, y - t / 2 + dy, z1 + e1)
        pieces.append(board(m, merge, T_.p(a), T_.p(b), w - gap, t, T_.v((0, 1, 0)), col, nails=nails, detail=detail,
                            bow=rng.uniform(-0.002, 0.008), twist=rng.normal() * 0.6))
        s += w
    return pieces


def rail_run(m, merge, pts, *, h=0.85, post_r=0.065, color=None, rails=2, post_every=1.4, sea_y=None, foot_y=None,
             detail=1.0, rail_w=0.14, start_post=True, end_post=True, rail_t=0.065):
    """A railing along a polyline of deck-top points: square posts, a chunky top rail and a mid rail, all a bit
    crooked. foot_y extends the posts down (e.g. to fasten on the deck edge)."""
    rng = m.rng
    color = color or TP["wood"]
    pts = [np.asarray(p, float) for p in pts]
    pieces = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        L = np.linalg.norm(b - a)
        n = max(1, int(round(L / post_every)))
        for k in range(n + 1):
            if (k == 0 and (i > 0 or not start_post)) or (k == n and i == len(pts) - 2 and not end_post):
                continue
            pp = a + (b - a) * k / n
            lean = np.array([rng.normal() * 0.02, 0, rng.normal() * 0.02])
            fy = foot_y if foot_y is not None else -0.12
            pieces.append(post(m, merge, pp + np.array([0, fy, 0]), pp + np.array([0, h + rng.uniform(0.0, 0.06), 0]) + lean, post_r,
                               rng.choice([color, TP["wood_dk"], TP["wood_lt"]]), detail=detail))
        d = (b - a) / L
        side = np.cross([0, 1, 0], d)
        for r in range(rails):
            yy = h if r == 0 else h * (0.5 if rails == 2 else 1 - r / rails)
            off = side * (post_r + 0.012) * (1 if r else 0)
            ww = rail_w if r == 0 else rail_w * 0.75
            sag = rng.uniform(0, 0.02)
            a2 = a + np.array([0, yy + rng.normal() * 0.01, 0]) + off - d * 0.06
            b2 = b + np.array([0, yy + rng.normal() * 0.01, 0]) + off + d * 0.06
            upn = np.array([0, 1.0, 0]) if r == 0 else side
            pieces.append(board(m, merge, a2, b2, ww, rail_t if r == 0 else rail_t * 0.8, upn, rng.choice([color, TP["wood_lt"], TP["wood_silver"]]),
                                bow=sag, nails=1 if r else 0, detail=detail))
    return pieces


# ----------------------------------------------------------------------------------------------------------------
# roofs


def tin_roof(m, merge, e0, e1, r0, r1, *, sheet_w=(0.7, 0.85), over=0.18, colors=None, patch=0.15, rust=0.4, sag=0.04,
             detail=1.6, nails=True, res=0.0085):
    """Corrugated sheets laid on the quad (eave e0->e1, ridge r0->r1): ridges run down-slope, sheets overlap and
    are slightly askew; some are rusty or patched; the roof sags in the middle."""
    rng = m.rng
    e0, e1, r0, r1 = (np.asarray(v, float) for v in (e0, e1, r0, r1))
    colors = colors or [TP["tin"], TP["tin_dk"], TP["tin_lt"]]
    L = np.linalg.norm(e1 - e0)
    across = (e1 - e0) / L
    s = -0.05
    pieces = []
    while s < L + 0.02:
        w = rng.uniform(*sheet_w)
        if s + w > L + 0.05:
            w = L + 0.06 - s
        if w < 0.25:
            break
        t0, t1 = (s + w / 2) / L, (s + w / 2) / L
        e = e0 + (e1 - e0) * t0 - across * 0.0
        r = r0 + (r1 - r0) * t1
        down = e - r
        slope_len = np.linalg.norm(down) + over + 0.04
        down_n = down / np.linalg.norm(down)
        nrm = np.cross(down_n, across)
        if nrm[1] < 0:
            nrm = -nrm
        mid_s = (s + w / 2) / L
        sg = sag * math.sin(math.pi * np.clip(mid_s, 0, 1))
        c = (e + r) / 2 + down_n * (over / 2 - 0.02) - nrm * sg + nrm * rng.uniform(0, 0.012)
        Rm = np.stack([across, nrm, down_n], axis=1)
        Rm = rot_axis(nrm, rng.normal() * 1.4) @ rot_axis(across, rng.normal() * 0.8) @ Rm
        col = colors[int(rng.integers(len(colors)))]
        is_patch = rng.random() < patch
        if is_patch:
            col = rng.choice([TP["rust"], TP["red"], TP["rust_lt"], TP["teal_dk"]])
        dents = [(rng.uniform(-w / 2, w / 2), rng.uniform(-slope_len / 2, slope_len / 2), rng.uniform(0.08, 0.2), rng.uniform(0.005, 0.02)) for _ in range(rng.integers(0, 3))]
        p = m.piece(color=col, gloss=35, merge=merge, res=res, lumps=0.0012, lump_freq=6, mottle=0.1, detail=detail)
        p.add(Corrugated(c, (w / 2 + 0.03, slope_len / 2), Rm, sag=rng.uniform(0.0, 0.02), curl=rng.uniform(0, 0.03),
                         seed=int(rng.integers(0, 10 ** 6)), dents=dents))
        if rust:
            p.paint(patches(rng.uniform(1.5, 3.0), 0.42 - rust * 0.35, int(rng.integers(10 ** 5)), stretch=1.0 - 0.6 * np.abs(down_n)), mix(TP["rust"], col, 0.2), feather=0.01)
            p.paint(patches(rng.uniform(3, 5), 0.5 - rust * 0.3, int(rng.integers(10 ** 5))), mix(TP["rust_lt"], col, 0.3), feather=0.006)
            # streaks running down from the nail lines toward the eave
            for k in range(rng.integers(1, 4)):
                x = rng.uniform(-w / 2, w / 2)
                top = c + across * x - down_n * rng.uniform(0, slope_len / 2)
                p.paint(Capsule(top, c + across * x + down_n * slope_len / 2, 0.02, 0.035), mix(TP["rust"], col, 0.45), feather=0.02)
        if nails:
            for f in (-0.42, 0.0, 0.42):
                for k in range(3):
                    x = (k - 1) * w * 0.33 + rng.normal() * 0.01
                    pos = c + across * x + down_n * f * slope_len + nrm * 0.016
                    p.add(Sphere(pos, 0.011), k=0.004, color=TP["iron"])
        pieces.append(p)
        s += w - rng.uniform(0.05, 0.1)
    return pieces


def shake_roof(m, merge, e0, e1, r0, r1, *, colors=None, moss=0.3, detail=1.0, res=0.012, over=0.12, sag=0.05):
    """A slope of wooden shakes on the quad (eave e0->e1, ridge r0->r1), mossy in places."""
    rng = m.rng
    e0, e1, r0, r1 = (np.asarray(v, float) for v in (e0, e1, r0, r1))
    colors = colors or [TP["wood_dk"], TP["wood"], TP["wood_br"]]
    mid_e, mid_r = (e0 + e1) / 2, (r0 + r1) / 2
    across = (e1 - e0) / np.linalg.norm(e1 - e0)
    down = mid_e - mid_r
    Ls = np.linalg.norm(down) + over
    down_n = down / np.linalg.norm(down)
    nrm = np.cross(down_n, across)
    if nrm[1] < 0:
        nrm = -nrm
        across = -across
    Rm = np.stack([across, nrm, down_n], axis=1)
    hx = np.linalg.norm(e1 - e0) / 2 + 0.12
    seed = int(rng.integers(10 ** 5))
    p = m.piece(color=colors[0], gloss=25, merge=merge, res=res, lumps=0.003, lump_freq=5, mottle=0.1, detail=detail)
    sh = Shingles(mid_r - down_n * 0.02, hx, Ls, Rm, seed=seed, sag=sag)
    p.add(sh)
    for i, col in enumerate(colors[1:]):
        def sel(P, _i=i, _sh=sh):
            q = (P - _sh.c) @ _sh.R
            s_, r_, cx, col_ = _sh.cells(q)
            hsh = _h2(col_, r_, seed + 31)
            return np.where((hsh * len(colors)).astype(int) == _i + 1, -1.0, 1.0)
        p.paint(Func(sel, (-1e4,) * 3, (1e4,) * 3), col, feather=0.01)
    if moss:
        p.paint(patches(1.6, 0.45 - moss, seed + 5), TP["moss"], feather=0.02)
        p.paint(patches(3.5, 0.55 - moss, seed + 6), TP["algae_lt"], feather=0.01)
    return p


# ----------------------------------------------------------------------------------------------------------------
# openings


def window(m, merges, c, out, w, h, *, frame_color=None, paint=None, panes=(2, 2), shutters=None, crooked=None,
           sill=True, curtain=None, detail=1.2, glass_color=None, box=None, t=0.05):
    """Window centred at c on a wall with outward normal `out`. merges = dict(trim=..., glass=..., deco=...).
    Returns the glass centre (for window lights)."""
    rng = m.rng
    c = np.asarray(c, float)
    out = np.asarray(out, float)
    out = out / np.linalg.norm(out)
    side = np.cross([0, 1.0, 0], out)
    up = np.array([0, 1.0, 0])
    if crooked is None:
        crooked = rng.normal() * 2.0
    Rz = rot_axis(out, crooked)
    side, up = Rz @ side, Rz @ up
    fc = frame_color or TP["cream"]
    fw = 0.075
    trim = merges["trim"]
    # frame: head, sill-board, jambs
    for (a, b, ww) in (
        (c + up * (h / 2 + fw / 2) - side * (w / 2 + fw + 0.04), c + up * (h / 2 + fw / 2) + side * (w / 2 + fw + 0.04), fw * 1.25),
        (c - side * (w / 2 + fw / 2) - up * (h / 2), c - side * (w / 2 + fw / 2) + up * (h / 2), fw),
        (c + side * (w / 2 + fw / 2) - up * (h / 2), c + side * (w / 2 + fw / 2) + up * (h / 2), fw),
    ):
        board(m, trim, a + out * 0.045, b + out * 0.045, ww, 0.045, out, TP["wood"], paint=fc, peel=0.25, nails=0, detail=detail, knot=0)
    if sill:
        sa = c - up * (h / 2 + 0.03) - side * (w / 2 + fw + 0.07) + out * 0.07
        sb = c - up * (h / 2 + 0.03) + side * (w / 2 + fw + 0.07) + out * 0.07
        board(m, trim, sa, sb, 0.13, 0.045, up * 0.97 + out * 0.2, TP["wood"], paint=fc, peel=0.3, nails=0, detail=detail, knot=0)
    # glass: recessed pane (emissive)
    gcol = glass_color or TP["glass"]
    g = m.piece(color=gcol, gloss=235, mat=1, merge=merges["glass"], res=0.02, lumps=0.0008, mottle=0.03, ao=False, detail=0.3)
    g.add(Box(c + out * 0.0, (w / 2 + 0.01, h / 2 + 0.01, 0.015), frame(side, up) if False else np.stack([side, up, out], axis=1), round=0.006))
    # muntins
    nx, ny = panes
    mu = m.piece(color=fc, gloss=40, merge=trim, res=0.008, lumps=0.0015, detail=detail * 0.6)
    Rw = np.stack([side, up, out], axis=1)
    for i in range(1, nx):
        x = -w / 2 + w * i / nx
        mu.add(Box(c + side * x + out * 0.025, (0.016, h / 2, 0.016), Rw, round=0.006))
    for j in range(1, ny):
        y = -h / 2 + h * j / ny
        mu.add(Box(c + up * y + out * 0.025, (w / 2, 0.016, 0.016), Rw, round=0.006))
    if nx == 1 and ny == 1:
        mu.add(Box(c - up * (h / 2 - 0.01) + out * 0.02, (w / 2, 0.012, 0.012), Rw, round=0.005))
    if curtain:
        cu = m.piece(color=curtain, gloss=20, merge=merges.get("deco", trim), res=0.01, lumps=0.002, detail=0.6)
        for sx in (-1, 1):
            cc = c + side * sx * w * 0.32 - out * 0.03
            cu.add(Ellipsoid(cc + up * h * 0.05, (w * 0.14, h * 0.48, 0.02), Rw), k=0.01)
            for k in range(3):
                cu.sub(Capsule(cc + side * (k - 1) * w * 0.07 + out * 0.02 - up * h * 0.4, cc + side * (k - 1) * w * 0.07 + out * 0.02 + up * h * 0.45, 0.01), k=0.008)
    if shutters:
        for sx in (-1, 1):
            if rng.random() < 0.15:
                continue
            ang = rng.uniform(-8, 25) if rng.random() < 0.3 else rng.uniform(-3, 3)
            hinge = c + side * sx * (w / 2 + fw + 0.02) + out * 0.06
            sw = w / 2 + 0.03
            Rs = rot_axis(up, sx * ang)
            sd = Rs @ side * sx
            for k in range(3):
                bc = hinge + sd * (sw * (k + 0.5) / 3)
                board(m, merges.get("deco", trim), bc - up * h / 2 * 0.98, bc + up * h / 2 * 0.98, sw / 3 - 0.008, 0.035, Rs @ out, TP["wood"], paint=shutters,
                      peel=0.3, nails=1, detail=detail * 0.7, knot=0)
            zc = hinge + sd * sw / 2 + Rs @ out * 0.025
            board(m, merges.get("deco", trim), zc - sd * sw * 0.42 - up * h * 0.3, zc + sd * sw * 0.42 + up * h * 0.3, 0.06, 0.03, Rs @ out, TP["wood"], paint=shutters,
                  peel=0.3, nails=0, detail=detail * 0.5, knot=0)
    if box is not None:
        box(c - up * (h / 2 + 0.1) + out * 0.2, out, side)
    return c + out * 0.03


def door(m, merges, c, out, w, h, *, color=None, paint=None, peel=0.2, knob=True, crooked=None, detail=1.0, trim=None, window=False,
         open_deg=0.0):
    """Board-and-batten door, bottom-centre c on a wall facing `out`. Returns door centre."""
    rng = m.rng
    c = np.asarray(c, float)
    out = np.asarray(out, float)
    out = out / np.linalg.norm(out)
    side = np.cross([0, 1.0, 0], out)
    up = np.array([0, 1.0, 0])
    if crooked is None:
        crooked = rng.normal() * 1.2
    color = color or TP["wood_br"]
    fc = trim or TP["cream"]
    mg = merges["trim"]
    hinge = c - side * w / 2
    Rd = rot_axis(up, -open_deg)
    sd = Rd @ side
    od = Rd @ out
    nb = max(3, int(round(w / 0.19)))
    for k in range(nb):
        x = (k + 0.5) / nb * w
        b0 = hinge + sd * x + od * 0.03
        Rc = rot_axis(od, crooked)
        board(m, merges.get("door", mg), b0 + Rc @ (up * 0.02), b0 + Rc @ (up * (h - 0.03)), w / nb - 0.01, 0.045, od, color, paint=paint, peel=peel, nails=2,
              detail=detail, knot=0.3, nail_inset=0.2)
    for yy in (0.25, h - 0.3):
        a = hinge + sd * 0.08 + up * yy + od * 0.07
        board(m, merges.get("door", mg), a, a + sd * (w - 0.16), 0.11, 0.035, od, color, paint=paint, peel=peel, nails=2, detail=detail * 0.8, knot=0)
    a = hinge + sd * 0.1 + up * 0.3 + od * 0.07
    board(m, merges.get("door", mg), a, a + sd * (w - 0.2) + up * (h - 0.75), 0.1, 0.03, od, color, paint=paint, peel=peel, nails=0, detail=detail * 0.7, knot=0)
    # frame
    for (a, b, ww) in ((c - side * (w / 2 + 0.05), c - side * (w / 2 + 0.05) + up * (h + 0.05), 0.09),
                       (c + side * (w / 2 + 0.05), c + side * (w / 2 + 0.05) + up * (h + 0.05), 0.09),
                       (c + up * (h + 0.06) - side * (w / 2 + 0.12), c + up * (h + 0.06) + side * (w / 2 + 0.12), 0.11)):
        board(m, mg, a + out * 0.05, b + out * 0.05, ww, 0.05, out, TP["wood"], paint=fc, peel=0.3, nails=0, detail=detail, knot=0)
    if knob:
        kp = m.piece(color=TP["brass"], gloss=170, merge=merges.get("door", mg), res=0.006, lumps=0.001, detail=0.5)
        kc = hinge + sd * (w - 0.12) + up * 1.0 + od * 0.1
        kp.add(Sphere(kc, 0.032))
        kp.add(Capsule(kc - od * 0.05, kc, 0.012), k=0.006)
        kp.add(Box(kc - od * 0.04 - up * 0.02, (0.03, 0.08, 0.008), np.stack([sd, up, od], axis=1), round=0.006), k=0.004, color=TP["iron"])
        # hinges
        for yy in (0.25, h - 0.3):
            hc = hinge + sd * 0.15 + up * yy + od * 0.1
            kp.add(Box(hc, (0.15, 0.025, 0.008), np.stack([sd, up, od], axis=1), round=0.006), k=0.002, color=TP["iron"], gloss=60)
    return c + up * h / 2


def stovepipe(m, merge, base, height, r=0.075, lean=(0.0, 0.0), bends=1, color=None, detail=1.0):
    """A crooked tin stovepipe with a coolie-hat cap; returns the smoke socket position."""
    rng = m.rng
    base = np.asarray(base, float)
    color = color or TP["tin_dk"]
    pts = [base]
    n = 3 + bends
    for i in range(1, n + 1):
        f = i / n
        pts.append(base + np.array([lean[0] * f + rng.normal() * 0.03, height * f, lean[1] * f + rng.normal() * 0.03]))
    p = m.piece(color=color, gloss=60, merge=merge, res=0.012, lumps=0.002, mottle=0.1, detail=detail)
    p.add(Tube(pts, r, samples=4))
    for i in range(1, n):
        p.add(Torus(pts[i], r * 1.02, 0.012, look_rot(pts[i + 1] - pts[i - 1]) @ euler((0, 0, 0))), k=0.006)
    top = pts[-1]
    p.add(Cylinder(top + np.array([0, 0.06, 0]), r * 0.5, 0.06), k=0.01)
    p.add(Ellipsoid(top + np.array([0, 0.16, 0]), (r * 2.1, 0.05, r * 2.1)), k=0.01, color=TP["tin"])
    p.sub(Ellipsoid(top + np.array([0, 0.11, 0]), (r * 1.9, 0.04, r * 1.9)), k=0.01)
    p.paint(patches(4, 0.05, int(rng.integers(999))), TP["rust"], feather=0.01)
    p.paint(band(top[1] - 0.25, top[1] + 0.3, 0.05, 5), shade(TP["iron"], 0.9), feather=0.05)  # soot
    # guy wire
    return top + np.array([0, 0.25, 0])


def stone_chimney(m, merge, base, height, w=0.45, lean=0.0, detail=1.0, colors=None):
    """Crooked stack of lumpy stones/bricks; returns smoke position."""
    rng = m.rng
    base = np.asarray(base, float)
    colors = colors or [TP["stone"], TP["stone_dk"], TP["stone_lt"], "#9b6a52"]
    p = m.piece(color=colors[0], merge=merge, res=0.016, lumps=0.006, lump_freq=6, dents=6, dent_size=0.04, mottle=0.1, detail=detail)
    y = 0.0
    off = np.zeros(3)
    rh = 0.13
    first = True
    while y < height:
        off = off + np.array([lean * rh + rng.normal() * 0.008, 0, rng.normal() * 0.008])
        for sx in (-1, 1):
            for sz in (-1, 1):
                sh = rng.uniform(-0.02, 0.02)
                cc = base + off + np.array([sx * w / 4 + sh, y + rh / 2, sz * w / 4 + rng.uniform(-0.02, 0.02)])
                bx = Box(cc, (w / 4 + 0.012, rh / 2 + 0.01, w / 4 + 0.012), (rng.normal() * 2, rng.normal() * 5, rng.normal() * 2), round=0.03)
                p.add(bx, k=0.01, color=colors[int(rng.integers(len(colors)))])
        y += rh
    top = base + off + np.array([0, height, 0])
    p.add(Box(top + np.array([0, 0.04, 0]), (w / 2 + 0.05, 0.05, w / 2 + 0.05), round=0.03), k=0.01, color=TP["stone_dk"])
    p.sub(Box(top + np.array([0, 0.1, 0]), (w / 2 - 0.1, 0.25, w / 2 - 0.1), round=0.03), k=0.01, color=TP["iron"])
    p.paint(band(top[1] - 0.2, top[1] + 0.3, 0.05, 6), shade(TP["iron"], 1.1), feather=0.05)
    return top + np.array([0, 0.2, 0])


# ----------------------------------------------------------------------------------------------------------------
# soft goods & small fittings


class Canvas(Prim):
    """A sagging canvas sheet: local X across (half hx), Z from 0 (top edge) to dz (front edge), Y = normal.
    Stripes of width sw get raised sewn seams (so decimation keeps the colour boundaries), the front edge is
    scalloped (valance)."""

    def __init__(self, c, hx, dz, rot=None, t=0.012, sag=0.06, billow=0.03, sw=0.0, seam=0.004, scallop=0.0, seed=0):
        super().__init__()
        self.c = np.asarray(c, float)
        self.R = euler(rot)
        self.hx, self.dz, self.t, self.sag, self.billow, self.sw, self.seam, self.scallop = hx, dz, t, sag, billow, sw, seam, scallop
        self.ph = (seed % 101) * 0.3

    def sdf(self, P):
        q = (P - self.c) @ self.R
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        u = np.clip(x / self.hx, -1, 1)
        v = np.clip(z / self.dz, 0, 1.2)
        off = -self.sag * (1 - u * u) * v - self.billow * np.sin(np.pi * v) + 0.006 * np.sin(x * 9 + self.ph) * v
        th = self.t
        if self.sw:
            g = (x / self.sw) - np.round(x / self.sw)
            th = th + self.seam * np.exp(-(g * self.sw / 0.009) ** 2)
        d = (np.abs(y - off) - th) * 0.8
        zl = self.dz + (self.scallop * np.abs(np.sin(np.pi * x / max(self.sw, 0.25))) if self.scallop else 0.0)
        de = np.maximum(np.abs(x) - self.hx, np.maximum(-z, z - zl))
        return np.maximum(d, de)

    def stripe_mask(self, odd=True):
        def f(P):
            q = (P - self.c) @ self.R
            k = np.floor(q[:, 0] / self.sw + 0.5).astype(int)
            return np.where((k % 2 == 1) == odd, -1.0, 1.0)
        return Func(f, (-1e4,) * 3, (1e4,) * 3)

    def bounds(self):
        c = self.c + self.R @ np.array([0, 0, self.dz / 2])
        return _aabb(c, self.R, (self.hx + 0.02, self.sag + self.billow + self.t + 0.04, self.dz / 2 + self.scallop + 0.03))


def ice_heap(m, merge, c, half, rot=None, chunks=14, detail=1.0, res=0.012, color=None):
    """Crushed ice heaped in a tray: lumpy pale slab with glassy cube chunks poking out."""
    rng = m.rng
    c = np.asarray(c, float)
    color = color or TP["ice"]
    p = m.piece(color=color, gloss=215, merge=merge, res=res, lumps=0.011, lump_freq=16, mottle=0.05, detail=detail)
    R = euler(rot)
    p.add(Box(c, half, R, round=min(half[1], 0.05)))
    for i in range(chunks):
        lp = np.array([rng.uniform(-1, 1) * half[0] * 0.92, half[1] * rng.uniform(0.5, 1.1), rng.uniform(-1, 1) * half[2] * 0.85])
        s = rng.uniform(0.022, 0.045)
        p.add(Box(c + R @ lp, (s, s * 0.8, s), R @ euler((rng.uniform(0, 90), rng.uniform(0, 90), rng.uniform(0, 90))), round=s * 0.35), k=0.01,
              color=rng.choice([color, "#cfe3ea", "#eef6f7"]))
    p.paint(patches(6, 0.2, int(rng.integers(999))), "#bcd6e0", feather=0.01)
    return p


def chain(m, merge, a, b, link=0.035, color=None, detail=0.5, sag=0.0):
    """A chain of little torus links from a to b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = np.linalg.norm(b - a)
    n = max(2, int(L / (link * 1.6)))
    p = m.piece(color=color or TP["iron"], gloss=90, merge=merge, res=min(0.005, link * 0.12), lumps=0.0008, detail=detail)
    d = (b - a) / L
    for i in range(n):
        t = (i + 0.5) / n
        c = a + (b - a) * t + np.array([0, -sag * 4 * t * (1 - t), 0])
        R = frame(d, np.cross(d, [1, 0, 0.3]) if i % 2 else np.cross(d, [0.3, 0, 1]))
        p.add(Torus(c, link * 0.55, link * 0.17, R @ euler((0, 0, 90))))
    return p


def hang_lantern(m, merges, top, size=1.0, frame_color=None, glass=None, detail=1.0):
    """Ship's lantern hanging from `top` (ring at the top). merges: metal=, glass=. Returns glass centre."""
    s = size
    top = np.asarray(top, float)
    fc = frame_color or TP["iron"]
    g = m.piece(color=glass or TP["lamp"], gloss=230, mat=1, merge=merges["glass"], res=0.008, lumps=0.001, mottle=0.03, ao=False, detail=0.4 * detail)
    gc = top + np.array([0, -0.27 * s, 0])
    g.add(Cylinder(gc, 0.085 * s, 0.1 * s, round=0.03 * s))
    p = m.piece(color=fc, gloss=90, merge=merges["metal"], res=0.007, lumps=0.0015, dents=2, detail=detail)
    p.add(Torus(top + np.array([0, -0.02 * s, 0]), 0.035 * s, 0.009 * s, rot=(90, 0, 0)))
    p.add(Cylinder(top + np.array([0, -0.12 * s, 0]), 0.07 * s, 0.025 * s, round=0.012 * s), k=0.01)
    p.add(Capsule(top + np.array([0, -0.1 * s, 0]), top + np.array([0, -0.16 * s, 0]), 0.1 * s, 0.11 * s), k=0.02)
    p.add(Cylinder(top + np.array([0, -0.4 * s, 0]), 0.105 * s, 0.03 * s, round=0.012 * s), k=0.01)
    for a in range(0, 360, 90):
        r = np.radians(a + 45)
        d = np.array([np.cos(r), 0, np.sin(r)]) * 0.1 * s
        p.add(Capsule(top + d + np.array([0, -0.16 * s, 0]), top + d + np.array([0, -0.39 * s, 0]), 0.011 * s), k=0.006)
    p.add(Torus(gc, 0.098 * s, 0.009 * s), k=0.004)
    p.paint(patches(5, 0.15, 3), TP["rust"], feather=0.01)
    return gc


def brass_till(m, merge, c, yaw=0.0, detail=1.0):
    """Old brass cash register, bottom-centre c, facing +Z rotated by yaw. Returns the top-front point."""
    t = T(c, yaw)
    p = m.piece(color=TP["brass"], gloss=170, merge=merge, res=0.006, lumps=0.0015, dents=4, dent_size=0.015, detail=detail)
    p.add(Box(t.p(0, 0.09, 0), (0.18, 0.09, 0.15), t.r(), round=0.02))
    p.add(Box(t.p(0, 0.2, -0.04), (0.17, 0.07, 0.11), t.r((-25, 0, 0)), round=0.02), k=0.01)
    p.add(Box(t.p(0, 0.33, -0.08), (0.11, 0.05, 0.03), t.r(), round=0.015), k=0.01)  # number flag box
    p.add(Box(t.p(0, 0.06, 0.155), (0.16, 0.045, 0.01), t.r(), round=0.008), k=0.004, color=shade(TP["brass"], 0.8))  # drawer
    for i in range(4):
        for j in range(3):
            p.add(Cylinder(t.p(-0.12 + i * 0.08, 0.255 - j * 0.03, 0.0 + j * 0.05 - 0.04), 0.017, 0.012, t.r((65, 0, 0)), round=0.006), k=0.003,
                  color=TP["cream"], gloss=150)
    p.add(Capsule(t.p(0.2, 0.18, 0.0), t.p(0.26, 0.18, 0.0), 0.012), k=0.006)
    p.add(Capsule(t.p(0.26, 0.18, 0.0), t.p(0.26, 0.1, 0.06), 0.01), k=0.006)
    p.add(Sphere(t.p(0.26, 0.1, 0.07), 0.02), k=0.004, color=TP["red_dk"])
    p.paint(patches(6, 0.25, 7), "#8e8a52", feather=0.006)  # verdigris
    return t.p(0, 0.38, 0.05)


# ----------------------------------------------------------------------------------------------------------------
# a whole shack body


class Shack:
    """Walls + roof + trim of a small timber building centred at the origin (floor y=0), footprint |x|<=hx, |z|<=hz.
    ridge = 'x' or 'z' (ridge direction). Walls 'v' (board & batten) or 'h' (clapboard). openings = {side: [(s0, s1,
    y0, y1)]} with s measured along the wall from its start corner (see wall_frame). roof = 'tin' | 'shake'."""

    SIDES = ("front", "right", "back", "left")

    def __init__(self, m, hx, hz, eave, ridge_y, *, ridge="x", walls="v", colors=None, paint=None, peel=0.2, replace=0.08,
                 trim=None, openings=None, roof="tin", roof_colors=None, rust=0.4, sag=0.05, ov=0.35, ov_gable=0.3,
                 lean=0.0, merge_walls="walls", merge_trim="trim", merge_roof="roof", detail=1.0, moss=0.3, skip_sides=(),
                 front_ov=None):
        self.m, self.hx, self.hz, self.eave, self.ridge_y, self.ridge = m, hx, hz, eave, ridge_y, ridge
        colors = colors or [TP["wood"], TP["wood_dk"], TP["wood_lt"], TP["wood_silver"]]
        openings = openings or {}
        trim = trim or TP["cream"]
        self.trim = trim
        for side in self.SIDES:
            if side in skip_sides:
                continue
            p0, p1, out, L = self.wall_frame(side)
            gab = self.is_gable(side)
            if gab:
                def top(s, L=L):
                    return eave + (ridge_y - eave) * (1 - abs(s - L / 2) / (L / 2))
            else:
                top = eave
            ops = openings.get(side, [])
            if walls == "v":
                vboard_wall(m, merge_walls, p0, p1, 0.0, top, out, colors, paint=paint, peel=peel, replace=replace, openings=ops,
                            detail=detail, lean=lean)
            else:
                hboard_wall(m, merge_walls, p0, p1, 0.0, top, out, colors, paint=paint, peel=peel, replace=replace, openings=ops,
                            detail=detail)
        # corner boards + skirt
        for sx in (-1, 1):
            for sz in (-1, 1):
                x, z = sx * (hx + 0.03), sz * (hz + 0.03)
                board(m, merge_trim, (x, -0.05, z), (x, eave + 0.02, z), 0.14, 0.05, (sx, 0, sz), TP["wood"], paint=trim,
                      peel=peel * 1.2 + 0.05, nails=2, detail=detail)
        for side in self.SIDES:
            if side in skip_sides:
                continue
            p0, p1, out, L = self.wall_frame(side)
            a = np.array([p0[0], 0.1, p0[1]]) + out * 0.05
            b = np.array([p1[0], 0.1, p1[1]]) + out * 0.05
            board(m, merge_trim, a, b, 0.2, 0.04, out, TP["wood_dk"], nails=0, detail=0.6 * detail)
        # roof
        self.roof_planes = []
        if ridge == "x":
            ye = eave - ov * (ridge_y - eave) / hz
            fo = ov if front_ov is None else front_ov
            for sz in (-1, 1):
                o = fo if sz > 0 else ov
                yo = eave - o * (ridge_y - eave) / hz
                e0 = np.array([-sz * (hx + ov_gable), yo, sz * (hz + o)])
                e1 = np.array([sz * (hx + ov_gable), yo, sz * (hz + o)])
                r0 = np.array([-sz * (hx + ov_gable), ridge_y + 0.04, 0])
                r1 = np.array([sz * (hx + ov_gable), ridge_y + 0.04, 0])
                self.roof_planes.append((e0, e1, r0, r1))
        else:
            ye = eave - ov * (ridge_y - eave) / hx
            for sx in (-1, 1):
                e0 = np.array([sx * (hx + ov), ye, sx * (hz + ov_gable)])
                e1 = np.array([sx * (hx + ov), ye, -sx * (hz + ov_gable)])
                r0 = np.array([0, ridge_y + 0.04, sx * (hz + ov_gable)])
                r1 = np.array([0, ridge_y + 0.04, -sx * (hz + ov_gable)])
                self.roof_planes.append((e0, e1, r0, r1))
        for (e0, e1, r0, r1) in self.roof_planes:
            if roof == "tin":
                tin_roof(m, merge_roof, e0, e1, r0, r1, colors=roof_colors, rust=rust, sag=sag, detail=detail * 1.3)
            else:
                shake_roof(m, merge_roof, e0, e1, r0, r1, colors=roof_colors, moss=moss, detail=detail * 1.3, sag=sag)
            # fascia along the eave
            d = (e1 - e0) / np.linalg.norm(e1 - e0)
            out = np.cross([0, 1, 0], d)
            if out @ (e0 - r0) < 0:
                out = -out
            board(m, merge_trim, e0 + np.array([0, -0.09, 0]) - out * 0.02, e1 + np.array([0, -0.09, 0]) - out * 0.02, 0.15, 0.045, out, TP["wood"],
                  paint=trim, peel=peel * 1.2 + 0.05, nails=2, detail=0.8 * detail)
        # ridge roll
        if ridge == "x":
            a, b = np.array([-(hx + ov_gable + 0.05), ridge_y + 0.08, 0]), np.array([hx + ov_gable + 0.05, ridge_y + 0.08, 0])
        else:
            a, b = np.array([0, ridge_y + 0.08, -(hz + ov_gable + 0.05)]), np.array([0, ridge_y + 0.08, hz + ov_gable + 0.05])
        rr = m.piece(color=(roof_colors or [TP["tin_dk"]])[0] if roof == "tin" else TP["wood_dk"], gloss=40, merge=merge_roof, res=0.012,
                     lumps=0.002, detail=0.5 * detail)
        rr.add(Tube([a, (a + b) / 2 + np.array([0, -0.025, 0]), b], 0.07, samples=4))
        if roof == "tin":
            rr.paint(patches(2, 0.1, 4), TP["rust"], feather=0.02)
        # barge boards on the gable ends
        for (e0, e1, r0, r1) in self.roof_planes:
            for e, r in ((e0, r0), (e1, r1)):
                if ridge == "x":
                    outv = np.array([np.sign(e[0]), 0, 0])
                else:
                    outv = np.array([0, 0, np.sign(e[2])])
                board(m, merge_trim, e + np.array([0, -0.08, 0]) + outv * 0.03, r + np.array([0, -0.06, 0]) + outv * 0.03, 0.18, 0.05, outv, TP["wood"],
                      paint=trim, peel=peel * 1.2 + 0.05, nails=2, detail=0.8 * detail)

    def is_gable(self, side):
        return (self.ridge == "x" and side in ("left", "right")) or (self.ridge == "z" and side in ("front", "back"))

    def wall_frame(self, side):
        hx, hz = self.hx, self.hz
        if side == "front":
            return (-hx, hz), (hx, hz), np.array([0, 0, 1.0]), 2 * hx
        if side == "back":
            return (hx, -hz), (-hx, -hz), np.array([0, 0, -1.0]), 2 * hx
        if side == "right":
            return (hx, hz), (hx, -hz), np.array([1.0, 0, 0]), 2 * hz
        return (-hx, -hz), (-hx, hz), np.array([-1.0, 0, 0]), 2 * hz

    def at(self, side, s, y, off=0.03):
        """Point on the outside face of a wall at distance s along it, height y."""
        p0, p1, out, L = self.wall_frame(side)
        p0 = np.array([p0[0], y, p0[1]])
        p1 = np.array([p1[0], y, p1[1]])
        return p0 + (p1 - p0) * (s / L) + out * off, out

    def roof_y(self, x, z):
        if self.ridge == "x":
            return self.ridge_y - abs(z) * (self.ridge_y - self.eave) / self.hz
        return self.ridge_y - abs(x) * (self.ridge_y - self.eave) / self.hx


def stilts(m, merge, xs, zs, top_y, bottom_y, r=0.13, braces=True, sea_y=None, detail=1.0):
    """Grid of crooked stilts under a floor (with braces); sea_y adds the algae band."""
    rng = m.rng
    tops = []
    for x in xs:
        for z in zs:
            top = (x + rng.normal() * 0.03, top_y, z + rng.normal() * 0.03)
            if sea_y is not None:
                piling(m, merge, top, bottom_y, r * rng.uniform(0.9, 1.1), lean=(rng.normal() * 0.12, rng.normal() * 0.12), sea_y=sea_y, barnacles=8,
                       detail=detail)
            else:
                post(m, merge, (top[0] + rng.normal() * 0.08, bottom_y, top[2] + rng.normal() * 0.08), top, r, rng.choice([TP["wood_dk"], TP["wood"]]),
                     square=False, detail=detail * 0.6)
            tops.append(np.array(top))
    if braces:
        for x in xs:
            a = np.array([x, top_y - 0.3, zs[0]])
            b = np.array([x, max(bottom_y + 0.4, top_y - 1.6), zs[-1]])
            board(m, merge, a + (0.14, 0, 0), b + (0.14, 0, 0), 0.16, 0.06, (1, 0, 0), TP["wood_dk"], nails=0, detail=0.4 * detail, knot=0)
    return tops


class Rowboat(Prim):
    """Small clinker rowboat, hollow, upright: length 2*hl along local Z (bow +Z), beam 2*hb, depth d below the
    gunwale (local y = 0 at the gunwale)."""

    def __init__(self, c, hl=1.4, hb=0.62, d=0.42, rot=None, t=0.035):
        super().__init__()
        self.c = np.asarray(c, float)
        self.R = euler(rot)
        self.hl, self.hb, self.d, self.t = hl, hb, d, t

    def outer(self, q):
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        u = np.clip(z / self.hl, -1.2, 1.2)
        b = self.hb * np.where(u > 0, np.clip(1 - u ** 2, 0, 1) ** 0.6, np.clip(1 - 0.55 * u ** 4, 0, 1))
        b = np.maximum(b, 0.01)
        dd = self.d * (1 - 0.15 * u * u) + 0.08 * np.clip(u, 0, None) ** 3
        zz, yy = np.abs(x) / b, np.maximum(-y, 0) / dd
        n = 2.3
        r = (zz ** n + yy ** n) ** (1 / n) + 1e-9
        g = np.sqrt((r ** (1 - n) * zz ** (n - 1) / b) ** 2 + (r ** (1 - n) * yy ** (n - 1) / dd) ** 2) + 1e-6
        return (r - 1) / g

    def sdf(self, P):
        q = (P - self.c) @ self.R
        d = self.outer(q)
        sh = np.abs(d + self.t / 2) - self.t / 2
        sh = np.maximum(sh, q[:, 1] - 0.0 + 0.0 * q[:, 2])
        sh = np.maximum(sh, -q[:, 2] - self.hl * 0.98)
        return sh

    def bounds(self):
        return _aabb(self.c, self.R, (self.hb + 0.05, self.d + 0.15, self.hl + 0.1))
