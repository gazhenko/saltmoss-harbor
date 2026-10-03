"""
Saltmoss Harbor secondary buildings: post office, net shed, three cottages, lighthouse and the dockside crane.

All face +Z in model space. Origin = footprint centre at ground level (y = 0 = the ground / street the building
stands on; cottages and the lighthouse keeper's door sit higher on raised floors reached by steps).
Sockets: door, smoke, light_* (lantern glass centres), win_* (window glass centres), plus per-building ones
(post_office: counter, sign_text; lighthouse: lamp; crane: hook on the `boom` bone).
"""
import math

import numpy as np
from clay import Prim, Func, Box, Sphere, Ellipsoid, Capsule, Cylinder, Torus, Tube, HalfSpace, euler, shade, mix, fbm, rgb
from kit_town import *
import kit_town as KT
import kit_props as KP

MODELS = {}
MG = dict(trim="trim", glass="glass", deco="deco", door="trim")
# where the triangles go: walls first (the camera lives next to them), props last
WEIGHTS = dict(walls=1.9, trim=1.0, roof=1.0, floor=0.7, stone=0.9, props=0.45, deco=0.6, metal=0.6, glass=0.3, net=0.8, tower=1.0)


def weigh(m, extra=None):
    w = dict(WEIGHTS, **(extra or {}))
    for p in m.pieces:
        p.detail *= w.get(p.merge, 1.0)
    return m


class calm:
    """Scoped defaults for the kit's board builders: wider boards, gentler hand-jitter (fewer, cleaner boards decimate
    into proper planks instead of creased ribbons)."""

    def __init__(self, bw=(0.26, 0.34), jitter=0.6):
        self.bw, self.jitter = bw, jitter

    def __enter__(self):
        self.ob, self.ov = KT.board, KT.vboard_wall
        ob, ov, bw, jit = self.ob, self.ov, self.bw, self.jitter

        def board_(*a, **kw):
            kw.setdefault("jitter", jit)
            return ob(*a, **kw)

        def vwall_(*a, **kw):
            kw.setdefault("bw", bw)
            return ov(*a, **kw)
        KT.board, KT.vboard_wall = board_, vwall_
        globals()["board"], globals()["vboard_wall"] = board_, vwall_
        return self

    def __exit__(self, *exc):
        KT.board, KT.vboard_wall = self.ob, self.ov
        globals()["board"], globals()["vboard_wall"] = self.ob, self.ov


def calmed(fn, **kw):
    def run():
        with calm(**kw):
            return weigh(fn())
    run.__name__ = fn.__name__
    return run


# ----------------------------------------------------------------------------------------------------------------
# helpers


class Moved(Prim):
    """Wrap a primitive: world = R @ local + off."""

    def __init__(self, inner, off=(0, 0, 0), R=None):
        super().__init__()
        self.inner = inner
        self.o = np.asarray(off, float)
        self.Rm = np.eye(3) if R is None else np.asarray(R, float)

    def sdf(self, P):
        return self.inner((P - self.o) @ self.Rm)

    def bounds(self):
        lo, hi = self.inner.bounds()
        lo, hi = np.maximum(lo, -1e4), np.minimum(hi, 1e4)
        C = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        W = C @ self.Rm.T + self.o
        return W.min(0), W.max(0)


def move_since(m, n0, off=(0, 0, 0), yaw=0.0):
    """Move every piece created since index n0 (their ops) by yaw about Y then off."""
    R = euler((0, yaw, 0))
    for p in m.pieces[n0:]:
        for op in p.ops:
            op.prim = Moved(op.prim, off, R)


def stone_wall(m, merge, a, b, y0, y1, thick=0.32, stone=(0.42, 0.26), colors=None, detail=1.0, res=0.024):
    """Dry-stone / rubble foundation wall from a to b (x,z), y0..y1: lumpy blocks over dark mortar."""
    rng = m.rng
    a = np.array([a[0], 0.0, a[1]], float)
    b = np.array([b[0], 0.0, b[1]], float)
    L = np.linalg.norm(b - a)
    d = (b - a) / L
    n = np.cross([0, 1.0, 0], d)
    colors = colors or [TP["stone"], TP["stone_dk"], TP["stone_lt"], "#857e72", "#9a9384"]
    p = m.piece(color="#5e5a53", merge=merge, res=res, lumps=0.006, lump_freq=5, dents=4, dent_size=0.05, mottle=0.1, detail=detail)
    R = np.stack([d, [0, 1.0, 0], n], axis=1)
    c = a + d * L / 2 + np.array([0, (y0 + y1) / 2, 0])
    p.add(Box(c, (L / 2, (y1 - y0) / 2, thick * 0.38), R, round=0.03))
    y = y0
    row = 0
    while y < y1 - 0.05:
        h = min(rng.uniform(stone[1] * 0.8, stone[1] * 1.2), y1 - y)
        s = -rng.uniform(0, stone[0]) if row % 2 else 0.0
        while s < L:
            w = rng.uniform(stone[0] * 0.7, stone[0] * 1.3)
            s0, s1 = max(s, -0.02), min(s + w, L + 0.02)
            if s1 - s0 > 0.08:
                cc = a + d * (s0 + s1) / 2 + np.array([0, y + h / 2, 0]) + n * rng.uniform(-0.02, 0.03)
                Rb = R @ euler((rng.normal() * 3, rng.normal() * 4, rng.normal() * 4))
                p.add(Box(cc, ((s1 - s0) / 2 - 0.018, h / 2 - 0.016, thick / 2), Rb, round=min(0.06, h * 0.35)), k=0.012,
                      color=colors[int(rng.integers(len(colors)))])
            s += w
        y += h
        row += 1
    p.paint(below(y0 + 0.35, 0.08, 3), "#6f7a55", feather=0.05)  # damp moss at the foot
    return p


def steps(m, merge, x, z0, top_y, n, run=0.28, width=1.0, color=None, detail=1.0):
    """n plank steps descending from the edge z0 (at top_y) toward +z to the ground (y=0), with stringers."""
    rng = m.rng
    rise = top_y / (n + 0.0)
    for i in range(n):
        y = top_y - (i + 1) * rise
        zc = z0 + i * run + run / 2
        board(m, merge, (x - width / 2 - rng.uniform(0, 0.03), y + rise - 0.025, zc), (x + width / 2 + rng.uniform(0, 0.03), y + rise - 0.025, zc),
              run + 0.02, 0.05, (0, 1, 0), color or rng.choice([TP["wood"], TP["wood_lt"], TP["wood_dk"]]), nails=1, detail=0.8 * detail)
    for sx in (-1, 1):
        board(m, merge, (x + sx * (width / 2 - 0.04), top_y - 0.1, z0 - 0.05), (x + sx * (width / 2 - 0.04), 0.02, z0 + n * run + 0.03), 0.2, 0.05,
              (sx, 0, 0), TP["wood_dk"], nails=1, detail=0.5 * detail)


def woodpile(m, merge, t, L=1.4, rows=4, detail=1.0):
    rng = m.rng
    p = m.piece(color=TP["wood_br"], merge=merge, res=0.014, lumps=0.004, dents=4, detail=detail)
    for r in range(rows):
        n = rows - r + 2
        for i in range(n):
            x = (i - (n - 1) / 2) * 0.2 + rng.normal() * 0.02
            y = 0.1 + r * 0.17
            rr = rng.uniform(0.07, 0.095)
            p.add(Capsule(t.p(x, y, -L / 2 + rng.normal() * 0.05), t.p(x, y, L / 2 + rng.normal() * 0.05), rr), k=0.004,
                  color=rng.choice([TP["wood_br"], "#7a5f48", TP["wood"], "#8c6d50"]))
    p.paint(Func(lambda P, t=t, L=L: (L / 2 - 0.02 - np.abs(((P - t.o) @ t.R)[:, 2])) * 1.0, (-1e4,) * 3, (1e4,) * 3), "#c7a77c", feather=0.01)
    # a chopping block + axe
    q = m.piece(color="#7f6248", merge=merge, res=0.012, lumps=0.004, detail=0.6 * detail)
    bc = t.p(0.0, 0, L / 2 + 0.45)
    q.add(Cylinder(bc + np.array([0, 0.2, 0]), 0.2, 0.2, round=0.04))
    q.paint(HalfSpace(bc + np.array([0, 0.37, 0]), (0, -1, 0)), "#b89670", feather=0.02)
    q.add(Box(bc + np.array([0.02, 0.45, 0.0]), (0.012, 0.07, 0.06), euler((0, 30, 10)), round=0.006), k=0.003, color=TP["iron"])
    q.add(Capsule(bc + np.array([0.02, 0.45, 0.0]), bc + np.array([0.3, 0.75, -0.18]), 0.016), k=0.005, color=TP["wood_new2"])


