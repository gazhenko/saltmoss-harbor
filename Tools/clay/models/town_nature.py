"""
Nature props for Saltmoss Harbor (hand-built tabletop-set style): wind-bent spruce, grass tufts, driftwood,
barnacled shore rocks, a seaweed pile and a tide pool. Also hosts the shared rock helpers used by town_sea.py.

Pivots: bottom-centre; rocks/tide pool sink ~0.2 m below y=0 so they bed into terrain.
"""
import math

import numpy as np
from clay import Prim, Func, Sphere, Ellipsoid, Capsule, Tube, Box, Cylinder, Torus, HalfSpace, euler, look_rot, gradient, fbm, shade, mix, rgb
from kit_town import TownModel, TP, frame, rot_axis, patches, band, below

MODELS = {}

# extra nature palette (muted plasticine)
NP = dict(
    spruce="#3e5a40", spruce_dk="#2f4834", spruce_lt="#58744f", spruce_tip="#6f8a5c",
    bark="#5d5045", bark_dk="#463c34", bark_lt="#7a6b5d",
    blade="#7d9455", blade_dk="#5b7340", blade_lt="#97a964", straw="#bea86e", straw_dk="#a08c58",
    drift="#ada79a", drift_dk="#938c80", drift_lt="#cfc9bb",
    rock="#868379", rock_dk="#6d6a63", rock_lt="#9d998e", rock_warm="#8f8676", rock_cool="#7b8083",
    lichen="#aa9d66", lichen_grey="#a6aa93", lichen_or="#c08a4a",
    kelp="#6b6234", kelp_dk="#544b28", kelp_lt="#857a42", wrack="#5f5a2c", bladder="#8a7c43",
    pool="#2d4e4d", star="#c8683a", anemone="#7ba06b", anemone_tip="#d4848a", pebble="#a09a8d",
    guano="#ebe7dc",
)


# ----------------------------------------------------------------------------------------------------------------
# shared helpers


class Chunk(Prim):
    """Faceted rock lump: a rounded ellipsoid mass (radii r) sliced by random knife cuts (planes), soft-edged by k
    (log-sum-exp smooth max). box=True adds six near-axis cuts for blockier stone."""

    def __init__(self, c, r, n=9, k=0.04, rot=None, seed=0, cut=(0.68, 0.9), box=False, boxd=(0.88, 1.0)):
        super().__init__()
        rng = np.random.default_rng(seed)
        r = np.asarray(r, float)
        rn = rng.normal(size=(n, 3))
        rn /= np.linalg.norm(rn, axis=1, keepdims=True)
        N, D = [rn], [np.sqrt(((rn * r) ** 2).sum(1)) * rng.uniform(*cut, n)]
        if box:
            ax = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float) + rng.normal(size=(6, 3)) * 0.12
            ax /= np.linalg.norm(ax, axis=1, keepdims=True)
            N.append(ax)
            D.append(np.sqrt(((ax * r) ** 2).sum(1)) * rng.uniform(*boxd, 6))
        self.N = np.vstack(N)
        self.D = np.concatenate(D)
        self.c = np.asarray(c, float)
        self.R = euler(rot)
        self.k = k
        self.r = r

    def _terms(self, q):
        k0 = np.linalg.norm(q / self.r, axis=1)
        k1 = np.linalg.norm(q / (self.r * self.r), axis=1)
        yield k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        for n, d in zip(self.N, self.D):
            yield q @ n - d

    def sdf(self, P):
        q = (P - self.c) @ self.R
        m = None
        for x in self._terms(q):
            m = x if m is None else np.maximum(m, x)
        s = np.zeros(len(q))
        for x in self._terms(q):
            s += np.exp(np.minimum((x - m) / self.k, 0))
        return m + self.k * np.log(s)

    def bounds(self):
        e = np.abs(self.R) @ (self.r * 1.02 + self.k * 3)
        return self.c - e, self.c + e


