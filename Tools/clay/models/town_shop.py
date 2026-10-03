"""
The Salty Puffin — Gran's fish shop on the pier: an open-fronted board shack with a serving counter facing +Z (the
boardwalk), an ice display tray (sockets display_0..11), a brass till (socket `till`), a blank hanging sign board
(socket `sign_text`), awning, crates of ice; plus the restored version (fresh paint, mended red roof, striped awning,
flower box, bunting).

Footprint (local, origin = floor centre of the shack, y = 0 walkable floor):
  platform x -3.0..5.0, z -2.3..4.6 (front porch z 1.6..4.6, side walk x 2.6..5.0 with Pip's side door)
  shack walls x -2.6..2.6, z -2.2..1.6; counter top y 0.75 at z ~1.6; serving step y 0.25 behind it.
Placed in town at (-5.8, 1.8, 1.0) yaw 90: the porch (z = 4.6) meets the pier's west edge, the side walk faces the shore.
"""
import numpy as np
from kit_town import *
from town_pier import _deck_cross, _structure

try:
    import kit_props as KP
except Exception:  # props kit may not exist yet
    KP = None


MODELS = {}

EAVE, RIDGE = 2.45, 3.75
HX, ZB, ZF = 2.6, -2.2, 1.6


def gable(s, L=2 * HX):
    return EAVE + (RIDGE - EAVE) * (1 - abs(s - L / 2) / (L / 2))