def washing_line(m, merge, a, b, h=1.75, detail=1.0):
    rng = m.rng
    a, b = np.asarray(a, float), np.asarray(b, float)
    for p_ in (a, b):
        post(m, merge, p_, p_ + np.array([rng.normal() * 0.03, h, rng.normal() * 0.03]), 0.04, TP["wood_dk"], square=False, detail=0.4)
    ta, tb = a + np.array([0, h - 0.08, 0]), b + np.array([0, h - 0.08, 0])
    mid = (ta + tb) / 2 + np.array([0, -0.18, 0])
    rope(m, merge, [ta, mid, tb], 0.007, detail=0.2)
    d = (tb - ta) / np.linalg.norm(tb - ta)
    nrm = np.cross(d, [0, 1, 0])
    cols = ["#d9cdb3", TP["slate"], "#b45e50", TP["mustard"], "#e3dccb", TP["sage"]]
    s = 0.25
    L = np.linalg.norm(tb - ta)
    i = 0
    while s < L - 0.3:
        w = rng.uniform(0.25, 0.5)
        tt = (s + w / 2) / L
        c = (1 - tt) ** 2 * ta + 2 * (1 - tt) * tt * mid + tt * tt * tb
        hh = rng.uniform(0.3, 0.6)
        p = m.piece(color=cols[i % len(cols)], gloss=20, merge=merge, res=0.008, lumps=0.003, lump_freq=8, detail=0.5 * detail)
        R = np.stack([d, [0, 1, 0], nrm], axis=1) @ euler((0, 0, rng.normal() * 4))
        p.add(Plank(c + np.array([0, -hh / 2, 0]), (w / 2, 0.014, hh / 2), R @ euler((90, 0, 0)), bow=0.02, sweep=0.02, twist=4, seed=i))
        for sx in (-1, 1):
            p.add(Box(c + d * sx * w * 0.35 + np.array([0, 0.01, 0]), (0.008, 0.03, 0.012), R, round=0.004), k=0.003, color=TP["wood_lt"])
        s += w + rng.uniform(0.08, 0.2)
        i += 1


def oar(m, merge, foot, top, color=None, blade_color=None):
    foot, top = np.asarray(foot, float), np.asarray(top, float)
    d = (top - foot) / np.linalg.norm(top - foot)
    p = m.piece(color=color or TP["wood_lt"], merge=merge, res=0.008, lumps=0.002, detail=0.5)
    p.add(Capsule(foot + d * 0.5, top, 0.024))
    R = frame(d, np.cross(d, [0, 1, 0]) if abs(d[1]) < 0.9 else [1, 0, 0])
    p.add(Box(foot + d * 0.32, (0.32, 0.012, 0.075), R, round=0.01), k=0.03, color=blade_color or TP["teal"])
    p.paint(Box(foot + d * 0.12, (0.13, 0.05, 0.1), R), TP["white"], feather=0.006)


def frustum(c, r0, r1, h):
    """Tapered round column from y=c.y (radius r0) to c.y+h (radius r1)."""
    c = np.asarray(c, float)

    def f(P):
        y = P[:, 1] - c[1]
        t = np.clip(y / h, 0, 1)
        r = r0 + (r1 - r0) * t
        rad = np.hypot(P[:, 0] - c[0], P[:, 2] - c[2]) - r
        cap = np.maximum(-y, y - h)
        return np.maximum(rad * 0.98, cap)
    R = max(r0, r1)
    return Func(f, c - np.array([R, 0, R]) - 0.05, c + np.array([R, h, R]) + 0.05)


# ----------------------------------------------------------------------------------------------------------------
# post office


def post_office():
    m = TownModel("post_office", budget=43000)
    rng = m.rng
    hx, hz, eave, ridge = 2.3, 1.7, 2.55, 3.65
    red, cream = "#9b4d40", TP["cream"]
    ops = {"front": [(0.55, 1.45, -1, 2.05), (2.45, 4.15, 0.95, 1.95)], "left": [(1.2, 2.1, 1.1, 1.85)], "right": [(1.25, 2.15, 1.1, 1.85)],
           "back": [(2.8, 3.6, 1.2, 1.8)]}
    sh = Shack(m, hx, hz, eave, ridge, ridge="x", walls="h", paint=red, peel=0.22, trim=cream, openings=ops, roof="tin",
               roof_colors=["#4f6f6c", TP["teal_dk"], "#5b7a74"], rust=0.35, sag=0.06, ov=0.35, ov_gable=0.3)
    # floor (seen through the counter window)
    deck(m, "floor", -hx, hx, -hz, hz, 0.0, along="x", nails=0, detail=0.5)
    # porch deck + lean-to roof on two posts
    deck(m, "floor", -hx - 0.25, hx + 0.25, hz + 0.02, hz + 1.25, 0.04, along="x", detail=0.8)
    for x in (-hx - 0.12, hx + 0.12):
        post(m, "trim", (x, 0.0, hz + 1.12), (x + rng.normal() * 0.02, 2.02, hz + 1.12), 0.06, TP["wood"], detail=0.6)
    tin_roof(m, "roof", (-hx - 0.35, 1.98, hz + 1.42), (hx + 0.35, 1.98, hz + 1.42), (-hx - 0.35, 2.26, hz + 0.04), (hx + 0.35, 2.26, hz + 0.04),
             colors=["#4f6f6c", TP["tin_dk"]], rust=0.3, sag=0.03, patch=0.2)
    board(m, "trim", (-hx - 0.3, 1.94, hz + 1.17), (hx + 0.3, 1.94, hz + 1.17), 0.14, 0.06, (0, 0, 1), TP["wood"], paint=cream, peel=0.3, nails=2)
    board(m, "trim", (-hx - 0.1, 2.2, hz + 0.08), (hx + 0.1, 2.2, hz + 0.08), 0.12, 0.06, (0, 0, 1), TP["wood_dk"], nails=2, detail=0.6)
    # door + windows
    dc, out = sh.at("front", 1.0, 0.0)
    door(m, MG, dc, out, 0.86, 1.98, paint=TP["teal"], peel=0.25)
    m.socket("door", None, dc + out * 0.1 + np.array([0, 1.0, 0]))
    wins = []
    # the big counter window: open hatch (no glass), counter ledge, Marge serves behind it
    wc, out = sh.at("front", 3.3, 1.45)
    for (a, b, ww) in ((wc + np.array([-0.92, 0.55, 0.05]), wc + np.array([0.92, 0.55, 0.05]), 0.1),
                       (wc + np.array([-0.88, -0.5, 0.05]), wc + np.array([-0.88, 0.55, 0.05]), 0.08),
                       (wc + np.array([0.88, -0.5, 0.05]), wc + np.array([0.88, 0.55, 0.05]), 0.08)):
        board(m, "trim", a, b, ww, 0.05, (0, 0, 1), TP["wood"], paint=cream, peel=0.25, nails=1)
    board(m, "trim", wc + np.array([-1.0, -0.52, 0.12]), wc + np.array([1.0, -0.52, 0.12]), 0.34, 0.06, (0, 1, 0), TP["wood_br"], nails=2, detail=1.2)
    for x in (-0.7, 0.7):
        post(m, "trim", wc + np.array([x, -0.57, 0.25]), wc + np.array([x, -1.0, 0.05]), 0.025, TP["wood_dk"], detail=0.3)
    # two shutters folded back flat against the wall either side of the counter window
    for sx in (-1, 1):
        for k in range(2):
            x = sx * (0.98 + 0.11 + k * 0.21)
            board(m, "deco", wc + np.array([x, -0.47, 0.09]), wc + np.array([x, 0.47, 0.09]), 0.2, 0.035, (0, 0, 1), TP["wood"], paint=TP["teal"],
                  peel=0.3, nails=1, detail=0.7, knot=0)
        board(m, "deco", wc + np.array([sx * 0.99, -0.3, 0.12]), wc + np.array([sx * 1.5, 0.3, 0.12]), 0.06, 0.03, (0, 0, 1), TP["wood"],
              paint=TP["teal"], peel=0.3, nails=0, detail=0.4, knot=0)
    m.socket("counter", None, (wc[0], 0.0, hz - 0.55), (0, 0, 0))
    # pigeonhole letter rack inside on the back wall, visible through the hatch
    rack_c = np.array([wc[0], 1.35, -hz + 0.2])
    rk = m.piece(color=TP["wood_br"], merge="deco", res=0.012, lumps=0.002, detail=1.2)
    rk.add(Box(rack_c, (0.9, 0.55, 0.16), round=0.02))
    for i in range(6):
        for j in range(4):
            cc = rack_c + np.array([-0.75 + i * 0.3, -0.4 + j * 0.27, 0.06])
            rk.sub(Box(cc, (0.12, 0.1, 0.16), round=0.015), k=0.01, color="#4a3a2c")
    lp = m.piece(color="#e8e0cc", merge="deco", res=0.008, lumps=0.002, detail=0.8)
    for i in range(6):
        for j in range(4):
            if rng.random() < 0.55:
                cc = rack_c + np.array([-0.75 + i * 0.3 + rng.normal() * 0.02, -0.43 + j * 0.27, 0.15])
                lp.add(Box(cc, (0.08, 0.05 + rng.uniform(0, 0.04), 0.012), euler((rng.normal() * 8, 0, rng.normal() * 15)), round=0.004), k=0.002,
                       color=rng.choice(["#e8e0cc", "#d9c9a3", "#c9d3d8", "#e3c9b4"]))
    # parcels on the counter + a brass bell
    for k in range(3):
        c = wc + np.array([-0.6 + k * 0.28, -0.46 + 0.0, 0.0]) + np.array([0, 0, 0.0])
        p = m.piece(color=rng.choice(["#a8865e", "#b79a6c", "#97764f"]), merge="deco", res=0.008, lumps=0.003, detail=0.6)
        s = rng.uniform(0.08, 0.13)
        p.add(Box(c + np.array([0, s, 0.05]), (s * 1.3, s, s), euler((0, rng.normal() * 15, 0)), round=0.012))
        p.paint(Box(c + np.array([0, s, 0.05]), (0.012, 1, 1)), "#cfc2a2", feather=0.003)
    bp = m.piece(color=TP["brass"], gloss=170, merge="deco", res=0.006, detail=0.4)
    bc = wc + np.array([0.6, -0.46, 0.15])
    bp.add(Ellipsoid(bc + np.array([0, 0.04, 0]), (0.06, 0.05, 0.06)))
    bp.add(Cylinder(bc + np.array([0, 0.008, 0]), 0.07, 0.008, round=0.004), k=0.004, color=TP["wood_dk"])
    # side windows + back window
    for side, s, w, h in (("left", 1.65, 0.62, 0.62), ("right", 1.7, 0.62, 0.62), ("back", 3.2, 0.55, 0.5)):
        c, out = sh.at(side, s, 1.47)
        wins.append(window(m, MG, c, out, w, h, frame_color=cream, shutters=TP["teal"] if side != "back" else None, curtain="#c9b48f"))
    for i, w in enumerate(wins):
        m.socket(f"win_{i}", None, w)
    # sign board on the porch roof front (blank face for Unity lettering)
    sc = np.array([0.0, 2.52, hz + 1.3])
    sc = np.array([0.0, 2.27, hz + 1.24])
    sb = m.piece(color="#e6dcc2", gloss=60, merge="deco", res=0.01, lumps=0.002, dents=3, detail=1.0)
    sb.add(Plank(sc, (1.15, 0.03, 0.2), frame((1, 0, 0), (0, 0, 1)), twist=1.0, seed=5))
    for (a, b) in (((-1.2, 0.21), (1.2, 0.21)), ((-1.2, -0.21), (1.2, -0.21)), ((-1.18, -0.2), (-1.18, 0.2)), ((1.18, -0.2), (1.18, 0.2))):
        board(m, "deco", sc + np.array([a[0], a[1], 0.03]), sc + np.array([b[0], b[1], 0.03]), 0.055, 0.035, (0, 0, 1), TP["wood"], paint="#8d3b31",
              peel=0.15, nails=0, detail=0.5, knot=0)
    for x in (-0.85, 0.85):
        post(m, "deco", (x, 1.98, hz + 1.24), (x, 2.08, hz + 1.24), 0.025, TP["wood_dk"], detail=0.2)
    m.socket("sign_text", None, sc + np.array([0, 0, 0.04]))
    # porch lantern
    lt = KP.hanging_lantern(m, T((-0.25, 2.06, hz + 0.75)), merge="metal", glass="glass", drop=0.08)
    m.socket("light_0", None, lt)
    smoke = stovepipe(m, "roof", (1.3, sh.roof_y(1.3, -0.9) - 0.15, -0.9), 1.1, lean=(0.06, -0.08))
    m.socket("smoke", None, smoke)
    # the big mailbox out front + dressing
    KP.mailbox(m, T((2.85, 0.0, 2.55), -8), merge="props", post_h=0.95, color=TP["red"], scale=1.9)
    KP.crate(m, T((-2.0, 0.04, 2.35), 12), merge="props", size=(0.56, 0.42, 0.42))
    KP.crate(m, T((-2.05, 0.47, 2.3), -6), merge="props", size=(0.44, 0.3, 0.36), lid=True)
    KP.flower_pot(m, T((-1.45, 0.04, 2.6), 0), merge="props", kind="thrift")
    KP.flower_box(m, T(sh.at("left", 1.65, 0.9, 0.05)[0], -90), merge="props", L=0.75)
    KP.bench(m, T((-hx - 0.62, 0.0, -0.2), -90), merge="props", L=1.1)
    return m