def surface_points(f, lo, hi, n, rng, cond=None, iters=10, tol=0.01):
    """Random points on the zero set of f inside [lo,hi] (Newton projection), with normals; cond(P,N)->mask."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    P = rng.uniform(lo, hi, size=(max(n * 12, 64), 3))
    for _ in range(iters):
        d = f(P)
        g = gradient(f, P)
        P = P - g * d[:, None]
    d = f(P)
    ok = np.abs(d) < tol
    P = P[ok]
    N = gradient(f, P)
    if cond is not None and len(P):
        mk = cond(P, N)
        P, N = P[mk], N[mk]
    idx = rng.permutation(len(P))[:n]
    return P[idx], N[idx]


def barnacles(m, merge, f, lo, hi, n, rng, *, size=(0.014, 0.03), cond=None, res=0.006, detail=1.0, mussels=0.25, tris=60):
    """Little volcano barnacles (and some blue-black mussels) pressed onto the surface of sdf f."""
    P, N = surface_points(f, lo, hi, n, rng, cond)
    if not len(P):
        return None
    out = []
    for c, nrm in zip(P, N):
        p = m.piece(color=TP["barnacle"], gloss=60, merge=merge, res=res, lumps=0.0008, mottle=0.08, detail=detail, decimate=tris)
        out.append(p)
        if rng.random() < mussels:
            t = np.cross(nrm, [0, 1, 0])
            if np.linalg.norm(t) < 1e-3:
                t = np.array([1.0, 0, 0])
            sz = rng.uniform(*size) * 1.3
            R = frame(rot_axis(nrm, rng.uniform(0, 360)) @ t, nrm)
            p.add(Ellipsoid(c + nrm * sz * 0.2, (sz * 1.7, sz * 0.55, sz * 0.8), R), color=TP["mussel"], gloss=170)
            p.add(Ellipsoid(c + nrm * sz * 0.2 + R[:, 2] * sz * 1.0, (sz * 1.5, sz * 0.5, sz * 0.7), R @ euler((0, 25, 0))), k=sz * 0.2,
                  color=TP["mussel"], gloss=170)
            continue
        # a little crusty cluster of barnacles
        nb = int(rng.integers(3, 7))
        for j in range(nb):
            br = rng.uniform(*size) * (1.0 if j == 0 else rng.uniform(0.55, 0.9))
            off = np.cross(nrm, rng.normal(size=3))
            off = off / (np.linalg.norm(off) + 1e-9) * (0 if j == 0 else size[1] * rng.uniform(1.2, 2.6))
            R = frame(np.cross(nrm, [0.3, 1, 0.2]) + 1e-6, nrm)
            cc = c + off
            p.add(Cylinder(cc + nrm * br * 0.25, br, br * 0.55, R, round=br * 0.5), k=br * 0.4,
                  color=TP["barnacle"] if rng.random() < 0.6 else TP["barnacle_dk"])
            p.sub(Sphere(cc + nrm * br * 0.9, br * 0.3), k=br * 0.15, color="#6f6a58")
    return out


def ribbon(p, pts, nrms, width, thick, k=None, color=None, gloss=None):
    """A flat strap (kelp blade, wrack) through pts with face normals nrms: chain of flattened ellipsoids."""
    pts = np.asarray(pts, float)
    nrms = np.asarray(nrms, float)
    widths = np.broadcast_to(np.asarray(width, float), (len(pts),))
    k = thick * 1.5 if k is None else k
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        L = np.linalg.norm(b - a)
        if L < 1e-5:
            continue
        nn = nrms[i] + nrms[i + 1]
        R = frame(b - a, nn)
        w = (widths[i] + widths[i + 1]) / 2
        p.add(Ellipsoid((a + b) / 2, (L * 0.75, thick, w), R), k=k, color=color, gloss=gloss)


def drape(f, start, direction, n, step, rng, lift=0.02, wander=0.25, grav=0.6):
    """Walk a strap over surface f from `start`, heading `direction` and pulled downhill: returns pts, normals."""
    pts, nrms = [], []
    p = np.asarray(start, float)[None, :]
    d = np.asarray(direction, float)
    for i in range(n):
        for _ in range(6):
            dist = f(p)
            g = gradient(f, p)
            p = p - g * (dist - lift)[:, None]
        g = gradient(f, p)[0]
        pts.append(p[0].copy())
        nrms.append(g)
        # move along the tangent plane: blend direction with downhill
        down = np.array([0, -1.0, 0]) - g * (-g[1])
        d = d - g * (d @ g)
        d = d / (np.linalg.norm(d) + 1e-9) * (1 - grav) + down / (np.linalg.norm(down) + 1e-9) * grav
        d = d + rng.normal(size=3) * wander
        d = d - g * (d @ g)
        d = d / (np.linalg.norm(d) + 1e-9)
        p = p + d[None, :] * step
    return np.array(pts), np.array(nrms)


def weed_skin(m, merge, f, lo, hi, top, *, thick=0.04, base=-0.25, seed=0, res=0.012, detail=0.8, ragged=0.15, freq=3.0):
    """A coat of glossy bladderwrack pressed onto the foot of a surface f (a lumpy shell hugging it) with a ragged,
    drippy top edge: the low-tide weed line."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)

    def g(P):
        d = f(P)
        n1 = fbm(P * freq, 3, seed)
        n2 = fbm(P * freq * 3.1, 2, seed + 1)
        # ragged top with dangling tongues, rising and falling around the rock
        edge = top + ragged * (fbm(P * np.array([freq * 1.4, 0.3, freq * 1.4]), 2, seed + 2) * 2.2
                               + fbm(P * np.array([freq * 0.35, 0.1, freq * 0.35]), 1, seed + 3) * 3.0)
        t = thick * (0.55 + 0.9 * np.clip(n1 + 0.5, 0, 1.2)) + thick * 0.35 * np.maximum(n2, 0)
        t = t * np.clip((edge - P[:, 1]) / (thick * 3) + 0.35, 0.35, 1.0)
        return np.maximum.reduce([d - t, -(d + 0.01), P[:, 1] - edge, base - P[:, 1]])
    p = m.piece(color=NP["wrack"], gloss=185, merge=merge, res=res, lumps=0.0015, lump_freq=10, mottle=0.1, detail=detail)
    p.add(Func(g, lo, hi))
    p.paint(patches(freq * 0.8, 0.0, seed + 5), NP["kelp"], feather=0.01)
    p.paint(patches(freq * 1.3, 0.2, seed + 6), NP["kelp_dk"], feather=0.01)
    p.paint(patches(freq * 2.5, 0.28, seed + 7), NP["bladder"], feather=0.01)
    return p