def shop(restored=False):
    name = "fish_shop_restored" if restored else "fish_shop"
    m = TownModel(name, budget=54000)
    rng = m.rng
    mg = dict(trim="trim", glass="glass", deco="deco", door="trim")
    if restored:
        wall_paint, peel, trim_c, counter_c, door_c = TP["teal"], 0.03, TP["white"], TP["red"], TP["mustard"]
        wood = [TP["wood"], TP["wood_lt"]]
        replace = 0.0
    else:
        wall_paint, peel, trim_c, counter_c, door_c = TP["teal"], 0.32, TP["cream"], TP["mustard"], TP["red"]
        wood = [TP["wood"], TP["wood_dk"], TP["wood_lt"], TP["wood_silver"]]
        replace = 0.1

    # ---------------- platform on pilings
    _deck_cross(m, -3.0, 5.0, -2.3, 4.6, 0.0, merge="floor", pw=(0.22, 0.3))
    _structure(m, -3.0, 5.0, -2.3, 4.6, -0.08, bents=[-2.1, 1.2, 4.4], pil_x=[-2.85, -0.2, 2.5, 4.85], merge="floor", piles="piles")
    # rail around the open sides of the platform (back + left side); the porch front and side walk stay open
    rail_run(m, "floor", [(4.92, 0, -0.6), (4.92, 0, -2.22), (2.7, 0, -2.22)], h=0.85, post_every=1.4, foot_y=-0.3, end_post=True)
    rail_run(m, "floor", [(-2.92, 0, 1.75), (-2.92, 0, 4.5)], h=0.85, post_every=1.4, foot_y=-0.3)

    # ---------------- serving step (Pip stands on it)
    _deck_cross(m, -2.45, 2.45, -0.15, 1.25, 0.25, merge="floor", pw=(0.2, 0.26), t=0.06)
    board(m, "floor", (-2.45, 0.12, -0.17), (2.45, 0.12, -0.17), 0.26, 0.05, (0, 0, -1), TP["wood_dk"], nails=2)

    # ---------------- walls
    cols = wood
    pw = None if restored else wall_paint
    if restored:
        pw = wall_paint
    # back wall (gable), seen from the water
    vboard_wall(m, "walls", (HX, ZB), (-HX, ZB), 0.0, gable, (0, 0, -1), cols, paint=pw, peel=peel, replace=replace,
                openings=[(1.7, 2.5, 1.2, 1.8)])
    # side walls (eave height)
    vboard_wall(m, "walls", (-HX, ZB), (-HX, ZF), 0.0, EAVE, (-1, 0, 0), cols, paint=pw, peel=peel, replace=replace,
                openings=[(1.2, 2.0, 1.15, 1.85)])
    vboard_wall(m, "walls", (HX, ZF), (HX, ZB), 0.0, EAVE, (1, 0, 0), cols, paint=pw, peel=peel, replace=replace,
                openings=[(0.35, 1.3, 0.25, 2.25), (2.2, 2.95, 1.15, 1.85)])
    # front: corner strips + gable above the serving opening
    vboard_wall(m, "walls", (-HX, ZF), (HX, ZF), 0.0, gable, (0, 0, 1), cols, paint=pw, peel=peel, replace=replace,
                openings=[(0.32, 2 * HX - 0.32, -1, 2.3)], battens=True)
    # framing visible inside: corner posts, top plates, header over the opening
    for x, z in ((-HX + 0.08, ZB + 0.08), (HX - 0.08, ZB + 0.08), (-HX + 0.08, ZF - 0.08), (HX - 0.08, ZF - 0.08)):
        post(m, "trim", (x, 0.0, z), (x, EAVE, z), 0.075, TP["wood_dk"], detail=0.6)
    post(m, "trim", (-HX + 0.05, 2.33, ZF + 0.02), (HX - 0.05, 2.33, ZF + 0.02), 0.09, trim_c if restored else TP["wood_br"], detail=0.8)
    for x in (-HX + 0.1, HX - 0.1):
        post(m, "trim", (x, EAVE - 0.06, ZB), (x, EAVE - 0.06, ZF), 0.06, TP["wood_dk"], detail=0.4)
    # tie beam across the middle (things hang from it)
    post(m, "trim", (-HX, EAVE - 0.05, -0.4), (HX, EAVE - 0.05, -0.4), 0.07, TP["wood_dk"], detail=0.5)
    # corner trim boards outside
    for x, z, n in ((-HX - 0.03, ZF + 0.03, (-1, 0, 1)), (HX + 0.03, ZF + 0.03, (1, 0, 1)), (-HX - 0.03, ZB - 0.03, (-1, 0, -1)), (HX + 0.03, ZB - 0.03, (1, 0, -1))):
        board(m, "trim", (x, -0.05, z), (x, EAVE + 0.02, z), 0.13, 0.05, n, TP["wood"], paint=trim_c, peel=0.1 if restored else 0.4, nails=2)
    # skirt board
    for (a, b, n) in (((-HX - 0.05, 0.1, ZB - 0.05), (HX + 0.05, 0.1, ZB - 0.05), (0, 0, -1)), ((-HX - 0.05, 0.1, ZB), (-HX - 0.05, 0.1, ZF), (-1, 0, 0)),
                      ((HX + 0.05, 0.1, ZB), (HX + 0.05, 0.1, ZF), (1, 0, 0))):
        board(m, "trim", a, b, 0.2, 0.04, n, TP["wood_dk"], nails=0, detail=0.6)

    # ---------------- windows & door
    lights = []
    lights.append(window(m, mg, (-HX - 0.03, 1.5, ZB + 1.6), (-1, 0, 0), 0.62, 0.55, frame_color=trim_c, shutters=door_c if restored else TP["sage"],
                         curtain="#c9b48f"))
    lights.append(window(m, mg, (HX + 0.03, 1.5, ZF - 2.57), (1, 0, 0), 0.6, 0.55, frame_color=trim_c, curtain="#c9b48f",
                         shutters=None))
    lights.append(window(m, mg, (HX - 2.1, 1.5, ZB - 0.03), (0, 0, -1), 0.62, 0.5, frame_color=trim_c, panes=(2, 1)))
    door(m, mg, (HX + 0.02, 0.0, ZF - 0.82), (1, 0, 0), 0.86, 1.95, color=TP["wood_br"], paint=door_c, peel=0.05 if restored else 0.3, open_deg=-100)
    m.socket("door", None, (HX + 0.1, 1.0, ZF - 0.82), (0, 90, 0))

    # ---------------- roof (ridge along Z)
    ov, fo, bo = 0.38, 0.75, 0.3
    ye = EAVE - ov * (RIDGE - EAVE) / HX
    roof_cols = [TP["red"], TP["red_dk"], "#a35a48"] if restored else None
    for sx in (-1, 1):
        e0 = (sx * (HX + ov), ye, ZB - bo) if sx < 0 else (sx * (HX + ov), ye, ZF + fo)
        e1 = (sx * (HX + ov), ye, ZF + fo) if sx < 0 else (sx * (HX + ov), ye, ZB - bo)
        r0 = (0, RIDGE + 0.04, e0[2])
        r1 = (0, RIDGE + 0.04, e1[2])
        tin_roof(m, "roof", e0, e1, r0, r1, colors=roof_cols, rust=0.08 if restored else 0.45, patch=0.0 if restored else 0.2,
                 sag=0.02 if restored else 0.07)
    # ridge roll
    rr = m.piece(color=TP["tin_dk"] if not restored else TP["red_dk"], gloss=40, merge="roof", res=0.012, lumps=0.002, detail=0.5)
    rr.add(Tube([(0, RIDGE + 0.07, ZB - bo - 0.05), (0.01, RIDGE + 0.05, 0.0), (0, RIDGE + 0.07, ZF + fo + 0.05)], 0.065, samples=4))
    if not restored:
        rr.paint(patches(2, 0.0, 4), TP["rust"], feather=0.02)
    # barge boards + fascia
    for z in (ZB - bo + 0.03, ZF + fo - 0.03):
        for sx in (-1, 1):
            a = np.array([sx * (HX + ov + 0.04), ye - 0.07, z])
            b = np.array([0.0, RIDGE - 0.02, z])
            board(m, "trim", a, b, 0.2, 0.05, (0, 0, 1 if z > 0 else -1), TP["wood"], paint=trim_c, peel=0.1 if restored else 0.35, nails=2)
    for sx in (-1, 1):
        board(m, "trim", (sx * (HX + ov + 0.02), ye - 0.1, ZB - bo), (sx * (HX + ov + 0.02), ye - 0.1, ZF + fo), 0.16, 0.045, (sx, 0, 0), TP["wood"],
              paint=trim_c, peel=0.1 if restored else 0.35, nails=2)
    # rafters under the front overhang
    for x in (-1.6, -0.6, 0.6, 1.6):
        y = RIDGE - abs(x) * (RIDGE - EAVE) / HX - 0.12
        post(m, "trim", (x, y, ZF - 0.2), (x, y, ZF + fo - 0.08), 0.045, TP["wood_dk"], detail=0.3)
    smoke = stovepipe(m, "roof", (-1.3, RIDGE - 0.6, -1.2), 1.15, lean=(-0.12, -0.05), bends=1)
    m.socket("smoke", None, smoke)

    # ---------------- counter
    zc = ZF + 0.02
    top_y = 0.75
    # front of counter: vertical painted boards
    x = -2.25
    while x < 2.25:
        w = rng.uniform(0.17, 0.24)
        w = min(w, 2.25 - x)
        board(m, "counter", (x + w / 2, 0.0, zc + 0.3), (x + w / 2, top_y - 0.07, zc + 0.3), w - 0.012, 0.045, (0, 0, 1), TP["wood"], paint=counter_c,
              peel=0.04 if restored else 0.3, nails=1, detail=1.0)
        x += w
    # counter top: two thick planks + front lip
    for i, (z0, w) in enumerate(((zc - 0.28, 0.3), (zc + 0.02, 0.32))):
        board(m, "counter", (-2.32, top_y - 0.035, z0 + w / 2), (2.32, top_y - 0.035, z0 + w / 2), w - 0.01, 0.07, (0, 1, 0),
              TP["wood_br"] if i else TP["wood"], nails=2, detail=1.3, bow=0.004)
    board(m, "counter", (-2.3, top_y - 0.02, zc + 0.36), (2.3, top_y - 0.02, zc + 0.36), 0.09, 0.05, (0, 0, 1), TP["wood_dk"], nails=0, detail=0.6)
    for x in (-2.2, 0.0, 2.2):
        post(m, "counter", (x, 0.0, zc + 0.24), (x, top_y - 0.07, zc + 0.24), 0.05, TP["wood_dk"], detail=0.4)
    # ice display tray: a wooden tray tilted toward the customers, heaped with crushed ice
    tray_c = np.array([-0.45, top_y + 0.07, zc + 0.08])
    tilt = 9.0
    Rt = euler((tilt, 0, 0))
    hw, hd = 1.5, 0.27
    for (a, b, n) in ((( -hw, 0.0, -hd), (hw, 0.0, -hd), (0, 0, -1)), ((-hw, 0.0, hd), (hw, 0.0, hd), (0, 0, 1)), ((-hw, 0.0, -hd), (-hw, 0.0, hd), (-1, 0, 0)),
                      ((hw, 0.0, -hd), (hw, 0.0, hd), (1, 0, 0))):
        board(m, "counter", tray_c + Rt @ np.array(a), tray_c + Rt @ np.array(b), 0.12, 0.04, Rt @ np.array(n), TP["wood"], paint=trim_c if restored else TP["teal_dk"],
              peel=0.05 if restored else 0.3, nails=1, detail=0.8)
    ice = ice_heap(m, "props", tray_c + Rt @ np.array([0, -0.01, 0]), (hw - 0.04, 0.045, hd - 0.03), Rt, chunks=26, detail=1.5)
    # display sockets: 2 rows x 6 on the ice, fish head toward the customers (+Z)
    k = 0
    for row, zz in enumerate((-0.12, 0.11)):
        for i in range(6):
            xx = -hw + 0.25 + i * (2 * hw - 0.5) / 5
            pos = tray_c + Rt @ np.array([xx, 0.06, zz])
            m.socket(f"display_{k}", None, pos, (tilt, 0, 0))
            k += 1
    # till on the right end of the counter
    till_top = brass_till(m, "props", (1.65, top_y, zc - 0.02), yaw=-12)
    m.socket("till", None, (1.65, top_y + 0.2, zc + 0.0), (0, -12, 0))
    # paper roll + scale on the counter
    p = m.piece(color=TP["brass"], gloss=170, merge="props", res=0.006, detail=0.6)
    sc = np.array([1.1, top_y, zc - 0.15])
    p.add(Cylinder(sc + (0, 0.04, 0), 0.06, 0.04, round=0.01))
    p.add(Capsule(sc + (0, 0.06, 0), sc + (0, 0.22, 0), 0.015), k=0.01)
    p.add(Ellipsoid(sc + (0, 0.25, 0), (0.14, 0.025, 0.14)), k=0.01, color=shade(TP["brass"], 0.9))
    p.sub(Ellipsoid(sc + (0, 0.27, 0), (0.12, 0.02, 0.12)), k=0.005)
    m.socket("counter", None, (0.0, top_y, zc + 0.1))
    m.socket("serve", None, (0.0, 0.25, 0.85), (0, 0, 0))

    # ---------------- hanging sign: iron bracket off the front gable, blank board on two chains
    sign_c = np.array([0.0, 2.92, ZF + 0.42])
    br = m.piece(color=TP["iron"], gloss=80, merge="deco", res=0.008, lumps=0.0015, detail=0.6)
    br.add(Capsule((-0.95, 3.42, ZF + 0.08), (-0.95, 3.42, ZF + 0.62), 0.018))
    br.add(Capsule((0.95, 3.42, ZF + 0.08), (0.95, 3.42, ZF + 0.62), 0.018))
    br.add(Capsule((-1.0, 3.42, ZF + 0.42), (1.0, 3.42, ZF + 0.42), 0.022), k=0.01)
    br.add(Tube([(-0.95, 3.1, ZF + 0.06), (-0.95, 3.3, ZF + 0.3), (-0.95, 3.42, ZF + 0.5)], 0.014, samples=4), k=0.01)
    br.add(Tube([(0.95, 3.1, ZF + 0.06), (0.95, 3.3, ZF + 0.3), (0.95, 3.42, ZF + 0.5)], 0.014, samples=4), k=0.01)
    for sx in (-1, 1):
        chain(m, "deco", (sx * 0.7, 3.4, ZF + 0.42), (sx * 0.7, 3.17, ZF + 0.42), link=0.04)
    Rs = frame((1, 0, 0), (0, 0, 1)) @ euler((0, 0, 0 if restored else 1.5))
    sb = m.piece(color=TP["cream"] if not restored else "#efe6cf", gloss=60, merge="deco", res=0.01, lumps=0.002, dents=3, detail=1.0)
    sb.add(Box(sign_c, (0.86, 0.03, 0.24), Rs, round=0.015))
    if not restored:
        sb.paint(patches(1.2, 0.32, 11), "#cdbf9f", feather=0.02)
    fc = TP["teal_dk"] if restored else TP["red_dk"]
    for (a, b) in (((-0.9, 0.23), (0.9, 0.23)), ((-0.9, -0.23), (0.9, -0.23)), ((-0.88, -0.23), (-0.88, 0.23)), ((0.88, -0.23), (0.88, 0.23))):
        pa = sign_c + Rs @ np.array([a[0], 0.0, a[1]])
        pb = sign_c + Rs @ np.array([b[0], 0.0, b[1]])
        board(m, "deco", pa + np.array([0, 0, 0.035]), pb + np.array([0, 0, 0.035]), 0.07, 0.035, (0, 0, 1), TP["wood"], paint=fc,
              peel=0.02 if restored else 0.3, nails=0, detail=0.5, knot=0, grooves=[])
    m.socket("sign_text", None, sign_c + (0, 0, 0.04), (0, 0, 0))

    # ---------------- awning over the serving opening
    aw_top, aw_drop = 2.34, 0.95
    slope = np.radians(20 if restored else 24)
    Ra = frame((1, 0, 0), (0, np.cos(slope), np.sin(slope)))
    if restored:
        cv = Canvas((0, aw_top, ZF + 0.06), 2.45, aw_drop, Ra, t=0.016, sag=0.05, billow=0.04, sw=0.49, scallop=0.09, seed=5)
        ap = m.piece(color="#e9ddc3", gloss=30, merge="awning", res=0.009, lumps=0.0015, detail=4.0, mottle=0.04)
        ap.add(cv)
        ap.paint(cv.stripe_mask(True), TP["red"], feather=0.003)
    else:
        cv = Canvas((0, aw_top, ZF + 0.06), 2.45, aw_drop, Ra, t=0.014, sag=0.1, billow=0.05, sw=0.0, scallop=0.0, seed=9)
        ap = m.piece(color="#b07a62", gloss=25, merge="awning", res=0.01, lumps=0.003, dents=6, dent_size=0.08, detail=1.2, mottle=0.12)
        ap.add(cv)
        ap.paint(patches(1.6, 0.12, 21), "#9a6a56", feather=0.02)
        ap.paint(patches(2.4, 0.28, 22), "#c9a78e", feather=0.01)
        # patch sewn on + a tear
        pc = np.array([0.9, aw_top - 0.32, ZF + 0.7])
        ap.add(Box(pc, (0.25, 0.012, 0.2), Ra, round=0.008), k=0.004, color="#7d8a6e")
        ap.sub(Ellipsoid((-1.4, aw_top - 0.5, ZF + 1.0), (0.12, 0.08, 0.04), Ra), k=0.01)
    # front edge spar + poles
    front = np.array([0, aw_top, ZF + 0.06]) + Ra @ np.array([0, -0.02, aw_drop])
    post(m, "awning", front + (-2.5, -0.04, 0), front + (2.5, -0.04, 0), 0.03, TP["wood_dk"], square=False, detail=0.4)
    for sx in (-1, 1):
        post(m, "awning", (sx * 2.42, 0.0, front[2] + 0.02), (sx * 2.42, front[1] + 0.02, front[2] + 0.02), 0.035, TP["wood_dk"], square=False, detail=0.4)
        rope(m, "awning", [(sx * 2.42, front[1] - 0.05, front[2]), (sx * 2.55, front[1] - 0.5, front[2] + 0.2), (sx * 2.6, 0.02, front[2] + 0.55)], 0.012, detail=0.2)

    # ---------------- interior: shelves, jars, tins, hooks, slate
    for y in (1.15, 1.6):
        board(m, "deco", (-2.3, y, ZB + 0.2), (1.0, y, ZB + 0.2), 0.26, 0.04, (0, 1, 0), TP["wood_br"], nails=1, detail=0.6)
        for x in (-2.0, -0.5, 0.8):
            post(m, "deco", (x, y - 0.02, ZB + 0.08), (x, y - 0.2, ZB + 0.08), 0.02, TP["wood_dk"], detail=0.2)
        x = -2.2
        while x < 0.9:
            kind = rng.integers(3)
            c = np.array([x, y + 0.02, ZB + 0.2 + rng.normal() * 0.03])
            p = m.piece(gloss=150 if kind == 0 else 90, color=rng.choice(["#d7c9a2", "#8fa47e", "#c98f63", "#b4483b", "#4c6c7a"]), merge="deco", res=0.008,
                        lumps=0.002, detail=0.35)
            if kind == 0:     # jar
                h = rng.uniform(0.14, 0.22)
                p.add(Cylinder(c + (0, h / 2, 0), 0.055, h / 2, round=0.02))
                p.add(Cylinder(c + (0, h + 0.01, 0), 0.05, 0.015, round=0.006), k=0.004, color=TP["red"] if rng.random() < 0.5 else TP["tin"])
            elif kind == 1:   # stack of tins
                for j in range(rng.integers(1, 4)):
                    p.add(Cylinder(c + (0, 0.045 + j * 0.09, 0), 0.045, 0.043, round=0.008), k=0.003)
                p.paint(band(c[1] + 0.02, c[1] + 0.06, 0, 1), TP["cream"], feather=0.004)
            else:             # bottle
                p.add(Capsule(c + (0, 0.05, 0), c + (0, 0.16, 0), 0.04, 0.035))
                p.add(Capsule(c + (0, 0.16, 0), c + (0, 0.25, 0), 0.015), k=0.02)
            x += rng.uniform(0.14, 0.24)
    # slate price board (blank) on the back wall
    sl = m.piece(color="#3c4245", gloss=40, merge="deco", res=0.01, detail=0.6)
    sl.add(Box((1.6, 1.45, ZB + 0.08), (0.42, 0.32, 0.02), round=0.01))
    sl.add(Box((1.6, 1.45, ZB + 0.07), (0.46, 0.36, 0.015), round=0.01), k=0.0, color=TP["wood_br"])
    sl.paint(Box((1.6, 1.45, ZB + 0.12), (0.4, 0.3, 0.05)), "#3c4245")
    # hooks + a hanging brass scale from the tie beam
    chain(m, "deco", (0.8, EAVE - 0.1, -0.4), (0.8, 1.75, -0.4), link=0.035)
    p = m.piece(color=TP["brass"], gloss=170, merge="deco", res=0.007, detail=0.5)
    p.add(Cylinder((0.8, 1.7, -0.4), 0.06, 0.06, round=0.02))
    p.add(Ellipsoid((0.8, 1.45, -0.4), (0.17, 0.03, 0.17)), k=0.0)
    p.sub(Ellipsoid((0.8, 1.48, -0.4), (0.15, 0.025, 0.15)), k=0.004)
    for a in range(3):
        r = np.radians(a * 120)
        p.add(Capsule((0.8, 1.64, -0.4), (0.8 + np.cos(r) * 0.15, 1.47, -0.4 + np.sin(r) * 0.15), 0.004), k=0.002)

    # ---------------- lanterns at the front corners
    for i, sx in enumerate((-1, 1)):
        arm0 = np.array([sx * (HX + 0.02), 2.2, ZF + 0.03])
        br = m.piece(color=TP["iron"], gloss=80, merge="deco", res=0.007, detail=0.4)
        br.add(Tube([arm0, arm0 + (sx * 0.2, 0.06, 0.15), arm0 + (sx * 0.3, 0.02, 0.3)], 0.013, samples=4))
        lights.append(hang_lantern(m, dict(metal="deco", glass="glass"), arm0 + (sx * 0.3, 0.0, 0.3), 0.85))
        m.socket(f"light_{i}", None, lights[-1])
    for i, w in enumerate(lights[:3]):
        m.socket(f"win_{i}", None, w)

    # ---------------- dressing
    dress(m, restored)
    return m