MODELS["town/post_office"] = calmed(post_office, jitter=0.75)


# ----------------------------------------------------------------------------------------------------------------
# net shed


def net_shed():
    m = TownModel("net_shed", budget=34000)
    rng = m.rng
    hx, hz, eave, ridge = 1.95, 1.8, 2.35, 3.55
    ops = {"front": [(0.95, 2.95, -1, 2.15), (1.65, 2.25, 2.55, 2.95)], "left": [(1.3, 2.0, 1.15, 1.75)]}
    sh = Shack(m, hx, hz, eave, ridge, ridge="z", walls="v", colors=[TP["wood"], TP["wood_dk"], TP["wood_silver"], TP["wood_lt"]],
               paint="#86453a", peel=0.55, trim=TP["wood_lt"], openings=ops, roof="tin", rust=0.6, sag=0.09, ov=0.3, ov_gable=0.35, lean=0.01)
    deck(m, "floor", -hx, hx, -hz, hz, 0.0, along="z", nails=0, detail=0.4)
    # big double doors, one ajar
    dc, out = sh.at("front", 1.45, 0.0)
    door(m, MG, dc, out, 0.98, 2.1, color=TP["wood_dk"], paint="#86453a", peel=0.5, knob=False)
    dc2, _ = sh.at("front", 2.45, 0.0)
    door(m, MG, dc2, out, 0.98, 2.1, color=TP["wood_dk"], paint="#86453a", peel=0.5, knob=True, crooked=-1.5)
    m.socket("door", None, (0.0, 1.0, hz + 0.1))
    # loft hatch in the gable
    hc, out = sh.at("front", 1.95, 2.75)
    for x in (-0.22, 0.0, 0.22):
        board(m, "trim", hc + np.array([x, -0.2, 0.04]), hc + np.array([x, 0.2, 0.04]), 0.2, 0.04, out, TP["wood_br"], nails=1, detail=0.6)
    wins = [window(m, MG, *sh.at("left", 1.65, 1.45), 0.6, 0.55, frame_color=TP["wood_lt"], panes=(2, 1))]
    m.socket("win_0", None, wins[0])
    # lantern on a bracket by the door
    ab = np.array([-hx + 0.55, 2.0, hz + 0.05])
    br = m.piece(color=TP["iron"], gloss=80, merge="metal", res=0.007, detail=0.3)
    br.add(Tube([ab, ab + (0.0, 0.05, 0.22), ab + (0.0, 0.0, 0.34)], 0.013, samples=4))
    lt = KP.hanging_lantern(m, T(ab + (0.0, -0.01, 0.34)), merge="metal", glass="glass", drop=0.1)
    m.socket("light_0", None, lt)
    # nets drying on a rack along the right side + one hung on the back wall
    KP.net_rack(m, T((hx + 0.85, 0.0, 0.0), 90), merge="props", net="net", width=2.5, h=1.85)
    # buoys and floats hung under the front eave
    KP.buoy_cluster(m, T((hx - 0.35, 2.3, hz + 0.25)), merge="props", n_glass=2, n_buoys=2)
    KP.buoy_cluster(m, T((-hx - 0.12, 2.15, -0.6)), merge="props", n_glass=3, n_buoys=1)
    # crab pots, oars, barrel, rope
    KP.crab_pot_stack(m, T((-hx + 0.25, 0.0, hz + 0.95), 8), merge="props", net="net", n=2)
    oar(m, "props", (hx - 0.05, 0.02, hz + 0.25), (hx - 0.2, 2.25, hz + 0.08))
    oar(m, "props", (hx - 0.35, 0.02, hz + 0.32), (hx - 0.3, 2.2, hz + 0.08), blade_color=TP["red"])
    KP.barrel(m, T((-hx - 0.45, 0.0, hz - 0.5), 30), merge="props")
    KP.rope_coil(m, T((0.9, 0.0, hz + 1.25), 50), merge="props")
    KP.life_ring(m, T(sh.at("left", 0.6, 1.75, 0.05)[0], -90), merge="props")
    smoke = stovepipe(m, "roof", (-1.0, sh.roof_y(-1.0, -0.8) - 0.1, -0.8), 0.9, lean=(-0.08, 0.05))
    m.socket("smoke", None, smoke)
    return m


