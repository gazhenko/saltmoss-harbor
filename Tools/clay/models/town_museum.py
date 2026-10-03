"""
The Tidewrack Museum — a giant clinker-built boat hull turned upside down on stone blocks on the west beach, cut away
on its long +Z side like a dollhouse so the inside is open and walkable. Inside: aquarium tanks (sockets tank_0..15,
fish shown side-on), curio cabinets, plinths and table vitrines (sockets slot_0..19 for treasures, bottom-centre),
Professor Inkwell's lectern (socket `lectern`, stand at `inkwell`), hanging lanterns, a drying net with floats.

Local frame: hull along X (stern x = -6.8, bow x = +7.2), open side +Z; floor y = 0.65 inside; origin on the sand
under the middle of the hull; front steps at z 3.3..4.35. Placed at (-32, ~1.09, 7.5) yaw 155.
"""
import math

import numpy as np
from kit_town import *
import kit_props as KP

MODELS = {}
FLOOR = 0.65
T_SHELL = 0.1
NPOW = 2.4
OPEN = dict(c=(-0.6, 1.65, 2.6), h=(5.35, 1.72, 1.7))   # the dollhouse cut (rounded box removed from the +Z side)


def y0(x):
    return 0.55 + 0.62 * (np.asarray(x) / 7.0) ** 2


def keel(x):
    return 4.2 + 0.35 * (np.asarray(x) / 7.0) ** 2


def beam(x):
    u = np.asarray(x) / 7.2
    bow = 3.0 * np.clip(1 - np.clip(u, 0, None) ** 2, 0, 1) ** 0.48
    stern = 3.0 * (1 - 0.52 * np.clip(-u, 0, None) ** 2)
    return np.where(u >= 0, bow, stern)