def wrack_fringe(m, merge, f, c, r, rng, n, top=0.3, base=-0.2, tris=None):
    """Bladderwrack/kelp clumps pressed around the foot of a rock (the low-tide fringe), with a few short straps."""
    c = np.asarray(c, float)
    r = np.asarray(r, float)
    sz = float(r.max())
    lo = np.array([c[0] - r[0] * 1.3, base, c[2] - r[2] * 1.3])
    hi = np.array([c[0] + r[0] * 1.3, top, c[2] + r[2] * 1.3])
    P, N = surface_points(f, lo, hi, n, rng, cond=lambda P, N: N[:, 1] > -0.6, iters=10)
    cols = [NP["wrack"], NP["kelp"], NP["kelp_dk"], NP["kelp_lt"], "#4f4a26"]
    out = []
    for i, (q, nn) in enumerate(zip(P, N)):
        p = m.piece(color=cols[i % len(cols)], gloss=180, merge=merge, res=0.006 + sz * 0.004, lumps=0.003 + sz * 0.002, lump_freq=12 / (0.5 + sz),
                    mottle=0.08, detail=0.5, decimate=tris or int(50 + sz * 15))
        rr = (0.06 + sz * 0.05) * rng.uniform(0.7, 1.3)
        side = np.cross(nn, [0, 1, 0])
        if np.linalg.norm(side) < 1e-3:
            side = np.array([1.0, 0, 0])
        Rt = frame(side, nn)
        # a flattened lobe of weed pressed on and draped down the surface, with bladder beads on it
        down = np.array([0, -1.0, 0]) - nn * (-nn[1])
        down = down / (np.linalg.norm(down) + 1e-9)
        Rt = np.stack([np.cross(nn, down), nn, down], axis=1)
        Rt = Rt @ euler((0, rng.normal() * 15, 0))
        p.add(Ellipsoid(q + nn * rr * 0.12 + down * rr * 0.4, (rr * 1.1, rr * 0.28, rr * 1.7), Rt))
        for j in range(int(rng.integers(1, 3))):
            off = Rt[:, 0] * rng.normal() * rr * 0.8 + down * rr * rng.uniform(0.6, 1.6)
            p.add(Ellipsoid(q + nn * rr * 0.1 + off, (rr * 0.45, rr * 0.22, rr * 1.0), Rt @ euler((0, rng.normal() * 25, 0))), k=rr * 0.3)
        for j in range(3):
            p.add(Sphere(q + nn * rr * 0.32 + Rt[:, 0] * rng.normal() * rr * 0.6 + down * rr * rng.uniform(0, 1.2), rr * 0.18), k=rr * 0.1,
                  color=NP["bladder"], gloss=200)
        out.append(p)
    return out


def rock_body(m, merge, c, r, *, seed, pieces=3, k=0.022, res=None, fissures=1, cut=(0.6, 0.86), box=False, ncut=11, colors=None, lumps=None, detail=1.0, sink=0.2, flat_base=True,
              lichen=0.3, wet=0.3, algae=0.3, gloss=40):
    """A faceted shore rock made of 1+pieces chunks; bottom flattened at -sink. Returns the Piece."""
    rng = np.random.default_rng(seed)
    c = np.asarray(c, float)
    r = np.asarray(r, float)
    colors = colors or [NP["rock"], NP["rock_dk"], NP["rock_lt"], NP["rock_warm"], NP["rock_cool"]]
    sz = float(r.max())
    res = res or float(np.clip(sz / 42, 0.008, 0.07))
    lumps = sz * 0.008 if lumps is None else lumps
    p = m.piece(color=colors[0], gloss=gloss, merge=merge, res=res, lumps=lumps, lump_freq=3.0 / max(sz, 0.3), dents=int(10 + sz * 6),
                dent_size=sz * 0.07, dent_depth=sz * 0.014, mottle=0.1, detail=detail)
    p.add(Chunk(c, r, n=ncut, k=k * sz, rot=(rng.normal() * 8, rng.uniform(0, 360), rng.normal() * 8), seed=int(rng.integers(1e6)),
                cut=cut, box=box), color=colors[0])
    for i in range(pieces):
        ang = rng.uniform(0, 2 * np.pi)
        off = np.array([math.cos(ang) * r[0] * rng.uniform(0.45, 0.8), rng.uniform(-0.35, 0.15) * r[1], math.sin(ang) * r[2] * rng.uniform(0.45, 0.8)])
        rr = r * rng.uniform(0.4, 0.62, 3)
        p.add(Chunk(c + off, rr, n=8, k=k * sz * 0.8, rot=(rng.normal() * 20, rng.uniform(0, 360), rng.normal() * 20), seed=int(rng.integers(1e6)),
                    cut=cut, box=box), k=k * sz * 1.2, color=colors[int(rng.integers(len(colors)))])
    # fissures: short knife cracks into the surface, darker inside
    for i in range(fissures):
        a = rng.uniform(0, 2 * np.pi)
        dirv = np.array([math.cos(a), rng.uniform(0.1, 0.6), math.sin(a)])
        dirv /= np.linalg.norm(dirv)
        cc = c + dirv * r * 0.95
        nrm = np.cross(dirv, rng.normal(size=3))
        nrm /= np.linalg.norm(nrm)
        Rf = frame(np.cross(nrm, dirv), nrm)
        p.sub(Box(cc, (sz * rng.uniform(0.25, 0.4), sz * 0.01 + 0.005, sz * 0.3), Rf, round=0.004), k=sz * 0.012, color=shade(colors[0], 0.6))
    # thumb presses / knife flats: shallow flattened scoops pressed into the surface
    f0 = p.sdf
    P, N = surface_points(f0, c - r * 1.1, c + r * 1.1, int(6 + sz * 7), rng, cond=lambda P, N: P[:, 1] > -sink + 0.05, iters=8)
    for q, nn in zip(P, N):
        rr = sz * rng.uniform(0.09, 0.2)
        Rt = frame(np.cross(nn, rng.normal(size=3)) + 1e-6, nn)
        p.sub(Ellipsoid(q + nn * rr * 0.32, (rr, rr * 0.4, rr * 0.8), Rt), k=sz * 0.02)
    if flat_base:
        p.inter(HalfSpace((0, -sink, 0), (0, -1, 0)), k=0.02)
    # colour: lichen on top, wet dark band and green algae low down
    if lichen:
        p.paint(patches(1.4 / sz, 0.42 - lichen * 0.5, int(rng.integers(1e5))), mix(NP["lichen_grey"], colors[0], 0.3), feather=0.01)
        p.paint(Func(lambda P, _y=c[1] + r[1] * 0.35: np.maximum(_y - P[:, 1], (0.5 - lichen * 0.35 - fbm(P * 3.0 / sz, 2, 77)) * 0.1),
                     (-1e4,) * 3, (1e4,) * 3), mix(NP["lichen"], colors[0], 0.35), feather=0.008)
    if wet:
        p.paint(below(-0.2 + (0.2 + min(sz * 0.2, 0.6)) * wet / 0.3, 0.05, 2.0, int(rng.integers(99))), shade(colors[0], 0.7), gloss=110, feather=0.05)
    if algae:
        p.paint(below(-0.2 + (0.12 + min(sz * 0.12, 0.35)) * algae / 0.3, 0.04, 3.0, int(rng.integers(99))), TP["algae"], gloss=130, feather=0.03)
    return p


