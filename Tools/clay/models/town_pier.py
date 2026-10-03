"""
Pier / boardwalk kit for Saltmoss Harbor. Every piece: origin at the deck-top centre of its footprint (y = 0 = the
walkable surface where you enter it), length along Z. Placed at y = 1.8 the pilings reach the seabed (local y = -5)
and their tide band sits at local y = -1.8 (sea level).

  boardwalk (no rails) / boardwalk_rail1 (rail on +X) / boardwalk_rail2 (both): 4 m (z -2..2) x 2.4 m (x -1.2..1.2)
  boardwalk_corner: 2.4 x 2.4, rails on +X and +Z (enter from -Z or -X)
  boardwalk_t: 2.4 x 2.4, rail on +Z (enter from -Z, -X, +X)
  boardwalk_end: 2.4 x 2.4, rails on +X, +Z, -X (dead end, enter from -Z)
  boardwalk_ramp: rises 1 m over 4 m (y 0 at z=-2 -> y 1 at z=+2), rails both sides
  boardwalk_stairs: descends 1.8 m over 4 m (y 0 at z=-2 -> y -1.8 at z=+2), 9 steps of 0.2 m, rails both sides
  pier_head: 8 x 8 m platform (x,z -4..4), rails on +Z, +-X and on -Z either side of the 2.4 m pier opening
  pier_platform: 4 x 4 m side platform, rails on +Z and -X... (open on -Z and +X? no: open on -X), see code
  floating_dock: 10 m (z -5..5) x 2.4 m, top y = 0 (place at y = 0.5), floats with waterline at local -0.5
  gangway: origin at the TOP end centre, runs 3.4 m along +Z dropping 1.3 m (21 deg), 1.2 m wide, handrails
  piling: single piling, top at y = 0 down to -5, tide band at -1.8
  ladder: origin at the deck edge top, hangs down along -Y on the +Z side to y = -2.6
  bollard, cleat: pivot bottom-centre
  seawall: 4 m timber bulkhead along X, top at y = 0 (place at y ~ 1.75), face toward +Z, down to y = -4
"""
import numpy as np
from kit_town import *

MODELS = {}
SEA = -1.8           # local sea level when the deck is placed at y = 1.8
FLOOR = -5.0         # piling feet
WOODS = [TP["wood"], TP["wood_lt"], TP["wood_dk"], TP["wood_br"], TP["wood_silver"], TP["wood"]]


def _deck_cross(m, x0, x1, z0, z1, y0, y1=None, t=0.08, pw=(0.21, 0.29), merge="deck", detail=1.0, colors=None):
    """Planks running across X, tiled along Z from z0 to z1; deck top rises linearly y0 -> y1 along z."""
    rng = m.rng
    y1 = y0 if y1 is None else y1
    colors = colors or WOODS
    z = z0
    out = []
    while z < z1 - 0.03:
        w = rng.uniform(*pw)
        if z1 - (z + w) < pw[0] * 0.6:
            w = z1 - z
        zc = z + w / 2
        f = (zc - z0) / (z1 - z0)
        y = y0 + (y1 - y0) * f
        slope = np.array([0, y1 - y0, z1 - z0])
        slope /= np.linalg.norm(slope)
        up = np.cross(slope, [1, 0, 0])
        if up[1] < 0:
            up = -up
        col = colors[int(rng.integers(len(colors)))]
        if rng.random() < 0.09:
            col = rng.choice([TP["wood_new"], TP["wood_new2"]])
        e0, e1 = rng.uniform(-0.03, 0.07), rng.uniform(-0.03, 0.07)
        cy = y - t / 2 + rng.normal() * 0.003
        a = np.array([x0 - e0, cy, zc]) - up * 0
        b = np.array([x1 + e1, cy, zc])
        out.append(board(m, merge, a, b, w - rng.uniform(0.01, 0.022), t, up, col, nails=0, detail=detail, knot=0.15,
                         bow=rng.uniform(-0.004, 0.01), twist=rng.normal() * 0.8, dents=1))
        z += w
    return out


