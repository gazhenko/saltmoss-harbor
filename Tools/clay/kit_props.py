"""
Saltmoss Harbor clutter-prop builders: each function adds clay pieces for one prop to an existing TownModel at a
placement `t` (kit_town.T: pos + yaw [+ scale]) and returns useful points (tops, light positions, sockets).
Used by the standalone prop models (models/town_props.py) and to dress buildings.

Merge groups: `merge` (plain clay: wood, iron, rope, ice, plants ...), `glass` (matClass 1, glows at night) and
`net` (matClass 4, the Unity shader cuts a diamond mesh out of it). Keep mats apart: a merge group takes the mat of
its first piece.
"""
from __future__ import annotations

import math

import numpy as np
from clay import Prim, Func, Box, Sphere, Ellipsoid, Capsule, Cylinder, Torus, Tube, HalfSpace, euler, shade, mix, fbm, rgb
from clay import catmull
from kit_town import TP, T, frame, rot_axis, board, post, rope, patches, band, below, Plank

# extra colours for props
PP = dict(
    ring_red="#ad4a3d", ring_white="#e2dccd", terracotta="#a8664c", terracotta_dk="#8c5440", soil="#4b3b2f",
    leaf="#5d7c44", leaf_dk="#46613a", geranium="#b9483f", geranium_pk="#c66f78", thrift="#d48aa0", lobelia="#6f78b8",
    daisy="#ece6d4", ivy="#4f6e3e", ice="#dcebef", ice_blue="#bcd9e3", cork="#a8703f", cork_dk="#8a5a34",
    float_green="#6e9c8c", float_aqua="#86b3ad", float_amber="#b09450", float_blue="#5b7ea3",
    flag_red="#a65a4c", flag_cream="#dfd4b8", flag_teal="#5f8d88", flag_mustard="#c9a352", tin_paint="#5c7894",
)


def pick(rng, seq):
    """Random element of a list (works for mixed str / array colours, unlike Generator.choice)."""
    return seq[int(rng.integers(len(seq)))]


def surface_y(piece, x, z, y_hi, y_lo, n=240):
    """Highest y where a vertical line at (x, z) enters `piece` (world coords)."""
    ys = np.linspace(y_hi, y_lo, n)
    P = np.column_stack([np.full(n, x), ys, np.full(n, z)])
    d = piece.sdf(P)
    idx = int(np.argmax(d < 0))
    return float(ys[idx]) if d[idx] < 0 else float(y_lo)


class RopePrim(Prim):
    """A laid rope along a polyline: 3 strands twisting around the axis (helical grooves)."""

    def __init__(self, pts, r, samples=None, lay=None, groove=None, taper_end=0.0):
        super().__init__()
        pts = np.asarray(pts, float)
        if samples and len(pts) >= 3:
            pts, _ = catmull(pts, np.full(len(pts), r), samples)
        self.a, self.b = pts[:-1], pts[1:]
        seg = self.b - self.a
        self.L = np.linalg.norm(seg, axis=1) + 1e-9
        self.dir = seg / self.L[:, None]
        self.cum = np.concatenate([[0], np.cumsum(self.L)[:-1]])
        self.total = float(self.L.sum())
        # parallel-transported reference vectors
        U = []
        u = np.cross(self.dir[0], [0, 1, 0])
        if np.linalg.norm(u) < 1e-3:
            u = np.cross(self.dir[0], [1, 0, 0])
        u /= np.linalg.norm(u)
        for d in self.dir:
            u = u - d * (u @ d)
            u /= np.linalg.norm(u)
            U.append(u.copy())
        self.U = np.array(U)
        self.V = np.cross(self.dir, self.U)
        self.r = r
        self.lay = lay or r * 7.0
        self.g = groove if groove is not None else r * 0.16
        self.taper_end = taper_end

    def sdf(self, P):
        best = np.full(len(P), 1e9)
        s = np.zeros(len(P))
        cu = np.zeros(len(P))
        cv = np.zeros(len(P))
        for i in range(len(self.a)):
            pa = P - self.a[i]
            h = np.clip(pa @ self.dir[i], 0, self.L[i])
            q = pa - np.outer(h, self.dir[i])
            dd = np.einsum("ij,ij->i", q, q)
            mk = dd < best
            if mk.any():
                best[mk] = dd[mk]
                s[mk] = self.cum[i] + h[mk]
                cu[mk] = q[mk] @ self.U[i]
                cv[mk] = q[mk] @ self.V[i]
        dist = np.sqrt(best)
        r = self.r
        if self.taper_end:
            r = r * (1 - self.taper_end * np.clip((s - (self.total - 0.12)) / 0.12, 0, 1))
        phi = np.arctan2(cv, cu)
        lay = 0.5 + 0.5 * np.cos(3 * (phi - 2 * np.pi * s / self.lay))
        return dist - r + self.g * lay ** 3

    def bounds(self):
        P = np.vstack([self.a, self.b])
        return P.min(0) - self.r * 1.5, P.max(0) + self.r * 1.5


def laid_rope(m, merge, pts, r=0.02, color=None, res=None, detail=1.0, samples=None, taper_end=0.0, lumps=0.0012):
    color = color or TP["rope"]
    p = m.piece(color=color, gloss=20, merge=merge, res=res or max(0.004, r / 3.0), lumps=lumps, lump_freq=18, mottle=0.09, detail=detail)
    p.add(RopePrim(pts, r, samples=samples, taper_end=taper_end))
    return p


# ================================================================================================================
# crates & barrels


def crate(m, t, merge="props", size=(0.56, 0.42, 0.42), color=None, band_color=None, mark=True, lid=False, detail=1.0,
          slat_t=0.022):
    """Slatted wooden crate, bottom-centre at t, long side along local x. Returns the top-centre point."""
    rng = m.rng
    W, H, D = size
    hx, hz = W / 2, D / 2
    woods = [TP["wood_br"], TP["wood_new2"], TP["wood"], TP["wood_new"], TP["wood_lt"]]
    base = color or woods[int(rng.integers(len(woods)))]
    if band_color is None:
        band_color = pick(rng, [TP["navy"], TP["red"], TP["teal_dk"], TP["ochre"]])
    # corner posts just inside the slats
    for sx in (-1, 1):
        for sz in (-1, 1):
            post(m, merge, t.p(sx * (hx - slat_t - 0.02), 0.0, sz * (hz - slat_t - 0.02)),
                 t.p(sx * (hx - slat_t - 0.02), H - 0.005, sz * (hz - slat_t - 0.02)), 0.022, shade(base, 0.88), detail=0.5 * detail)
    rows = 3
    sh = H / rows
    for side in range(4):
        if side < 2:  # long sides z = +-hz
            sz = 1 if side == 0 else -1
            a0, b0, out = np.array([-hx + 0.005, 0, sz * (hz - slat_t / 2)]), np.array([hx - 0.005, 0, sz * (hz - slat_t / 2)]), np.array([0, 0, sz])
        else:
            sx = 1 if side == 2 else -1
            a0, b0, out = np.array([sx * (hx - slat_t / 2), 0, -hz + slat_t + 0.002]), np.array([sx * (hx - slat_t / 2), 0, hz - slat_t - 0.002]), np.array([sx, 0, 0])
        for r in range(rows):
            yc = sh * (r + 0.5) + 0.004
            col = base if rng.random() > 0.2 else woods[int(rng.integers(len(woods)))]
            a = t.p(a0 + [0, yc, 0])
            b = t.p(b0 + [0, yc, 0])
            p = board(m, merge, a, b, sh - 0.022, slat_t, t.v(out), col, nails=1, nail_inset=0.03, detail=detail, knot=0.2,
                      lumps=0.0015, dents=1, jitter=0.7)
            if side < 2 and r == 1:
                # stencilled band + mark
                c = t.p((a0 + b0) / 2 + [0, yc, 0] + out * slat_t / 2)
                p.paint(Box(c, (W * 0.6, sh * 0.5, 0.03), t.r(), round=0.01), mix(band_color, base, 0.25), feather=0.003)
                if mark and False:
                    X = t.v((1, 0, 0))
                    p.paint(Ellipsoid(c + X * 0.025, (0.09, 0.04, 0.04), t.r()), mix(TP["cream"], base, 0.2), feather=0.004)
                    p.paint(Box(c - X * 0.085, (0.03, 0.045, 0.04), t.r(), round=0.01), mix(TP["cream"], base, 0.2), feather=0.004)
                    p.paint(Sphere(c + X * 0.08 + t.v((0, 0.01, 0)), 0.009), mix(band_color, base, 0.2), feather=0.002)
                p.detail = 2.5 * detail
            if side >= 2 and r == rows - 1:
                # hand-hole slot through the top end slat
                c = t.p(a0 * [1, 0, 0] + [0, yc, 0])
                Z = t.v((0, 0, 1))
                p.sub(Capsule(c - Z * 0.06, c + Z * 0.06, 0.02), k=0.006, color=shade(col, 0.6))
    # bottom slats
    for i in range(3):
        z = (i - 1) * (D / 3)
        board(m, merge, t.p(-hx + 0.01, 0.011, z), t.p(hx - 0.01, 0.011, z), D / 3 - 0.02, slat_t, t.v((0, 1, 0)), shade(base, 0.9),
              nails=0, detail=0.4 * detail, knot=0, jitter=0.5)
    if lid:
        for i in range(3):
            z = (i - 1) * (D / 3)
            board(m, merge, t.p(-hx, H + 0.012, z), t.p(hx, H + 0.012, z), D / 3 - 0.015, slat_t, t.v((0, 1, 0)), base,
                  nails=1, nail_inset=0.03, detail=0.6 * detail, knot=0.2, jitter=0.6)
        return t.p(0, H + slat_t + 0.002, 0)
    return t.p(0, H, 0)


def ice_heap(m, merge, t, hx, hz, y0, peak, chunks=40, detail=1.0, clip_box=None):
    """Crushed ice heaped in a rectangular container (local frame of t): base level y0, mound up to y0+peak."""
    rng = m.rng
    p = m.piece(color=PP["ice"], gloss=215, merge=merge, res=0.006, lumps=0.002, lump_freq=30, dents=5, dent_size=0.02,
                dent_depth=0.003, mottle=0.05, detail=detail)
    p.add(Ellipsoid(t.p(0, y0, 0), (hx * 1.05, peak, hz * 1.05), t.r()), k=0.0)
    for i in range(chunks):
        u, v = rng.uniform(-0.92, 0.92), rng.uniform(-0.9, 0.9)
        h = peak * math.sqrt(max(0.0, 1 - (u * u + v * v) / 1.05)) * 0.92
        s = rng.uniform(0.018, 0.04)
        c = t.p(u * hx, y0 + h + rng.uniform(-0.5, 0.35) * s, v * hz)
        p.add(Box(c, (s, s * rng.uniform(0.5, 0.9), s * rng.uniform(0.7, 1.1)), t.r(tuple(rng.uniform(-70, 70, 3))), round=s * 0.18), k=0.003,
              color=pick(rng, [PP["ice"], PP["ice_blue"], "#eef5f6"]))
    if clip_box is not None:
        p.inter(clip_box, k=0.004)
    p.paint(patches(9, 0.15, int(rng.integers(999))), PP["ice_blue"], feather=0.01)
    return p