# ----------------------------------------------------------------------------------------------------------------
# rocks


def _rock(name, r, seed, pieces, *, kelp=0, n_barn=12, budget=4000, lichen=0.3, **kw):
    def fn():
        m = TownModel(name, budget=budget, seed=seed)
        rng = np.random.default_rng(seed)
        c = np.array([0, r[1] * 0.62 - 0.2, 0])
        body = rock_body(m, "rock", c, r, seed=seed, pieces=pieces, lichen=lichen, detail=1.0, **kw)
        f = body.sdf
        sz = max(r)
        lo, hi = c - np.array(r) * 1.3, c + np.array(r) * 1.3
        lo[1] = -0.2
        hi[1] = min(0.35 + sz * 0.05, c[1] + r[1])
        barnacles(m, "barnacles", f, lo, hi, n_barn, rng, size=(0.014 + sz * 0.004, 0.026 + sz * 0.007), detail=0.3, res=0.005 + sz * 0.002,
                  cond=lambda P, N: (N[:, 1] > -0.4) & (P[:, 1] > -0.15))
        if kelp:
            rlo = np.array([-r[0] * 1.3, -0.25, -r[2] * 1.3])
            rhi = np.array([r[0] * 1.3, 0.2 + 0.15 * kelp + sz * 0.1, r[2] * 1.3])
            weed_skin(m, "kelp", f, rlo, rhi, 0.02 + 0.08 * kelp + sz * 0.06, thick=0.02 + sz * 0.012, seed=seed, res=0.008 + sz * 0.005,
                      freq=3.5 / (0.4 + sz * 0.5), ragged=0.08 + sz * 0.07)
        return m
    MODELS[f"town/{name}"] = fn


_rock("rock_a", (0.36, 0.26, 0.3), 11, 1, n_barn=5, budget=2500, box=True, cut=(0.55, 0.8), ncut=8)
_rock("rock_b", (0.62, 0.42, 0.5), 23, 2, kelp=1, n_barn=7, budget=3200, cut=(0.55, 0.8), ncut=12)
_rock("rock_c", (1.0, 0.5, 0.75), 37, 2, kelp=1, n_barn=9, budget=3800, box=True, cut=(0.58, 0.85), ncut=10, fissures=2)
_rock("rock_d", (1.45, 1.0, 1.15), 41, 3, kelp=2, n_barn=11, budget=4000, cut=(0.5, 0.8), ncut=15, fissures=2, k=0.016)
_rock("rock_e", (2.1, 1.25, 1.6), 59, 4, kelp=2, n_barn=12, budget=4000, lichen=0.4)


# ----------------------------------------------------------------------------------------------------------------
# wind-bent spruce