def _structure(m, x0, x1, z0, z1, ybot0, ybot1=None, bents=None, pil_x=None, merge="frame", piles="piles", brace=True, piling_top=None,
               detail=1.0, piling_r=0.21):
    """Stringers along Z under the deck, cap beams at the bents, pilings + one diagonal brace per bent."""
    rng = m.rng
    ybot1 = ybot0 if ybot1 is None else ybot1
    bents = bents if bents is not None else [z0 + 0.15]
    pil_x = pil_x if pil_x is not None else [x0 + 0.15, x1 - 0.15]
    xs = np.linspace(x0 + 0.3, x1 - 0.3, max(2, int(round((x1 - x0) / 1.1)) + 1))
    for x in xs:
        post(m, merge, (x, ybot0 - 0.11, z0 + 0.02), (x, ybot1 - 0.11, z1 - 0.02), 0.09, rng.choice([TP["wood_dk"], TP["wood"]]), detail=0.6 * detail)
    for zb in bents:
        f = (zb - z0) / max(z1 - z0, 1e-3)
        yb = ybot0 + (ybot1 - ybot0) * f - 0.2
        post(m, merge, (x0 - 0.12, yb - 0.12, zb), (x1 + 0.12, yb - 0.12, zb), 0.12, TP["wood_dk"], detail=0.6 * detail)
        tops = []
        for x in pil_x:
            top = (x + rng.normal() * 0.02, yb + 0.05, zb + rng.normal() * 0.02)
            piling(m, piles, top, FLOOR, piling_r * rng.uniform(0.9, 1.08), lean=(rng.normal() * 0.08, rng.normal() * 0.08), sea_y=SEA,
                   barnacles=9, detail=detail * 1.6)
            tops.append(top)
        if brace and len(tops) >= 2:
            a, b = np.array(tops[0]), np.array(tops[-1])
            board(m, merge, a + np.array([0, -0.4, 0.24]), b + np.array([0, -1.6, 0.24]), 0.2, 0.075, (0, 0, 1), TP["wood_dk"], nails=0,
                  detail=0.4 * detail, knot=0)


def _rails(m, side_pts, merge="rail", detail=1.0, h=0.88, start_post=True, end_post=True, post_every=2.0):
    rail_run(m, merge, side_pts, h=h, post_r=0.078, rail_w=0.16, rail_t=0.072, post_every=post_every, foot_y=-0.3, detail=detail, start_post=start_post, end_post=end_post)


def boardwalk(name, rails, budget=3000):
    def fn():
        m = TownModel(name, budget=budget)
        _deck_cross(m, -1.2, 1.2, -2.0, 2.0, 0.0)
        _structure(m, -1.2, 1.2, -2.0, 2.0, -0.08)
        for sx in rails:
            x = sx * 1.12
            _rails(m, [(x, 0, -2.0), (x, 0, 2.0)], end_post=False)
        return m
    return fn


MODELS["town/boardwalk"] = boardwalk("boardwalk", [])


def boardwalk_short():
    """2.4 m long straight link (z -1.2..1.2), rails both sides."""
    m = TownModel("boardwalk_short", budget=2000)
    _deck_cross(m, -1.2, 1.2, -1.2, 1.2, 0.0)
    _structure(m, -1.2, 1.2, -1.2, 1.2, -0.08, bents=[-1.05])
    for sx in (-1, 1):
        _rails(m, [(sx * 1.12, 0, -1.2), (sx * 1.12, 0, 1.2)], end_post=False, post_every=1.2)
    return m


MODELS["town/boardwalk_short"] = boardwalk_short


def boardwalk_short_rail1():
    """2.4 m long straight (z -1.2..1.2), rail on +X only."""
    m = TownModel("boardwalk_short_rail1", budget=1800)
    _deck_cross(m, -1.2, 1.2, -1.2, 1.2, 0.0)
    _structure(m, -1.2, 1.2, -1.2, 1.2, -0.08, bents=[-1.05])
    _rails(m, [(1.12, 0, -1.2), (1.12, 0, 1.2)], end_post=False, post_every=1.2)
    return m