def crate_simple(m, merge, c, yaw=0.0, size=(0.55, 0.32, 0.4), color=None, ice=False):
    """Local fallback crate (the props kit replaces it when available)."""
    rng = m.rng
    t = T(c, yaw)
    w, h, d = size
    color = color or rng.choice([TP["wood_lt"], TP["wood"], TP["wood_br"]])
    for sz in (-1, 1):
        for j in range(2):
            y = 0.06 + j * h * 0.48
            board(m, merge, t.p(-w / 2, y, sz * d / 2), t.p(w / 2, y, sz * d / 2), h * 0.4, 0.025, t.v((0, 0, sz)), color, nails=0, detail=0.35,
                  knot=0, grooves=[])
    for sx in (-1, 1):
        for j in range(2):
            y = 0.06 + j * h * 0.48
            board(m, merge, t.p(sx * w / 2, y, -d / 2), t.p(sx * w / 2, y, d / 2), h * 0.4, 0.025, t.v((sx, 0, 0)), color, nails=0, detail=0.35,
                  knot=0, grooves=[])
        for sz in (-1, 1):
            post(m, merge, t.p(sx * (w / 2 - 0.02), 0.0, sz * (d / 2 - 0.02)), t.p(sx * (w / 2 - 0.02), h, sz * (d / 2 - 0.02)), 0.022, shade(color, 0.85), detail=0.2)
    board(m, merge, t.p(-w / 2, 0.02, 0), t.p(w / 2, 0.02, 0), d, 0.025, t.v((0, 1, 0)), color, nails=0, detail=0.2, grooves=[], knot=0)
    if ice:
        ice_heap(m, "props", t.p(0, h - 0.04, 0), (w / 2 - 0.03, 0.06, d / 2 - 0.03), t.r(), chunks=8, detail=0.8)


