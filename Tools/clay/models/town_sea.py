"""
Sea & sky set pieces for Saltmoss Harbor (scattered at sea by the game): sea stacks, icebergs, kelp, a bell buoy
channel marker, a half-sunk wreck, and cotton-wool clouds / smoke puffs / spray.

y = 0 is sea level for everything that floats or stands in the sea; the sea is opaque clay, so parts below about
-0.5 are never seen and are kept coarse. Clouds: pivot at the centre of the flat-ish bottom. Smoke puffs: pivot at
the puff centre. Spray: pivot at the water line, bottom-centre.
"""
import math

import numpy as np
from clay import Prim, Func, Sphere, Ellipsoid, Capsule, Tube, Box, Cylinder, Torus, HalfSpace, euler, look_rot, gradient, fbm, shade, mix, rgb
from kit_town import TownModel, TP, T, frame, rot_axis, patches, band, below, board, rope
from town_nature import NP, Chunk, surface_points, barnacles, ribbon, drape

MODELS = {}

SP = dict(
    ice="#dbe8ee", ice_lt="#eef4f5", ice_blue="#a9c8d8", ice_deep="#7fa9c2", snow="#f1f3f1",
    turf="#6f8a4b", turf_dk="#566f3c", turf_lt="#8aa05c", thrift="#d78fa0",
    buoy_red="#a8473b", buoy_red_dk="#86372f", bell="#9c7a3e", patina="#6f9a86",
    cotton="#f2f0ea", cotton_shade="#c8ccd2", smoke="#d6d3cd", smoke_dk="#b3b0ab", foam="#eef2f0", foam_blue="#cfe0e3",
    hull_paint="#3f5f6e", hull_trim="#a4483a",
)


# ----------------------------------------------------------------------------------------------------------------
# little nesting gull (shared)


def gull(m, merge, pos, yaw, s=1.0, sitting=True):
    t = T(pos, yaw, s)
    p = m.piece(color="#eeebe3", gloss=60, merge=merge, res=0.012 * s, lumps=0.002 * s, mottle=0.05, detail=1.0, decimate=int(220))
    p.add(Ellipsoid(t.p(0, 0.12, 0), np.array([0.11, 0.1, 0.17]) * s, t.r((8, 0, 0))))
    p.add(Sphere(t.p(0, 0.25, 0.12), 0.075 * s), k=0.05 * s)
    p.add(Capsule(t.p(0, 0.26, 0.18), t.p(0, 0.245, 0.27), 0.022 * s, 0.01 * s), k=0.01 * s, color="#e7c13f", gloss=120)
    p.paint(Sphere(t.p(0, 0.243, 0.255), 0.008 * s), "#c4442e")
    for sx in (-1, 1):
        p.add(Ellipsoid(t.p(sx * 0.09, 0.15, -0.03), np.array([0.04, 0.07, 0.15]) * s, t.r((10, sx * 8, 0))), k=0.02 * s, color="#8e959c")
        p.add(Sphere(t.p(sx * 0.04, 0.27, 0.175), 0.012 * s), k=0.003 * s, color="#1d1e20", gloss=220)
    p.add(Ellipsoid(t.p(0, 0.14, -0.2), np.array([0.05, 0.025, 0.07]) * s, t.r((-15, 0, 0))), k=0.02 * s, color="#2b2d30")
    return p


def surface_drips(m, merge, f, lo, hi, n, rng, *, width=0.06, length=10, step=0.12, color=None, res=0.02, detail=0.6, thick=0.02, tris=None):
    """Gull streaks: white drips running down a surface from ledges (points where the surface faces up)."""
    P, N = surface_points(f, lo, hi, n, rng, cond=lambda P, N: N[:, 1] > 0.35)
    out = []
    for c, nn in zip(P, N):
        pts, nrm = drape(f, c, (0, -1, 0), length, step, rng, lift=thick * 0.6, wander=0.08, grav=0.92)
        if len(pts) < 3:
            continue
        p = m.piece(color=color or NP["guano"], gloss=70, merge=merge, res=res, lumps=0.002, mottle=0.04, detail=detail, decimate=tris)
        w = width * np.linspace(1.0, 0.35, len(pts)) * rng.uniform(0.7, 1.3)
        ribbon(p, pts, nrm, w, thick)
        out.append(p)
    return out


# ----------------------------------------------------------------------------------------------------------------
# sea stacks