def boardwalk_square():
    """2.4 x 2.4 open junction, no rails."""
    m = TownModel("boardwalk_square", budget=1500)
    _deck_cross(m, -1.2, 1.2, -1.2, 1.2, 0.0)
    _structure(m, -1.2, 1.2, -1.2, 1.2, -0.08, bents=[-1.05])
    return m


MODELS["town/boardwalk_short_rail1"] = boardwalk_short_rail1
MODELS["town/boardwalk_square"] = boardwalk_square


def boardwalk_gap():
    """4 m straight, rails both sides but a 1.5 m opening in the +X rail (z -0.75..0.75) for a gangway."""
    m = TownModel("boardwalk_gap", budget=3000)
    _deck_cross(m, -1.2, 1.2, -2.0, 2.0, 0.0)
    _structure(m, -1.2, 1.2, -2.0, 2.0, -0.08)
    _rails(m, [(-1.12, 0, -2.0), (-1.12, 0, 2.0)], end_post=False)
    _rails(m, [(1.12, 0, -2.0), (1.12, 0, -0.75)], end_post=True)
    _rails(m, [(1.12, 0, 0.75), (1.12, 0, 2.0)], end_post=False)
    return m


MODELS["town/boardwalk_gap"] = boardwalk_gap
MODELS["town/boardwalk_rail1"] = boardwalk("boardwalk_rail1", [1])
MODELS["town/boardwalk_rail2"] = boardwalk("boardwalk_rail2", [-1, 1])


def square(name, rail_sides, budget=2200):
    """2.4 x 2.4 junction. rail_sides subset of '+x', '-x', '+z'."""
    def fn():
        m = TownModel(name, budget=budget)
        _deck_cross(m, -1.2, 1.2, -1.2, 1.2, 0.0)
        _structure(m, -1.2, 1.2, -1.2, 1.2, -0.08, bents=[-1.05])
        r = 1.12
        if "+x" in rail_sides and "+z" in rail_sides:
            pts = [(r, 0, -1.2), (r, 0, r), (-1.2, 0, r)] if "-x" not in rail_sides else [(r, 0, -1.2), (r, 0, r), (-r, 0, r), (-r, 0, -1.2)]
            _rails(m, pts, post_every=1.2, end_post=False)
        elif "+z" in rail_sides:
            _rails(m, [(1.2, 0, r), (-1.2, 0, r)], post_every=1.2, start_post=False, end_post=False)
        return m
    return fn


MODELS["town/boardwalk_corner"] = square("boardwalk_corner", {"+x", "+z"})
MODELS["town/boardwalk_t"] = square("boardwalk_t", {"+z"})
MODELS["town/boardwalk_end"] = square("boardwalk_end", {"+x", "+z", "-x"})


def ramp():
    m = TownModel("boardwalk_ramp", budget=3000)
    _deck_cross(m, -1.2, 1.2, -2.0, 2.0, 0.0, 1.0)
    # cleats across for grip
    for z in np.arange(-1.6, 2.0, 0.55):
        y = (z + 2.0) / 4.0
        board(m, "deck", (-1.0, y + 0.012, z), (1.0, y + 0.012 + 0.0, z), 0.05, 0.03, (0, 1, -0.25), TP["wood_dk"], nails=0, detail=0.3, knot=0)
    _structure(m, -1.2, 1.2, -2.0, 2.0, -0.08, 0.92)
    for sx in (-1, 1):
        x = sx * 1.12
        _rails(m, [(x, 0.0, -2.0), (x, 1.0, 2.0)], end_post=True)
    return m


MODELS["town/boardwalk_ramp"] = ramp