def dress(m, restored):
    rng = m.rng
    # crates of ice stacked by the counter end and on the side walk
    if KP is not None and hasattr(KP, "fish_crate"):
        KP.fish_crate(m, T((2.45, 0.0, 2.35), -8), merge="props")
        KP.fish_crate(m, T((2.5, 0.33, 2.32), 10), merge="props")
        KP.fish_crate(m, T((3.4, 0.0, 2.3), 25), merge="props")
        KP.crate(m, T((-2.55, 0.0, 2.2), 5), merge="props") if hasattr(KP, "crate") else None
        if hasattr(KP, "barrel"):
            KP.barrel(m, T((3.9, 0.0, -1.7), 0), merge="props")
        if hasattr(KP, "rope_coil"):
            KP.rope_coil(m, T((4.2, 0.0, 0.9), 40), merge="props")
    else:
        crate_simple(m, "props", (2.45, 0.0, 2.35), -8, ice=True)
        crate_simple(m, "props", (2.5, 0.33, 2.32), 10, ice=True)
        crate_simple(m, "props", (3.4, 0.0, 2.3), 25, ice=True)
        crate_simple(m, "props", (-2.55, 0.0, 2.2), 5)
    # buoys hung on the left wall
    for i in range(3):
        c = np.array([-HX - 0.13, 1.3 - i * 0.12, -1.6 + i * 0.42])
        p = m.piece(color=rng.choice([TP["red"], TP["mustard"], TP["cream"]]), gloss=120 if restored else 70, merge="props", res=0.012, lumps=0.003, detail=0.5)
        p.add(Ellipsoid(c, (0.1, 0.17, 0.1)))
        p.add(Capsule(c + (0, 0.15, 0), c + (0, 0.27, 0), 0.025), k=0.02)
        p.paint(band(c[1] - 0.04, c[1] + 0.04, 0, 1), TP["white"] if i != 2 else TP["red"], feather=0.005)
        rope(m, "props", [c + (0, 0.27, 0), c + (0.02, 0.5, 0.0), (-HX - 0.05, 1.95, c[2])], 0.01, detail=0.2)
    if restored:
        # flower box under the left window + pots on the porch, bunting along the front gable
        if KP is not None and hasattr(KP, "flower_box"):
            KP.flower_box(m, T((-HX - 0.05, 1.05, ZB + 1.6), -90), merge="props")
        else:
            fb = m.piece(color=TP["red"], merge="props", res=0.01, detail=0.6)
            fb.add(Box((-HX - 0.16, 1.02, ZB + 1.6), (0.12, 0.1, 0.42), round=0.02))
            fl = m.piece(color=TP["grass_dk"], merge="props", res=0.01, lumps=0.012, lump_freq=14, detail=0.8)
            for j in range(9):
                c = np.array([-HX - 0.17 + rng.normal() * 0.04, 1.15 + rng.uniform(0, 0.08), ZB + 1.25 + j * 0.088])
                fl.add(Sphere(c, 0.07), k=0.02)
                fl.add(Sphere(c + (rng.normal() * 0.02, 0.06, rng.normal() * 0.02), 0.035), k=0.005,
                       color=rng.choice(["#d2577a", "#e7d36a", "#f1ece0", "#c9433b"]), gloss=60)
        bunting_simple(m, [(-HX - 0.3, EAVE + 0.05, ZF + 0.7), (0, RIDGE - 0.3, ZF + 0.85), (HX + 0.3, EAVE + 0.05, ZF + 0.7)])
        bunting_simple(m, [(-2.9, 2.3, 4.5), (0.0, 2.0, 4.5), (2.9, 2.3, 4.5)], posts=True)