def tree_pine():
    m = TownModel("tree_pine", budget=4000, seed=71)
    rng = m.rng
    H = 5.0
    lean = 2.0  # leeward lean toward +x (prevailing wind from -x)
    spine = lambda t: np.array([lean * t ** 1.7 + 0.1 * math.sin(t * 7), H * t, 0.08 * math.sin(t * 5 + 1)])
    ts = np.linspace(0, 1, 9)
    pts = [spine(t) for t in ts]
    radii = [0.19 * (1 - t) ** 0.9 + 0.03 for t in ts]
    trunk = m.piece(color=NP["bark"], gloss=25, merge="trunk", res=0.018, lumps=0.008, lump_freq=4, dents=6, dent_size=0.06, dent_depth=0.008,
                    mottle=0.12, detail=0.6)
    trunk.add(Tube(pts, radii, samples=3))
    for i in range(5):
        a = i / 5 * 2 * np.pi + rng.normal() * 0.3
        d = np.array([math.cos(a), 0, math.sin(a)])
        trunk.add(Tube([np.array([0, 0.3, 0]) + d * 0.05, d * 0.25 + np.array([0, 0.05, 0]), d * rng.uniform(0.38, 0.52) + np.array([0, -0.04, 0])],
                       [0.12, 0.09, 0.055], samples=3), k=0.1)
    for i in range(7):
        a = rng.uniform(0, 2 * np.pi)
        t0 = rng.uniform(0.0, 0.45)
        p0, p1 = spine(t0), spine(t0 + rng.uniform(0.12, 0.25))
        r0 = 0.19 * (1 - t0) + 0.03
        o = np.array([math.cos(a), 0, math.sin(a)]) * r0
        trunk.sub(Capsule(p0 + o, p1 + o * 0.8, 0.018), k=0.012, color=NP["bark_dk"])
    trunk.paint(HalfSpace((-0.05, 0, 0), (1, 0, 0)), NP["bark_lt"], feather=0.08)
    # bare windward stubs (the wind has stripped that side)
    for t in (0.22, 0.34, 0.47, 0.58, 0.7):
        b = spine(t)
        trunk.add(Capsule(b, b + np.array([-0.3 - rng.uniform(0, 0.2), rng.uniform(-0.05, 0.12), rng.normal() * 0.18]), 0.025, 0.01), k=0.02,
                  color=NP["bark_lt"])
    # foliage: drooping finger-lobes in tiers, flagged to the lee side
    cols = [NP["spruce"], NP["spruce_dk"], NP["spruce_lt"], "#46624a"]
    tiers = np.linspace(0.2, 0.93, 9)
    for ti, t in enumerate(tiers):
        base = spine(t)
        R = 1.5 * (1 - t) ** 0.8 + 0.25
        fp = m.piece(color=cols[ti % 4], gloss=30, merge="foliage", res=0.024, lumps=0.012, lump_freq=6, dents=3, dent_size=0.08,
                     dent_depth=0.015, mottle=0.12, detail=1.0)
        nl = 6 if t < 0.8 else 4
        for j in range(nl):
            a = (j / nl) * 2 * np.pi + ti * 0.7 + rng.normal() * 0.25
            lee = math.cos(a)
            reach = R * (0.18 + 0.9 * (0.5 + 0.5 * lee) ** 1.5) * rng.uniform(0.85, 1.1)
            d = np.array([math.cos(a), 0, math.sin(a)])
            root = base + np.array([0, 0.05, 0])
            mid = root + d * reach * 0.5 + np.array([0, -0.06 - reach * 0.05, 0])
            tip = root + d * reach + np.array([0, -0.15 - reach * 0.22, 0])
            Rm = frame(d, [0, 1, 0])
            fp.add(Tube([root, mid, tip], [0.12, 0.13, 0.05], samples=3), k=0.06)
            fp.add(Ellipsoid(mid + np.array([0, 0.02, 0]), (reach * 0.42, 0.1 + R * 0.03, 0.15 + reach * 0.12), Rm @ euler((0, 0, -8))), k=0.08)
            # hanging tassels make a ragged silhouette under the lobe
            for q in range(2):
                f_ = rng.uniform(0.45, 0.95)
                hp = root + (tip - root) * f_ + np.cross(d, [0, 1, 0]) * rng.normal() * 0.08
                fp.add(Capsule(hp, hp + np.array([0.04, -rng.uniform(0.1, 0.2), 0]), 0.06, 0.036), k=0.05)
        # sunlit tops lighter, undersides darker
        fp.paint(HalfSpace(base + np.array([0, 0.04, 0]), (0, -1, 0)), NP["spruce_tip"] if ti % 2 else NP["spruce_lt"], feather=0.1)
        fp.paint(HalfSpace(base + np.array([0, -0.2, 0]), (0, 1, 0)), NP["spruce_dk"], feather=0.08)
    top = spine(1.0)
    tp = m.piece(color=NP["spruce_lt"], gloss=30, merge="foliage", res=0.022, lumps=0.01, detail=0.6)
    tp.add(Capsule(top - np.array([0, 0.35, 0]), top + np.array([0.2, 0.4, 0]), 0.16, 0.03))
    tp.add(Ellipsoid(top - np.array([-0.05, 0.3, 0]), (0.3, 0.12, 0.22)), k=0.08)
    return m


MODELS["town/tree_pine"] = tree_pine


# ----------------------------------------------------------------------------------------------------------------
# grass tufts