MODELS["town/net_shed"] = calmed(net_shed, bw=(0.25, 0.33), jitter=0.8)


# ----------------------------------------------------------------------------------------------------------------
# cottages


def porch(m, hx, z0, depth, fl, rails=True, rail_gap=(-0.55, 0.55)):
    """Front porch deck at floor height fl from z0 to z0+depth, posts down to the ground, rails either side of the steps."""
    rng = m.rng
    deck(m, "floor", -hx, hx, z0, z0 + depth, fl, along="x", detail=0.8)
    for x in np.linspace(-hx + 0.08, hx - 0.08, 3):
        post(m, "floor", (x, -0.6, z0 + depth - 0.08), (x, fl - 0.05, z0 + depth - 0.08), 0.06, TP["wood_dk"], detail=0.4)
    if rails:
        ze = z0 + depth - 0.06
        rail_run(m, "trim", [(-hx + 0.04, fl, z0 + 0.05), (-hx + 0.04, fl, ze), (rail_gap[0], fl, ze)], h=0.82, post_every=1.2, foot_y=-0.15,
                 end_post=True)
        rail_run(m, "trim", [(rail_gap[1], fl, ze), (hx - 0.04, fl, ze), (hx - 0.04, fl, z0 + 0.05)], h=0.82, post_every=1.2, foot_y=-0.15)


def cottage_a():
    """Mustard clapboard, red tin roof, stone chimney on the right gable, front porch with steps, woodpile."""
    m = TownModel("cottage_a", budget=48000)
    rng = m.rng
    FL = 0.6
    hx, hz, eave, ridge = 2.55, 1.75, 2.45, 3.7
    zc = -0.45   # house centre z (so porch + steps stay on the pad)
    n0 = len(m.pieces)
    ops = {"front": [(0.55, 1.3, 0.9, 1.85), (2.1, 3.0, -1, 2.0), (3.8, 4.55, 0.9, 1.85)], "left": [(1.3, 2.2, 1.0, 1.8)],
           "right": [(0.5, 1.1, 1.05, 1.75)], "back": [(1.2, 2.0, 1.05, 1.8), (3.2, 3.9, 1.05, 1.8)]}
    sh = Shack(m, hx, hz, eave, ridge, ridge="x", walls="h", paint=TP["mustard"], peel=0.2, trim=TP["cream"], openings=ops, roof="tin",
               roof_colors=[TP["red"], TP["red_dk"], "#a35a48"], rust=0.35, sag=0.08, ov=0.4, ov_gable=0.3)
    wins = []
    for side, s, w, h in (("front", 0.92, 0.65, 0.85), ("front", 4.17, 0.65, 0.85), ("left", 1.75, 0.8, 0.7), ("right", 0.8, 0.5, 0.6),
                          ("back", 1.6, 0.7, 0.65), ("back", 3.55, 0.6, 0.65)):
        c, out = sh.at(side, s, 1.37 if side != "right" else 1.4)
        wins.append(window(m, MG, c, out, w, h, frame_color=TP["cream"], shutters=TP["red"] if side == "front" else None,
                           curtain=rng.choice(["#c9b48f", "#b8796f", "#d8cdb0"])))
    dc, out = sh.at("front", 2.55, 0.0)
    door(m, MG, dc, out, 0.86, 1.95, paint=TP["teal"], peel=0.2)
    dsock = dc + out * 0.1 + np.array([0, 1.0, 0])
    # window flower boxes on the front
    for s in (0.92, 4.17):
        c, out = sh.at("front", s, 0.72, 0.04)
        KP.flower_box(m, T(c, 0), merge="props", L=0.8, paint=TP["red"])
    # hanging porch lantern from the eave
    lt = KP.hanging_lantern(m, T((-0.75, eave - 0.05, hz + 0.32)), merge="metal", glass="glass", drop=0.1)
    move_since(m, n0, (0, FL, zc))
    wins = [w + np.array([0, FL, zc]) for w in wins]
    lt = lt + np.array([0, FL, zc])
    dsock = dsock + np.array([0, FL, zc])
    # stone chimney against the right gable
    smoke = stone_chimney(m, "stone", (hx + 0.32, FL - 0.3, zc - 0.1), ridge + 0.75 - FL + 0.3 + FL, w=0.55, lean=0.012)
    # foundation: stone walls down into the slope
    for a, b in (((-hx, hz), (hx, hz)), ((hx, hz), (hx, -hz)), ((hx, -hz), (-hx, -hz)), ((-hx, -hz), (-hx, hz))):
        aa = (a[0] * 1.0 + np.sign(a[0]) * 0.02, a[1] + zc)
        bb = (b[0] * 1.0 + np.sign(b[0]) * 0.02, b[1] + zc)
        stone_wall(m, "stone", aa, bb, -1.2, FL - 0.02, thick=0.3)
    porch(m, hx - 0.2, hz + zc + 0.02, 1.05, FL)
    steps(m, "floor", 0.0, hz + zc + 1.07, FL, 3, run=0.27, width=1.0)
    # dressing
    woodpile(m, "props", T((-hx - 0.55, 0.0, zc - 0.1)), L=1.6)
    KP.flower_pot(m, T((0.85, FL, hz + zc + 0.8)), merge="props")
    KP.flower_pot(m, T((-0.8, 0.0, hz + zc + 1.95)), merge="props", kind="thrift", r=0.14)
    KP.bench(m, T((1.45, FL, hz + zc + 0.4), 0), merge="props", L=1.0)
    m.socket("door", None, dsock)
    m.socket("smoke", None, smoke)
    m.socket("light_0", None, lt)
    for i, w in enumerate(wins):
        m.socket(f"win_{i}", None, w)
    return m


MODELS["town/cottage_a"] = calmed(cottage_a, jitter=0.75)