def stairs():
    m = TownModel("boardwalk_stairs", budget=3200)
    rng = m.rng
    n = 9
    rise = 1.8 / n
    # landing at the top (z -2 .. -1.6), then 9 treads to z = +2
    _deck_cross(m, -1.2, 1.2, -2.0, -1.62, 0.0)
    run = (4.0 - 0.38) / n
    for i in range(n):
        y = -(i + 1) * rise
        z0 = -1.62 + i * run
        zc = z0 + run / 2
        col = rng.choice(WOODS)
        board(m, "deck", (-1.0 - rng.uniform(0, 0.04), y - 0.03, zc), (1.0 + rng.uniform(0, 0.04), y - 0.03, zc), run + 0.03, 0.06, (0, 1, 0), col,
              nails=0, detail=1.0, knot=0.1, bow=rng.uniform(0, 0.01))
    # stringers
    for x in (-1.08, 1.08):
        board(m, "frame", (x, -0.1, -1.7), (x, -1.95, 2.05), 0.28, 0.07, (1, 0, 0), TP["wood_dk"], nails=2, detail=0.7)
    _structure(m, -1.2, 1.2, -2.0, -1.62, -0.08, bents=[-1.85], brace=False)
    for sx in (-1, 1):
        x = sx * 1.17
        _rails(m, [(x, 0.0, -2.0), (x, -1.8, 2.0)], end_post=True, post_every=2.2)
    return m


MODELS["town/boardwalk_stairs"] = stairs


def pier_head():
    m = TownModel("pier_head", budget=9000)
    _deck_cross(m, -4.0, 4.0, -4.0, 4.0, 0.0, pw=(0.24, 0.32))
    _structure(m, -4.0, 4.0, -4.0, 4.0, -0.08, bents=[-3.85, 0.0, 3.85], pil_x=[-3.85, 0.0, 3.85])
    r = 3.92
    _rails(m, [(-1.25, 0, -r), (-r, 0, -r), (-r, 0, r), (r, 0, r), (r, 0, -r), (1.25, 0, -r)], post_every=2.0)
    # bumpers: old tyres hung on the seaward face
    rng = m.rng
    for x in (-2.6, 0.2, 2.8):
        c = np.array([x, -0.55, 4.12])
        p = m.piece(color="#2f3033", gloss=60, merge="frame", res=0.02, lumps=0.004, detail=3.0)
        p.add(Torus(c, 0.28, 0.11, rot=(90, 0, rng.normal() * 8)))
        rope(m, "frame", [c + (0, 0.35, -0.05), c + (0, 0.6, -0.1)], 0.02, detail=0.2)
    return m


MODELS["town/pier_head"] = pier_head


def pier_platform():
    """4 x 4 side platform (x,z -2..2) for the crane; rails on +Z, +X and -Z, open on -X (the pier side)."""
    m = TownModel("pier_platform", budget=4000)
    _deck_cross(m, -2.0, 2.0, -2.0, 2.0, 0.0, pw=(0.22, 0.3))
    _structure(m, -2.0, 2.0, -2.0, 2.0, -0.08, bents=[-1.85, 1.85], pil_x=[-1.85, 1.85])
    _rails(m, [(-2.0, 0, 1.92), (1.92, 0, 1.92), (1.92, 0, -1.92), (-2.0, 0, -1.92)], post_every=2.0, start_post=False, end_post=False)
    return m


MODELS["town/pier_platform"] = pier_platform