def _tuft(name, seed, n, h, spread, cols, dry=0.3, budget=1500):
    def fn():
        m = TownModel(name, budget=budget, seed=seed)
        rng = m.rng
        base = m.piece(color=NP["blade_dk"], gloss=25, merge="tuft", res=0.01, lumps=0.006, lump_freq=10, mottle=0.1, detail=0.25)
        base.add(Ellipsoid((0, 0.0, 0), (spread * 0.6, 0.06, spread * 0.55)))
        base.inter(HalfSpace((0, -0.03, 0), (0, -1, 0)), k=0.01)
        wind = np.array([1.0, 0, 0.25])
        for i in range(n):
            a = rng.uniform(0, 2 * np.pi)
            rr = spread * 0.45 * math.sqrt(rng.uniform(0, 1))
            root = np.array([math.cos(a) * rr, 0.0, math.sin(a) * rr])
            out = np.array([math.cos(a), 0, math.sin(a)]) * rng.uniform(0.15, 0.45) * (0.4 + rr / spread) + wind * rng.uniform(0.05, 0.3)
            hh = h * rng.uniform(0.5, 1.05) * (1.1 - 0.5 * rr / spread)
            droop = rng.uniform(0.0, 0.45)
            pts = [root + np.array([0, -0.02, 0]),
                   root + out * hh * 0.25 + np.array([0, hh * 0.42, 0]),
                   root + out * hh * 0.75 + np.array([0, hh * 0.8, 0]),
                   root + out * hh * (1.15 + droop) + np.array([0, hh * (1.0 - droop * 0.55), 0])]
            col = cols[int(rng.integers(len(cols)))]
            b = m.piece(color=col, gloss=35, merge="tuft", res=0.006, lumps=0.001, lump_freq=25, mottle=0.06, detail=1.0)
            w0 = rng.uniform(0.016, 0.024)
            b.add(Tube(pts, [w0, w0 * 0.85, w0 * 0.55, 0.004], samples=3))
            if rng.random() < dry:
                b.paint(HalfSpace(root + np.array([0, hh * rng.uniform(0.5, 0.75), 0]), (0, -1, 0)), NP["straw"] if rng.random() < 0.6 else NP["straw_dk"],
                        feather=0.05)
            else:
                b.paint(HalfSpace(root + np.array([0, hh * 0.3, 0]), (0, 1, 0)), shade(col, 0.72), feather=0.07)
        return m
    MODELS[f"town/{name}"] = fn


_tuft("grass_tuft_a", 101, 26, 0.42, 0.26, [NP["blade"], NP["blade_lt"], NP["blade_dk"]], dry=0.25)
_tuft("grass_tuft_b", 202, 30, 0.6, 0.32, [NP["blade"], NP["blade_dk"], "#869a5a"], dry=0.5)
_tuft("grass_tuft_c", 303, 20, 0.32, 0.22, [NP["blade_lt"], "#8fa660", NP["blade"]], dry=0.15)


# ----------------------------------------------------------------------------------------------------------------
# driftwood


def driftwood():
    m = TownModel("driftwood", budget=3800, seed=88)
    rng = m.rng
    L = 2.1
    xs = np.linspace(-L / 2, L / 2, 8)
    pts = [np.array([x, 0.15 + 0.03 * math.sin(x * 2.3) - 0.02 * x, 0.06 * math.sin(x * 1.7 + 1)]) for x in xs]
    radii = [0.17, 0.15, 0.135, 0.14, 0.125, 0.11, 0.1, 0.075]
    p = m.piece(color=NP["drift"], gloss=20, merge="log", res=0.012, lumps=0.006, lump_freq=6, dents=8, dent_size=0.05, dent_depth=0.006,
                mottle=0.1, detail=1.0)
    p.add(Tube(pts, radii, samples=3))
    # root end: splayed stubby roots
    root = pts[0]
    for i in range(6):
        a = i / 6 * 2 * np.pi + rng.normal() * 0.3
        d = np.array([-0.6, math.cos(a), math.sin(a)])
        d /= np.linalg.norm(d)
        p.add(Tube([root, root + d * 0.22, root + d * 0.38 + np.array([-0.06, rng.normal() * 0.04, 0])], [0.07, 0.045, 0.02], samples=3), k=0.05)
    # broken branch stubs
    for x, a in ((0.1, 1.2), (0.55, -0.8), (-0.35, 2.4)):
        b = np.array([x, 0.17, 0.0])
        d = np.array([0.4, math.cos(a), math.sin(a)])
        d /= np.linalg.norm(d)
        p.add(Capsule(b, b + d * rng.uniform(0.18, 0.3), 0.045, 0.025), k=0.03)
        p.sub(Sphere(b + d * 0.3, 0.02), k=0.01, color=NP["drift_dk"])
    # long weather checks along the grain
    for i in range(9):
        a = rng.uniform(0, 2 * np.pi)
        x0 = rng.uniform(-0.85, 0.5)
        x1 = x0 + rng.uniform(0.3, 0.7)
        r0 = np.interp(x0, xs, radii)
        o = np.array([0, math.cos(a), math.sin(a)])
        c0 = np.array([x0, 0.15, 0]) + o * r0
        c1 = np.array([x1, 0.15, 0]) + o * np.interp(x1, xs, radii)
        p.sub(Capsule(c0, c1, 0.012), k=0.008, color=NP["drift_dk"])
    # flat where it rests
    p.inter(HalfSpace((0, 0.005, 0), (0, -1, 0)), k=0.02)
    p.paint(patches(3.0, 0.2, 5), NP["drift_lt"], feather=0.02)
    p.paint(patches(2.2, 0.25, 6, stretch=(0.4, 1, 1)), "#a39a8b", feather=0.03)
    p.paint(below(0.07, 0.02, 4), shade(NP["drift"], 0.75), feather=0.04)
    return m


MODELS["town/driftwood"] = driftwood


# ----------------------------------------------------------------------------------------------------------------
# seaweed pile