def _stack(name, seed, H, base, waist=0.25, arch=False, gulls=3, budget=20000, lean=(0.0, 0.0)):
    def fn():
        m = TownModel(name, budget=budget, seed=seed)
        rng = m.rng
        cols = [NP["rock"], NP["rock_dk"], NP["rock_warm"], NP["rock_cool"], "#7c736a", NP["rock_lt"]]
        body = m.piece(color=cols[0], gloss=45, merge="rock", res=0.07, lumps=0.06, lump_freq=0.5, dents=50, dent_size=0.5, dent_depth=0.06,
                       mottle=0.1, detail=1.0)
        y = -3.0
        off = np.zeros(3)
        levels = []
        prims = []
        while y < H - 0.6:
            t = (y + 3) / (H + 3)
            h = rng.uniform(1.4, 2.4)
            sh = (1 - waist * math.sin(math.pi * t * 0.9) - 0.22 * t)
            rx = base[0] * sh * rng.uniform(0.93, 1.07)
            rz = base[1] * sh * rng.uniform(0.93, 1.07)
            off = off + np.array([lean[0] * h + rng.normal() * 0.08, 0, lean[1] * h + rng.normal() * 0.08])
            c = off + np.array([0, y + h * 0.5, 0])
            ch = Chunk(c, (rx, h * 0.75, rz), n=10, k=0.12, rot=(rng.normal() * 2.5, rng.uniform(0, 360), rng.normal() * 2.5), seed=int(rng.integers(1e6)),
                       cut=(0.66, 0.9), box=True, boxd=(0.94, 1.0))
            prims.append(ch)
            body.add(ch, k=0.45, color=cols[len(levels) % len(cols)])
            levels.append((c, rx, rz, h))
            y += h * 0.62
        # tall buttress blocks leaning on the sides break up the layer-cake rhythm
        for i in range(4):
            j = int(rng.integers(0, max(1, len(levels) - 2)))
            c0, rx0, rz0, h0 = levels[j]
            a = rng.uniform(0, 2 * np.pi)
            d = np.array([math.cos(a) * rx0, 0, math.sin(a) * rz0]) * 0.75
            hh = rng.uniform(2.5, 4.5)
            body.add(Chunk(c0 + d + np.array([0, hh * 0.35, 0]), (rx0 * 0.45, hh * 0.6, rz0 * 0.45), n=9, k=0.1, rot=(rng.normal() * 4, rng.uniform(0, 360), rng.normal() * 4),
                           seed=int(rng.integers(1e6)), cut=(0.6, 0.88), box=True), k=0.35, color=cols[(i + 2) % len(cols)])
        top_c, top_rx, top_rz, top_h = levels[-1]
        top_y = top_c[1] + top_h * 0.75
        if arch:
            ax = levels[2][0][0]
            body.sub(Capsule((ax, 0.2, -base[1] * 2), (ax, 0.3, base[1] * 2), 1.3), k=0.35, color=NP["rock_dk"])
            body.sub(Ellipsoid((ax, 1.5, 0), (1.15, 1.6, base[1] * 2)), k=0.35)
        # vertical joints and horizontal bedding grooves cut with a knife
        for i in range(7):
            a = rng.uniform(0, 2 * np.pi)
            d = np.array([math.cos(a), 0, math.sin(a)])
            y0 = rng.uniform(-1.0, H * 0.6)
            cc = np.array([d[0] * base[0], y0 + 1.5, d[2] * base[1]]) * np.array([0.95, 1, 0.95])
            body.sub(Box(cc, (0.04, rng.uniform(1.0, 2.6), base[0] * 0.5), frame(np.cross(d, [0, 1, 0]), [0, 1, 0]) @ euler((0, 90, rng.normal() * 4)),
                         round=0.02), k=0.06, color=shade(NP["rock"], 0.55))
        for i in range(5):
            yy = rng.uniform(1.0, H - 1.0)

            def groove(P, _y=yy, _p=rng.uniform(0, 6)):
                g = np.abs(P[:, 1] - _y - 0.15 * np.sin(P[:, 0] * 0.7 + _p) - 0.1 * np.sin(P[:, 2] * 0.9)) - 0.045
                m_ = (np.abs(P[:, 1] - _y) < 0.6)
                out = np.full(len(P), 1.0)
                if m_.any():
                    d = np.minimum.reduce([q(P[m_]) for q in prims])
                    out[m_] = np.maximum(g[m_], -(d + 0.1))
                return out
            body.sub(Func(groove, (-1e4,) * 3, (1e4,) * 3), k=0.05, color=shade(NP["rock"], 0.7))
        body.inter(HalfSpace((0, -3.0, 0), (0, -1, 0)), k=0.05)
        body.paint(below(0.75, 0.25, 0.8, 3), shade(NP["rock"], 0.62), gloss=110, feather=0.15)
        body.paint(band(-0.8, 0.35, 0.18, 1.0, 5), TP["algae"], gloss=140, feather=0.1)
        body.paint(band(0.25, 0.65, 0.12, 1.4, 6), TP["slime"], gloss=100, feather=0.08)
        body.paint(patches(0.45, 0.22, 7), mix(NP["lichen_grey"], NP["rock"], 0.4), feather=0.02)
        body.paint(Func(lambda P: np.maximum(2.5 - P[:, 1], (0.4 - fbm(P * 0.7, 2, 21)) * 0.1), (-1e4,) * 3, (1e4,) * 3),
                   mix(NP["lichen_or"], NP["rock"], 0.6), feather=0.01)
        f = body.sdf
        # gull streaks: broad white smears running down from the ledges
        P, N = surface_points(f, np.array([-base[0] * 1.6, 2.0, -base[1] * 1.6]), np.array([base[0] * 1.6, top_y - 0.3, base[1] * 1.6]), 16, rng,
                              cond=lambda P, N: N[:, 1] > 0.3)
        for q in P:
            ln = rng.uniform(1.0, 3.2)
            body.paint(Capsule(q + np.array([0, 0.1, 0]), q - np.array([0, ln, 0]), rng.uniform(0.22, 0.36), 0.08), mix(NP["guano"], NP["rock"], 0.04),
                       feather=0.08)
        lo = np.array([-base[0] * 2.2, -0.5, -base[1] * 2.2])
        hi = np.array([base[0] * 2.2, 0.55, base[1] * 2.2])
        barnacles(m, "barn", f, lo, hi, 26, rng, size=(0.05, 0.085), res=0.016, tris=40, cond=lambda P, N: N[:, 1] > -0.5)
        from town_nature import weed_skin
        weed_skin(m, "weed", f, np.array([-base[0] * 1.6, -0.6, -base[1] * 1.6]), np.array([base[0] * 1.6, 1.6, base[1] * 1.6]), 0.4, thick=0.06,
                  base=-0.6, seed=seed, res=0.035, freq=1.6, ragged=0.38, detail=0.6)
        # turf cap: a cushion of green clay pressed on top, lipping over the edge, scored with a tool
        turf = m.piece(color=mix(SP["turf"], NP["rock"], 0.15), gloss=30, merge="turf", res=0.045, lumps=0.035, lump_freq=1.1, dents=16, dent_size=0.35, dent_depth=0.05,
                       mottle=0.12, detail=0.9)
        tc = top_c + np.array([0, top_h * 0.62, 0])
        turf.add(Ellipsoid(tc, (top_rx * 1.08, 0.5, top_rz * 1.08), (rng.normal() * 4, rng.uniform(0, 360), rng.normal() * 4)).lumpy(0.12, 0.9, seed))
        for i in range(5):
            a = rng.uniform(0, 2 * np.pi)
            d = np.array([math.cos(a), 0, math.sin(a)])
            e = tc + np.array([d[0] * top_rx * 1.0, -rng.uniform(0.35, 0.7), d[2] * top_rz * 1.0])
            Rl = np.stack([np.cross([0, 1, 0], d), d, np.array([0, -1.0, 0])], axis=1)
            turf.add(Ellipsoid(e, (rng.uniform(0.5, 1.0), 0.14, rng.uniform(0.4, 0.7)), Rl).lumpy(0.05, 2.0, seed + i), k=0.35)
        for i in range(22):
            a = rng.uniform(0, 2 * np.pi)
            rr = rng.uniform(0.1, 0.85)
            cc = tc + np.array([math.cos(a) * top_rx * rr, 0.48, math.sin(a) * top_rz * rr])
            d = np.array([math.cos(a + 1.3), 0, math.sin(a + 1.3)])
            turf.sub(Capsule(cc - d * 0.4, cc + d * 0.4, 0.055), k=0.04, color=SP["turf_dk"])
        turf.paint(patches(0.9, 0.15, 3), SP["turf_lt"], feather=0.03)
        turf.paint(HalfSpace(tc + np.array([0, -0.25, 0]), (0, 1, 0)), SP["turf_dk"], feather=0.2)
        ft = turf.sdf
        # sea-pink thrift cushions and straw tussocks on the turf
        P, N = surface_points(ft, tc - np.array([top_rx, 0.2, top_rz]), tc + np.array([top_rx, 0.8, top_rz]), 16, rng, cond=lambda P, N: N[:, 1] > 0.6)
        for c, n in zip(P, N):
            tp = m.piece(color=SP["turf_lt"], gloss=30, merge="turf", res=0.02, lumps=0.008, lump_freq=8, detail=0.4, decimate=70)
            if rng.random() < 0.5:
                tp.add(Ellipsoid(c + n * 0.05, (0.2, 0.11, 0.2)))
                tp.paint(HalfSpace(c + n * 0.09, -n), SP["thrift"], feather=0.03)
            else:
                tp.add(Ellipsoid(c + n * 0.1, (0.16, 0.2, 0.16)), color=mix(NP["straw"], SP["turf"], 0.4))
                tp.add(Ellipsoid(c + n * 0.22 + rng.normal(size=3) * 0.04, (0.1, 0.14, 0.1)), k=0.05, color=NP["straw"])
        P, N = surface_points(ft, tc - np.array([top_rx, 0.0, top_rz]), tc + np.array([top_rx, 0.8, top_rz]), gulls, rng, cond=lambda P, N: N[:, 1] > 0.8)
        for c in P:
            gull(m, "gulls", c - np.array([0, 0.03, 0]), rng.uniform(0, 360), s=1.4)
        m.socket("top", None, tuple(tc + np.array([0, 0.5, 0])))
        return m
    MODELS[f"town/{name}"] = fn