def cottage_b():
    """Faded teal board & batten, mossy shake roof (gable to the front), lean-to woodshed, stovepipe, washing line."""
    m = TownModel("cottage_b", budget=48000)
    rng = m.rng
    FL = 0.5
    hx, hz, eave, ridge = 2.0, 2.2, 2.35, 3.85
    zc = -0.6
    xc = -0.35
    n0 = len(m.pieces)
    ops = {"front": [(0.4, 1.3, -1, 1.95), (2.3, 3.2, 0.95, 1.8), (1.75, 2.25, 2.65, 3.1)], "left": [(1.6, 2.6, 1.0, 1.75)],
           "right": [(2.6, 3.4, 1.0, 1.7)], "back": [(1.6, 2.4, 1.05, 1.7)]}
    sh = Shack(m, hx, hz, eave, ridge, ridge="z", walls="v", paint=TP["teal"], peel=0.4, trim=TP["cream"], openings=ops, roof="shake",
               roof_colors=[TP["wood_dk"], TP["wood"], "#5f5a52"], moss=0.45, sag=0.09, ov=0.35, ov_gable=0.32, lean=0.008)
    wins = []
    for side, s, w, h, y in (("front", 2.75, 0.8, 0.75, 1.37), ("front", 2.0, 0.4, 0.4, 2.87), ("left", 2.1, 0.9, 0.65, 1.37),
                             ("right", 3.0, 0.7, 0.6, 1.35), ("back", 2.0, 0.7, 0.55, 1.37)):
        c, out = sh.at(side, s, y)
        wins.append(window(m, MG, c, out, w, h, frame_color=TP["cream"], panes=(2, 2) if h > 0.5 else (1, 1),
                           shutters=TP["mustard"] if (side == "front" and y < 2) else None, curtain=rng.choice(["#c9b48f", "#d8cdb0", "#a9b59a"])))
    dc, out = sh.at("front", 0.85, 0.0)
    door(m, MG, dc, out, 0.84, 1.92, paint=TP["red"], peel=0.35)
    dsock = dc + out * 0.1 + np.array([0, 1.0, 0])
    # little entry canopy over the door
    tin_roof(m, "roof", (-hx - 0.1, 2.12, hz + 0.75), (-hx + 1.55, 2.12, hz + 0.75), (-hx - 0.1, 2.35, hz + 0.02), (-hx + 1.55, 2.35, hz + 0.02),
             colors=[TP["tin"], TP["tin_dk"]], rust=0.5, sag=0.02, patch=0.3)
    for x in (-hx + 0.0, -hx + 1.45):
        post(m, "trim", (x, 2.15, hz + 0.05), (x, 1.85, hz + 0.05) + np.array([0, 0, 0.5]), 0.03, TP["wood_dk"], detail=0.3)
    lt = KP.hanging_lantern(m, T((-hx + 1.25, 2.1, hz + 0.5)), merge="metal", glass="glass", drop=0.08)
    smoke = stovepipe(m, "roof", (0.9, sh.roof_y(0.9, -0.9) - 0.12, -0.9), 1.3, lean=(0.12, -0.06), bends=2)
    move_since(m, n0, (xc, FL, zc))
    wins = [w + np.array([xc, FL, zc]) for w in wins]
    lt, dsock, smoke = (v + np.array([xc, FL, zc]) for v in (lt, dsock, smoke))
    # lean-to woodshed on the right side: open front, single slope tin roof
    x0, x1 = hx + xc + 0.02, hx + xc + 1.45
    z0, z1 = zc - 1.6, zc + 0.9
    yhi = 2.35 + FL - 0.2
    vboard_wall(m, "walls", (x1, z1), (x1, z0), 0.0, 1.7, (1, 0, 0), [TP["wood"], TP["wood_dk"], TP["wood_silver"]], replace=0.15, battens=False)
    vboard_wall(m, "walls", (x1, z0), (x0, z0), 0.0, lambda s: 1.7 + (yhi - 1.7) * s / (x1 - x0), (0, 0, -1), [TP["wood"], TP["wood_dk"], TP["wood_silver"]],
                replace=0.15, battens=False)
    for z in (z0, z1):
        post(m, "trim", (x1, 0.0, z), (x1, 1.8, z), 0.06, TP["wood_dk"], detail=0.4)
    tin_roof(m, "roof", (x1 + 0.3, 1.72, z1 + 0.3), (x1 + 0.3, 1.72, z0 - 0.3), (x0, 2.35 + FL - 0.15, z1 + 0.3), (x0, 2.35 + FL - 0.15, z0 - 0.3),
             rust=0.55, sag=0.04, patch=0.3)
    woodpile(m, "props", T(((x0 + x1) / 2, 0.0, (z0 + z1) / 2 - 0.1)), L=2.0, rows=5)
    # raised floor on short stilts + stone piers, skirt boards
    sx_ = np.linspace(-hx + 0.15, hx - 0.15, 3) + xc
    sz_ = np.linspace(-hz + 0.15, hz - 0.15, 3) + zc
    stilts(m, "floor", sx_, sz_, FL - 0.06, -1.2, r=0.11, braces=False)
    pads = m.piece(color=TP["stone"], merge="stone", res=0.02, lumps=0.008, lump_freq=4, dents=5, dent_size=0.05, detail=0.8)
    for x in sx_:
        for z in sz_:
            pads.add(Ellipsoid((x, 0.02, z), (0.26, 0.16, 0.24), euler((rng.normal() * 6, rng.uniform(0, 90), rng.normal() * 6))), k=0.02,
                     color=rng.choice([TP["stone"], TP["stone_dk"], TP["stone_lt"]]))
    for x in sx_:
        board(m, "floor", (x, FL - 0.14, -hz + zc - 0.05), (x, FL - 0.14, hz + zc + 0.05), 0.16, 0.08, (1, 0, 0), TP["wood_dk"], nails=2, detail=0.6)
    for (a, b, o) in (((-hx + xc, FL - 0.12, hz + zc + 0.04), (hx + xc, FL - 0.12, hz + zc + 0.04), (0, 0, 1)),
                      ((hx + xc + 0.04, FL - 0.12, hz + zc), (hx + xc + 0.04, FL - 0.12, -hz + zc), (1, 0, 0)),
                      ((hx + xc, FL - 0.12, -hz + zc - 0.04), (-hx + xc, FL - 0.12, -hz + zc - 0.04), (0, 0, -1)),
                      ((-hx + xc - 0.04, FL - 0.12, -hz + zc), (-hx + xc - 0.04, FL - 0.12, hz + zc), (-1, 0, 0))):
        board(m, "trim", a, b, 0.2, 0.05, o, TP["wood_dk"], nails=2, detail=0.8)
    # front landing + steps (door is on the left of the gable front)
    dx = -hx + 0.85 + xc
    deck(m, "floor", dx - 0.7, dx + 0.7, hz + zc + 0.02, hz + zc + 0.85, FL, along="x", detail=0.6)
    steps(m, "floor", dx, hz + zc + 0.87, FL, 2, run=0.28, width=1.0)
    rail_run(m, "trim", [(dx + 0.66, FL, hz + zc + 0.06), (dx + 0.66, FL, hz + zc + 0.8)], h=0.8, post_every=0.8, foot_y=-0.2)
    # washing line off the left side
    washing_line(m, "deco", (-hx + xc - 0.4, 0.0, zc + 1.4), (-hx + xc - 0.6, 0.0, zc - 2.2))
    KP.flower_pot(m, T((dx + 0.45, FL, hz + zc + 0.55)), merge="props")
    KP.crate(m, T((x1 - 0.5, 0.0, z1 + 0.45), 20), merge="props")
    m.socket("door", None, dsock)
    m.socket("smoke", None, smoke)
    m.socket("light_0", None, lt)
    for i, w in enumerate(wins):
        m.socket(f"win_{i}", None, w)
    return m


MODELS["town/cottage_b"] = calmed(cottage_b, bw=(0.27, 0.35), jitter=0.6)