def seaweed_pile():
    m = TownModel("seaweed_pile", budget=3900, seed=91)
    rng = m.rng
    mound = m.piece(color=NP["wrack"], gloss=160, merge="weed", res=0.014, lumps=0.01, lump_freq=8, dents=8, dent_size=0.06, dent_depth=0.012,
                    mottle=0.12, detail=0.5)
    wcols = [NP["wrack"], NP["kelp_dk"], NP["kelp"], "#4f4a26"]
    for i in range(8):
        c = np.array([rng.normal() * 0.28, 0.0, rng.normal() * 0.2])
        hgt = rng.uniform(0.1, 0.2) * (1.2 - np.linalg.norm(c) * 1.2)
        mound.add(Ellipsoid(c, (rng.uniform(0.18, 0.32), max(hgt, 0.06), rng.uniform(0.14, 0.26)), (rng.normal() * 6, rng.uniform(0, 180), rng.normal() * 6)),
                  k=0.07, color=wcols[i % 4])
    mound.inter(HalfSpace((0, -0.03, 0), (0, -1, 0)), k=0.02)
    f = mound.sdf
    # long straps slid off the heap and lying tangled on the ground
    for i in range(16):
        a = rng.uniform(0, 2 * np.pi)
        start = np.array([rng.normal() * 0.18, 0.4, rng.normal() * 0.14])
        pts, nrm = drape(f, start, (math.cos(a), 0, math.sin(a)), 7, 0.07, rng, lift=0.01, wander=0.35, grav=0.25)
        last = pts[-1]
        d = np.array([math.cos(a), 0, math.sin(a)])
        ne = int(rng.integers(1, 6))
        extra = [np.array([last[0], 0.013, last[2]]) + d * 0.075 * (j + 1) + np.cross(d, [0, 1, 0]) * 0.04 * math.sin(j * 1.3 + i) for j in range(ne)]
        pts = np.vstack([pts, np.array(extra)])
        nrm = np.vstack([nrm, np.tile([0, 1.0, 0], (ne, 1))])
        k = m.piece(color=[NP["kelp"], NP["kelp_lt"], NP["kelp_dk"], NP["wrack"]][i % 4], gloss=185, merge="weed", res=0.0065, lumps=0.001,
                    mottle=0.06, detail=1.0)
        ribbon(k, pts, nrm, np.linspace(0.03, 0.055, len(pts)) * rng.uniform(0.8, 1.3), 0.01)
    # a thick kelp stipe coiled over the top with its holdfast
    sp = m.piece(color=NP["kelp_dk"], gloss=150, merge="weed", res=0.008, lumps=0.002, detail=0.6)
    coil = [np.array([0.35 * math.cos(t) * (1 - t / 9), 0.0, 0.25 * math.sin(t) * (1 - t / 9)]) for t in np.linspace(0, 6.5, 12)]
    coil = [c + np.array([0, max(0.03, -f(c[None, :] + np.array([[0, 0.3, 0]]))[0] * 0 + 0.0), 0]) for c in coil]
    coil2 = []
    for c in coil:
        q = c[None, :] + np.array([[0, 0.5, 0]])
        for _ in range(8):
            q = q - gradient(f, q) * (f(q) - 0.02)[:, None]
        coil2.append(q[0])
    sp.add(Tube(coil2, np.linspace(0.028, 0.016, len(coil2)), samples=3))
    hf = coil2[0] + np.array([0.06, 0.0, 0])
    for j in range(7):
        d = rng.normal(size=3)
        d[1] = abs(d[1]) * 0.4
        sp.add(Capsule(hf, hf + d / np.linalg.norm(d) * 0.08, 0.016, 0.008), k=0.015, color=NP["bladder"])
    # bladder wrack beads
    bp = m.piece(color=NP["bladder"], gloss=195, merge="weed", res=0.006, lumps=0.001, detail=0.4)
    P, N = surface_points(f, (-0.5, 0.02, -0.4), (0.5, 0.3, 0.4), 16, rng, cond=lambda P, N: N[:, 1] > 0.3)
    for c, n in zip(P, N):
        bp.add(Ellipsoid(c + n * 0.012, (0.026, 0.018, 0.018), frame(np.cross(n, [1, 0, 0.3]) + 1e-6, n)), k=0.004)
    # an old crab shell for story
    cs = m.piece(color="#c46a43", gloss=80, merge="bits", res=0.006, lumps=0.002, detail=0.5)
    cc = np.array([0.42, 0.03, 0.2])
    cs.add(Ellipsoid(cc, (0.07, 0.03, 0.055), (0, 30, 8)))
    cs.paint(HalfSpace(cc + np.array([0, -0.01, 0]), (0, 1, 0)), "#e2c7a6")
    for sgn in (-1, 1):
        for j in range(3):
            a = math.radians(30 + sgn * (40 + j * 25))
            cs.add(Capsule(cc + np.array([math.sin(a) * 0.05, -0.005, math.cos(a) * 0.05 * sgn]),
                           cc + np.array([math.sin(a) * 0.11, -0.02, math.cos(a) * 0.1 * sgn]), 0.008, 0.005), k=0.006)
    return m


MODELS["town/seaweed_pile"] = seaweed_pile


# ----------------------------------------------------------------------------------------------------------------
# tide pool