def bunting_simple(m, pts, posts=False):
    rng = m.rng
    pts = [np.asarray(p, float) for p in pts]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        mid = (a + b) / 2 + np.array([0, -0.12, 0])
        rope(m, "deco", [a, mid, b], 0.008, detail=0.2)
        n = int(np.linalg.norm(b - a) / 0.32)
        for k in range(n):
            t = (k + 0.5) / n
            c = (1 - t) ** 2 * a + 2 * (1 - t) * t * mid + t * t * b
            d = (b - a) / np.linalg.norm(b - a)
            col = [TP["red"], TP["cream"], TP["teal"], TP["mustard"]][k % 4]
            p = m.piece(color=col, gloss=30, merge="deco", res=0.006, lumps=0.001, detail=0.25)
            n_ = np.cross(d, [0, 1, 0])
            R = np.stack([d, [0, 1, 0], n_], axis=1) @ euler((0, 0, rng.normal() * 6))
            # triangular pennant: a box intersected with two half-spaces
            p.add(Box(c + R @ np.array([0, -0.11, 0]), (0.1, 0.11, 0.006), R))
            p.inter(HalfSpace(c + R @ np.array([0.1, 0.0, 0]), R @ np.array([1, -0.45, 0])))
            p.inter(HalfSpace(c + R @ np.array([-0.1, 0.0, 0]), R @ np.array([-1, -0.45, 0])))
    if posts:
        for p in (pts[0], pts[-1]):
            post(m, "deco", (p[0], 0.0, p[2]), (p[0], p[1] + 0.1, p[2]), 0.04, TP["wood_dk"], square=False, detail=0.3)


MODELS["town/fish_shop"] = lambda: shop(False)
MODELS["town/fish_shop_restored"] = lambda: shop(True)