def hull_outer(P):
    """Approximate signed distance to the outer hull surface (superellipse cross-section), and the girth angle."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    b = np.maximum(beam(x), 0.02)
    yb = y0(x)
    H = keel(x) - yb
    zz = np.abs(z) / b
    yy = np.maximum(y - yb, 0) / H
    n = NPOW - 0.7 * np.clip(x / 7.0, 0, 1) ** 2    # sharper V toward the bow
    r = (zz ** n + yy ** n) ** (1 / n) + 1e-9
    dz = r ** (1 - n) * zz ** (n - 1) / b
    dy = r ** (1 - n) * yy ** (n - 1) / H
    g = np.sqrt(dz * dz + dy * dy) + 1e-6
    d = (r - 1) / g
    # below the sheer the section continues straight down (so the cut is clean)
    phi = np.arctan2(yy, np.sign(z + 1e-9) * zz)
    return d, phi


def strake_index(phi):
    return np.floor(phi / (math.pi / 23)).astype(int)


def hull_sdf(P, lap=0.034, seam=0.016):
    d, phi = hull_outer(P)
    q = phi / (math.pi / 23)
    f = q - np.floor(q)
    # clinker: each strake laps over the one below it (thicker toward its lower edge = toward the gunwale)
    side = np.where(phi < math.pi / 2, 1.0, -1.0)
    ff = np.where(side > 0, 1 - f, f)
    d = d - lap * ff
    g = np.minimum(f, 1 - f) * (math.pi / 23) * 3.0
    d = d + seam * np.exp(-(g / 0.045) ** 2)
    sh = np.abs(d + T_SHELL / 2) - T_SHELL / 2
    sh = np.maximum(sh, y0(P[:, 0]) - P[:, 1])
    sh = np.maximum(sh, -6.8 - P[:, 0])
    return sh


def open_box():
    return Box(OPEN["c"], OPEN["h"], round=0.25)


def museum():
    m = TownModel("museum_hull", budget=58000)
    rng = m.rng
    lights = []

    # ---------------- the hull shell (two halves along X so the grids stay small)
    hull_cols = dict(bottom="#8b4b3c", boot=TP["cream"], top=TP["teal"], wood=TP["wood"])
    for (xa, xb) in ((-7.0, 0.3), (0.2, 7.4)):
        def f(P, xa=xa, xb=xb):
            d = hull_sdf(P)
            return np.maximum(d, np.maximum(xa - P[:, 0], P[:, 0] - xb))
        p = m.piece(color=hull_cols["top"], gloss=45, merge="hull", res=0.026, lumps=0.006, lump_freq=3, dents=10, dent_size=0.12,
                    dent_depth=0.012, mottle=0.1, detail=3.0)
        p.add(Func(f, (xa - 0.05, 0.3, -3.3), (xb + 0.05, 4.8, 3.3)))
        p.sub(open_box(), k=0.06, color=TP["wood_lt"])
        # paint: upturned — red antifouling over the top, a cream boot-top stripe, faded teal topsides near the ground

        def band_phi(lo, hi):
            def g(P):
                d, phi = hull_outer(P)
                a = np.minimum(phi, math.pi - phi)
                return np.maximum(lo - a, a - hi) * 2.0
            return Func(g, (-99,) * 3, (99,) * 3)
        p.paint(band_phi(0.62, 2.0), hull_cols["bottom"], feather=0.01)
        p.paint(band_phi(0.5, 0.62), hull_cols["boot"], feather=0.01)
        # per-strake shade variety + a couple of replaced planks in raw wood

        def strakes(sel):
            def g(P):
                d, phi = hull_outer(P)
                k = strake_index(phi)
                return np.where(sel(k), -1.0, 1.0)
            return Func(g, (-99,) * 3, (99,) * 3)
        p.paint(strakes(lambda k: (k * 7919 % 5) == 0), shade(hull_cols["top"], 0.85), feather=0.01)
        p.paint(strakes(lambda k: (k * 7919 % 7) == 3), shade(hull_cols["bottom"], 1.12), feather=0.01)
        # weathering: big peeled patches to grey wood, salt bloom near the ground
        p.paint(strakes(lambda k: (k * 7919 % 9) == 4), TP["wood"], feather=0.01)
        p.paint(patches(0.8, 0.3, m.peel_seed, stretch=(0.35, 1.0, 1.0)), TP["wood"], feather=0.02)
        p.paint(below(1.0, 0.15, 1.5), mix(TP["teal"], TP["wood_silver"], 0.4), feather=0.15)
        p.paint(band(0.45, 0.85, 0.1, 2), TP["algae"], feather=0.1)
    # stem post at the bow and the keel strip along the top
    keel_pts = [(x, keel(x) + 0.03, 0.0) for x in np.linspace(-6.85, 6.9, 9)]
    keel_pts += [(7.15, 3.4, 0.0), (7.3, 2.2, 0.0), (7.2, 0.9, 0.0)]
    kp = m.piece(color=TP["wood_dk"], gloss=40, merge="hull", res=0.02, lumps=0.004, detail=0.8)
    kp.add(Tube(keel_pts, 0.12, samples=3))
    kp.paint(patches(1.2, 0.1, 5), TP["wood_tar"], feather=0.02)
    # transom: vertical planks closing the stern
    zs = np.arange(-1.9, 1.95, 0.24)
    for zc in zs:
        b = float(beam(-6.85))
        top = y0(-6.85) + (keel(-6.85) - y0(-6.85)) * max(0.0, 1 - (abs(zc) / b) ** NPOW) ** (1 / NPOW) - 0.06
        board(m, "hull", (-6.82, y0(-6.85) - 0.05, zc), (-6.82, top, zc), 0.23, 0.07, (-1, 0, 0), TP["wood"], paint=hull_cols["bottom"] if top > 2 else hull_cols["top"],
              peel=0.35, nails=1, detail=0.8)
    # big painted name plank under the cut edge (sign) — blank board, Unity writes the name
    sign_c = np.array([-0.6, 3.52, 2.18])
    board(m, "trim", sign_c + (-2.2, 0, 0), sign_c + (2.2, 0, 0), 0.5, 0.06, (0, 0.35, 1), TP["cream"], nails=2, detail=1.0, knot=0, grooves=[])
    for dy in (-0.27, 0.27):
        board(m, "trim", sign_c + (-2.3, dy, 0.03), sign_c + (2.3, dy, 0.03), 0.08, 0.04, (0, 0.35, 1), TP["wood"], paint=TP["red_dk"], peel=0.3, nails=1, detail=0.5)
    m.socket("sign_text", None, sign_c + (0, 0, 0.05), (-20, 0, 0))

    # ---------------- ribs inside + posts holding the cut edge
    def rib(xi):
        def f(P):
            d, phi = hull_outer(P)
            r = np.maximum(np.abs(P[:, 0] - xi) - 0.055, np.abs(d + T_SHELL + 0.06) - 0.065)
            r = np.maximum(r, y0(P[:, 0]) + 0.05 - P[:, 1])
            return r
        return f
    for xi in np.arange(-6.2, 6.4, 0.78):
        b = float(beam(xi))
        if b < 0.6:
            continue
        p = m.piece(color=TP["wood_br"], gloss=35, merge="frame", res=0.024, lumps=0.004, detail=0.7)
        p.add(Func(rib(xi), (xi - 0.12, 0.4, -b - 0.1), (xi + 0.12, keel(xi) + 0.1, b + 0.1)))
        p.sub(open_box(), k=0.04)
    edge_y = OPEN["c"][1] + OPEN["h"][1]
    for xi in np.arange(-5.6, 4.6, 1.56):
        zc = 2.15
        post(m, "frame", (xi, FLOOR, zc), (xi + rng.normal() * 0.03, edge_y + 0.1, zc - 0.02), 0.075, TP["wood_br"], detail=0.6)
    # beam along the cut edge
    post(m, "frame", (-5.95, edge_y + 0.05, 2.18), (4.75, edge_y + 0.05, 2.18), 0.09, TP["wood_dk"], detail=0.7)
    # keelson inside
    kp2 = m.piece(color=TP["wood_dk"], gloss=30, merge="frame", res=0.02, detail=0.5)
    kp2.add(Tube([(x, keel(x) - T_SHELL - 0.16, 0.0) for x in np.linspace(-6.4, 5.8, 6)], 0.09, samples=3))

    # ---------------- stone blocks, joists, floor, steps
    for x in np.arange(-6.3, 6.6, 1.55):
        for sz in (-1, 1):
            b = float(beam(x))
            if b < 0.8:
                continue
            c = np.array([x + rng.normal() * 0.1, 0.27, sz * (b - 0.12)])
            if sz > 0 and -6.0 < x < 4.8:
                c[2] = 3.05
            p = m.piece(color=rng.choice([TP["stone"], TP["stone_dk"], TP["stone_lt"]]), merge="stones", res=0.025, lumps=0.03, lump_freq=3.5, dents=6,
                        dent_size=0.09, dent_depth=0.02, detail=1.0)
            hy = (float(y0(x)) + 0.05) / 2
            p.add(Box(c + (0, hy - 0.27, 0), (0.42, hy, 0.34), (rng.normal() * 3, rng.uniform(-20, 20), rng.normal() * 3), round=0.14))
            p.add(Box(c + (rng.normal() * 0.1, 2 * hy - 0.27 - 0.05, rng.normal() * 0.05), (0.3, 0.1, 0.26), (rng.normal() * 6, rng.uniform(0, 90), rng.normal() * 6),
                      round=0.08), k=0.04)
            p.paint(patches(2, 0.15, int(rng.integers(999))), TP["moss"], feather=0.02)
            p.paint(below(0.15, 0.05, 3), TP["sand"], feather=0.06)
    for x in np.arange(-6.3, 5.9, 1.1):
        b = float(beam(x))
        post(m, "floor", (x, FLOOR - 0.17, -b + 0.2), (x, FLOOR - 0.17, 3.25), 0.07, TP["wood_dk"], detail=0.3)
    x = -6.55
    while x < 5.9:
        w = rng.uniform(0.2, 0.27)
        b = float(beam(x + w / 2))
        z0 = -(b - 0.22)
        col = rng.choice([TP["wood"], TP["wood_lt"], TP["wood_br"], TP["wood_dk"]])
        board(m, "floor", (x + w / 2, FLOOR - 0.035, z0), (x + w / 2, FLOOR - 0.035, 3.3 + rng.uniform(-0.03, 0.05)), w - 0.008, 0.07, (0, 1, 0), col,
              nails=1, detail=0.9, bow=rng.uniform(0, 0.006), twist=rng.normal() * 0.4, rot_jit=0.3)
        x += w
    for i in range(3):
        top = FLOOR - (i + 1) * FLOOR / 3 + FLOOR / 3
        zc = 3.3 + 0.36 * i + 0.18
        st = m.piece(color=rng.choice([TP["stone"], TP["stone_lt"]]), merge="stones", res=0.02, lumps=0.012, lump_freq=6, dents=4, dent_size=0.06,
                     dent_depth=0.01, detail=0.8)
        st.add(Box((-0.6, top / 2 - 0.02, zc - 0.02), (1.25 - i * 0.05, top / 2 + 0.02, 0.2), (0, rng.normal() * 2, 0), round=0.05))
        st.paint(patches(2.5, 0.25, 40 + i), TP["moss"], feather=0.02)
    # rope rail along the open front edge (gap at the steps)
    for (xa, xb) in ((-5.9, -2.0), (0.8, 4.7)):
        xs = np.linspace(xa, xb, 4)
        for xp in xs:
            post(m, "floor", (xp, FLOOR - 0.1, 3.2), (xp, FLOOR + 0.75, 3.2), 0.05, TP["wood_dk"], square=False, detail=0.4)
        for i in range(len(xs) - 1):
            rope(m, "floor", [(xs[i], FLOOR + 0.7, 3.2), ((xs[i] + xs[i + 1]) / 2, FLOOR + 0.5, 3.22), (xs[i + 1], FLOOR + 0.7, 3.2)], 0.025, detail=0.4)
    m.socket("door", None, (-0.6, 0.0, 4.7), (0, 0, 0))

    # ---------------- exhibits
    slot = [0]
    tank = [0]

    def add_slot(pos, yaw=0.0):
        m.socket(f"slot_{slot[0]}", None, pos, (0, yaw, 0))
        slot[0] += 1

    def add_tank(c, facing_yaw, w=1.05, h=0.62, d=0.5):
        """Aquarium diorama: wooden frame, painted water back panel with kelp, sand floor; fish socket in the middle."""
        t = T(c, facing_yaw)
        fr = m.piece(color=TP["wood_br"], gloss=60, merge="exhibits", res=0.012, lumps=0.002, detail=0.8)
        fr.add(Box(t.p(0, -0.06, 0), (w / 2 + 0.05, 0.06, d / 2 + 0.03), t.r(), round=0.015))
        fr.add(Box(t.p(0, h + 0.04, 0), (w / 2 + 0.05, 0.04, d / 2 + 0.03), t.r(), round=0.015), k=0.005)
        for sx in (-1, 1):
            for sz in (-1, 1):
                fr.add(Box(t.p(sx * w / 2, h / 2, sz * d / 2), (0.03, h / 2 + 0.04, 0.03), t.r(), round=0.01), k=0.004, color=TP["brass"], gloss=150)
        wa = m.piece(color="#3f6f78", gloss=200, merge="exhibits", res=0.012, lumps=0.003, detail=0.7)
        wa.add(Box(t.p(0, h / 2, -d / 2 + 0.02), (w / 2, h / 2, 0.02), t.r(), round=0.01))
        wa.paint(Box(t.p(0, h * 0.85, -d / 2), (w, h * 0.2, 0.2), t.r()), "#6c9aa0", feather=0.06)
        sand = m.piece(color=TP["sand"], gloss=40, merge="exhibits", res=0.012, lumps=0.012, lump_freq=12, detail=0.5)
        sand.add(Box(t.p(0, 0.03, 0), (w / 2, 0.035, d / 2), t.r(), round=0.02))
        for k in range(3):
            x0 = rng.uniform(-w / 2 + 0.1, w / 2 - 0.1)
            kelp = m.piece(color=rng.choice([TP["algae"], TP["algae_lt"], "#7c7a3c"]), gloss=120, merge="exhibits", res=0.008, lumps=0.003, detail=0.35)
            kelp.add(Tube([t.p(x0, 0.03, -d / 2 + 0.08), t.p(x0 + 0.05, h * 0.4, -d / 2 + 0.09), t.p(x0 - 0.03, h * rng.uniform(0.6, 0.9), -d / 2 + 0.1)],
                          [0.025, 0.02, 0.012], samples=4))
        sc = t.p(0, h * 0.5, 0.02)
        m.socket(f"tank_{tank[0]}", None, sc, (0, facing_yaw + 90, 0))
        tank[0] += 1

    # aquarium wall along the back (two rows of four)
    for row in range(2):
        for i in range(4):
            x = -5.3 + i * 1.18
            y = FLOOR + 0.62 + row * 0.82
            add_tank((x, y, -2.05), 0)
        # stand under the tanks
    for x in (-5.9, -4.1, -2.3, -0.75):
        post(m, "exhibits", (x, FLOOR, -2.0), (x, FLOOR + 0.56, -2.0), 0.05, TP["wood_dk"], detail=0.3)
    board(m, "exhibits", (-5.95, FLOOR + 0.52, -2.0), (-0.65, FLOOR + 0.52, -2.0), 0.55, 0.05, (0, 1, 0), TP["wood_br"], nails=1, detail=0.5)
    # tanks across the stern (facing +X, two rows of four)
    for row in range(2):
        for i in range(4):
            z = -1.4 + i * 0.98
            y = FLOOR + 0.62 + row * 0.82
            add_tank((-6.35, y, z), 90, w=0.88, d=0.48)
    board(m, "exhibits", (-6.35, FLOOR + 0.52, -1.95), (-6.35, FLOOR + 0.52, 1.95), 0.55, 0.05, (0, 1, 0), TP["wood_br"], nails=1, detail=0.5)
    for z in (-1.8, 0.0, 1.8):
        post(m, "exhibits", (-6.35, FLOOR, z), (-6.35, FLOOR + 0.5, z), 0.05, TP["wood_dk"], detail=0.3)

    # curio cabinets on the back wall (bow half): 2 cabinets x 3 shelves x 2 slots
    for ci, x0 in enumerate((0.15, 2.35)):
        W, Hc, D = 2.0, 2.15, 0.5
        c = np.array([x0 + W / 2, FLOOR, -2.0])
        cab = m.piece(color=TP["wood_br"], gloss=70, merge="exhibits", res=0.014, lumps=0.003, detail=1.0)
        for sx in (-1, 1):
            cab.add(Box(c + (sx * W / 2, Hc / 2, 0), (0.04, Hc / 2, D / 2), round=0.012))
        cab.add(Box(c + (0, Hc, 0.02), (W / 2 + 0.08, 0.06, D / 2 + 0.05), round=0.02), k=0.005)
        cab.add(Box(c + (0, Hc / 2, -D / 2 + 0.02), (W / 2, Hc / 2, 0.02), round=0.01), k=0.003, color="#5e2f2a")
        cab.add(Box(c + (0, 0.08, 0), (W / 2, 0.08, D / 2), round=0.01), k=0.003)
        for j, ys in enumerate((0.75, 1.3, 1.82)):
            cab.add(Box(c + (0, ys - 0.02, 0), (W / 2, 0.022, D / 2 - 0.01), round=0.008), k=0.003)
            for k in (-0.5, 0.5):
                add_slot(c + (k * W * 0.5, ys, 0.02))
        cab.add(Box(c + (0, 0.4, D / 2), (W / 2 - 0.05, 0.25, 0.02), round=0.01), k=0.004)  # drawer front
        cab.paint(Box(c + (0, Hc + 0.02, 0.0), (W, 0.03, D)), TP["brass"], feather=0.01)
    # plinths in the bow: 4 big pieces
    for i, (x, z) in enumerate(((5.0, -1.2), (5.6, 0.3), (4.6, 1.5), (3.6, 0.0))):
        h = 0.62 if i != 1 else 0.45
        p = m.piece(color=TP["stone_lt"], gloss=60, merge="exhibits", res=0.014, lumps=0.005, detail=0.6)
        p.add(Box((x, FLOOR + h / 2, z), (0.27, h / 2, 0.27), round=0.03))
        p.add(Box((x, FLOOR + h + 0.03, z), (0.33, 0.04, 0.33), round=0.02), k=0.004, color=TP["stone"])
        p.add(Box((x, FLOOR + 0.04, z), (0.33, 0.05, 0.33), round=0.02), k=0.004, color=TP["stone"])
        add_slot((x, FLOOR + h + 0.07, z), -30 + i * 25)
    # two vitrine tables in the middle (red baize tops)
    for i, x in enumerate((-3.3, -1.3)):
        c = np.array([x, FLOOR, 0.35])
        tb = m.piece(color=TP["wood_br"], gloss=70, merge="exhibits", res=0.012, lumps=0.003, detail=0.8)
        tb.add(Box(c + (0, 0.78, 0), (0.62, 0.05, 0.38), round=0.02))
        tb.add(Box(c + (0, 0.835, 0), (0.56, 0.012, 0.32), round=0.006), k=0.002, color="#7c2f2c", gloss=20)
        for sx in (-1, 1):
            for sz in (-1, 1):
                tb.add(Capsule(c + (sx * 0.55, 0.0, sz * 0.3), c + (sx * 0.55, 0.76, sz * 0.3), 0.035, 0.03), k=0.01)
        for k in (-0.28, 0.28):
            add_slot(c + (k, 0.85, 0.0))
    # Professor Inkwell's lectern by the open front, facing the visitors (+Z)
    lc = np.array([1.6, FLOOR, 1.3])
    lt = m.piece(color=TP["wood_br"], gloss=80, merge="exhibits", res=0.01, lumps=0.003, detail=1.0)
    lt.add(Box(lc + (0, 0.05, 0), (0.3, 0.05, 0.25), round=0.02))
    lt.add(Capsule(lc + (0, 0.05, 0), lc + (0, 0.95, 0), 0.07, 0.06), k=0.02)
    lt.add(Box(lc + (0, 1.05, 0.0), (0.33, 0.04, 0.24), euler((-22, 0, 0)), round=0.02), k=0.02)
    lt.add(Box(lc + (0, 1.11, 0.02), (0.22, 0.02, 0.15), euler((-22, 0, 0)), round=0.01), k=0.003, color="#ece2c6", gloss=20)
    lt.add(Capsule(lc + (-0.05, 1.12, 0.03), lc + (-0.05, 1.09, 0.17), 0.006), k=0.002, color="#8a3b32")
    m.socket("lectern", None, lc + (0, 1.1, 0), (0, 180, 0))
    m.socket("inkwell", None, lc + (0, 0.0, -0.55), (0, 0, 0))

    # ---------------- hanging things: lanterns from the keelson, a drying net with floats, a big anchor + oars
    for i, x in enumerate((-3.6, 0.0, 3.4)):
        top = np.array([x, keel(x) - T_SHELL - 0.25, 0.4])
        chain(m, "deco", top + (0, 0.2, -0.4), top, link=0.04)
        lights.append(np.array(KP.hanging_lantern(m, T(top), merge="deco", glass="glass", drop=0.35, size=1.0)))
    net = m.piece(color=TP["net_green"], gloss=40, mat=4, merge="net", res=0.016, lumps=0.01, lump_freq=4, detail=0.6)

    def netf(P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        sag = 0.35 * np.sin(np.clip((x + 4.8) / 7.6, 0, 1) * np.pi) + 0.1 * np.sin(x * 2.1)
        surf = keel(x) - 0.45 - sag - 0.25 * (z / 1.6) ** 2
        d = np.abs(y - surf) - 0.022
        return np.maximum(d, np.maximum(np.abs(x + 1.0) - 3.8, np.abs(z + 0.3) - 1.4))
    net.add(Func(netf, (-4.9, 2.9, -1.8), (2.9, 4.4, 1.2)))
    for k in range(7):
        x = -4.4 + k * 1.1
        sag = 0.35 * math.sin(np.clip((x + 4.8) / 7.6, 0, 1) * math.pi) + 0.1 * math.sin(x * 2.1)
        y = keel(x) - 0.45 - sag - 0.27
        KP.glass_float(m, T((x, y - 0.05, -0.3 + rng.normal() * 0.6)), merge="deco", r=0.1)
    # a great fish skeleton hanging from the keelson (the museum's showpiece)
    sk = m.piece(color="#e6dcc2", gloss=70, merge="deco", res=0.012, lumps=0.003, detail=2.0)
    spine = [np.array([x, 3.05 + 0.18 * math.sin(x * 0.9) - 0.04 * x, 0.55 + 0.25 * math.sin(x * 0.6)]) for x in np.linspace(-2.6, 2.4, 14)]
    for i, c in enumerate(spine):
        sk.add(Ellipsoid(c, (0.11, 0.1, 0.1)), k=0.03)
        if 2 <= i <= 11:
            L = 0.55 * math.sin(math.pi * (i - 1) / 11) + 0.15
            for sz in (-1, 1):
                sk.add(Tube([c, c + (0.05, -L * 0.4, sz * L * 0.55), c + (0.12, -L * 0.95, sz * L * 0.4)], [0.035, 0.03, 0.02], samples=3), k=0.02)
        if i % 2 == 0:
            sk.add(Capsule(c, c + (0.05, 0.28, 0), 0.025, 0.015), k=0.02)
    head = spine[-1] + np.array([0.35, -0.05, 0])
    sk.add(Ellipsoid(head, (0.42, 0.22, 0.2), euler((0, 0, -8))), k=0.06)
    sk.add(Ellipsoid(head + (0.45, -0.12, 0), (0.3, 0.06, 0.12), euler((0, 0, -18))), k=0.05)
    sk.sub(Sphere(head + (0.12, 0.06, 0.18), 0.07), k=0.02, color="#3a3430")
    sk.sub(Sphere(head + (0.12, 0.06, -0.18), 0.07), k=0.02, color="#3a3430")
    tail = spine[0] - np.array([0.25, 0, 0])
    sk.add(Ellipsoid(tail + (-0.2, 0.25, 0), (0.08, 0.35, 0.04), euler((0, 0, 35))), k=0.04)
    sk.add(Ellipsoid(tail + (-0.2, -0.25, 0), (0.08, 0.35, 0.04), euler((0, 0, -35))), k=0.04)
    for c in (spine[3], spine[10]):
        chain(m, "deco", c + (0, 0.1, 0), (c[0], keel(c[0]) - T_SHELL - 0.2, c[2]), link=0.035)
    KP.anchor(m, T((5.4, 0.0, 3.9), -40), merge="deco")
    for k in range(2):
        oar = m.piece(color=TP["wood_lt"], gloss=50, merge="deco", res=0.01, detail=0.3)
        a = np.array([-5.0 + k * 0.4, FLOOR + 0.05, -1.4 + k * 0.2])
        oar.add(Capsule(a + (5.6, 0.3 + k * 0.1, 0.4), a + (6.2, 2.2, 0.0), 0.03))
        oar.add(Ellipsoid(a + (6.3, 2.5, -0.03), (0.09, 0.3, 0.02), euler((0, 20, -15))), k=0.02)
    KP.barrel(m, T((4.9, 0.0, 3.9), 0), merge="deco")
    KP.crate(m, T((-4.8, 0.0, 3.8), 12), merge="deco")
    KP.lantern_post(m, T((1.05, 0.0, 4.5), 180), merge="deco", metal="deco", glass="glass")
    for i, l in enumerate(lights):
        m.socket(f"light_{i}", None, l)
    print(f"[museum] slots {slot[0]}, tanks {tank[0]}")
    return m


MODELS["town/museum_hull"] = museum