def cottage_c():
    """Rose clapboard saltbox (long back roof slope), patched grey tin, cream trim, brick-and-stone chimney through the
    ridge, flower boxes, bench by the door."""
    m = TownModel("cottage_c", budget=48000)
    rng = m.rng
    FL = 0.55
    hx, hz = 2.6, 1.9
    zc = -0.4
    eave_f, eave_b, ridge_y, ridge_z = 2.5, 1.55, 3.85, 0.55     # saltbox: ridge toward the front
    n0 = len(m.pieces)
    rose, cream = TP["rose"], TP["cream"]
    cols = [TP["wood"], TP["wood_lt"]]

    def gable_top(s, front_to_back):
        # s along the side wall; side walls run front->back (right) or back->front (left)
        z = hz - s if front_to_back else -hz + s
        if z >= ridge_z:
            return eave_f + (ridge_y - eave_f) * (hz - z) / (hz - ridge_z)
        return eave_b + (ridge_y - eave_b) * (z + hz) / (ridge_z + hz)
    ops_front = [(0.6, 1.35, 0.95, 1.9), (2.15, 3.05, -1, 2.0), (3.85, 4.6, 0.95, 1.9)]
    hboard_wall(m, "walls", (-hx, hz), (hx, hz), 0.0, eave_f, (0, 0, 1), cols, paint=rose, peel=0.25, openings=ops_front)
    hboard_wall(m, "walls", (hx, -hz), (-hx, -hz), 0.0, eave_b, (0, 0, -1), cols, paint=rose, peel=0.25, openings=[(1.9, 2.6, 0.6, 1.3)])
    hboard_wall(m, "walls", (hx, hz), (hx, -hz), 0.0, lambda s: gable_top(s, True), (1, 0, 0), cols, paint=rose, peel=0.25,
                openings=[(1.0, 1.75, 1.0, 1.8), (1.25, 1.7, 2.55, 3.0)])
    hboard_wall(m, "walls", (-hx, -hz), (-hx, hz), 0.0, lambda s: gable_top(s, False), (-1, 0, 0), cols, paint=rose, peel=0.25,
                openings=[(2.0, 2.8, 1.0, 1.75)])
    for sx in (-1, 1):
        for sz in (-1, 1):
            board(m, "trim", (sx * (hx + 0.03), -0.05, sz * (hz + 0.03)), (sx * (hx + 0.03), (eave_f if sz > 0 else eave_b) + 0.02, sz * (hz + 0.03)),
                  0.14, 0.05, (sx, 0, sz), TP["wood"], paint=cream, peel=0.3, nails=2)
    # roof: front slope (short, steep) and back slope (long), grey tin with patches
    ov, og = 0.35, 0.3
    kf = (ridge_y - eave_f) / (hz - ridge_z)
    kb = (ridge_y - eave_b) / (ridge_z + hz)
    yf = eave_f - ov * kf
    yb = eave_b - ov * kb
    tin_roof(m, "roof", (-hx - og, yf, hz + ov), (hx + og, yf, hz + ov), (-hx - og, ridge_y + 0.04, ridge_z), (hx + og, ridge_y + 0.04, ridge_z),
             rust=0.45, sag=0.05, patch=0.25)
    tin_roof(m, "roof", (hx + og, yb, -hz - ov), (-hx - og, yb, -hz - ov), (hx + og, ridge_y + 0.04, ridge_z), (-hx - og, ridge_y + 0.04, ridge_z),
             rust=0.45, sag=0.1, patch=0.3)
    rr = m.piece(color=TP["tin_dk"], gloss=40, merge="roof", res=0.012, lumps=0.002, detail=0.5)
    rr.add(Tube([(-hx - og - 0.05, ridge_y + 0.08, ridge_z), (0, ridge_y + 0.04, ridge_z), (hx + og + 0.05, ridge_y + 0.08, ridge_z)], 0.07, samples=4))
    for sx in (-1, 1):
        x = sx * (hx + og + 0.03)
        board(m, "trim", (x, yf - 0.08, hz + ov), (x, ridge_y - 0.05, ridge_z), 0.18, 0.05, (sx, 0, 0), TP["wood"], paint=cream, peel=0.3, nails=2)
        board(m, "trim", (x, yb - 0.08, -hz - ov), (x, ridge_y - 0.05, ridge_z), 0.18, 0.05, (sx, 0, 0), TP["wood"], paint=cream, peel=0.3, nails=2)
    board(m, "trim", (-hx - og, yf - 0.1, hz + ov - 0.02), (hx + og, yf - 0.1, hz + ov - 0.02), 0.15, 0.045, (0, 0, 1), TP["wood"], paint=cream, peel=0.3)
    board(m, "trim", (-hx - og, yb - 0.1, -hz - ov + 0.02), (hx + og, yb - 0.1, -hz - ov + 0.02), 0.15, 0.045, (0, 0, -1), TP["wood"], paint=cream, peel=0.3)
    wins = []
    for (c, out, w, h, sh_) in (((-hx + 0.97, 1.42, hz + 0.03), (0, 0, 1), 0.65, 0.85, TP["sage"]), ((hx - 0.97, 1.42, hz + 0.03), (0, 0, 1), 0.65, 0.85, TP["sage"]),
                                ((hx + 0.03, 1.4, hz - 1.37), (1, 0, 0), 0.65, 0.7, None), ((hx + 0.03, 2.77, hz - 1.47), (1, 0, 0), 0.38, 0.38, None),
                                ((-hx - 0.03, 1.37, -hz + 2.4), (-1, 0, 0), 0.7, 0.65, None), ((hx - 2.25, 0.95, -hz - 0.03), (0, 0, -1), 0.6, 0.6, None)):
        wins.append(window(m, MG, c, out, w, h, frame_color=cream, shutters=sh_, panes=(2, 2) if h > 0.5 else (1, 1),
                           curtain=rng.choice(["#d8cdb0", "#c9b48f", "#e0c9b8"])))
    dc = np.array([-hx + 2.6, 0.0, hz + 0.03])
    door(m, MG, dc, (0, 0, 1), 0.88, 1.98, paint=TP["navy"], peel=0.25)
    dsock = dc + np.array([0, 1.0, 0.1])
    for s in (0.97, 4.0):
        KP.flower_box(m, T((-hx + s, 0.76, hz + 0.05), 0), merge="props", L=0.78, paint=TP["sage"])
    lt = KP.hanging_lantern(m, T((dc[0] + 0.75, 2.25, hz + 0.3)), merge="metal", glass="glass", drop=0.1)
    br = m.piece(color=TP["iron"], gloss=80, merge="metal", res=0.007, detail=0.3)
    br.add(Tube([(dc[0] + 0.75, 2.3, hz + 0.03), (dc[0] + 0.75, 2.33, hz + 0.2), (dc[0] + 0.75, 2.27, hz + 0.3)], 0.012, samples=4))
    move_since(m, n0, (0, FL, zc))
    wins = [w + np.array([0, FL, zc]) for w in wins]
    lt, dsock = lt + np.array([0, FL, zc]), dsock + np.array([0, FL, zc])
    # chimney through the ridge (stone base inside, brick-red top)
    smoke = stone_chimney(m, "stone", (-0.9, ridge_y + FL - 0.9, ridge_z + zc - 0.1), 1.6, w=0.5, lean=-0.015,
                          colors=["#9b6a52", "#8c5a45", "#a6735a", TP["stone"]])
    for a, b in (((-hx - 0.02, hz + zc), (hx + 0.02, hz + zc)), ((hx + 0.02, hz + zc), (hx + 0.02, -hz + zc)), ((hx + 0.02, -hz + zc), (-hx - 0.02, -hz + zc)),
                 ((-hx - 0.02, -hz + zc), (-hx - 0.02, hz + zc))):
        stone_wall(m, "stone", a, b, -1.2, FL - 0.02, thick=0.3)
    # stone steps up to the door
    st = m.piece(color=TP["stone"], merge="stone", res=0.02, lumps=0.006, lump_freq=5, dents=4, dent_size=0.05, detail=1.0)
    for i in range(3):
        y = FL - (i + 1) * FL / 3
        z = hz + zc + 0.2 + i * 0.3
        st.add(Box((dc[0] + rng.normal() * 0.03, y + FL / 6 - 0.04, z), (0.6 - i * 0.02 + 0.08 * i, FL / 6 + 0.04, 0.2 + 0.02 * i), euler((0, rng.normal() * 4, 0)),
                   round=0.05), k=0.02, color=rng.choice([TP["stone"], TP["stone_lt"], TP["stone_dk"]]))
    KP.bench(m, T((1.0, 0.0, hz + zc + 0.75), 0), merge="props", L=1.2)
    KP.flower_pot(m, T((dc[0] - 0.75, 0.0, hz + zc + 0.45)), merge="props", r=0.15, h=0.24)
    KP.flower_pot(m, T((dc[0] + 0.7, 0.0, hz + zc + 0.55)), merge="props", kind="thrift")
    KP.barrel(m, T((-hx - 0.4, 0.0, zc - 1.2), 10), merge="props", h=0.75)
    m.socket("door", None, dsock)
    m.socket("smoke", None, smoke)
    m.socket("light_0", None, lt)
    for i, w in enumerate(wins):
        m.socket(f"win_{i}", None, w)
    return m


MODELS["town/cottage_c"] = calmed(cottage_c, jitter=0.75)


# ----------------------------------------------------------------------------------------------------------------
# lighthouse