def fish_crate(m, t, merge="props", size=(0.72, 0.2, 0.46), color=None, band_color=None, detail=1.0):
    """Shallow slatted fish box heaped with crushed ice. Returns list of 3 points on the ice (for fish sockets)."""
    rng = m.rng
    W, H, D = size
    hx, hz = W / 2, D / 2
    woods = [TP["wood"], TP["wood_br"], TP["wood_lt"], TP["wood_new2"]]
    base = color or woods[int(rng.integers(len(woods)))]
    st = 0.022
    for sx in (-1, 1):
        for sz in (-1, 1):
            post(m, merge, t.p(sx * (hx - st - 0.018), 0.0, sz * (hz - st - 0.018)), t.p(sx * (hx - st - 0.018), H + 0.01, sz * (hz - st - 0.018)), 0.02,
                 shade(base, 0.85), detail=0.4)
    bc = band_color or pick(rng, [TP["teal"], TP["red"], TP["navy"]])
    for side in range(4):
        if side < 2:
            sz = 1 if side == 0 else -1
            a0, b0, out = np.array([-hx, 0, sz * (hz - st / 2)]), np.array([hx, 0, sz * (hz - st / 2)]), np.array([0, 0, sz])
        else:
            sx = 1 if side == 2 else -1
            a0, b0, out = np.array([sx * (hx - st / 2), 0, -hz + st]), np.array([sx * (hx - st / 2), 0, hz - st]), np.array([sx, 0, 0])
        for r in range(2):
            yc = H * (r + 0.5) / 2 + 0.006
            p = board(m, merge, t.p(a0 + [0, yc, 0]), t.p(b0 + [0, yc, 0]), H / 2 - 0.014, st, t.v(out), base, nails=1, nail_inset=0.025,
                      detail=detail, knot=0.15, lumps=0.0015, dents=1, jitter=0.6)
            if r == 1:
                p.paint(band(t.p(0, yc + 0.0, 0)[1] - 0.022, t.p(0, yc, 0)[1] + 0.03), mix(bc, base, 0.4), feather=0.004)
            if side >= 2 and r == 1:
                c = t.p(a0 * [1, 0, 0] + [0, yc, 0])
                Z = t.v((0, 0, 1))
                p.sub(Capsule(c - Z * 0.05, c + Z * 0.05, 0.017), k=0.005, color=shade(base, 0.6))
    for i in range(4):
        z = (i - 1.5) * (D / 4)
        board(m, merge, t.p(-hx + 0.01, 0.011, z), t.p(hx - 0.01, 0.011, z), D / 4 - 0.015, st, t.v((0, 1, 0)), shade(base, 0.9), nails=0,
              detail=0.3, knot=0, jitter=0.5)
    inner = Box(t.p(0, H, 0), (hx - st - 0.004, H + 0.3, hz - st - 0.004), t.r(), round=0.01)
    ice = ice_heap(m, merge, t, hx - st - 0.01, hz - st - 0.01, H - 0.05, 0.085, chunks=75, detail=detail * 1.6,
                   clip_box=Box(t.p(0, H + 0.1, 0), (hx - st - 0.004, 0.25, hz - st - 0.004), t.r(), round=0.02))
    pts = []
    for (u, v) in ((-0.22, -0.05), (0.02, 0.06), (0.24, -0.04)):
        wp = t.p(u * W, 0, v * D)
        y = surface_y(ice, wp[0], wp[2], t.p(0, H + 0.3, 0)[1], t.p(0, 0, 0)[1])
        pts.append(np.array([wp[0], y + 0.03, wp[2]]))
    return pts


def barrel(m, t, merge="props", h=0.86, r=0.27, bulge=0.045, n=14, color=None, hoop_color=None, band_color=None, lid=True,
           detail=1.0):
    """Coopered barrel standing on its end: bowed staves, iron hoops with rust runs, a planked head. Returns top centre."""
    rng = m.rng
    woods = [TP["wood_br"], TP["wood"], TP["wood_dk"], "#7d6450"]
    base = color or woods[int(rng.integers(len(woods)))]
    st = 0.032
    hoop_color = hoop_color or TP["iron"]
    ph = rng.uniform(0, 2 * np.pi)
    hoop_ys = [0.07, 0.24, h - 0.24, h - 0.07]
    for i in range(n):
        ang = ph + 2 * np.pi * (i + rng.normal() * 0.04) / n
        rad = np.array([math.cos(ang), 0, math.sin(ang)])
        a = t.p(rad * (r - st / 2) + [0, 0.004, 0])
        b = t.p(rad * (r - st / 2) + [0, h + rng.uniform(-0.003, 0.003), 0])
        w = 2 * np.pi * (r + bulge * 0.5) / n * 1.0
        col = base if rng.random() > 0.25 else woods[int(rng.integers(len(woods)))]
        p = board(m, merge, a, b, w, st, t.v(-rad), col, bow=bulge, sweep=0.0, twist=0.0, nails=0, knot=0.15, ends=(0.0, 0.0),
                  jitter=0.2, rot_jit=0.08, detail=detail, lumps=0.0015, dents=1, round=0.008)
        if band_color is not None:
            p.paint(band(t.p(0, h * 0.42, 0)[1], t.p(0, h * 0.58, 0)[1]), mix(band_color, col, 0.2), feather=0.004)
        # rust runs below hoops
        for hy in hoop_ys[1:3]:
            if rng.random() < 0.35:
                rr = r + bulge * (1 - ((hy - h / 2) / (h / 2)) ** 2)
                c = t.p(rad * rr + [0, hy - 0.02, 0])
                p.paint(Capsule(c, c - np.array([0, rng.uniform(0.05, 0.15), 0]), 0.016, 0.006), mix(TP["rust"], col, 0.35), feather=0.008)
    for hy in hoop_ys:
        u = (hy - h / 2) / (h / 2)
        rr = r + bulge * (1 - u * u)
        hp = m.piece(color=hoop_color, gloss=70, merge=merge, res=0.006, lumps=0.0012, dents=2, dent_size=0.02, detail=0.8 * detail)
        tilt = t.r((rng.normal() * 1.2, 0, rng.normal() * 1.2))
        hp.add(Cylinder(t.p(0, hy, 0), rr + 0.006, 0.02, tilt, round=0.007))
        hp.sub(Cylinder(t.p(0, hy, 0), rr - 0.014, 0.06, tilt), k=0.004)
        hp.paint(patches(5, 0.12, int(rng.integers(999))), TP["rust_dk"], feather=0.008)
        hp.paint(patches(8, 0.3, int(rng.integers(999))), TP["rust"], feather=0.006)
    if lid:
        hy = h - 0.035
        for k in range(4):
            x = (k - 1.5) * (2 * (r - 0.02) / 4)
            pb = board(m, merge, t.p(x, hy, -(r + 0.01)), t.p(x, hy, r + 0.01), 2 * (r - 0.02) / 4 - 0.008, 0.03, t.v((0, 1, 0)),
                       shade(base, 0.92), nails=0, knot=0.2, jitter=0.4, detail=0.6 * detail)
            pb.inter(Cylinder(t.p(0, hy, 0), r - 0.012, 0.05), k=0.004)
        # bung
        bp = m.piece(color=TP["wood_dk"], merge=merge, res=0.006, lumps=0.001, detail=0.3)
        bp.add(Cylinder(t.p(r * 0.45, hy + 0.018, r * 0.2), 0.026, 0.012, round=0.006))
    return t.p(0, h, 0)


# ================================================================================================================
# rope


def rope_coil(m, t, merge="props", r0=0.06, turns=3.5, rr=0.033, color=None, loops=2, tail=0.6, detail=1.0):
    """Flemish-coiled rope on the ground (bottom at t), a couple of loose loops thrown on top and a loose tail
    running off toward +x. One continuous laid rope."""
    rng = m.rng
    pitch = rr * 2.05
    pts = []
    nper = 18
    for i in range(int(turns * nper) + 1):
        th = 2 * np.pi * i / nper
        rho = r0 + pitch * th / (2 * np.pi)
        pts.append((rho * math.cos(th), rr * 0.97, rho * math.sin(th)))
    rho_out = r0 + pitch * turns
    th0 = 2 * np.pi * turns
    # loose loops on top (smaller, offset, tilted)
    off = np.array([rng.uniform(-0.02, 0.02), 0, rng.uniform(-0.02, 0.02)])
    for k in range(loops):
        rl = rho_out * rng.uniform(0.72, 0.92)
        for i in range(1, nper + 1):
            th = th0 + 2 * np.pi * (k + i / nper)
            f = (k * nper + i) / (loops * nper)
            y = rr * (2.9 + 0.5 * math.sin(th * 1.0 + k)) if f > 0.05 else rr * (1 + f * 30)
            rho = rho_out + (rl - rho_out) * min(1.0, f * 6)
            pts.append((off[0] + rho * math.cos(th), y, off[2] + rho * math.sin(th)))
    # tail: climb back down and run off
    last = np.array(pts[-1])
    ang = math.atan2(last[2], last[0])
    d = np.array([math.cos(ang + 0.6), 0, math.sin(ang + 0.6)])
    side = np.cross([0, 1, 0], d)
    for i in range(1, 9):
        f = i / 8
        p = last + d * tail * f + side * 0.08 * math.sin(f * 3.0)
        p[1] = rr * 0.97 + (last[1] - rr * 0.97) * max(0, 1 - f * 2.5)
        pts.append(tuple(p))
    W = [t.p(p) for p in pts]
    col = color or TP["rope"]
    laid_rope(m, merge, W, rr, col, detail=detail, taper_end=0.25)
    return t.p(0, rr * 4, 0)


# ================================================================================================================
# lanterns