def tide_pool():
    m = TownModel("tide_pool", budget=4000, seed=131)
    rng = m.rng
    R = 1.15
    # ring of low rocks
    nr = 8
    rocks = []
    for i in range(nr):
        a = i / nr * 2 * np.pi + rng.normal() * 0.18
        rad = R * rng.uniform(0.95, 1.2)
        c = np.array([math.cos(a) * rad, 0.0, math.sin(a) * rad * 0.85])
        r = np.array([rng.uniform(0.32, 0.52), rng.uniform(0.18, 0.34), rng.uniform(0.3, 0.45)])
        rocks.append((c, r))
    rp = m.piece(color=NP["rock"], gloss=50, merge="rocks", res=0.016, lumps=0.006, lump_freq=6, dents=10, dent_size=0.06, dent_depth=0.006,
                 mottle=0.1, detail=1.0)
    cols = [NP["rock"], NP["rock_dk"], NP["rock_lt"], NP["rock_warm"]]
    for i, (c, r) in enumerate(rocks):
        rp.add(Chunk(c + np.array([0, r[1] * 0.6 - 0.12, 0]), r, n=11, k=0.015, rot=(rng.normal() * 10, rng.uniform(0, 360), rng.normal() * 10),
                     seed=int(rng.integers(1e6)), cut=(0.55, 0.82)), k=0.06, color=cols[i % 4])
    # basin floor: a shallow rocky dish joining the ring
    rp.add(Ellipsoid((0, -0.2, 0), (R * 1.05, 0.2, R * 0.92)), k=0.15, color=NP["rock_dk"])
    rp.sub(Ellipsoid((0, 0.02, 0), (R * 0.82, 0.12, R * 0.7)), k=0.1)
    rp.inter(HalfSpace((0, -0.2, 0), (0, -1, 0)), k=0.02)
    rp.paint(below(0.12, 0.03, 4), shade(NP["rock"], 0.62), gloss=120, feather=0.03)
    rp.paint(band(0.0, 0.1, 0.03, 5, 3), TP["algae"], gloss=130, feather=0.02)
    rp.paint(patches(1.5, 0.2, 9), NP["lichen_grey"], feather=0.01)
    f = rp.sdf
    barnacles(m, "rocks", f, (-R * 1.5, 0.0, -R * 1.4), (R * 1.5, 0.3, R * 1.4), 14, rng, size=(0.014, 0.026), tris=50,
              cond=lambda P, N: N[:, 1] > -0.2)
    # glossy pool surface (water) sitting in the dish
    w = m.piece(color=NP["pool"], gloss=235, merge="pool", res=0.014, lumps=0.0006, lump_freq=3, mottle=0.03, ao=False, decimate=260)
    w.add(Cylinder((0, -0.06, 0), R * 0.88, 0.11, round=0.03))
    w.inter(Ellipsoid((0, -0.06, 0), (R * 0.9, 0.4, R * 0.78)), k=0.05)
    w.paint(Ellipsoid((0, 0.05, 0), (R * 0.55, 0.1, R * 0.45)), shade(NP["pool"], 0.8), feather=0.15)
    # starfish on the ledge
    life = m.piece(color=NP["star"], gloss=70, merge="life", res=0.006, lumps=0.002, dents=4, dent_size=0.015, detail=1.0)
    sc = np.array([0.45, 0.07, -0.45])
    for k in range(5):
        a = k / 5 * 2 * np.pi + 0.3
        tip = sc + np.array([math.cos(a) * 0.15, -0.015 + 0.02 * math.sin(a * 2), math.sin(a) * 0.15])
        life.add(Capsule(sc + np.array([0, 0.012, 0]), tip, 0.035, 0.012), k=0.02)
    for k in range(10):
        a = rng.uniform(0, 2 * np.pi)
        life.add(Sphere(sc + np.array([math.cos(a) * rng.uniform(0, 0.11), 0.04, math.sin(a) * rng.uniform(0, 0.11)]), 0.009), k=0.004, color="#e39a5e")
    # anemone: squat green column with a ring of pink nubs
    ac = np.array([-0.55, 0.0, 0.3])
    life.add(Cylinder(ac + np.array([0, 0.05, 0]), 0.07, 0.06, round=0.03), k=0.02, color=NP["anemone"], gloss=150)
    for k in range(12):
        a = k / 12 * 2 * np.pi
        life.add(Capsule(ac + np.array([math.cos(a) * 0.055, 0.11, math.sin(a) * 0.055]),
                         ac + np.array([math.cos(a) * 0.1, 0.15 + 0.02 * math.sin(a * 3), math.sin(a) * 0.1]), 0.014, 0.009), k=0.008,
                 color=NP["anemone_tip"], gloss=170)
    life.sub(Sphere(ac + np.array([0, 0.13, 0]), 0.03), k=0.01, color="#7a3c40")
    # a few pebbles and a mussel clump in the water's edge
    pb = m.piece(color=NP["pebble"], gloss=120, merge="life", res=0.008, lumps=0.002, detail=0.5)
    for k in range(7):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(0.2, 0.75)
        pb.add(Ellipsoid((math.cos(a) * rr, 0.03, math.sin(a) * rr * 0.8), (rng.uniform(0.03, 0.06), 0.022, rng.uniform(0.025, 0.05)), (0, rng.uniform(0, 180), 0)),
               k=0.005, color=[NP["pebble"], NP["rock_lt"], "#7f7a70", "#b7ad97"][k % 4])
    return m


MODELS["town/tide_pool"] = tide_pool