def lighthouse():
    m = TownModel("lighthouse", budget=53000)
    rng = m.rng
    base_h = 0.9
    t0, t1 = base_h, 8.2          # tower body
    r0, r1 = 2.05, 1.55
    lean = np.array([0.04, 0, -0.03])   # tower axis drifts a little with height
    # rocky stone plinth: big lumpy blocks in a ring
    pl = m.piece(color=TP["stone"], merge="stone", res=0.03, lumps=0.012, lump_freq=3, dents=8, dent_size=0.12, dent_depth=0.012, detail=1.6)
    pl.add(Cylinder((0, base_h / 2 - 0.25, 0), r0 + 0.55, base_h / 2 + 0.25, round=0.2), k=0.05)
    for i in range(16):
        a = 2 * np.pi * (i + rng.normal() * 0.15) / 16
        rr = r0 + 0.5 + rng.normal() * 0.08
        c = np.array([np.cos(a) * rr, rng.uniform(0.0, 0.35), np.sin(a) * rr])
        pl.add(Box(c, (rng.uniform(0.35, 0.5), rng.uniform(0.3, 0.5), rng.uniform(0.3, 0.42)), euler((rng.normal() * 8, -np.degrees(a), rng.normal() * 8)),
                   round=0.14), k=0.06, color=rng.choice([TP["stone"], TP["stone_dk"], TP["stone_lt"]]))
    pl.paint(patches(1.5, 0.2, 3), "#c39046", feather=0.03)        # lichen
    pl.paint(patches(2.5, 0.3, 4), TP["moss"], feather=0.02)
    # tower: stacked bands so the red/white boundaries stay crisp, each a touch off-axis
    nb = 6
    for i in range(nb):
        ya = t0 + (t1 - t0) * i / nb
        yb = t0 + (t1 - t0) * (i + 1) / nb
        ra = r0 + (r1 - r0) * i / nb
        rb = r0 + (r1 - r0) * (i + 1) / nb
        col = TP["red"] if i % 2 == 0 else "#e6dfcd"
        off = lean * (ya - t0) + np.array([rng.normal() * 0.012, 0, rng.normal() * 0.012])
        grow = 0.014 * (i % 2)   # white bands pressed on over the red, a lip at each edge
        p = m.piece(color=col, merge="tower", res=0.028, lumps=0.014, lump_freq=1.8, dents=16, dent_size=0.22, dent_depth=0.014, detail=1.3)
        p.add(Moved(frustum((0, 0, 0), ra + grow, rb + grow, yb - ya + (0.05 if i % 2 else 0.0)),
                    off + np.array([0, ya - (0.025 if i % 2 else 0.0), 0]), euler((rng.normal() * 0.9, rng.uniform(0, 360), rng.normal() * 0.9))))
        p.paint(patches(1.2, 0.25, 10 + i), mix(col, TP["stone"], 0.35), feather=0.02)
        p.paint(below(ya + 0.25, 0.08, 4), mix(col, TP["wood_wet"], 0.3), feather=0.05)
    axis_top = lean * (t1 - t0) + np.array([0, t1, 0])
    # door at the base (+Z) in a stone surround with a step
    dz = r0 - 0.06
    door(m, MG, (0, base_h, dz + 0.05), (0, 0, 1), 0.82, 1.85, paint=TP["teal_dk"], peel=0.25, trim=TP["stone_lt"])
    m.socket("door", None, (0, base_h + 1.0, dz + 0.2))
    sp = m.piece(color=TP["stone_lt"], merge="stone", res=0.02, lumps=0.005, detail=0.8)
    sp.add(Box((0, base_h - 0.12, dz + 0.55), (0.7, 0.13, 0.32), round=0.05))
    sp.add(Box((0, base_h * 0.45, dz + 0.95), (0.6, base_h * 0.45 + 0.02, 0.22), round=0.05), k=0.02)
    # small windows spiralling up
    wins = []
    for k, (y, ang) in enumerate(((3.1, 160), (5.3, 20), (6.9, 200))):
        a = math.radians(ang)
        r = r0 + (r1 - r0) * (y - t0) / (t1 - t0) + 0.02
        c = lean * (y - t0) + np.array([math.sin(a) * r, y, math.cos(a) * r])
        out = np.array([math.sin(a), 0, math.cos(a)])
        wins.append(window(m, MG, c, out, 0.38, 0.55, frame_color=TP["cream"], panes=(1, 2), sill=True))
    for i, w in enumerate(wins):
        m.socket(f"win_{i}", None, w)
    # gallery: corbelled ring deck + iron railing
    gy = t1 + 0.12
    g = m.piece(color="#d9d2c0", merge="tower", res=0.025, lumps=0.004, dents=6, detail=1.0)
    g.add(Cylinder(axis_top + np.array([0, 0.06, 0]), r1 + 0.7, 0.1, round=0.05))
    for i in range(14):
        a = 2 * np.pi * i / 14
        d = np.array([np.cos(a), 0, np.sin(a)])
        g.add(Box(axis_top + d * (r1 + 0.18) + np.array([0, -0.2, 0]), (0.2, 0.2, 0.1), euler((0, -np.degrees(a), 0)), round=0.06), k=0.03)
    ir = m.piece(color=TP["iron"], gloss=90, merge="metal", res=0.012, lumps=0.002, detail=0.9)
    rg = r1 + 0.6
    for i in range(18):
        a = 2 * np.pi * i / 18
        d = np.array([np.cos(a), 0, np.sin(a)])
        ir.add(Capsule(axis_top + d * rg + np.array([0, 0.15, 0]), axis_top + d * rg + np.array([0, 1.0, 0]), 0.025))
    for y in (0.55, 1.0):
        ir.add(Torus(axis_top + np.array([0, y, 0]), rg, 0.028), k=0.01)
    ir.paint(patches(3, 0.2, 9), TP["rust"], feather=0.02)
    # lamp room: low parapet, glazing (emissive), mullions, red domed cap with vent ball
    lr = 1.05
    ly0 = gy + 0.12
    pp = m.piece(color="#e6dfcd", merge="tower", res=0.025, lumps=0.004, detail=0.8)
    pp.add(Cylinder(axis_top + np.array([0, 0.45, 0]), lr + 0.06, 0.32, round=0.05))
    gl = m.piece(color="#d8bd84", gloss=240, mat=1, merge="lamp_glass", res=0.02, lumps=0.001, mottle=0.03, ao=False, detail=0.6)
    gl.add(Cylinder(axis_top + np.array([0, 1.38, 0]), lr - 0.04, 0.62, round=0.02))
    lamp_c = axis_top + np.array([0, 1.38, 0])
    mu = m.piece(color=TP["iron"], gloss=90, merge="metal", res=0.012, lumps=0.0015, detail=0.8)
    for i in range(8):
        a = 2 * np.pi * (i + 0.5) / 8
        d = np.array([np.cos(a), 0, np.sin(a)])
        mu.add(Box(axis_top + d * lr + np.array([0, 1.38, 0]), (0.04, 0.66, 0.04), euler((0, -np.degrees(a), 0)), round=0.015))
    mu.add(Torus(axis_top + np.array([0, 0.78, 0]), lr, 0.04), k=0.01)
    mu.add(Torus(axis_top + np.array([0, 2.0, 0]), lr, 0.045), k=0.01)
    for y in (1.18, 1.58):
        mu.add(Torus(axis_top + np.array([0, y, 0]), lr - 0.01, 0.022), k=0.005)
    for i in range(8):
        a0 = 2 * np.pi * (i + 0.5) / 8
        pts = [axis_top + np.array([np.cos(a0 + f * 0.785) * (lr - 0.01), 0.8 + f * 1.18, np.sin(a0 + f * 0.785) * (lr - 0.01)]) for f in (0, 0.33, 0.66, 1.0)]
        mu.add(Tube(pts, 0.016, samples=3), k=0.004)
    cap = m.piece(color=TP["red_dk"], gloss=80, merge="roof", res=0.02, lumps=0.004, dents=5, detail=1.0)
    cap.add(Cylinder(axis_top + np.array([0, 2.07, 0]), lr + 0.22, 0.05, round=0.03))
    cap.add(Ellipsoid(axis_top + np.array([0, 2.1, 0]), (lr + 0.1, 0.75, lr + 0.1)), k=0.05)
    cap.inter(HalfSpace(axis_top + np.array([0, 2.02, 0]), (0, -1, 0)), k=0.0)
    cap.add(Cylinder(axis_top + np.array([0, 2.95, 0]), 0.1, 0.12, round=0.03), k=0.04, color=TP["iron"])
    cap.add(Sphere(axis_top + np.array([0, 3.2, 0]), 0.2), k=0.03, color=TP["iron"])
    cap.add(Capsule(axis_top + np.array([0, 3.3, 0]), axis_top + np.array([0, 3.9, 0]), 0.018), k=0.01, color=TP["iron"])
    cap.paint(patches(2, 0.2, 21), TP["rust"], feather=0.02)
    m.socket("lamp", None, lamp_c)
    # little stone-and-board oil store against the back (-Z)
    n0 = len(m.pieces)
    ox, oz = 0.0, -r0 - 0.9
    def ry(z):
        return 1.62 + 0.43 * (z + 1.05) / 1.8 - 0.04
    ow = [TP["wood"], TP["wood_dk"], TP["wood_silver"]]
    vboard_wall(m, "walls", (-0.95, 0.75), (-0.95, -0.75), 0.0, lambda s: ry(0.75 - s), (-1, 0, 0), ow, paint="#e6dfcd", peel=0.45)
    vboard_wall(m, "walls", (0.95, -0.75), (0.95, 0.75), 0.0, lambda s: ry(-0.75 + s), (1, 0, 0), ow, paint="#e6dfcd", peel=0.45)
    vboard_wall(m, "walls", (-0.95, -0.75), (0.95, -0.75), 0.0, ry(-0.75), (0, 0, -1), ow, paint="#e6dfcd", peel=0.45, openings=[(0.55, 1.35, -1, 1.58)])
    tin_roof(m, "roof", (-1.2, 1.62, -1.05), (1.2, 1.62, -1.05), (-1.2, 2.05, 0.75), (1.2, 2.05, 0.75), rust=0.5, sag=0.03, patch=0.2)
    door(m, MG, (0.0, 0.0, -0.75 - 0.02), (0, 0, -1), 0.75, 1.55, paint=TP["red"], peel=0.4, knob=False)
    move_since(m, n0, (ox, base_h - 0.05, oz))
    KP.barrel(m, T((1.35, base_h - 0.1, oz + 0.2), 30), merge="props", h=0.75, r=0.24)
    KP.barrel(m, T((1.25, base_h - 0.1, oz + 0.8), 0), merge="props", h=0.75, r=0.24)
    lt = KP.hanging_lantern(m, T((0.55, base_h + 2.05, dz + 0.42)), merge="metal", glass="glass", drop=0.08)
    br = m.piece(color=TP["iron"], gloss=80, merge="metal", res=0.008, detail=0.3)
    br.add(Tube([(0.55, base_h + 2.1, dz + 0.02), (0.55, base_h + 2.13, dz + 0.25), (0.55, base_h + 2.07, dz + 0.42)], 0.014, samples=4))
    m.socket("light_0", None, lt)
    KP.life_ring(m, T((-0.95, base_h + 1.5, dz - 0.13), 0), merge="props")
    return m


MODELS["town/lighthouse"] = calmed(lighthouse, jitter=0.8)


# ----------------------------------------------------------------------------------------------------------------
# crane