def ship_lantern(m, t, merge="metal", glass="glass", size=1.0, color=None, detail=1.0, ring=True):
    """Ship's lantern standing on its base at t (bottom centre). Returns (light_pos, ring_top_pos)."""
    rng = m.rng
    s = size
    col = color or TP["iron"]
    p = m.piece(color=col, gloss=80, merge=merge, res=0.0055 * s, lumps=0.0012, dents=3, dent_size=0.015, dent_depth=0.002, detail=detail)
    p.add(Cylinder(t.p(0, 0.024 * s, 0), 0.088 * s, 0.024 * s, t.r(), round=0.012 * s))
    p.add(Torus(t.p(0, 0.05 * s, 0), 0.078 * s, 0.009 * s, t.r()), k=0.006 * s, color=TP["brass"], gloss=150)
    # cage
    for i in range(4):
        a = 2 * np.pi * (i + 0.5) / 4
        d = np.array([math.cos(a), 0, math.sin(a)])
        p.add(Capsule(t.p(d * 0.078 * s + [0, 0.05 * s, 0]), t.p(d * 0.078 * s + [0, 0.215 * s, 0]), 0.0075 * s), k=0.004 * s)
    for y in (0.1, 0.165):
        p.add(Torus(t.p(0, y * s, 0), 0.08 * s, 0.006 * s, t.r()), k=0.004 * s)
    # top collar, cone, cap
    p.add(Cylinder(t.p(0, 0.225 * s, 0), 0.085 * s, 0.013 * s, t.r(), round=0.006 * s), k=0.005 * s, color=TP["brass"], gloss=150)
    p.add(Capsule(t.p(0, 0.24 * s, 0), t.p(0, 0.3 * s, 0), 0.07 * s, 0.032 * s), k=0.01 * s)
    p.add(Cylinder(t.p(0, 0.312 * s, 0), 0.03 * s, 0.014 * s, t.r()), k=0.005 * s)
    p.add(Ellipsoid(t.p(0, 0.33 * s, 0), (0.052 * s, 0.014 * s, 0.052 * s), t.r()), k=0.006 * s)
    for i in range(6):  # vent holes on the cone
        a = 2 * np.pi * i / 6
        d = np.array([math.cos(a), 0, math.sin(a)])
        p.sub(Sphere(t.p(d * 0.06 * s + [0, 0.262 * s, 0]), 0.009 * s), k=0.003 * s, color=TP["iron"])
    top = t.p(0, 0.34 * s, 0)
    if ring:
        p.add(Torus(t.p(0, 0.385 * s, 0), 0.04 * s, 0.0075 * s, t.r((90, 0, 0))), k=0.004 * s)
        top = t.p(0, 0.43 * s, 0)
    p.paint(patches(7 / s, 0.08, int(rng.integers(999))), TP["rust"], feather=0.006)
    p.paint(band(t.p(0, 0.26 * s, 0)[1], t.p(0, 0.36 * s, 0)[1], 0.01, 9), shade(TP["iron"], 0.8), feather=0.01)
    g = m.piece(color=TP["lamp"], gloss=230, mat=1, merge=glass, res=0.006 * s, lumps=0.0008, mottle=0.03, ao=False, detail=0.6 * detail)
    g.add(Cylinder(t.p(0, 0.132 * s, 0), 0.06 * s, 0.085 * s, t.r(), round=0.03 * s))
    g.add(Ellipsoid(t.p(0, 0.132 * s, 0), (0.068 * s, 0.07 * s, 0.068 * s), t.r()), k=0.02 * s)
    return t.p(0, 0.132 * s, 0), top