def floating_dock():
    m = TownModel("floating_dock", budget=6000)
    rng = m.rng
    # planks across X, 10 m along Z
    _deck_cross(m, -1.2, 1.2, -5.0, 5.0, 0.0, pw=(0.22, 0.3), t=0.06)
    for x in (-0.95, 0.0, 0.95):
        post(m, "frame", (x, -0.14, -4.95), (x, -0.14, 4.95), 0.07, TP["wood_dk"], detail=0.4)
    # rub rails / edge boards
    for sx in (-1, 1):
        board(m, "frame", (sx * 1.24, -0.12, -5.05), (sx * 1.24, -0.12, 5.05), 0.2, 0.06, (sx, 0, 0), TP["wood_dk"], nails=0, detail=0.5)
    # floats: old tarred barrels lying along Z
    for zc in (-3.6, -1.2, 1.2, 3.6):
        for sx in (-1, 1):
            c = np.array([sx * 0.6, -0.48, zc + rng.normal() * 0.05])
            p = m.piece(color=rng.choice([TP["wood_tar"], "#3b3f3f", "#4a3a30"]), gloss=90, merge="floats", res=0.025, lumps=0.006, detail=0.6)
            p.add(Capsule(c - (0, 0, 0.75), c + (0, 0, 0.75), 0.36, 0.36))
            p.paint(band(-0.62, -0.42, 0.05, 4), TP["algae"], gloss=140, feather=0.03)
            for zz in (-0.45, 0.45):
                p.add(Torus(c + (0, 0, zz), 0.355, 0.022, rot=(90, 0, 0)), k=0.006, color=TP["rust_dk"])
    # cleats on the boat side (+X)
    for zc in (-3.8, 0.0, 3.8):
        c = np.array([1.05, 0.0, zc])
        p = m.piece(color=TP["iron"], gloss=70, merge="frame", res=0.008, lumps=0.002, detail=0.4)
        p.add(Capsule(c + (0, 0.07, -0.18), c + (0, 0.07, 0.18), 0.03))
        p.add(Capsule(c + (0, 0.0, -0.07), c + (0, 0.07, -0.07), 0.03), k=0.02)
        p.add(Capsule(c + (0, 0.0, 0.07), c + (0, 0.07, 0.07), 0.03), k=0.02)
    # tyre fenders on the boat side
    for zc in (-2.4, 2.4):
        c = np.array([1.36, -0.25, zc])
        p = m.piece(color="#2f3033", gloss=60, merge="floats", res=0.02, lumps=0.004, detail=3.0)
        p.add(Torus(c, 0.26, 0.1, rot=(0, 0, 90)))
    rope(m, "frame", [(1.05, 0.08, -3.8), (0.8, 0.03, -3.4), (0.7, 0.04, -3.0), (0.95, 0.03, -2.8)], 0.025, detail=0.3)
    return m


MODELS["town/floating_dock"] = floating_dock


def gangway():
    m = TownModel("gangway", budget=3000)
    rng = m.rng
    L, drop = 3.4, 1.3
    _deck_cross(m, -0.6, 0.6, 0.0, L, 0.0, -drop, t=0.055, pw=(0.18, 0.24))
    for z in np.arange(0.3, L, 0.38):
        y = -drop * z / L
        board(m, "deck", (-0.5, y + 0.012, z), (0.5, y + 0.012, z), 0.045, 0.03, (0, 1, 0.38), TP["wood_dk"], nails=0, detail=0.3, knot=0)
    for sx in (-1, 1):
        board(m, "frame", (sx * 0.64, -0.12, -0.05), (sx * 0.64, -0.12 - drop, L + 0.05), 0.22, 0.06, (sx, 0, 0), TP["wood_dk"], nails=2, detail=0.6)
        rail_run(m, "rail", [(sx * 0.62, 0.0, 0.05), (sx * 0.62, -drop, L - 0.05)], h=0.85, post_r=0.04, post_every=1.7, foot_y=-0.2, detail=0.8)
    # hinge plate + roller at the bottom
    p = m.piece(color=TP["rust"], gloss=60, merge="frame", res=0.012, detail=0.3)
    p.add(Cylinder((0, -drop - 0.12, L - 0.1), 0.08, 0.55, rot=(0, 0, 90), round=0.02))
    return m


MODELS["town/gangway"] = gangway


def single_piling():
    m = TownModel("piling", budget=1200)
    piling(m, "piling", (0, 0.0, 0), FLOOR, 0.16, lean=(0.05, -0.04), sea_y=SEA, barnacles=16)
    return m


MODELS["town/piling"] = single_piling