def crane():
    m = TownModel("crane", budget=24000)
    rng = m.rng
    pivot = np.array([0.0, 1.5, 0.0])
    m.bone("root")
    m.bone("boom", "root", tuple(pivot))
    mast_h = 5.0
    # base: crossed sleepers + iron turntable plate, raking braces to the mast
    for yaw in (45, -45):
        t = T((0, 0, 0), yaw)
        board(m, "frame", t.p(-1.25, 0.09, 0), t.p(1.25, 0.09, 0), 0.24, 0.18, t.v((0, 1, 0)), TP["wood_dk"], nails=2, detail=0.8)
    tp = m.piece(color=TP["iron"], gloss=80, merge="metal", res=0.012, lumps=0.002, detail=0.6)
    tp.add(Cylinder((0, 0.22, 0), 0.42, 0.04, round=0.015))
    for i in range(8):
        a = 2 * np.pi * i / 8
        tp.add(Sphere((np.cos(a) * 0.36, 0.26, np.sin(a) * 0.36), 0.025), k=0.005)
    tp.paint(patches(3, 0.1, 5), TP["rust"], feather=0.02)
    post(m, "frame", (0.0, 0.2, 0.0), (0.02, mast_h, -0.02), 0.13, TP["wood"], detail=1.2)
    for yaw in (45, 135, 225, 315):
        t = T((0, 0, 0), yaw)
        post(m, "frame", t.p(1.12, 0.18, 0), t.p(0.13, 1.22, 0), 0.07, TP["wood_dk"], detail=0.5)
    # mast head: iron band + sheave block
    mh = m.piece(color=TP["iron"], gloss=80, merge="metal", res=0.01, lumps=0.002, detail=0.6)
    for y in (mast_h - 0.15, 2.9, 1.27):
        mh.add(Box((0.01, y, -0.01), (0.15, 0.05, 0.15), round=0.02), k=0.005)
    mh.add(Cylinder((0.0, mast_h + 0.05, 0.0), 0.09, 0.08, round=0.02), k=0.01)
    mh.add(Torus((0.0, mast_h + 0.18, 0.0), 0.07, 0.02, euler((0, 0, 90))), k=0.005)
    # hand winch on the mast's back: two cheeks, rope drum, gear wheel, cranks
    wc = np.array([0.0, 1.05, -0.45])
    for sx in (-1, 1):
        board(m, "frame", (sx * 0.32, 0.2, -0.75), (sx * 0.32, 1.3, -0.25), 0.18, 0.06, (sx, 0, 0), TP["wood_br"], nails=2, detail=0.6)
    wd = m.piece(color=TP["wood_br"], merge="frame", res=0.01, lumps=0.003, detail=0.8)
    wd.add(Cylinder(wc, 0.13, 0.27, euler((0, 0, 90)), round=0.02))
    wd.add(Cylinder(wc + np.array([0.2, 0, 0]), 0.2, 0.025, euler((0, 0, 90)), round=0.01), k=0.005, color=TP["iron"])
    for k in range(5):
        wd.add(Torus(wc + np.array([-0.18 + k * 0.08, 0, 0]), 0.14, 0.022, euler((0, 0, 90))), k=0.004, color=TP["rope"])
    gw = m.piece(color=TP["iron"], gloss=70, merge="metal", res=0.008, lumps=0.002, detail=0.8)
    gw.add(Cylinder(wc + np.array([-0.4, 0, 0]), 0.3, 0.03, euler((0, 0, 90)), round=0.01))
    for i in range(16):
        a = 2 * np.pi * i / 16
        gw.add(Box(wc + np.array([-0.4, np.cos(a) * 0.31, np.sin(a) * 0.31]), (0.03, 0.03, 0.03), euler((np.degrees(a), 0, 0)), round=0.008), k=0.004)
    gw.sub(Cylinder(wc + np.array([-0.4, 0, 0]), 0.2, 0.06, euler((0, 0, 90))), k=0.01)
    gw.add(Capsule(wc + np.array([-0.45, 0, 0]), wc + np.array([0.45, 0, 0]), 0.025), k=0.004)
    for sx in (-1, 1):
        e = wc + np.array([sx * 0.45, 0, 0])
        gw.add(Capsule(e, e + np.array([0, -0.32, 0.12 * sx]), 0.02), k=0.004)
        gw.add(Capsule(e + np.array([0, -0.32, 0.12 * sx]), e + np.array([sx * 0.16, -0.32, 0.12 * sx]), 0.025), k=0.004, color=TP["wood_dk"])
    gw.paint(patches(4, 0.1, 7), TP["rust"], feather=0.01)
    # counterweight box of stones behind
    KP.crate(m, T((0.0, 0.18, -1.0), 0), merge="frame", size=(0.75, 0.5, 0.5))
    stn = m.piece(color=TP["stone"], merge="frame", res=0.015, lumps=0.006, detail=0.6)
    for k in range(6):
        stn.add(Sphere((rng.uniform(-0.25, 0.25), 0.72 + rng.uniform(0, 0.08), -1.0 + rng.uniform(-0.15, 0.15)), rng.uniform(0.09, 0.13)), k=0.02,
                color=rng.choice([TP["stone"], TP["stone_dk"], TP["stone_lt"]]))
    KP.rope_coil(m, T((0.85, 0.18, -0.55), 30), merge="frame")
    # ---------------- the boom (rigid to bone `boom`, pivot at the gooseneck on the mast)
    nb0 = len(m.pieces)
    L = 6.8
    rise = math.radians(24)
    d = np.array([0, math.sin(rise), math.cos(rise)])
    heel = pivot + np.array([0, 0, 0.2])
    tip = heel + d * L
    side = np.array([1.0, 0, 0])
    up = np.cross(d, side)
    # two timber spars converging to the tip + spreader blocks
    for sx in (-1, 1):
        board(m, "boom", heel + side * sx * 0.16, tip + side * sx * 0.05, 0.16, 0.12, side, TP["wood"], paint="#93503f", peel=0.35, nails=2,
              detail=1.0, bow=0.02)
    for f in (0.2, 0.45, 0.7):
        c = heel + d * L * f
        w = 0.16 * (1 - f) + 0.05 * f
        board(m, "boom", c - side * (w + 0.06), c + side * (w + 0.06), 0.09, 0.07, up, TP["wood_dk"], nails=1, detail=0.4)
    bm = m.piece(color=TP["iron"], gloss=80, merge="boom", res=0.01, lumps=0.002, detail=0.7)
    bm.add(Cylinder(heel, 0.08, 0.26, euler((0, 0, 90)), round=0.02))                 # gooseneck pin
    bm.add(Torus(heel + np.array([0, 0, -0.2]), 0.16, 0.035), k=0.01)                     # collar round the mast
    bm.add(Box(tip, (0.1, 0.1, 0.12), frame(d, up) @ euler((0, 0, 0)), round=0.03), k=0.01)  # tip cheek block
    bm.add(Cylinder(tip + up * -0.05, 0.12, 0.04, euler((0, 0, 90)), round=0.015), k=0.005, color=TP["wood_br"])
    bm.paint(patches(3, 0.15, 13), TP["rust"], feather=0.01)
    # topping lift from the mast head (on the pivot axis) to the tip; hoist rope down to the hook
    top = np.array([0.0, mast_h + 0.12, 0.0])
    rope(m, "boom", [top, (top + tip) / 2 + np.array([0, -0.12, 0]), tip + up * 0.05], 0.02)
    rope(m, "boom", [heel + up * 0.12, heel + d * L * 0.5 + up * 0.13, tip + up * 0.08], 0.016)
    hook_top = tip + np.array([0, -0.08, 0])
    hook = tip + np.array([0, -2.0, 0])
    rope(m, "boom", [hook_top, hook + np.array([0, 0.28, 0])], 0.02)
    hk = m.piece(color=TP["iron"], gloss=90, merge="boom", res=0.008, lumps=0.002, detail=0.8)
    blk = hook + np.array([0, 0.18, 0])
    hk.add(Box(blk, (0.07, 0.12, 0.05), round=0.03))
    hk.add(Cylinder(blk, 0.07, 0.055, euler((0, 0, 90)), round=0.02), k=0.01, color=TP["wood_br"])
    hk.add(Capsule(blk + np.array([0, -0.1, 0]), hook + np.array([0, -0.04, 0]), 0.022), k=0.01)
    hk.add(Tube([hook + np.array([0, -0.04, 0]), hook + np.array([0, -0.18, 0.02]), hook + np.array([0, -0.22, 0.12]), hook + np.array([0, -0.12, 0.18]),
                 hook + np.array([0, -0.06, 0.15])], 0.03, samples=4), k=0.01)
    hk.paint(patches(4, 0.1, 17), TP["rust"], feather=0.01)
    for p in m.pieces[nb0:]:
        p.rigid = "boom"
    m.socket("hook", "boom", hook + np.array([0, -0.12, 0.08]))
    m.socket("boom_tip", "boom", tip)
    return m


MODELS["town/crane"] = calmed(crane, jitter=0.8)