def chain(m, merge, a, b, link=0.035, wire=0.0075, color=None, detail=0.6):
    """A few iron chain links from a to b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = np.linalg.norm(b - a)
    d = (b - a) / L
    n = max(1, int(round(L / (link * 1.1))))
    p = m.piece(color=color or TP["iron"], gloss=70, merge=merge, res=0.0035, lumps=0.0006, detail=detail)
    side = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
    for i in range(n):
        c = a + d * (i + 0.5) * L / n
        R0 = frame(d, side)
        Rl = frame(d, R0[:, 1] if i % 2 == 0 else R0[:, 2])
        # link: elongated ring whose plane holds d; alternate planes
        p.add(Ellipsoid(c, (link * 0.75, wire * 1.2, link * 0.42), Rl), k=0.0)
        p.sub(Ellipsoid(c, (link * 0.75 - wire * 2.1, wire * 4, link * 0.42 - wire * 2.1), Rl), k=0.002)
    p.paint(patches(10, 0.1, 3), TP["rust"], feather=0.005)
    return p


def hanging_lantern(m, t, merge="metal", glass="glass", drop=0.16, size=1.0, detail=1.0):
    """Lantern hanging from a ring whose top is at t (origin). Returns light position."""
    s = size
    ring_r = 0.032
    rp = m.piece(color=TP["iron"], gloss=70, merge=merge, res=0.004, lumps=0.0006, detail=0.5 * detail)
    rp.add(Torus(t.p(0, -ring_r, 0), ring_r - 0.006, 0.0065, t.r((90, 0, 0))))
    lantern_h = 0.43 * s
    base_y = -(ring_r * 2 + drop + lantern_h) + 0.02
    light, top = ship_lantern(m, t.sub((0, base_y, 0)), merge, glass, size=s, detail=detail)
    chain(m, merge, t.p(0, -ring_r * 2 + 0.004, 0), top + np.array([0, -0.005, 0]))
    return light


def lantern_post(m, t, merge="props", metal="metal", glass="glass", h=2.4, arm=0.5, color=None, detail=1.0):
    """Weathered timber lantern post with a gallows arm toward +z and a hanging ship's lantern; braced timber
    foot on the ground. Returns light position."""
    rng = m.rng
    col = color or pick(rng, [TP["wood"], TP["wood_dk"], TP["wood_br"]])
    post(m, merge, t.p(0, 0.0, 0), t.p(0.01, h, -0.005), 0.06, col, detail=detail)
    # cap on the post top
    cp = m.piece(color=TP["tin_dk"], gloss=50, merge=merge, res=0.006, lumps=0.001, detail=0.4 * detail)
    cp.add(Box(t.p(0.01, h + 0.012, -0.005), (0.085, 0.012, 0.085), t.r((rng.normal() * 3, 8, rng.normal() * 3)), round=0.006))
    cp.paint(patches(8, 0.1, 5), TP["rust"], feather=0.008)
    # arm + brace
    ay = h - 0.12
    post(m, merge, t.p(0, ay, -0.06), t.p(0, ay + 0.015, arm + 0.06), 0.035, shade(col, 1.05), detail=0.8 * detail)
    post(m, merge, t.p(0, ay - 0.4, 0.05), t.p(0, ay - 0.04, arm * 0.62), 0.025, shade(col, 0.95), detail=0.5 * detail)
    # hook under the arm end
    hk = t.p(0, ay - 0.035, arm - 0.04)
    hp = m.piece(color=TP["iron"], gloss=60, merge=metal, res=0.004, lumps=0.0006, detail=0.4)
    hp.add(Capsule(hk + t.v((0, 0.04, 0)), hk, 0.006))
    hp.add(Torus(hk + t.v((0, -0.012, 0)), 0.014, 0.005, t.r((90, 90, 0))), k=0.003)
    light = hanging_lantern(m, t.sub((0, ay - 0.04 - 0.02, arm - 0.04)), metal, glass, drop=0.1, detail=detail)
    # braced foot: two crossed sleepers + four short struts
    for yaw in (0, 90):
        tt = t.sub((0, 0, 0), yaw)
        board(m, merge, tt.p(-0.32, 0.03, 0), tt.p(0.32, 0.03, 0), 0.1, 0.06, tt.v((0, 1, 0)), shade(col, 0.9), nails=1, detail=0.6 * detail)
    for k in range(4):
        a = np.pi / 2 * k
        d = np.array([math.cos(a), 0, math.sin(a)])
        post(m, merge, t.p(d * 0.27 + [0, 0.06, 0]), t.p(d * 0.05 + [0, 0.42, 0]), 0.02, shade(col, 0.95), detail=0.4 * detail)
    return light


# ================================================================================================================
# life ring, bench, mailbox, anchor


def life_ring(m, t, merge="props", R=0.27, r=0.06, detail=1.0):
    """Life ring hanging on a peg from a small wall bracket. Origin = back face of the bracket (z=0) at the peg
    height (y=0); mounts on walls/rails facing +z. Returns ring centre."""
    rng = m.rng
    # bracket: backplate + peg
    bp = board(m, merge, t.p(0, -0.26, 0.016), t.p(0, 0.12, 0.016), 0.13, 0.032, t.v((0, 0, 1)), TP["wood_dk"], nails=1, nail_inset=0.04,
               detail=0.6 * detail, knot=0.2)
    zc = 0.032 + r + 0.008
    peg = m.piece(color=TP["wood_br"], merge=merge, res=0.006, lumps=0.0015, detail=0.4 * detail)
    peg.add(Capsule(t.p(0, 0.0, 0.03), t.p(0, 0.012, zc + r + 0.03), 0.017))
    peg.add(Sphere(t.p(0, 0.014, zc + r + 0.035), 0.024), k=0.008)
    cy = 0.017 - (R - r) + 0.004
    c = t.p(0, cy, zc)
    tilt = t.r((-6, 0, rng.normal() * 2))
    ring = m.piece(color=PP["ring_red"], gloss=70, merge=merge, res=0.007, lumps=0.0025, lump_freq=8, dents=4, dent_size=0.03,
                   dent_depth=0.004, detail=1.4 * detail)
    ring.add(Torus(c, R, r, tilt @ euler((90, 0, 0))))
    # four white quadrant bands (in the ring plane)
    X, Y = tilt @ np.array([1, 0, 0.0]), tilt @ np.array([0, 1, 0.0])

    # bands centred on 0, 90, 180, 270 deg: white where cos(4a) > 0.4
    def wbands(P, _c=c):
        q = P - _c
        ang = np.arctan2(q @ Y, q @ X) + 0.06 * fbm(P * 6, 1, 3)
        return (0.25 - np.cos(4 * ang)) * 0.05
    ring.paint(Func(wbands, (-1e4,) * 3, (1e4,) * 3), PP["ring_white"], feather=0.002)
    ring.paint(patches(5, 0.32, int(rng.integers(999))), mix(PP["ring_white"], TP["wood_dk"], 0.3), feather=0.005)  # grime
    # grab line: tied at the four red sectors, sagging loops between
    pts = []
    n = 48
    ties = [np.pi / 4 + k * np.pi / 2 for k in range(4)]
    for i in range(n + 1):
        a = 2 * np.pi * i / n
        dt = min(abs(((a - tt + np.pi) % (2 * np.pi)) - np.pi) for tt in ties)
        sag = 0.065 * math.sin(min(dt, np.pi / 4) / (np.pi / 4) * np.pi / 2) ** 1.5
        rad = R + r * 0.92 + sag
        pts.append(c + X * math.cos(a) * rad + Y * math.sin(a) * rad)
    laid_rope(m, merge, pts, 0.013, TP["rope"], detail=0.8 * detail)
    # whippings at ties
    wp = m.piece(color=TP["rope_dk"], merge=merge, res=0.004, lumps=0.0008, detail=0.4 * detail)
    Zr = np.cross(X, Y)
    for a in ties:
        d = X * math.cos(a) + Y * math.sin(a)
        tang = -X * math.sin(a) + Y * math.cos(a)
        wp.add(Torus(c + d * R, r * 1.02, 0.008, frame(d, tang)), k=0.0)
    return c


def bench(m, t, merge="props", L=1.3, seat_h=0.45, depth=0.38, back=True, color=None, detail=1.0):
    """Rickety plank bench facing +z (back toward -z). Returns seat centre top."""
    rng = m.rng
    woods = [TP["wood"], TP["wood_lt"], TP["wood_dk"], TP["wood_silver"]]
    col = color or pick(rng, woods)
    hl = L / 2
    st = 0.055
    # trestles at x = +-0.48: splayed legs in the yz plane, bearer under the seat
    for sx in (-1, 1):
        x = sx * (hl - 0.17)
        for sz in (-1, 1):
            short = 0.025 if (sx == 1 and sz == 1) else 0.0
            foot = t.p(x + sx * 0.03, short, sz * (depth / 2 + 0.03))
            top = t.p(x, seat_h - st - 0.035, sz * (depth / 2 - 0.06))
            post(m, merge, foot, top, 0.036, pick(rng, woods), detail=0.6 * detail)
            if short:
                wd = m.piece(color=TP["wood_new"], merge=merge, res=0.005, lumps=0.001, detail=0.3)
                wd.add(Box(t.p(x + sx * 0.03, short * 0.5, sz * (depth / 2 + 0.03)), (0.05, short * 0.5, 0.035), t.r((0, 15, 4)), round=0.004))
        board(m, merge, t.p(x, seat_h - st - 0.02, -depth / 2 - 0.02), t.p(x, seat_h - st - 0.02, depth / 2 + 0.02), 0.08, 0.04, t.v((1, 0, 0)),
              shade(col, 0.95), nails=1, detail=0.5 * detail)
    # low stretcher
    board(m, merge, t.p(-hl + 0.12, 0.16, 0.0), t.p(hl - 0.12, 0.17, 0.0), 0.08, 0.035, t.v((0, 0, 1)), pick(rng, woods), nails=1, detail=0.5 * detail)
    # seat planks
    for i, z in enumerate((-depth * 0.25, depth * 0.25)):
        c = col if i == 0 else pick(rng, [TP["wood_new2"], col])
        board(m, merge, t.p(-hl + rng.uniform(-0.02, 0.03), seat_h - st / 2, z), t.p(hl + rng.uniform(-0.03, 0.02), seat_h - st / 2 + rng.normal() * 0.006, z),
              depth / 2 - 0.012, st, t.v((0, 1, 0)), c, nails=2, nail_inset=0.17, detail=detail, bow=rng.uniform(0.004, 0.012))
    if back:
        for sx in (-1, 1):
            x = sx * (hl - 0.17)
            post(m, merge, t.p(x, seat_h - 0.06, -depth / 2 - 0.035), t.p(x + rng.normal() * 0.01, seat_h + 0.42, -depth / 2 - 0.09), 0.032,
                 pick(rng, woods), detail=0.5 * detail)
        board(m, merge, t.p(-hl + 0.04, seat_h + 0.3, -depth / 2 - 0.105), t.p(hl - 0.02, seat_h + 0.33, -depth / 2 - 0.1), 0.15, 0.035,
              t.v((0, 0.15, 1)), pick(rng, woods), nails=1, nail_inset=0.17, detail=0.8 * detail, bow=0.01)
    return t.p(0, seat_h, 0)


def mailbox(m, t, merge="props", post_h=1.0, color=None, detail=1.0, scale=1.25):
    """Big rounded tin mailbox on a timber post, door at +z, flag up on the +x side. Returns the slot/door point."""
    rng = m.rng
    s = scale
    col = color or pick(rng, [TP["red"], PP["tin_paint"], TP["navy"]])
    pc = pick(rng, [TP["wood"], TP["wood_dk"]])
    post(m, merge, t.p(0, 0.0, 0), t.p(0.012, post_h, -0.005), 0.062, pc, detail=0.6 * detail)
    # support board + diagonal brace
    board(m, merge, t.p(0, post_h + 0.015, -0.24 * s), t.p(0, post_h + 0.015, 0.26 * s), 0.16 * s, 0.03, t.v((0, 1, 0)), pc, nails=1, detail=0.5 * detail)
    post(m, merge, t.p(0, post_h - 0.32, 0.04), t.p(0, post_h - 0.01, 0.2 * s), 0.022, pc, detail=0.4 * detail)
    w, hh, L = 0.17 * s, 0.13 * s, 0.27 * s  # half width, box half-height, half length
    y0 = post_h + 0.03
    tilt = t.r((rng.normal() * 1.5, rng.normal() * 3, rng.normal() * 2))
    c = t.p(0, y0 + hh, 0.01)
    p = m.piece(color=col, gloss=70, merge=merge, res=0.008, lumps=0.002, dents=6, dent_size=0.04, dent_depth=0.005, detail=1.3 * detail)
    p.add(Box(c, (w, hh, L), tilt, round=0.02))
    p.add(Cylinder(c + tilt @ np.array([0, hh, 0]), w, L, tilt @ euler((90, 0, 0)), round=0.02), k=0.01)
    # ribs
    for zr in (-0.6, 0.6):
        rc = c + tilt @ np.array([0, 0, zr * L])
        p.add(Box(rc, (w + 0.008, hh, 0.012), tilt, round=0.008), k=0.004)
        p.add(Cylinder(rc + tilt @ np.array([0, hh, 0]), w + 0.008, 0.012, tilt @ euler((90, 0, 0)), round=0.008), k=0.004)
    # door (front face), latch
    dc = c + tilt @ np.array([0, hh * 0.35, L + 0.008])
    p.add(Box(dc - tilt @ np.array([0, hh * 0.35, 0]), (w - 0.012, hh - 0.01, 0.01), tilt, round=0.008), k=0.003, color=shade(col, 0.92))
    p.add(Cylinder(dc, w - 0.012, 0.01, tilt @ euler((90, 0, 0)), round=0.008), k=0.003, color=shade(col, 0.92))
    p.add(Box(c + tilt @ np.array([0, hh * 1.5, L + 0.025]), (0.025, 0.012, 0.02), tilt, round=0.006), k=0.004, color=TP["iron"])
    p.paint(patches(4, 0.18, int(rng.integers(999))), mix(TP["tin"], col, 0.25), feather=0.006)
    p.paint(patches(6, 0.3, int(rng.integers(999))), TP["rust"], feather=0.006)
    p.paint(below(y0 + 0.04, 0.02, 8), TP["rust_dk"], feather=0.02)
    # flag on +x side, raised
    fp = m.piece(color=TP["red"] if col != TP["red"] else TP["mustard"], gloss=60, merge=merge, res=0.005, lumps=0.001, detail=0.6 * detail)
    piv = c + tilt @ np.array([w + 0.012, -hh * 0.2, -L * 0.3])
    fp.add(Cylinder(piv, 0.018, 0.008, tilt @ euler((0, 0, 90))))
    fp.add(Box(piv + tilt @ np.array([0.01, 0.15, 0.0]), (0.006, 0.15, 0.012), tilt @ euler((rng.uniform(-8, 3), 0, 0)), round=0.004), k=0.003)
    fp.add(Box(piv + tilt @ np.array([0.01, 0.27, 0.06]), (0.006, 0.04, 0.06), tilt @ euler((rng.uniform(-8, 3), 0, 0)), round=0.004), k=0.003)
    return c + tilt @ np.array([0, hh * 0.4, L + 0.02])


def _anchor_parts(L=1.1, stock=0.5):
    """Key geometry for an Admiralty anchor in its own frame: crown at origin, shank along +y, arms in xy, stock along z."""
    arms = []
    for sx in (-1, 1):
        arms.append([np.array([sx * 0.04, 0.02, 0]), np.array([sx * 0.2, 0.06, 0]), np.array([sx * 0.33, 0.17, 0]), np.array([sx * 0.4, 0.33, 0])])
    return dict(L=L, stock_y=L - 0.12, stock=stock, arms=arms)


def anchor(m, t, merge="props", L=1.1, detail=1.0):
    """Old iron fisherman's (Admiralty) anchor resting on one fluke, its crown and one end of the stock;
    rusty with barnacles and a few chain links. Returns ring position."""
    rng = m.rng
    G = _anchor_parts(L)
    # contact points in the anchor frame
    keys = {"crown": (np.array([0, -0.0, 0]), 0.07), "fluke_l": (np.array([-0.45, 0.4, 0]), 0.03), "fluke_r": (np.array([0.45, 0.4, 0]), 0.03),
            "stock_a": (np.array([0, G["stock_y"], -G["stock"]]), 0.058), "stock_b": (np.array([0, G["stock_y"], G["stock"]]), 0.058),
            "ring": (np.array([0, L + 0.15, 0]), 0.02)}
    best = None
    for ax in np.arange(-90, 91, 2.0):
        for az in np.arange(-90, 91, 2.0):
            R = euler((ax, 0, az))
            ys = {k: (R @ p)[1] - rr for k, (p, rr) in keys.items()}
            mn = min(ys.values())
            sel = sorted(ys.values())[:3]
            # want crown + one fluke + one stock end as the three lowest, equal
            trio = [ys["crown"], min(ys["fluke_l"], ys["fluke_r"]), min(ys["stock_a"], ys["stock_b"])]
            score = np.ptp(trio) + 2 * max(0, max(trio) - sel[2])
            if best is None or score < best[0]:
                best = (score, R, mn)
    _, Ra, mn = best
    # recentre: anchor frame -> local with the lowest point on y=0 and the footprint centred
    pts = np.array([Ra @ p for p, _ in keys.values()])
    cx, cz = (pts[:, 0].max() + pts[:, 0].min()) / 2, (pts[:, 2].max() + pts[:, 2].min()) / 2
    off = np.array([-cx, -mn, -cz])

    def W(p):
        return t.p(Ra @ np.asarray(p, float) + off)
    RW = t.R @ Ra
    p = m.piece(color=TP["iron"], gloss=45, merge=merge, res=0.008, lumps=0.005, lump_freq=7, dents=12, dent_size=0.045, dent_depth=0.006,
                detail=1.5 * detail)
    p.add(Capsule(W((0, 0.03, 0)), W((0, L, 0)), 0.05, 0.04))
    p.add(Sphere(W((0, 0, 0)), 0.07), k=0.03)
    arm_r = [0.055, 0.05, 0.044, 0.036]
    for arm in G["arms"]:
        p.add(Tube([W(a) for a in arm], arm_r, samples=4), k=0.03)
        tip, prev = arm[-1], arm[-2]
        dirv = (tip - prev) / np.linalg.norm(tip - prev)
        inn = np.cross([0, 0, 1], dirv)
        if inn @ (-tip) < 0:
            inn = -inn
        fc = tip - dirv * 0.05 + inn * 0.025
        Rf = RW @ frame(dirv, inn)
        p.add(Ellipsoid(t.p(Ra @ fc + off), (0.115, 0.03, 0.1), Rf), k=0.025)
        p.add(Capsule(W(tip), W(tip + dirv * 0.08), 0.032, 0.012), k=0.018)
    # stock with ball ends
    sy = G["stock_y"]
    p.add(Capsule(W((0, sy, -G["stock"])), W((0, sy, G["stock"])), 0.042, 0.036), k=0.02)
    for sz in (-1, 1):
        p.add(Sphere(W((0, sy, sz * G["stock"])), 0.058), k=0.015)
    p.add(Box(W((0, sy, 0)), (0.065, 0.055, 0.075), RW, round=0.02), k=0.015)
    # ring
    p.add(Torus(W((0, L + 0.075, 0)), 0.072, 0.02, RW @ euler((90, 0, 0))), k=0.008)
    p.paint(patches(3.0, 0.02, int(rng.integers(999))), TP["rust_dk"], feather=0.012)
    p.paint(patches(5, 0.2, int(rng.integers(999))), mix(TP["rust"], TP["rust_dk"], 0.3), feather=0.01)
    p.paint(patches(8, 0.34, int(rng.integers(999))), TP["rust_lt"], feather=0.008)
    # barnacles + weed on the lower arm and crown
    arms_sorted = sorted(G["arms"], key=lambda arm: (Ra @ arm[-1])[1])
    low = arms_sorted[0]
    for i in range(14):
        k = int(rng.integers(0, 3))
        f = rng.uniform(0, 1)
        q = low[k] * (1 - f) + low[k + 1] * f
        seg = low[k + 1] - low[k]
        seg /= np.linalg.norm(seg)
        pd = np.cross(seg, rng.normal(size=3))
        pd /= np.linalg.norm(pd)
        rad = arm_r[k] * (1 - f) + arm_r[k + 1] * f
        br = rng.uniform(0.013, 0.022)
        cq = q + pd * (rad + br * 0.2)
        p.add(Ellipsoid(W(cq), (br, br, br), RW), k=0.006, color=pick(rng, [TP["barnacle"], TP["barnacle_dk"]]), gloss=60)
        p.sub(Sphere(W(q + pd * (rad + br * 1.05)), br * 0.4), k=0.003, color=TP["slime"])
    p.paint(Ellipsoid(W(low[2] * 0.5 + low[3] * 0.5), (0.1, 0.1, 0.1), RW), mix(TP["algae"], TP["rust_dk"], 0.3), gloss=110, feather=0.04)
    p.paint(Ellipsoid(W(low[1]), (0.05, 0.05, 0.05), RW), mix(TP["algae_lt"], TP["rust_dk"], 0.3), gloss=110, feather=0.03)
    # chain trailing from the ring to the ground
    rw = W((0, L + 0.14, 0))
    end = np.array([rw[0], 0.012, rw[2]]) + t.v((0.3, 0, 0.15))
    mid = (rw + end) / 2 + np.array([0, -0.12, 0])
    chain(m, merge, rw + np.array([0, -0.02, 0]), mid, link=0.07, wire=0.013, detail=0.7)
    chain(m, merge, mid, end, link=0.07, wire=0.013, detail=0.7)
    return rw


# ================================================================================================================
# nets, floats, pots


def net_rack(m, t, merge="props", net="net", width=2.6, h=1.9, detail=1.0, net_color=None):
    """Two rough poles + crossbar with a fishing net draped over it (net = matClass 4 sheet), cork float line."""
    rng = m.rng
    hx = width / 2
    pc = pick(rng, [TP["wood"], TP["wood_dk"], TP["wood_br"]])
    for sx in (-1, 1):
        post(m, merge, t.p(sx * hx, -0.05, 0), t.p(sx * hx + rng.normal() * 0.02, h + 0.08, rng.normal() * 0.02), 0.055, pc, square=False,
             detail=0.8 * detail)
        # raking struts
        post(m, merge, t.p(sx * (hx + 0.45), 0.0, 0.05), t.p(sx * hx, h * 0.62, 0), 0.03, shade(pc, 0.95), square=False, detail=0.4 * detail)
        # lashing at the top
        lp = m.piece(color=TP["rope_dk"], merge=merge, res=0.004, lumps=0.001, detail=0.3)
        for k in range(3):
            lp.add(Torus(t.p(sx * hx, h - 0.02 - k * 0.025, 0), 0.06, 0.008, t.r((rng.normal() * 6, 0, rng.normal() * 6))))
    pr = 0.045
    py = h - 0.02
    bar = m.piece(color=shade(pc, 1.05), merge=merge, res=0.01, lumps=0.003, lump_freq=6, dents=3, detail=0.7 * detail)
    bar.add(Capsule(t.p(-hx - 0.18, py + 0.01, 0), t.p(hx + 0.2, py - 0.01, 0), pr))
    # --- the net: a heavy bunched drape over the middle of the bar (thick folds; the shader cuts the mesh) ---
    th = 0.021
    xl = min(hx - 0.2, 0.8)
    seed = int(rng.integers(999))
    front_len, back_len = min(h - 0.5, 1.25), min(h * 0.45, 0.8)
    Rt = t.R

    def zfold(x, y, sgn, length):
        dn = np.clip((py - y) / length, 0, 1.2)
        amp = 0.025 + 0.11 * dn ** 0.7
        ph = 0.6 * np.sin(x * 1.7 + sgn) + 0.8 * fbm(np.column_stack([x * 0.8, y * 0.6, np.full_like(x, sgn)]), 2, seed)
        return sgn * (pr + th + 0.004 + 0.05 * dn + amp * (0.5 + 0.5 * np.sin(2 * np.pi * x / (0.3 + 0.12 * dn) + ph * 3)))

    def ybot(x, length):
        return py - length + 0.1 * np.sin(x * 2.3 + seed) + 0.05 * np.sin(x * 6.1)

    def xhalf(y, length):
        dn = np.clip((py - y) / length, 0, 1)
        return xl * (1 - 0.45 * dn) + 0.03 * np.sin(y * 7 + seed)

    def f(P):
        q = (P - t.o) @ Rt
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        rr = np.sqrt((y - py) ** 2 + z ** 2)
        d_top = np.where(y >= py, np.abs(rr - (pr + th + 0.004)) - th, 1e3)
        d_top = np.maximum(d_top, np.abs(x) - xl)
        ds = [d_top]
        for sgn, length in ((1, front_len), (-1, back_len)):
            zf = zfold(x, y, sgn, length)
            dc = (np.abs(z - zf) - th) * 0.55
            dc = np.maximum(dc, np.maximum(y - py, ybot(x, length) - y))
            dc = np.maximum(dc, np.abs(x) - xhalf(y, length))
            ds.append(dc)
        return np.minimum.reduce(ds)
    e = np.abs(Rt) @ np.array([xl + 0.1, (front_len + 0.6) / 2, 0.36])
    cb = t.p(0, py - (front_len + 0.6) / 2 + 0.16, 0)
    nc = net_color or pick(rng, [TP["net_green"], TP["net_blue"]])
    npc = m.piece(color=nc, gloss=40, mat=4, merge=net, res=0.0095, lumps=0.004, lump_freq=6, mottle=0.06, ao=True, detail=1.2 * detail)
    npc.add(Func(f, cb - e, cb + e))
    npc.paint(patches(1.8, 0.28, seed), TP["net_orange"], feather=0.01)
    npc.paint(below(t.p(0, 0.6, 0)[1], 0.1, 3), shade(nc, 0.8), feather=0.05)
    # cork float line along the front hem
    xs = np.linspace(-xhalf(py - front_len, front_len) + 0.05, xhalf(py - front_len, front_len) - 0.05, 11)
    fl = []
    for x in xs:
        yb = float(ybot(np.array([x]), front_len)[0]) + 0.05
        zf = float(zfold(np.array([x]), np.array([yb]), 1, front_len)[0])
        fl.append(t.p(x, yb, zf + th + 0.004))
    laid_rope(m, merge, fl, 0.008, TP["rope"], samples=3, detail=0.4)
    cp = m.piece(color=PP["cork"], gloss=30, merge=merge, res=0.006, lumps=0.002, lump_freq=20, detail=0.6 * detail)
    for i, x in enumerate(xs[::2]):
        q = fl[i * 2]
        cp.add(Ellipsoid(q + t.v((0, 0, 0.012)), (0.05, 0.03, 0.03), t.r((0, 0, rng.normal() * 8))), k=0.0,
               color=pick(rng, [PP["cork"], PP["cork_dk"], TP["ochre"]]))
    return t.p(0, py, 0)


def glass_float(m, t, merge, r=0.09, color=None, detail=1.0):
    """Glass fishing float in a rope net cage; t at the float centre. Returns the top tie point."""
    rng = m.rng
    col = color or pick(rng, [PP["float_green"], PP["float_aqua"], PP["float_amber"], PP["float_blue"]])
    g = m.piece(color=col, gloss=245, merge=merge, res=0.006, lumps=0.0015, lump_freq=10, mottle=0.05, detail=detail)
    g.add(Sphere(t.p(0, 0, 0), r))
    g.paint(patches(9, 0.3, int(rng.integers(999))), shade(col, 1.25), feather=0.01)
    np_ = m.piece(color=TP["rope_dk"], gloss=15, merge=merge, res=0.004, lumps=0.0008, detail=0.8 * detail)
    np_.add(Torus(t.p(0, 0, 0), r * 1.0, 0.0065, t.r()))
    for a in (0, 60, 120):
        np_.add(Torus(t.p(0, 0, 0), r * 1.0, 0.0065, t.r((90, a, 0))), k=0.003)
    np_.add(Torus(t.p(0, r * 0.98, 0), 0.02, 0.006, t.r()), k=0.004)
    return t.p(0, r + 0.02, 0)


def painted_buoy(m, t, merge, size=1.0, colors=None, detail=1.0):
    """Egg-shaped painted float with an eye on top; t at its centre. Returns the eye point."""
    rng = m.rng
    s = size
    a, b = colors or pick(rng, [(TP["red"], TP["cream"]), (TP["mustard"], TP["navy"]), (TP["teal"], TP["cream"]), ("#c46a3a", TP["white"])])
    p = m.piece(color=a, gloss=90, merge=merge, res=0.007, lumps=0.0025, dents=4, dent_size=0.03, dent_depth=0.004, detail=detail)
    R = t.r((rng.normal() * 4, 0, rng.normal() * 6))
    p.add(Ellipsoid(t.p(0, 0, 0), (0.09 * s, 0.14 * s, 0.09 * s), R))
    p.add(Capsule(t.p(0, 0.12 * s, 0), t.p(0, 0.17 * s, 0), 0.022 * s), k=0.02 * s)
    p.add(Torus(t.p(0, 0.2 * s, 0), 0.026 * s, 0.008 * s, t.r((90, 0, 0))), k=0.004, color=TP["iron"])
    p.paint(Box(t.p(0, 0.003 * s, 0), (0.2 * s, 0.038 * s, 0.2 * s), R), b, feather=0.004)
    p.paint(Box(t.p(0, 0.19 * s, 0), (0.2 * s, 0.05 * s, 0.2 * s), R), b, feather=0.004)
    p.paint(patches(6, 0.32, int(rng.integers(999))), mix(TP["wood"], a, 0.3), feather=0.004)
    p.paint(Box(t.p(0, -0.15 * s, 0), (0.2 * s, 0.05 * s, 0.2 * s), R), TP["slime"], gloss=90, feather=0.02)
    return t.p(0, 0.225 * s, 0)


def buoy_cluster(m, t, merge="props", n_glass=3, n_buoys=2, detail=1.0):
    """Floats and buoys hanging on ropes from a hook; t = hook point (origin at the top)."""
    rng = m.rng
    hp = m.piece(color=TP["iron"], gloss=60, merge=merge, res=0.004, lumps=0.0006, detail=0.4)
    hp.add(Torus(t.p(0, -0.028, 0), 0.024, 0.0065, t.r((90, 0, 0))))
    knot = t.p(0, -0.065, 0)
    kp = m.piece(color=TP["rope_dk"], merge=merge, res=0.004, lumps=0.001, detail=0.3)
    kp.add(Ellipsoid(knot, (0.03, 0.035, 0.03)))
    items = ["g"] * n_glass + ["b"] * n_buoys
    rng.shuffle(items)
    k = len(items)
    for i, kind in enumerate(items):
        a = 2 * np.pi * i / k + rng.normal() * 0.3
        rad = rng.uniform(0.1, 0.24)
        drop = rng.uniform(0.38, 0.95)
        c = t.p(math.cos(a) * rad, -0.07 - drop, math.sin(a) * rad)
        tt = T(c, rng.uniform(0, 360))
        top = glass_float(m, tt, merge, r=rng.uniform(0.1, 0.135), detail=detail) if kind == "g" else painted_buoy(m, tt.sub((0, -0.12, 0)), merge, size=rng.uniform(1.1, 1.3), detail=detail)
        mid = (knot + top) / 2 + np.array([rng.normal() * 0.01, 0, rng.normal() * 0.01])
        laid_rope(m, merge, [knot, mid, top], 0.009, TP["rope"], detail=0.4 * detail)
    return knot


def crab_pot(m, t, merge="props", net="net", size=(0.82, 0.36, 0.66), mesh_color=None, frame_color=None, detail=1.0):
    """Rectangular steel crab pot (frame bars + mesh panels, two tunnel eyes). t at its bottom centre. Returns top centre."""
    rng = m.rng
    W, H, D = size
    hx, hz = W / 2, D / 2
    fc = frame_color or pick(rng, [TP["iron"], TP["rust_dk"], "#4b4f52"])
    fr = m.piece(color=fc, gloss=60, merge=merge, res=0.0065, lumps=0.0012, dents=3, dent_size=0.03, detail=detail)
    br = 0.016
    cs = [np.array([sx * hx, y, sz * hz]) for y in (br, H - br) for sx in (-1, 1) for sz in (-1, 1)]
    edges = [(0, 1), (2, 3), (0, 2), (1, 3), (4, 5), (6, 7), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    for i, j in edges:
        fr.add(Capsule(t.p(cs[i] + rng.normal(size=3) * 0.004), t.p(cs[j] + rng.normal(size=3) * 0.004), br), k=0.01)
    # mid hoop around the long axis
    for x in (-hx * 0.35, hx * 0.35):
        fr.add(Capsule(t.p(x, br, -hz), t.p(x, H - br, -hz), br * 0.8), k=0.008)
        fr.add(Capsule(t.p(x, br, hz), t.p(x, H - br, hz), br * 0.8), k=0.008)
    fr.paint(patches(4, 0.05, int(rng.integers(999))), TP["rust"], feather=0.01)
    mc = mesh_color or pick(rng, [TP["net_green"], TP["net_orange"], TP["net_blue"], "#7a8a6a"])
    ms = m.piece(color=mc, gloss=40, mat=4, merge=net, res=0.0065, lumps=0.0015, lump_freq=8, mottle=0.06, detail=0.9 * detail)
    th = 0.009
    ms.add(Box(t.p(0, H - br, 0), (hx - 0.004, th, hz - 0.004), t.r((rng.normal() * 0.8, 0, rng.normal() * 0.8)), round=0.004))
    ms.add(Box(t.p(0, br, 0), (hx - 0.004, th, hz - 0.004), t.r(), round=0.004))
    for sx in (-1, 1):
        ms.add(Box(t.p(sx * (hx - 0.002), H / 2, 0), (th, H / 2 - br * 0.5, hz - 0.004), t.r(), round=0.004))
    eyes = []
    for sz in (-1, 1):
        ms.add(Box(t.p(0, H / 2, sz * (hz - 0.002)), (hx - 0.004, H / 2 - br * 0.5, th), t.r(), round=0.004))
        ec = t.p(rng.uniform(-0.1, 0.1), H * 0.52, sz * hz)
        eyes.append((ec, sz))
    for ec, sz in eyes:
        ms.sub(Ellipsoid(ec, (0.11, 0.075, 0.05), t.r()), k=0.006)
        inward = t.v((0, 0, -sz))
        # tunnel: a hollow cone of mesh running inward from the eye, open at both ends
        tn = m.piece(color=mc, gloss=40, mat=4, merge=net, res=0.006, lumps=0.001, mottle=0.06, detail=0.5 * detail)
        tn.add(Capsule(ec - inward * 0.05, ec + inward * 0.24, 0.1, 0.05))
        tn.sub(Capsule(ec - inward * 0.08, ec + inward * 0.3, 0.1 - th * 2.4, 0.05 - th * 2.4), k=0.002)
        tn.inter(HalfSpace(ec, -inward), k=0.003)
        tn.inter(HalfSpace(ec + inward * 0.2, inward), k=0.003)
        ring = m.piece(color=fc, gloss=60, merge=merge, res=0.005, lumps=0.001, detail=0.4 * detail)
        ring.add(Torus(ec, 0.1, 0.012, t.r((90, 0, 0))))
        ring.paint(patches(6, 0.1, 7), TP["rust"], feather=0.006)
    return t.p(0, H, 0)


def crab_pot_stack(m, t, merge="props", net="net", n=3, detail=1.0):
    """Stack of crab pots, a buoy and a rope coil on top. Returns top point."""
    rng = m.rng
    y = 0.0
    tt = t
    cols = [TP["net_green"], TP["net_orange"], TP["net_blue"], "#7a8a6a"]
    rng.shuffle(cols)
    top = None
    for i in range(n):
        sub = t.sub((rng.normal() * 0.04, y, rng.normal() * 0.04), rng.normal() * 7)
        top = crab_pot(m, sub, merge, net, mesh_color=cols[i % len(cols)], detail=detail)
        y += 0.36 + 0.004
    tb = t.sub((0.16, y + 0.11, -0.08), 0)
    eye = painted_buoy(m, T(tb.p(0, 0, 0), R=tb.R @ euler((0, 0, 78))), merge, size=1.15, colors=(TP["red"], TP["cream"]), detail=1.5 * detail)
    # rope from the buoy eye down over the side of the stack
    e = np.asarray(eye)
    pts = [e, t.p(-0.12, y + 0.05, 0.0), t.p(-0.33, y + 0.01, 0.08), t.p(-0.43, y - 0.08, 0.12), t.p(-0.44, y * 0.55, 0.2),
           t.p(-0.5, 0.25, 0.32), t.p(-0.62, 0.03, 0.45), t.p(-0.85, 0.022, 0.5)]
    laid_rope(m, merge, pts, 0.017, TP["rope"], samples=4, detail=2.5 * detail)
    return t.p(0, y, 0)


def ice_chest(m, t, merge="props", size=(0.92, 0.5, 0.52), open_deg=52, paint=None, detail=1.0):
    """Insulated wooden ice chest, lid hinged at the back (-z) and propped open; tin liner, crushed ice inside."""
    rng = m.rng
    W, H, D = size
    hx, hz = W / 2, D / 2
    paint = paint or pick(rng, [TP["teal"], TP["sage"], TP["cream"]])
    wood = TP["wood"]
    st = 0.04
    # walls: two horizontal boards per side
    for side in range(4):
        if side < 2:
            sz = 1 if side == 0 else -1
            a0, b0, out = np.array([-hx, 0, sz * (hz - st / 2)]), np.array([hx, 0, sz * (hz - st / 2)]), np.array([0, 0, sz])
        else:
            sx = 1 if side == 2 else -1
            a0, b0, out = np.array([sx * (hx - st / 2), 0, -hz + st]), np.array([sx * (hx - st / 2), 0, hz - st]), np.array([sx, 0, 0])
        for r in range(2):
            yc = 0.05 + (H - 0.05) * (r + 0.5) / 2
            board(m, merge, t.p(a0 + [0, yc, 0]), t.p(b0 + [0, yc, 0]), (H - 0.05) / 2 - 0.008, st, t.v(out), wood, paint=paint, peel=0.22,
                  nails=1, nail_inset=0.04, detail=detail, jitter=0.6)
    # corner battens + feet
    for sx in (-1, 1):
        for sz in (-1, 1):
            post(m, merge, t.p(sx * (hx + 0.012), 0.0, sz * (hz + 0.012)), t.p(sx * (hx + 0.012), H, sz * (hz + 0.012)), 0.028, TP["wood_dk"], detail=0.4 * detail)
    for z in (-hz * 0.6, hz * 0.6):
        board(m, merge, t.p(-hx - 0.02, 0.025, z), t.p(hx + 0.02, 0.025, z), 0.08, 0.05, t.v((0, 1, 0)), TP["wood_dk"], nails=0, detail=0.3, jitter=0.4)
    # tin liner rim + inner walls
    ln = m.piece(color=TP["tin"], gloss=90, merge=merge, res=0.008, lumps=0.0015, dents=3, detail=0.6 * detail)
    ln.add(Box(t.p(0, H / 2 + 0.03, 0), (hx - st + 0.004, H / 2 - 0.01, hz - st + 0.004), t.r(), round=0.01))
    ln.sub(Box(t.p(0, H / 2 + 0.08, 0), (hx - st - 0.01, H / 2, hz - st - 0.01), t.r(), round=0.01), k=0.004)
    ln.paint(patches(5, 0.2, 4), TP["rust"], feather=0.006)
    ice_heap(m, merge, t, hx - st - 0.015, hz - st - 0.015, H - 0.06, 0.09, chunks=45, detail=1.4 * detail,
             clip_box=Box(t.p(0, H, 0), (hx - st - 0.012, 0.3, hz - st - 0.012), t.r(), round=0.01))
    # rope handles on the ends
    for sx in (-1, 1):
        for zz in (-0.09, 0.09):
            cb = m.piece(color=TP["wood_dk"], merge=merge, res=0.006, lumps=0.001, detail=0.2)
            cb.add(Box(t.p(sx * (hx + 0.03), H * 0.68, zz), (0.022, 0.03, 0.025), t.r(), round=0.008))
        laid_rope(m, merge, [t.p(sx * (hx + 0.05), H * 0.68, -0.1), t.p(sx * (hx + 0.1), H * 0.56, -0.06), t.p(sx * (hx + 0.11), H * 0.5, 0.0),
                             t.p(sx * (hx + 0.1), H * 0.56, 0.06), t.p(sx * (hx + 0.05), H * 0.68, 0.1)], 0.017, TP["rope"], samples=4, detail=1.2)
    # lid, hinged at the back top edge
    hinge = np.array([0, H + 0.005, -hz])
    Rl = euler((-open_deg, 0, 0))
    lt = T(t.p(hinge), R=t.R @ Rl)
    for k in range(3):
        z = 0.02 + (D - 0.02) * (k + 0.5) / 3
        board(m, merge, lt.p(-hx - 0.02, 0.022, z), lt.p(hx + 0.02, 0.022, z), D / 3 - 0.012, 0.042, lt.v((0, 1, 0)), wood, paint=paint, peel=0.25,
              nails=2, nail_inset=0.05, detail=0.9 * detail, jitter=0.6)
    for x in (-hx + 0.1, hx - 0.1):
        board(m, merge, lt.p(x, -0.005, 0.04), lt.p(x, -0.005, D - 0.02), 0.07, 0.03, lt.v((0, 1, 0)), wood, nails=0, detail=0.3, jitter=0.4)
    hg = m.piece(color=TP["iron"], gloss=60, merge=merge, res=0.005, lumps=0.0008, detail=0.3)
    for x in (-hx * 0.55, hx * 0.55):
        hg.add(Cylinder(t.p(x, H + 0.005, -hz - 0.01), 0.014, 0.05, t.r((0, 0, 90)), round=0.004))
    # prop stick holding the lid
    post(m, merge, t.p(hx - 0.12, H - 0.02, -0.0), lt.p(hx - 0.12, -0.01, D * 0.62), 0.014, TP["wood_new2"], square=False, detail=0.3)
    return t.p(0, H, 0)


# ================================================================================================================
# flowers


def _geranium(m, merge, c, R, rng, color, detail=1.0, n_heads=5, spread=0.11, height=0.16):
    """Leaves + flower heads around c (world point at soil level) in frame R."""
    lp = m.piece(color=PP["leaf_dk"], gloss=40, merge=merge, res=0.0055, lumps=0.003, lump_freq=22, mottle=0.08, detail=1.2 * detail)
    lp.add(Ellipsoid(c + R @ np.array([0, 0.03, 0]), (spread * 0.85, 0.045, spread * 0.85), R))
    for i in range(int(n_heads * 4)):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(0.25, 1.05) * spread
        lc = c + R @ np.array([math.cos(a) * rr, rng.uniform(0.03, 0.085) * (1.1 - 0.5 * rr / spread), math.sin(a) * rr])
        tilt = euler((rng.uniform(-30, 30), rng.uniform(0, 360), rng.uniform(-30, 30)))
        lr = rng.uniform(0.036, 0.055)
        lp.add(Ellipsoid(lc, (lr, 0.01, lr), R @ tilt), k=0.012, color=pick(rng, [PP["leaf"], PP["leaf_dk"], "#6b8a4c"]))
    fp = m.piece(color=color, gloss=45, merge=merge, res=0.0045, lumps=0.002, lump_freq=30, mottle=0.06, detail=detail)
    for i in range(n_heads):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(0.0, spread * 0.8)
        top = c + R @ np.array([math.cos(a) * rr, height * rng.uniform(0.75, 1.15), math.sin(a) * rr])
        base = c + R @ np.array([math.cos(a) * rr * 0.4, 0.03, math.sin(a) * rr * 0.4])
        fp.add(Capsule(base, top, 0.0055), k=0.004, color=PP["leaf_dk"])
        for k in range(13):
            q = top + rng.normal(size=3) * np.array([0.022, 0.016, 0.022]) + np.array([0, 0.012, 0])
            fp.add(Sphere(q, rng.uniform(0.013, 0.019)), k=0.006, color=pick(rng, [color, shade(color, 1.12), shade(color, 0.88)]))


def _thrift(m, merge, c, R, rng, detail=1.0):
    gp = m.piece(color=PP["leaf"], gloss=30, merge=merge, res=0.0045, lumps=0.001, detail=0.8 * detail)
    for i in range(26):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(0, 0.05)
        b = c + R @ np.array([math.cos(a) * rr, 0.01, math.sin(a) * rr])
        tip = b + R @ np.array([math.cos(a) * 0.05, rng.uniform(0.05, 0.09), math.sin(a) * 0.05])
        gp.add(Capsule(b, tip, 0.006, 0.002), k=0.003, color=pick(rng, [PP["leaf"], "#7a9356"]))
    fp = m.piece(color=PP["thrift"], gloss=30, merge=merge, res=0.004, lumps=0.0015, lump_freq=40, detail=detail)
    for i in range(7):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(0, 0.06)
        b = c + R @ np.array([math.cos(a) * rr * 0.4, 0.02, math.sin(a) * rr * 0.4])
        top = c + R @ np.array([math.cos(a) * rr, rng.uniform(0.15, 0.22), math.sin(a) * rr])
        fp.add(Capsule(b, top, 0.003), k=0.002, color="#8a9a5c")
        fp.add(Sphere(top, rng.uniform(0.018, 0.024)), k=0.004, color=pick(rng, [PP["thrift"], shade(PP["thrift"], 1.1), "#c77d95"]))


def flower_pot(m, t, merge="props", kind="geranium", r=0.12, h=0.2, color=None, detail=1.0):
    """Terracotta pot with geraniums (or sea-pinks: kind='thrift'). Returns soil centre."""
    rng = m.rng
    col = color or PP["terracotta"]
    p = m.piece(color=col, gloss=25, merge=merge, res=0.006, lumps=0.002, dents=5, dent_size=0.025, dent_depth=0.003, detail=detail)
    p.add(Capsule(t.p(0, 0.0, 0), t.p(0, h, 0), r * 0.78, r))
    p.inter(HalfSpace(t.p(0, 0.0, 0), t.v((0, -1, 0))), k=0.006)
    p.inter(HalfSpace(t.p(0, h, 0), t.v((0, 1, 0))), k=0.004)
    p.add(Torus(t.p(0, h - 0.012, 0), r + 0.004, 0.022, t.r((rng.normal() * 1.5, 0, rng.normal() * 1.5))), k=0.008)
    p.sub(Cylinder(t.p(0, h + 0.02, 0), r - 0.018, 0.05), k=0.008, color=PP["terracotta_dk"])
    p.paint(below(t.p(0, 0.05, 0)[1], 0.01, 9), PP["terracotta_dk"], feather=0.015)
    p.paint(patches(5, 0.28, int(rng.integers(999))), "#c9b9a0", feather=0.01)  # salt bloom
    s = m.piece(color=PP["soil"], gloss=15, merge=merge, res=0.006, lumps=0.003, lump_freq=25, detail=0.3)
    s.add(Cylinder(t.p(0, h - 0.035, 0), r - 0.012, 0.012, round=0.006))
    c = t.p(0, h - 0.025, 0)
    if kind == "thrift":
        _thrift(m, merge, c, t.R, rng, detail)
    else:
        _geranium(m, merge, c, t.R, rng, pick(rng, [PP["geranium"], PP["geranium_pk"]]), detail, n_heads=6, spread=r * 1.05, height=0.2)
    return c


def flower_box(m, t, merge="props", L=1.0, depth=0.22, h=0.19, paint=None, detail=1.0):
    """Window flower box: back face at z=0 (wall), box toward +z, bottom at y=0; two brackets below.
    Origin = back-bottom-centre. Returns soil centre."""
    rng = m.rng
    paint = paint or pick(rng, [TP["teal"], TP["red"], TP["mustard"], TP["navy"], TP["sage"]])
    hl = L / 2
    st = 0.035
    board(m, merge, t.p(-hl, h / 2, depth - st / 2), t.p(hl, h / 2, depth - st / 2), h, st, t.v((0, 0, 1)), TP["wood"], paint=paint, peel=0.2,
          nails=1, nail_inset=0.03, detail=detail, jitter=0.6)
    board(m, merge, t.p(-hl + 0.01, h / 2, st / 2), t.p(hl - 0.01, h / 2, st / 2), h, st, t.v((0, 0, -1)), TP["wood"], paint=paint, peel=0.3,
          nails=0, detail=0.4, jitter=0.5)
    for sx in (-1, 1):
        board(m, merge, t.p(sx * (hl - st / 2), h / 2, st), t.p(sx * (hl - st / 2), h / 2, depth - st), h, st, t.v((sx, 0, 0)), TP["wood"],
              paint=paint, peel=0.25, nails=1, nail_inset=0.02, detail=0.6 * detail, jitter=0.5)
    board(m, merge, t.p(-hl + 0.02, st / 2, depth / 2), t.p(hl - 0.02, st / 2, depth / 2), depth - 0.02, st, t.v((0, 1, 0)), TP["wood_dk"], nails=0,
          detail=0.3, jitter=0.4)
    # brackets
    for sx in (-1, 1):
        x = sx * (hl - 0.15)
        post(m, merge, t.p(x, -0.2, 0.02), t.p(x, -0.01, 0.02), 0.02, TP["wood_dk"], detail=0.3)
        post(m, merge, t.p(x, -0.01, 0.02), t.p(x, -0.01, depth - 0.03), 0.02, TP["wood_dk"], detail=0.3)
        post(m, merge, t.p(x, -0.18, 0.03), t.p(x, -0.02, depth - 0.06), 0.016, TP["wood_dk"], detail=0.3)
    s = m.piece(color=PP["soil"], gloss=15, merge=merge, res=0.007, lumps=0.004, lump_freq=20, detail=0.3)
    s.add(Box(t.p(0, h - 0.035, depth / 2), (hl - st, 0.02, depth / 2 - st), t.r(), round=0.01))
    # flowers: geraniums + daisies + trailing ivy over the front
    n = int(L / 0.25)
    for i in range(n):
        x = -hl + st + (i + 0.5) * (L - 2 * st) / n + rng.normal() * 0.02
        c = t.p(x, h - 0.025, depth / 2 + rng.normal() * 0.02)
        if i % 2 == 0:
            _geranium(m, merge, c, t.R, rng, pick(rng, [PP["geranium"], PP["geranium_pk"]]), 0.8 * detail, n_heads=4, spread=0.11, height=0.17)
        else:
            dp = m.piece(color=PP["daisy"], gloss=30, merge=merge, res=0.0045, lumps=0.001, detail=0.5 * detail)
            dp.add(Ellipsoid(c + t.v((0, 0.025, 0)), (0.09, 0.035, 0.07), t.r()), k=0.0, color=PP["leaf"])
            for k in range(9):
                q = c + t.v((rng.normal() * 0.06, rng.uniform(0.05, 0.11), rng.normal() * 0.045))
                dp.add(Ellipsoid(q, (0.024, 0.007, 0.024), t.r((rng.uniform(-30, 30), 0, rng.uniform(-30, 30)))), k=0.003,
                       color=pick(rng, [PP["daisy"], PP["lobelia"]]))
                dp.add(Sphere(q + t.v((0, 0.005, 0)), 0.007), k=0.002, color=TP["mustard"])
                dp.add(Capsule(c, q, 0.003), k=0.002, color=PP["leaf_dk"])
    for i in range(6):
        x = rng.uniform(-hl + 0.08, hl - 0.08)
        a = t.p(x, h - 0.02, depth - 0.03)
        pts = [a, t.p(x + 0.02, h + 0.01, depth + 0.02), t.p(x + 0.03, h - 0.08, depth + 0.035), t.p(x + rng.normal() * 0.04, -rng.uniform(0.05, 0.22), depth + 0.04)]
        ip = m.piece(color=PP["ivy"], gloss=40, merge=merge, res=0.0045, lumps=0.001, detail=0.7 * detail)
        ip.add(Tube(pts, 0.0055, samples=4))
        P = np.array(pts)
        for k in range(6):
            f = (k + 0.5) / 6
            q = P[min(int(f * 3), 2)] * (1 - (f * 3 % 1)) + P[min(int(f * 3) + 1, 3)] * (f * 3 % 1)
            ip.add(Ellipsoid(q + t.v((rng.normal() * 0.012, 0, 0.01)), (0.026, 0.022, 0.006), t.r((rng.normal() * 20, rng.normal() * 30, 0))), k=0.003)
    return t.p(0, h, depth / 2)


# ================================================================================================================
# bunting, signs


class Pennant(Prim):
    """Thin triangular flag hanging from its top edge: local x across (half w), local -y down (length L), z normal.
    Waves a little; hem rolled over the line."""

    def __init__(self, c, w, L, R, th=0.006, wave=0.015, seed=0):
        super().__init__()
        self.c, self.w, self.L, self.R, self.th, self.wave = np.asarray(c, float), w, L, R, th, wave
        self.ph = seed * 0.77

    def sdf(self, P):
        q = (P - self.c) @ self.R
        x, y, z = q[:, 0], -q[:, 1], q[:, 2]
        v = np.clip(y / self.L, 0, 1)
        z = z - self.wave * np.sin(v * 3.5 + self.ph) * v - 0.008 * np.sin(x * 25 + self.ph)
        half = 0.5 * self.w * (1 - v)
        # 2D distance to the triangle (x, y): edges approximated
        slope = 0.5 * self.w / self.L
        k = 1 / math.sqrt(1 + slope * slope)
        d2 = np.maximum((np.abs(x) - half) * k, np.maximum(-y, y - self.L))
        dz = np.abs(z) - self.th
        qd = np.stack([d2, dz], 1)
        d = np.linalg.norm(np.maximum(qd, 0), axis=1) + np.minimum(qd.max(1), 0)
        # rolled hem along the top
        hem = np.sqrt((y - 0.004) ** 2 + z ** 2) - 0.0115
        hem = np.maximum(hem, np.abs(x) - self.w * 0.5)
        return np.minimum(d, hem)

    def bounds(self):
        lo = np.array([-self.w / 2 - 0.02, -self.L - 0.02, -0.05])
        hi = np.array([self.w / 2 + 0.02, 0.03, 0.05])
        C = np.array([[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])])
        W = C @ self.R.T + self.c
        return W.min(0), W.max(0)


def bunting_pole(m, t, merge="props", metal="metal", h=2.55, tie=2.35, detail=1.0):
    """A weathered pole planted to carry a string of bunting: round timber, tin cap, an iron eye at `tie` for the
    string, a lashing of rope just below, and the same braced foot as the lantern posts."""
    rng = m.rng
    col = pick(rng, [TP["wood"], TP["wood_dk"], TP["wood_br"]])
    post(m, merge, t.p(0, 0.0, 0), t.p(0.012, h, -0.006), 0.05, col, square=False, detail=detail)
    cp = m.piece(color=TP["tin_dk"], gloss=50, merge=merge, res=0.006, lumps=0.001, detail=0.4 * detail)
    cp.add(Sphere(t.p(0.012, h + 0.01, -0.006), 0.062), k=0.0)
    cp.sub(Box(t.p(0.012, h - 0.05, -0.006), (0.08, 0.05, 0.08)))
    cp.paint(patches(8, 0.1, 6), TP["rust"], feather=0.008)
    ey = m.piece(color=TP["iron"], gloss=60, merge=metal, res=0.004, lumps=0.0006, detail=0.4)
    ey.add(Torus(t.p(0.011, tie, -0.006), 0.062, 0.008, t.r((90, 0, 0))))
    rp = m.piece(color=TP["rope"], gloss=20, merge=merge, res=0.004, lumps=0.0008, detail=0.4 * detail)
    for k in range(3):
        rp.add(Torus(t.p(0.011, tie - 0.12 - k * 0.022, -0.006), 0.056, 0.009, t.r((rng.normal() * 4, 0, rng.normal() * 4))), k=0.004)
    for yaw in (0, 90):
        tt = t.sub((0, 0, 0), yaw)
        board(m, merge, tt.p(-0.3, 0.03, 0), tt.p(0.3, 0.03, 0), 0.09, 0.055, tt.v((0, 1, 0)), shade(col, 0.9), nails=1, detail=0.6 * detail)
    for k in range(4):
        a = np.pi / 2 * k
        d = np.array([math.cos(a), 0, math.sin(a)])
        post(m, merge, t.p(d * 0.25 + [0, 0.06, 0]), t.p(d * 0.045 + [0, 0.4, 0]), 0.018, shade(col, 0.95), detail=0.4 * detail)


def bunting(m, t, merge="props", span=6.0, sag=0.4, spacing=0.3, flag_w=0.19, flag_l=0.25, colors=None, detail=1.0):
    """A string of faded cloth pennants from x=-span/2 to +span/2 at y=0 sagging `sag` in the middle (origin at
    the chord midpoint)."""
    rng = m.rng
    colors = colors or [PP["flag_red"], PP["flag_cream"], PP["flag_teal"], PP["flag_mustard"]]
    hs = span / 2

    def yline(x):
        return -sag * (1 - (x / hs) ** 2)
    # the line, in short segments
    xs = np.linspace(-hs, hs, 11)
    for i in range(len(xs) - 1):
        seg = np.linspace(xs[i], xs[i + 1], 4)
        pts = [t.p(x, yline(x), 0) for x in seg]
        lp = m.piece(color=TP["rope"], gloss=20, merge=merge, res=0.0038, lumps=0.0005, detail=0.25 * detail)
        lp.add(Tube(pts, 0.0055))
    n = int((span - 0.3) / spacing) + 1
    x0 = -(n - 1) * spacing / 2
    for i in range(n):
        x = x0 + i * spacing + rng.normal() * 0.01
        y = yline(x)
        slope = 2 * sag * x / (hs * hs)
        R = t.R @ euler((rng.normal() * 9, rng.normal() * 6, math.degrees(math.atan(slope))))
        col = colors[i % len(colors)]
        col = mix(col, TP["cream"], rng.uniform(0.0, 0.18))
        p = m.piece(color=col, gloss=15, merge=merge, res=0.0042, lumps=0.0012, lump_freq=20, mottle=0.07, detail=detail)
        p.add(Pennant(t.p(x, y, 0), flag_w, flag_l, R, wave=rng.uniform(0.008, 0.02), seed=i))
        p.paint(patches(7, 0.3, i), shade(col, 0.85), feather=0.01)
    return t.p(0, -sag, 0)


def sign_post(m, t, merge="props", h=2.15, arrows=None, paint=None, detail=1.0):
    """Timber sign post with arrow boards (blank faces). Returns list of (pos, yaw) for text sockets, faces +z
    of each board, text reading along the board's +x."""
    rng = m.rng
    arrows = arrows or [(1.9, 12, 1), (1.62, -18, -1), (1.36, 30, 1)]
    pc = pick(rng, [TP["wood"], TP["wood_dk"]])
    post(m, merge, t.p(0, -0.05, 0), t.p(0.012, h, -0.008), 0.055, pc, detail=0.8 * detail)
    cp = m.piece(color=pc, merge=merge, res=0.007, lumps=0.002, detail=0.3)
    cp.add(Capsule(t.p(0.012, h, -0.008), t.p(0.012, h + 0.07, -0.008), 0.065, 0.01))
    # stones around the foot
    sp = m.piece(color=TP["stone"], merge=merge, res=0.01, lumps=0.006, lump_freq=8, dents=4, detail=0.5 * detail)
    for k in range(7):
        a = 2 * np.pi * k / 7 + rng.normal() * 0.2
        rr = rng.uniform(0.1, 0.17)
        s = rng.uniform(0.05, 0.085)
        sp.add(Ellipsoid(t.p(math.cos(a) * rr, s * 0.45, math.sin(a) * rr), (s, s * 0.7, s * 0.85), t.r((0, rng.uniform(0, 180), rng.normal() * 10))),
               k=0.02, color=pick(rng, [TP["stone"], TP["stone_dk"], TP["stone_lt"]]))
    socks = []
    for i, (y, yaw, d) in enumerate(arrows):
        L, w, st = 0.78, 0.17, 0.035
        tt = t.sub((0, 0, 0), yaw)
        zf = 0.055 + st / 2 + 0.004
        a = tt.p(-0.1 * d - 0.04 * d, y, zf)
        b = tt.p(d * (L - 0.14), y, zf)
        col = paint or pick(rng, [TP["cream"], TP["white"], TP["cream"], TP["mustard"]])
        p = board(m, merge, a, b, w, st, tt.v((0, 0, 1)), TP["wood"], paint=col, peel=0.22, nails=1, nail_inset=0.06, detail=detail, jitter=0.5,
                  ends=(0.0, 0.0), bow=0.002, twist=rng.normal() * 1.0)
        tip = tt.p(d * (L - 0.14), y, zf)
        X = tt.v((d, 0, 0))
        Y = tt.v((0, 1, 0))
        # point: cut with two 45-degree planes
        for sy in (-1, 1):
            n_ = X * 0.7071 + Y * sy * 0.7071
            p.inter(HalfSpace(tip, n_), k=0.003)
        # swallowtail notch at the back
        back = tt.p(-0.14 * d, y, zf)
        p.sub(Box(back - X * 0.02, (0.05, 0.05, 0.05), frame(X, Y) @ euler((0, 0, 45)), round=0.002), k=0.003)
        mid = (tt.p(-0.1 * d, y, zf) + tip) / 2 - X * 0.03
        sockp = mid + tt.v((0, 0, st / 2 + 0.004))
        socks.append((sockp, t_yaw(t) + yaw))
    return socks


def t_yaw(t):
    R = t.R
    return math.degrees(math.atan2(R[0, 2], R[2, 2]))