_stack("sea_stack_a", 501, 12.0, (2.9, 2.5), waist=0.22, gulls=3, lean=(0.05, -0.02))
_stack("sea_stack_b", 502, 8.5, (4.4, 3.0), waist=0.12, arch=True, gulls=4, lean=(-0.04, 0.03))


# ----------------------------------------------------------------------------------------------------------------
# icebergs


def _berg(name, seed, chunks, budget=8000, res=0.045, notch=True):
    def fn():
        m = TownModel(name, budget=budget, seed=seed)
        rng = m.rng
        ice = m.piece(color=SP["ice"], gloss=205, merge="ice", res=res, lumps=0.012, lump_freq=1.1, dents=18, dent_size=0.3, dent_depth=0.03,
                      mottle=0.05, detail=1.0)
        prims = []
        for i, (c, r, kw) in enumerate(chunks):
            ch = Chunk(c, r, n=kw.get("n", 9), k=kw.get("k", 0.06), rot=(rng.normal() * 6, rng.uniform(0, 360), rng.normal() * 6), seed=int(rng.integers(1e6)),
                       cut=kw.get("cut", (0.55, 0.85)), box=kw.get("box", True), boxd=(0.9, 1.0))
            prims.append(ch)
            ice.add(ch, k=kw.get("blend", 0.12), color=[SP["ice"], SP["ice_lt"], SP["ice"]][i % 3])
        ice.inter(HalfSpace((0, -2.5, 0), (0, -1, 0)), k=0.05)

        def body(P):
            d = prims[0](P)
            for q in prims[1:]:
                d = np.minimum(d, q(P))
            return d
        if notch:  # wave-cut notch at the waterline
            ice.sub(Func(lambda P: np.maximum(np.abs(P[:, 1] - 0.12) - 0.16, -(body(P) + 0.2)), (-1e4,) * 3, (1e4,) * 3), k=0.06,
                    color=SP["ice_blue"])
        top = max(c[1] + r[1] for c, r, kw in chunks)
        for i in range(3):  # knife-scored melt striations
            yy, ph = rng.uniform(0.5, top * 0.8), rng.uniform(0, 6)

            def groove(P, _y=yy, _p=ph):
                g = np.abs(P[:, 1] - _y - 0.2 * np.sin(P[:, 0] * 0.8 + _p) - 0.12 * np.sin(P[:, 2] * 1.1)) - 0.025
                return np.maximum(g, -(body(P) + 0.05))
            ice.sub(Func(groove, (-1e4,) * 3, (1e4,) * 3), k=0.02, color=SP["ice_blue"])
        ice.paint(below(0.35, 0.12, 0.8, 4), SP["ice_blue"], gloss=230, feather=0.15)
        ice.paint(below(-0.4, 0.1, 0.8, 5), SP["ice_deep"], gloss=230, feather=0.2)
        ice.paint(patches(0.6, 0.18, 9), SP["ice_lt"], feather=0.05)
        ice.paint(Func(lambda P: np.maximum(top * 0.62 - P[:, 1], (0.05 - fbm(P * 0.9, 2, 8)) * 0.1), (-1e4,) * 3, (1e4,) * 3), SP["snow"], gloss=70,
                  feather=0.03)
        return m
    MODELS[f"town/{name}"] = fn


_berg("iceberg_a", 601, [((0, -0.5, 0), (1.8, 1.7, 1.4), dict(k=0.05)), ((0.9, 0.2, 0.3), (0.9, 0.9, 0.8), dict(k=0.05))], budget=6000, res=0.035)
_berg("iceberg_b", 602, [((0, -0.4, 0), (3.0, 2.2, 2.4), dict(k=0.08)), ((-0.8, 1.2, 0.2), (1.6, 1.8, 1.4), dict(k=0.06)),
                         ((1.4, 0.6, -0.6), (1.3, 1.2, 1.1), dict(k=0.06))], budget=8000, res=0.045)
_berg("iceberg_c", 603, [((0, -0.5, 0), (5.0, 2.6, 3.6), dict(k=0.1)), ((-1.6, 2.5, 0.3), (2.0, 3.6, 1.8), dict(k=0.08)),
                         ((1.9, 2.0, -0.5), (1.6, 3.0, 1.5), dict(k=0.08, cut=(0.5, 0.8))), ((0.3, 1.5, 1.6), (1.6, 1.5, 1.0), dict(k=0.07))],
      budget=8000, res=0.06)


# ----------------------------------------------------------------------------------------------------------------
# kelp