def ladder():
    m = TownModel("ladder", budget=1500)
    rng = m.rng
    for sx in (-1, 1):
        post(m, "ladder", (sx * 0.24, 0.6, 0.06), (sx * 0.24, -2.6, 0.1), 0.035, TP["wood_dk"], detail=0.7)
    for y in np.arange(-2.4, 0.3, 0.3):
        post(m, "ladder", (-0.27, y, 0.08), (0.27, y + rng.normal() * 0.02, 0.08), 0.022, rng.choice([TP["wood"], TP["wood_lt"]]), square=False, detail=0.5)
    # algae on the lower rungs
    for p in m.pieces:
        p.paint(below(SEA + 0.15, 0.08, 3), TP["algae"], gloss=140, feather=0.04)
    return m


MODELS["town/ladder"] = ladder


def bollard():
    m = TownModel("bollard", budget=1200)
    p = m.piece(color=TP["iron"], gloss=80, merge="bollard", res=0.008, lumps=0.003, dents=4, dent_size=0.03)
    p.add(Cylinder((0, 0.03, 0), 0.2, 0.03, round=0.015))
    p.add(Capsule((0, 0.03, 0), (0.0, 0.36, 0.0), 0.12, 0.1), k=0.05)
    p.add(Ellipsoid((0, 0.42, 0), (0.16, 0.07, 0.16)), k=0.04)
    p.paint(patches(4, 0.1, 5), TP["rust"], feather=0.01)
    p.paint(patches(2.5, 0.25, 9), TP["navy"], feather=0.01)
    rope(m, "bollard", [(0.0, 0.25, 0.13), (0.14, 0.22, 0.0), (0.0, 0.2, -0.13), (-0.14, 0.18, 0.0), (0, 0.16, 0.14), (0.05, 0.05, 0.4), (0.1, 0.02, 0.8)], 0.025, detail=0.6)
    return m


MODELS["town/bollard"] = bollard


def cleat():
    m = TownModel("cleat", budget=600)
    p = m.piece(color=TP["iron"], gloss=80, merge="cleat", res=0.006, lumps=0.0015)
    p.add(Capsule((-0.17, 0.08, 0), (0.17, 0.08, 0), 0.035, 0.03))
    p.add(Capsule((-0.06, 0.0, 0), (-0.05, 0.08, 0), 0.032), k=0.02)
    p.add(Capsule((0.06, 0.0, 0), (0.05, 0.08, 0), 0.032), k=0.02)
    p.add(Box((0, 0.008, 0), (0.12, 0.01, 0.05), round=0.008), k=0.01)
    p.paint(patches(6, 0.15, 3), TP["rust"], feather=0.01)
    return m


MODELS["town/cleat"] = cleat


def seawall():
    """Timber bulkhead holding the shore: vertical piles, horizontal planks on the seaward face (+Z), cap board on
    top (y = 0), tide stain + weed below y = -1.75."""
    m = TownModel("seawall", budget=3500)
    rng = m.rng
    sea = -1.75
    for x in (-1.9, 0.0, 1.9):
        piling(m, "piles", (x, 0.02, 0.05), -4.0, 0.15, lean=(rng.normal() * 0.04, 0.0), sea_y=sea, barnacles=8, detail=0.8)
    y = -3.2
    while y < -0.12:
        h = rng.uniform(0.22, 0.3)
        col = rng.choice(WOODS)
        board(m, "planks", (-2.05 - rng.uniform(0, 0.05), y + h / 2, -0.12), (2.05 + rng.uniform(0, 0.05), y + h / 2, -0.12), h - 0.012, 0.07, (0, 0, 1), col,
              nails=1, detail=0.9, bow=rng.normal() * 0.01)
        y += h
    board(m, "planks", (-2.06, -0.04, -0.05), (2.06, -0.04, -0.05), 0.42, 0.08, (0, 1, 0), TP["wood_dk"], nails=2, detail=0.8)
    for p in m.pieces:
        p.paint(below(sea, 0.1, 2), TP["wood_wet"], gloss=110, feather=0.04)
        p.paint(band(sea - 0.5, sea + 0.25, 0.12, 2.5), TP["algae"], gloss=130, feather=0.04)
    return m


MODELS["town/seawall"] = seawall