def _frond(m, merge, start, direction, length, rng, *, width=0.08, color=None, bladders=0, lift=0.022, tris=None, res=0.012):
    """A blade/frond floating on the sea surface from `start`, snaking along `direction`."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    side = np.cross([0, 1.0, 0], d)
    n = max(4, int(length / 0.14))
    ph = rng.uniform(0, 6)
    pts = []
    for i in range(n):
        s = i / (n - 1) * length
        p = np.asarray(start, float) + d * s + side * (0.12 * math.sin(s * 2.2 + ph) + 0.05 * math.sin(s * 5.3 + ph))
        p[1] = lift + 0.012 * math.sin(s * 3.1 + ph)
        pts.append(p)
    pts = np.array(pts)
    nrm = np.tile([0, 1.0, 0], (n, 1)) + np.c_[np.zeros(n), np.zeros(n), np.zeros(n)]
    # ruffled edges: tilt the blade normal a little back and forth
    nrm = nrm + np.outer(np.sin(np.arange(n) * 1.7 + ph) * 0.25, side)
    p = m.piece(color=color or NP["kelp"], gloss=190, merge=merge, res=res, lumps=0.002, lump_freq=8, mottle=0.08, detail=1.0, decimate=tris)
    w = width * (0.35 + 0.65 * np.sin(np.linspace(0.15, 2.9, n)) ** 0.6)
    ribbon(p, pts, nrm, w, 0.014)
    p.paint(patches(3, 0.15, int(rng.integers(999))), NP["kelp_lt"], feather=0.01)
    for i in range(bladders):
        s = rng.uniform(0.1, 0.9) * length
        q = pts[min(n - 1, int(s / length * (n - 1)))] + side * rng.choice([-1, 1]) * width * 0.6
        p.add(Ellipsoid(q + np.array([0, 0.015, 0]), (0.055, 0.045, 0.045)), k=0.015, color=NP["bladder"], gloss=200)
    return p


def kelp_cluster_a():
    """Bull kelp: stipes rising from the bed to round floats on the surface, blades streaming down-current (+x)."""
    m = TownModel("kelp_cluster_a", budget=6000, seed=701)
    rng = m.rng
    hold = np.array([-0.4, -2.1, 0.0])
    for i in range(6):
        a = i / 6 * 2 * np.pi + rng.normal() * 0.3
        bulb = np.array([math.cos(a) * rng.uniform(0.5, 1.3), 0.03, math.sin(a) * rng.uniform(0.5, 1.2)])
        st = m.piece(color=NP["kelp_dk"], gloss=150, merge="kelp", res=0.03, lumps=0.003, detail=0.15)
        mid = (hold + bulb) / 2 + np.array([rng.normal() * 0.3, 0, rng.normal() * 0.3])
        st.add(Tube([hold + np.array([rng.normal() * 0.1, 0, rng.normal() * 0.1]), mid, bulb - np.array([0, 0.12, 0])], [0.035, 0.04, 0.05], samples=3))
        bp = m.piece(color=NP["bladder"], gloss=210, merge="kelp", res=0.01, lumps=0.003, lump_freq=10, detail=1.0, decimate=200)
        r = rng.uniform(0.12, 0.17)
        bp.add(Sphere(bulb + np.array([0, -0.01, 0]), r))
        bp.add(Capsule(bulb + np.array([0, -0.05, 0]), bulb - np.array([0, 0.25, 0]), 0.06, 0.035), k=0.05)
        bp.paint(HalfSpace(bulb + np.array([0, 0.03, 0]), (0, -1, 0)), NP["kelp_lt"], feather=0.04)
        for j in range(rng.integers(3, 6)):
            ang = rng.normal() * 0.55
            d = np.array([math.cos(ang), 0, math.sin(ang)])
            _frond(m, "kelp", bulb + d * r * 0.8, d, rng.uniform(1.0, 2.0), rng, width=rng.uniform(0.09, 0.14),
                   color=[NP["kelp"], NP["kelp_lt"], NP["wrack"], NP["kelp_dk"]][j % 4], tris=150, res=0.011)
    return m


def kelp_cluster_b():
    """Giant kelp canopy: a loose floating mat of bladdered fronds with a few tips curling up out of the water."""
    m = TownModel("kelp_cluster_b", budget=6000, seed=702)
    rng = m.rng
    for i in range(12):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(0, 1.4)
        st = np.array([math.cos(a) * rr - 0.8, 0, math.sin(a) * rr * 0.8])
        ang = rng.normal() * 0.6
        d = np.array([math.cos(ang), 0, math.sin(ang)])
        _frond(m, "kelp", st, d, rng.uniform(1.4, 2.6), rng, width=rng.uniform(0.07, 0.11), bladders=int(rng.integers(3, 7)),
               color=[NP["kelp"], NP["kelp_lt"], NP["wrack"], NP["kelp_dk"]][i % 4], tris=230, res=0.011)
    # a few frond tips lifting out of the water
    for i in range(4):
        b = np.array([rng.uniform(-1.5, 1.5), 0.0, rng.uniform(-1, 1)])
        p = m.piece(color=NP["kelp_lt"], gloss=190, merge="kelp", res=0.01, lumps=0.002, detail=1.0, decimate=120)
        d = rng.normal(size=3)
        d[1] = 0
        d /= np.linalg.norm(d)
        pts = [b, b + d * 0.12 + np.array([0, 0.14, 0]), b + d * 0.2 + np.array([0, 0.3, 0]), b + d * 0.32 + np.array([0, 0.36, 0])]
        nrm = [np.cross(d, [0, 1, 0])] * 4
        ribbon(p, pts, nrm, [0.03, 0.045, 0.04, 0.02], 0.014)
    # submerged stipe bundle (unseen, coarse)
    sb = m.piece(color=NP["kelp_dk"], gloss=120, merge="kelp", res=0.05, lumps=0.003, detail=0.1)
    for i in range(5):
        sb.add(Capsule((rng.normal() * 0.3 - 0.8, -2.0, rng.normal() * 0.3), (rng.normal() * 0.8 - 0.6, -0.08, rng.normal() * 0.6), 0.04), k=0.05)
    return m


MODELS["town/kelp_cluster_a"] = kelp_cluster_a
MODELS["town/kelp_cluster_b"] = kelp_cluster_b


# ----------------------------------------------------------------------------------------------------------------
# channel marker (bell buoy)


def channel_marker():
    m = TownModel("channel_marker", budget=4000, seed=801)
    rng = m.rng
    hull = m.piece(color=SP["buoy_red"], gloss=90, merge="buoy", res=0.016, lumps=0.004, lump_freq=4, dents=8, dent_size=0.08, dent_depth=0.008,
                   mottle=0.08, detail=1.0)
    hull.add(Cylinder((0, -0.15, 0), 0.72, 0.42, round=0.16))
    hull.add(Ellipsoid((0, -0.6, 0), (0.6, 0.4, 0.6)), k=0.15)
    hull.add(Cylinder((0, 0.3, 0), 0.6, 0.08, round=0.05), k=0.06)                 # deck plate
    hull.add(Torus((0, 0.16, 0), 0.74, 0.06), k=0.04, color=TP["iron"], gloss=40)  # rubbing strake
    for a in range(0, 360, 90):
        r = math.radians(a + 45)
        hull.add(Box((math.cos(r) * 0.66, 0.05, math.sin(r) * 0.66), (0.05, 0.12, 0.05), (0, -a - 45, 0), round=0.02), k=0.03, color=TP["iron"])
    hull.paint(band(-0.06, 0.06, 0.02, 4), SP["buoy_red_dk"], feather=0.02)
    hull.paint(Box((0, -0.1, 0.72), (0.18, 0.12, 0.2)), "#e9e2d0", feather=0.01)  # the white number patch
    hull.paint(patches(2.0, 0.3, 4), TP["rust"], feather=0.02)
    hull.paint(below(0.02, 0.05, 3, 2), TP["algae"], gloss=140, feather=0.04)
    hull.paint(below(-0.12, 0.04, 3, 3), TP["slime"], gloss=120, feather=0.04)
    for i in range(5):  # rust streaks
        a = rng.uniform(0, 2 * np.pi)
        hull.paint(Capsule((math.cos(a) * 0.73, 0.18, math.sin(a) * 0.73), (math.cos(a) * 0.73, -0.1, math.sin(a) * 0.73), 0.03, 0.015), mix(TP["rust"], SP["buoy_red"], 0.3),
                   feather=0.02)
    hull.paint(Sphere((0.25, 0.42, -0.2), 0.12), NP["guano"], feather=0.05)
    # tower: four legs, two rings, all red-painted iron going rusty
    tw = m.piece(color=SP["buoy_red"], gloss=70, merge="tower", res=0.012, lumps=0.003, lump_freq=5, mottle=0.08, detail=1.0)
    top_y = 2.05
    for a in range(0, 360, 90):
        r = math.radians(a + 45)
        tw.add(Capsule((math.cos(r) * 0.5, 0.35, math.sin(r) * 0.5), (math.cos(r) * 0.17, top_y, math.sin(r) * 0.17), 0.04, 0.032), k=0.02)
    tw.add(Torus((0, 0.95, 0), 0.38, 0.03), k=0.02)
    tw.add(Torus((0, top_y, 0), 0.17, 0.035), k=0.02)
    for a in range(0, 360, 90):
        r = math.radians(a)
        tw.add(Capsule((math.cos(r) * 0.42, 0.45, math.sin(r) * 0.42), (math.cos(r + 1.57) * 0.26, 1.45, math.sin(r + 1.57) * 0.26), 0.018), k=0.015)
    tw.add(Box((0, 1.18 + 0.38, 0), (0.24, 0.025, 0.04), round=0.012), k=0.01, color=TP["iron"])
    tw.paint(patches(3, 0.15, 6), TP["rust"], feather=0.02)
    tw.paint(patches(2, 0.35, 7), "#c4a36a", feather=0.02)
    # radar reflector / day mark plate
    tw.add(Box((0, 1.25, 0), (0.25, 0.25, 0.02), (0, 0, 45), round=0.02), k=0.01, color=SP["buoy_red_dk"])
    # bell hanging under a yoke
    bl = m.piece(color=SP["bell"], gloss=150, merge="bell", res=0.008, lumps=0.002, dents=4, dent_size=0.03, detail=1.0)
    bc = np.array([0, 1.38, 0])
    bl.add(Ellipsoid(bc + np.array([0, 0.08, 0]), (0.12, 0.13, 0.12)))
    bl.add(Cylinder(bc - np.array([0, 0.06, 0]), 0.15, 0.07, round=0.03), k=0.08)
    bl.add(Torus(bc - np.array([0, 0.13, 0]), 0.15, 0.025), k=0.02)
    bl.sub(Ellipsoid(bc - np.array([0, 0.15, 0]), (0.12, 0.15, 0.12)), k=0.02, color="#5a4626")
    bl.add(Capsule(bc + np.array([0, 0.2, 0]), bc + np.array([0, 0.3, 0]), 0.025), k=0.01, color=TP["iron"])
    bl.add(Sphere(bc - np.array([0, 0.16, 0]), 0.035), k=0.0, color=TP["iron"])     # clapper
    bl.paint(patches(4, 0.1, 5), SP["patina"], feather=0.02)
    for a in (0, 180):  # swinging hammers
        r = math.radians(a)
        hp = np.array([math.cos(r) * 0.27, 1.32, math.sin(r) * 0.27])
        bl.add(Capsule(hp + np.array([0, 0.25, 0]), hp, 0.012), k=0.0, color=TP["iron"])
        bl.add(Sphere(hp, 0.04), k=0.01, color=TP["iron"])
    # lamp on top: cast housing + emissive lens
    lh = m.piece(color=TP["iron"], gloss=70, merge="tower", res=0.008, lumps=0.002, detail=0.8)
    lc = np.array([0, top_y + 0.17, 0])
    lh.add(Cylinder(lc - np.array([0, 0.12, 0]), 0.12, 0.04, round=0.015))
    lh.add(Cylinder(lc + np.array([0, 0.12, 0]), 0.13, 0.03, round=0.015), k=0.01)
    lh.add(Ellipsoid(lc + np.array([0, 0.17, 0]), (0.07, 0.05, 0.07)), k=0.02)
    for a in range(0, 360, 90):
        r = math.radians(a + 45)
        lh.add(Capsule(lc + np.array([math.cos(r) * 0.1, -0.1, math.sin(r) * 0.1]), lc + np.array([math.cos(r) * 0.1, 0.1, math.sin(r) * 0.1]), 0.012), k=0.006)
    gl = m.piece(color=TP["lamp"], gloss=230, mat=1, merge="lamp", res=0.008, lumps=0.0008, mottle=0.02, ao=False, detail=0.5)
    gl.add(Cylinder(lc, 0.085, 0.09, round=0.03))
    # a gull having a rest on the deck plate
    gull(m, "buoy", (0.32, 0.38, 0.12), 200, s=1.0)
    m.socket("bell", None, tuple(bc))
    m.socket("light", None, tuple(lc))
    return m


MODELS["town/channel_marker"] = channel_marker


# ----------------------------------------------------------------------------------------------------------------
# the wreck: an old fishing boat half sunk, listing, stern under


def wreck():
    m = TownModel("wreck", budget=30000, seed=901)
    rng = m.rng
    L, D = 8.0, 1.5
    # boat frame: keel midship origin, u = +z toward the bow; pitched bow-up and rolled to starboard
    R = euler((-10, 15, 24))
    o = np.array([0, -1.05, 0])
    t = T(o, R=R)

    def hb(u):  # half beam at the sheer
        s = np.clip(u / (L / 2), -1, 1)
        return np.where(s > 0, 1.3 * np.sqrt(np.clip(1 - s ** 2.2, 0, 1)), 1.3 * (1 - 0.32 * s ** 2))

    def sheer(u):
        s = np.clip(u / (L / 2), -1, 1)
        return D + 0.45 * np.maximum(s, 0) ** 2 + 0.12 * s ** 2

    def keel(u):
        s = np.clip(u / (L / 2), -1, 1)
        return 0.25 * np.maximum(s, 0) ** 3

    def hull_local(q):
        u, w, v = q[:, 2], q[:, 1], q[:, 0]
        wn = np.clip((w - keel(u)) / np.maximum(sheer(u) - keel(u), 1e-3), 0, 1.2)
        half = hb(u) * np.clip(wn, 0, 1) ** 0.42
        d_side = np.abs(v) - half
        d_bot = keel(u) - w
        d_top = w - sheer(u)
        d_end = np.maximum(u - L / 2 - 0.05, -L / 2 - u)
        return np.maximum.reduce([d_side * 0.75, d_bot, d_end]), d_top

    def to_local(P):
        return (P - o) @ R

    def shell(P):
        q = to_local(P)
        d_sb, d_top = hull_local(q)
        return np.maximum.reduce([d_sb, d_top, -(d_sb + 0.085)])

    def strakes(P):
        q = to_local(P)
        u, w = q[:, 2], q[:, 1]
        rel = (w - keel(u)) / np.maximum(sheer(u) - keel(u), 1e-3)
        g = np.abs(((rel * 7.0) % 1.0) - 0.5)
        return 0.012 * np.exp(-((0.5 - g) / 0.07) ** 2)

    lo, hi = o - np.array([5, 4, 5]), o + np.array([5, 4, 5])
    hp = m.piece(color=SP["hull_paint"], gloss=50, merge="hull", res=0.028, lumps=0.006, lump_freq=3, dents=30, dent_size=0.12, dent_depth=0.012,
                 mottle=0.1, detail=1.0)
    hp.add(Func(lambda P: shell(P) + strakes(P), lo, hi))
    # missing planks (holes) on the exposed side, revealing the frames
    for (u0, u1, k0) in ((-0.6, 1.0, 4), (1.4, 2.5, 5), (-2.6, -1.4, 5), (0.3, 1.7, 2)):
        def hole(P, _u0=u0, _u1=u1, _k=k0):
            q = to_local(P)
            u, w, v = q[:, 2], q[:, 1], q[:, 0]
            rel = (w - keel(u)) / np.maximum(sheer(u) - keel(u), 1e-3) * 7.0
            jag = 0.08 * np.sin(u * 13) + 0.05 * np.sin(u * 29)
            return np.maximum.reduce([np.abs(rel - (_k + 0.5)) * 0.2 - 0.1, np.maximum(_u0 + jag - u, u - _u1 - jag), -v])
        hp.sub(Func(hole, lo, hi), k=0.01, color="#2f3b40")
    # weathering: faded paint with bare wood, red boot-top trim near the sheer, algae and barnacles at the water
    hp.paint(Func(lambda P: (0.05 - fbm(P * 1.6, 2, 3)) * 0.1, lo, hi), TP["wood"], feather=0.01)
    hp.paint(Func(lambda P: np.abs((lambda q: q[:, 1] - sheer(q[:, 2]) + 0.12)(to_local(P))) - 0.07, lo, hi), SP["hull_trim"], feather=0.02)
    hp.paint(below(0.45, 0.15, 1.2, 3), shade(SP["hull_paint"], 0.65), gloss=120, feather=0.06)
    hp.paint(band(-0.6, 0.28, 0.12, 1.5, 4), TP["algae"], gloss=150, feather=0.06)
    hp.paint(band(0.15, 0.5, 0.1, 2.0, 5), TP["slime"], gloss=110, feather=0.05)
    for i in range(6):
        u = rng.uniform(-3, 3)
        a = t.p(np.array([hb(np.array([u]))[0] * 1.0, sheer(np.array([u]))[0] - 0.1, u]))
        hp.paint(Capsule(a, a - np.array([0, 0.8, 0]), 0.03, 0.05), mix(TP["rust"], SP["hull_paint"], 0.35), feather=0.03)
    # stem post at the bow and a gunwale rail (cap) along both sides
    cap = m.piece(color=TP["wood_dk"], gloss=40, merge="frames", res=0.02, lumps=0.004, detail=0.8)
    us = np.linspace(-L / 2 + 0.1, L / 2 - 0.05, 12)
    for sgn in (-1, 1):
        pts = [t.p(np.array([sgn * hb(np.array([u]))[0], sheer(np.array([u]))[0] + 0.02, u])) for u in us if not (sgn > 0 and 0.2 < u < 1.6)]
        if len(pts) > 2:
            cap.add(Tube(pts, 0.05, samples=2), k=0.02)
    cap.add(Tube([t.p(np.array([0, keel(np.array([L / 2]))[0], L / 2])), t.p(np.array([0, 1.0, L / 2 + 0.1])), t.p(np.array([0, sheer(np.array([L / 2]))[0] + 0.3, L / 2 + 0.05]))],
                 0.07, samples=3), k=0.03)
    # frames (ribs) inside the hull, following the section, some broken
    for u in np.arange(-3.4, 3.6, 0.5):
        ua = np.array([u])
        top = float(sheer(ua)[0])
        kl = float(keel(ua)[0])
        hbu = float(hb(ua)[0])
        sts = []
        for wn in (1.0, 0.7, 0.4, 0.15):
            sts.append(np.array([-(hbu * wn ** 0.42 - 0.13), kl + (top - kl) * wn - (0.05 if wn == 1.0 else 0), u]))
        sts.append(np.array([0, kl + 0.12, u]))
        for wn in (0.15, 0.4, 0.7, 1.0):
            sts.append(np.array([(hbu * wn ** 0.42 - 0.13), kl + (top - kl) * wn - (0.05 if wn == 1.0 else 0), u]))
        if rng.random() < 0.35:
            sts = sts[: int(rng.integers(4, 8))]
        rb = m.piece(color=TP["wood_dk"], gloss=40, merge="frames", res=0.02, lumps=0.004, detail=0.5)
        rb.add(Tube([t.p(s_) for s_ in sts], 0.045, samples=2))
    # a few surviving foredeck planks
    for i, x in enumerate(np.arange(-0.9, 1.0, 0.24)):
        if rng.random() < 0.3:
            continue
        u0, u1 = 2.0, 3.4 - abs(x) * 0.8
        yy = float(sheer(np.array([2.6]))[0]) - 0.08
        board(m, "deck", t.p(np.array([x, yy, u0 + rng.uniform(0, 0.4)])), t.p(np.array([x, yy, u1])), 0.21, 0.05, t.v((0, 1, 0)),
              rng.choice([TP["wood"], TP["wood_dk"], TP["wood_br"]]), nails=1, detail=0.7)
    # wheelhouse remains: three walls of boards, a window hole, the roof slid off at an angle
    wh_u0, wh_u1, whw = -2.7, -1.3, 0.85
    base_y = float(sheer(np.array([-2.0]))[0]) - 0.25
    for side in (-1, 1):
        x = side * whw
        for j, u in enumerate(np.arange(wh_u0, wh_u1, 0.22)):
            hgt = 1.5 - (0.4 * rng.random() if side > 0 else 0) - (0.3 if u > -1.8 and side > 0 else 0)
            board(m, "house", t.p(np.array([x, base_y, u + 0.11])), t.p(np.array([x, base_y + hgt, u + 0.11])), 0.2, 0.045, t.v((side, 0, 0)),
                  rng.choice([TP["cream"], TP["wood_lt"], TP["cream"]]), paint=TP["white"], peel=0.4, nails=1, detail=0.6)
    for j, x in enumerate(np.arange(-whw + 0.1, whw, 0.22)):
        if abs(x) < 0.3:
            board(m, "house", t.p(np.array([x, base_y, wh_u1])), t.p(np.array([x, base_y + 0.65, wh_u1])), 0.2, 0.045, t.v((0, 0, 1)), TP["cream"],
                  paint=TP["white"], peel=0.4, nails=1, detail=0.6)
            board(m, "house", t.p(np.array([x, base_y + 1.15, wh_u1])), t.p(np.array([x, base_y + 1.5, wh_u1])), 0.2, 0.045, t.v((0, 0, 1)), TP["cream"],
                  paint=TP["white"], peel=0.4, nails=1, detail=0.6)
        else:
            board(m, "house", t.p(np.array([x, base_y, wh_u1])), t.p(np.array([x, base_y + 1.5, wh_u1])), 0.2, 0.045, t.v((0, 0, 1)), TP["cream"],
                  paint=TP["white"], peel=0.4, nails=1, detail=0.6)
    roof = m.piece(color=TP["tin_dk"], gloss=40, merge="house", res=0.012, lumps=0.003, detail=0.7)
    from kit_town import Corrugated
    rc = t.p(np.array([-0.3, base_y + 1.45, -2.0]))
    roof.add(Corrugated(rc, (1.0, 0.85), t.R @ euler((0, 10, -20)), sag=0.04, curl=0.03, seed=3))
    roof.paint(patches(1.5, 0.05, 4), TP["rust"], feather=0.02)
    # broken mast with a splintered top, a slack stay and a fallen boom trailing a rope into the water
    mp = m.piece(color=TP["wood_br"], gloss=40, merge="mast", res=0.016, lumps=0.004, dents=4, detail=0.8)
    mb = t.p(np.array([0, 0.3, 1.2]))
    mt = t.p(np.array([0.25, 3.6, 1.0]))
    mp.add(Capsule(mb, mt, 0.09, 0.075))
    ax = (mt - mb) / np.linalg.norm(mt - mb)
    for j in range(6):
        a = j / 6 * 2 * np.pi
        o2 = np.cross(ax, [math.cos(a), 0, math.sin(a)])
        o2 = o2 / (np.linalg.norm(o2) + 1e-9)
        mp.add(Capsule(mt + o2 * 0.04, mt + o2 * 0.05 + ax * rng.uniform(0.12, 0.35), 0.03, 0.006), k=0.02)
    mp.add(Torus(mb + ax * 2.1, 0.09, 0.025, look_rot(ax)), k=0.01, color=TP["iron"])
    bm0 = mb + ax * 1.2
    bm1 = bm0 + t.v((0.9, -1.0, -2.0))
    mp.add(Capsule(bm0, bm1, 0.06, 0.05), k=0.02)
    rope(m, "mast", [mt - ax * 0.4, (mt + t.p(np.array([0, sheer(np.array([3.8]))[0], 3.9]))) / 2 + np.array([0, -0.5, 0]), t.p(np.array([0, sheer(np.array([3.8]))[0], 3.9]))],
         r=0.02, detail=0.4)
    rope(m, "mast", [bm1, bm1 + np.array([0.15, -0.35, 0.1]), bm1 + np.array([0.25, -0.9, 0.3])], r=0.022, detail=0.3)
    # barnacles along the waterline on the hull
    barnacles(m, "barn", hp.sdf, o + np.array([-4, 0.7, -5]), o + np.array([4, 1.4, 5]), 20, rng, size=(0.03, 0.05), res=0.012, tris=40,
              cond=lambda P, N: (P[:, 1] > -0.25) & (P[:, 1] < 0.35))
    gull(m, "barn", t.p(np.array([0, sheer(np.array([3.6]))[0] + 0.05, 3.6])), 160, s=1.0)
    m.socket("mast_top", None, tuple(mt))
    return m


MODELS["town/wreck"] = wreck


# ----------------------------------------------------------------------------------------------------------------
# cotton wool: clouds, smoke, spray


def _cloud(name, seed, W, H, D, n=14, towers=((0.0, 1.0),), budget=6000, flat=0.6):
    """Cotton-wool cumulus: a flat-bottomed base of squashed puffs with heaped columns of billows on top."""
    def fn():
        m = TownModel(name, budget=budget, seed=seed)
        rng = m.rng
        res = max(0.08, W / 130)
        p = m.piece(color=SP["cotton"], gloss=0, mat=2, merge="cloud", res=res, lumps=W * 0.005, lump_freq=14.0 / W, dents=0, mottle=0.03, ao=False, detail=1.0)
        # base layer: wide squashed puffs
        for i in range(n):
            x = rng.uniform(-0.42, 0.42) * W
            z = rng.uniform(-0.35, 0.35) * D * (1 - abs(x) / W)
            r = rng.uniform(0.12, 0.2) * W * (1 - abs(x) / W * 0.7)
            p.add(Ellipsoid((x, r * 0.45, z), (r * 1.4, r * 0.7, r * 1.1)), k=W * 0.05)
        # heaped columns of billows, narrowing upward
        for cx, hs in towers:
            Ht = H * hs
            y = H * 0.18
            rad = W * 0.2 * (0.8 + 0.2 * hs)
            while y < Ht - rad * 0.4:
                for j in range(3):
                    x = cx * W + rng.normal() * rad * 0.6
                    z = rng.normal() * min(D * 0.2, rad * 0.6)
                    rr = rad * rng.uniform(0.7, 1.0)
                    p.add(Sphere((x, y + rr * 0.3, z), rr), k=W * 0.05)
                y += rad * 0.55
                rad *= 0.8
        # soft cauliflower billows over the upper surface
        f0 = p.sdf
        P, N = surface_points(f0, (-W * 0.6, H * 0.2, -D * 0.6), (W * 0.6, H * 1.3, D * 0.6), 30, rng, cond=lambda P, N: N[:, 1] > 0.0, iters=8,
                              tol=W * 0.004)
        for c, nn in zip(P, N):
            p.add(Sphere(c - nn * W * 0.01, rng.uniform(0.05, 0.09) * W), k=W * 0.045)
        p.inter(HalfSpace((0, H * 0.05 * flat, 0), (0, -1, 0)), k=W * 0.05)
        p.paint(below(H * 0.3, H * 0.05, 3.0 / W, 3), SP["cotton_shade"], feather=H * 0.14)
        p.paint(below(H * 0.13, H * 0.03, 3.0 / W, 4), shade(SP["cotton_shade"], 0.93), feather=H * 0.08)
        return m
    MODELS[f"town/{name}"] = fn


_cloud("cloud_1", 1001, 12.0, 7.0, 7.0, n=10, towers=((0.0, 1.0),))
_cloud("cloud_2", 1002, 18.0, 9.0, 9.0, n=14, towers=((-0.22, 1.0), (0.25, 0.8)))
_cloud("cloud_3", 1003, 25.0, 6.0, 9.0, n=20, towers=((-0.3, 0.9), (0.05, 0.75), (0.32, 1.0)))
_cloud("cloud_4", 1004, 15.0, 14.0, 10.0, n=12, towers=((0.0, 1.0),))


def _puff(name, seed, size, n=6, color=None, budget=1500):
    def fn():
        m = TownModel(name, budget=budget, seed=seed)
        rng = m.rng
        p = m.piece(color=color or SP["smoke"], gloss=0, mat=2, merge="puff", res=size / 60, lumps=size * 0.025, lump_freq=6.0 / size, mottle=0.04, ao=False)
        p.add(Sphere((0, 0, 0), size * 0.32))
        for i in range(n):
            d = rng.normal(size=3)
            d[1] = abs(d[1]) * 0.6
            d /= np.linalg.norm(d)
            p.add(Sphere(d * size * rng.uniform(0.18, 0.3), size * rng.uniform(0.16, 0.24)), k=size * 0.08)
        p.paint(below(-size * 0.1, size * 0.05, 3 / size, 2), SP["smoke_dk"], feather=size * 0.15)
        return m
    MODELS[f"town/{name}"] = fn


_puff("smoke_puff_1", 1101, 0.32, n=5)
_puff("smoke_puff_2", 1102, 0.45, n=7)
_puff("smoke_puff_3", 1103, 0.6, n=9)


def spray_1():
    """A crashing splash: a lumpy collar of white sea-foam clay with ragged sheets and droplets flung up, cotton mist on top."""
    m = TownModel("spray_1", budget=1500, seed=1201)
    rng = m.rng
    foam = m.piece(color=SP["foam"], gloss=150, mat=3, merge="foam", res=0.02, lumps=0.015, lump_freq=7, mottle=0.04, detail=1.0)
    foam.add(Ellipsoid((0, 0.02, 0), (0.6, 0.1, 0.55)).lumpy(0.03, 5, 3))
    for i in range(7):
        a = i / 7 * 2 * np.pi + rng.normal() * 0.35
        d = np.array([math.cos(a), 0, math.sin(a)])
        b0 = d * rng.uniform(0.3, 0.45) + np.array([0, 0.06, 0])
        hgt = rng.uniform(0.4, 1.2)
        mid = b0 + d * hgt * 0.2 + np.array([0, hgt * 0.55, 0])
        tip = b0 + d * hgt * 0.45 + np.array([0, hgt, 0])
        foam.add(Tube([b0, mid, tip], [0.11, 0.07, 0.03], samples=3), k=0.06)
        for j in range(int(rng.integers(1, 3))):
            foam.add(Sphere(tip + d * rng.uniform(0.05, 0.2) + np.array([rng.normal() * 0.05, rng.uniform(0.05, 0.25), rng.normal() * 0.05]),
                            rng.uniform(0.035, 0.065)), k=0.0)
    foam.paint(below(0.12, 0.03, 4), SP["foam_blue"], feather=0.06)
    mist = m.piece(color=SP["cotton"], gloss=0, mat=2, merge="mist", res=0.03, lumps=0.03, lump_freq=4, mottle=0.03, ao=False, detail=0.6)
    for i in range(7):
        a = rng.uniform(0, 2 * np.pi)
        mist.add(Sphere((math.cos(a) * rng.uniform(0.1, 0.45), rng.uniform(0.7, 1.4), math.sin(a) * rng.uniform(0.1, 0.45)), rng.uniform(0.16, 0.3)), k=0.12)
    return m


def spray_2():
    """Bow spray: a fan of flung water arcing sideways (+x) with cotton mist trailing."""
    m = TownModel("spray_2", budget=1500, seed=1202)
    rng = m.rng
    foam = m.piece(color=SP["foam"], gloss=150, mat=3, merge="foam", res=0.022, lumps=0.01, lump_freq=6, mottle=0.04, detail=1.0)
    for i in range(8):
        z = (i / 7 - 0.5) * 1.2
        pts = [np.array([0, 0.05, z]), np.array([0.45, 0.65 + rng.normal() * 0.1, z * 1.1]), np.array([0.95, 0.85 + rng.normal() * 0.12, z * 1.25]),
               np.array([1.4, 0.55, z * 1.35])]
        foam.add(Tube(pts, [0.08, 0.06, 0.04, 0.025], samples=4), k=0.05)
        for j in range(2):
            q = pts[3] + np.array([rng.uniform(0.05, 0.3), rng.uniform(-0.3, 0.1), rng.normal() * 0.1])
            foam.add(Sphere(q, rng.uniform(0.03, 0.055)), k=0.0)
    foam.add(Ellipsoid((0.1, 0.02, 0), (0.25, 0.08, 0.75)), k=0.06)
    foam.paint(below(0.15, 0.03, 4), SP["foam_blue"], feather=0.06)
    mist = m.piece(color=SP["cotton"], gloss=0, mat=2, merge="mist", res=0.03, lumps=0.025, lump_freq=4, mottle=0.03, ao=False, detail=0.6)
    for i in range(6):
        mist.add(Sphere((rng.uniform(0.6, 1.4), rng.uniform(0.7, 1.1), rng.normal() * 0.4), rng.uniform(0.15, 0.26)), k=0.12)
    return m


MODELS["town/spray_1"] = spray_1
MODELS["town/spray_2"] = spray_2
