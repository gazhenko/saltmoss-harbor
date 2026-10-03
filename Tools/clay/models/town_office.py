"""
Harbour office — Walter's shack on stilts at the quay: slate-blue clapboard, a window counter with a propped shutter
(Walter serves from inside), a chalk forecast board on the porch (socket `board_text`), a ship's wheel on the front
wall, a lookout cupola with a fish weathervane, a flagpole with a windsock.

Local frame: shack |x| <= 2.3, |z| <= 1.8, porch z 1.8..4.0, platform x -3.0..3.0, z -2.3..4.0, floor y = 0, front +Z.
Placed at (8, 1.8, -5) yaw 180: the porch edge meets the quay street at world z = -9.
"""
import numpy as np
from kit_town import *
from town_pier import _deck_cross, _structure
import kit_props as KP

MODELS = {}
HX, HZ, EAVE, RIDGE = 2.3, 1.8, 2.5, 3.65


def office():
    m = TownModel("harbor_office", budget=54000)
    rng = m.rng
    mg = dict(trim="trim", glass="glass", deco="deco", door="trim")
    paint, trim = TP["slate"], TP["cream"]

    # platform + porch on pilings
    _deck_cross(m, -3.0, 3.0, -2.3, 4.0, 0.0, merge="floor", pw=(0.22, 0.3))
    _structure(m, -3.0, 3.0, -2.3, 4.0, -0.08, bents=[-2.1, 1.0, 3.8], pil_x=[-2.85, 0.0, 2.85], merge="floor", piles="piles")
    rail_run(m, "floor", [(-2.92, 0, 3.9), (-2.92, 0, -2.22), (2.92, 0, -2.22), (2.92, 0, 3.9)], h=0.85, post_every=1.5, foot_y=-0.3)

    # body: front wall = door | wheel | window counter | strip
    door_s = (0.45, 1.4)
    win_s = (2.35, 4.05)
    ops = {"front": [(door_s[0], door_s[1], -1, 2.02), (win_s[0], win_s[1], 0.98, 2.0)],
           "back": [(1.6, 2.6, 1.15, 1.85)],
           "right": [(1.3, 2.1, 1.1, 1.85)],
           "left": [(1.4, 2.2, 1.1, 1.85)]}
    sh = Shack(m, HX, HZ, EAVE, RIDGE, ridge="x", walls="h", colors=[TP["wood"], TP["wood_lt"]], paint=paint, peel=0.22, trim=trim,
               openings=ops, roof="shake", roof_colors=[TP["wood_dk"], TP["wood"], TP["wood_br"], "#6a6155"], moss=0.22, ov=0.4, ov_gable=0.3,
               front_ov=0.75, sag=0.05)
    lights = []
    # door
    dc, out = sh.at("front", sum(door_s) / 2, 0.0, 0.0)
    door(m, mg, dc, out, 0.88, 1.98, paint=TP["red"], peel=0.25, trim=trim)
    m.socket("door", None, dc + out * 0.1 + np.array([0, 1.0, 0]))
    # window counter: wide opening, ledge, top-hinged shutter propped up with a stick
    wc, out = sh.at("front", sum(win_s) / 2, 1.49, 0.0)
    ww = win_s[1] - win_s[0]
    for (a, b, wdt) in ((wc + np.array([-ww / 2 - 0.05, 0.56, 0]), wc + np.array([ww / 2 + 0.05, 0.56, 0]), 0.12),
                        (wc + np.array([-ww / 2 - 0.04, -0.5, 0]), wc + np.array([-ww / 2 - 0.04, 0.55, 0]), 0.09),
                        (wc + np.array([ww / 2 + 0.04, -0.5, 0]), wc + np.array([ww / 2 + 0.04, 0.55, 0]), 0.09)):
        board(m, "trim", a + out * 0.05, b + out * 0.05, wdt, 0.05, out, TP["wood"], paint=trim, peel=0.3, nails=1)
    ledge_y = 1.0
    board(m, "trim", wc + np.array([-ww / 2 - 0.15, ledge_y - 1.49, 0.2]), wc + np.array([ww / 2 + 0.15, ledge_y - 1.49, 0.2]), 0.5, 0.06, (0, 1, 0),
          TP["wood_br"], nails=2, detail=1.2)
    for sx in (-1, 1):
        a = wc + np.array([sx * ww * 0.4, ledge_y - 1.53, 0.05])
        board(m, "trim", a, a + np.array([0, -0.35, 0.3]), 0.06, 0.04, (sx, 0, 0), TP["wood_dk"], nails=0, detail=0.4)
    # shutter: boards hinged at the top, swung out 65 deg
    hinge = wc + np.array([0, 0.56, 0.06])
    ang = np.radians(65)
    sd = np.array([0, -np.cos(ang), np.sin(ang)])  # down the shutter
    sn = np.array([0, np.sin(ang), np.cos(ang)])
    nb = 7
    for k in range(nb):
        x = -ww / 2 + (k + 0.5) * ww / nb
        board(m, "deco", hinge + np.array([x, 0, 0]), hinge + np.array([x, 0, 0]) + sd * 1.0, ww / nb - 0.01, 0.04, sn, TP["wood"], paint=paint, peel=0.3,
              nails=1, detail=0.8)
    for f in (0.2, 0.8):
        board(m, "deco", hinge + sd * f + sn * 0.035 + np.array([-ww / 2 + 0.05, 0, 0]), hinge + sd * f + sn * 0.035 + np.array([ww / 2 - 0.05, 0, 0]), 0.1,
              0.03, sn, TP["wood"], paint=trim, peel=0.3, nails=1, detail=0.5)
    post(m, "deco", wc + np.array([ww / 2 - 0.2, ledge_y - 1.46, 0.35]), hinge + sd * 0.95 + np.array([ww / 2 - 0.2, 0, 0]), 0.022, TP["wood_br"], square=False,
         detail=0.3)
    m.socket("counter", None, wc + np.array([0, ledge_y - 1.49 + 0.03, 0.25]))
    # inside the window: Walter's desk with charts, lamp, radio, ledger
    dk = np.array([wc[0], 0.0, 0.85])
    board(m, "deco", dk + (-0.75, 0.82, 0), dk + (0.75, 0.82, 0), 0.5, 0.05, (0, 1, 0), TP["wood_br"], nails=0, detail=0.6)
    for sx in (-1, 1):
        post(m, "deco", dk + (sx * 0.68, 0, -0.15), dk + (sx * 0.68, 0.8, -0.15), 0.035, TP["wood_dk"], detail=0.3)
    p = m.piece(color="#e5dcc3", gloss=20, merge="deco", res=0.008, detail=0.5)
    p.add(Box(dk + (-0.3, 0.86, -0.05), (0.25, 0.008, 0.18), euler((0, 12, 0)), round=0.004))
    p.add(Box(dk + (0.25, 0.87, 0.05), (0.18, 0.012, 0.13), euler((0, -8, 0)), round=0.004), color="#8a3b32")
    radio = m.piece(color="#6b4b35", gloss=80, merge="deco", res=0.008, detail=0.6)
    radio.add(Box(dk + (0.5, 1.0, -0.12), (0.17, 0.13, 0.1), round=0.04))
    radio.add(Sphere(dk + (0.45, 1.0, -0.01), 0.03), k=0.01, color=TP["brass"])
    radio.add(Sphere(dk + (0.57, 1.0, -0.01), 0.03), k=0.01, color=TP["brass"])
    radio.paint(Box(dk + (0.5, 1.06, 0.0), (0.12, 0.04, 0.05)), "#d8c9a0")
    lights.append(np.array(KP.hanging_lantern(m, T(dk + (-0.4, 2.3, -0.1)), merge="deco", glass="glass", drop=0.25, size=0.8)))
    # chart pinned on the back wall + a barometer
    ch = m.piece(color="#d9cfae", gloss=15, merge="deco", res=0.01, detail=0.4)
    ch.add(Box((0.4, 1.5, -HZ + 0.06), (0.55, 0.38, 0.01), euler((0, 0, 2)), round=0.004))
    ch.paint(Ellipsoid((0.3, 1.55, -HZ + 0.07), (0.25, 0.15, 0.05)), "#9fb1a6")
    ch.paint(Ellipsoid((0.65, 1.38, -HZ + 0.07), (0.12, 0.09, 0.05)), "#9fb1a6")
    # ship's wheel on the front wall between door and window
    wh, out = sh.at("front", 1.88, 1.55, 0.09)
    whp = m.piece(color=TP["wood_br"], gloss=70, merge="deco", res=0.008, lumps=0.002, detail=1.0)
    Rw = frame((1, 0, 0), out)
    whp.add(Torus(wh, 0.3, 0.035, Rw))
    whp.add(Cylinder(wh, 0.07, 0.05, frame(out, (0, 1, 0)) @ euler((0, 0, 90)), round=0.02), k=0.01, color=TP["brass"])
    for k in range(8):
        a = k * np.pi / 4 + 0.2
        d = np.array([np.cos(a), np.sin(a), 0.0])
        whp.add(Capsule(wh + d * 0.05, wh + d * 0.43, 0.02, 0.016), k=0.008)
        whp.add(Sphere(wh + d * 0.45, 0.028), k=0.008)
    # barometer by the window
    bp, out = sh.at("front", 4.35, 1.6, 0.06)
    bm = m.piece(color=TP["brass"], gloss=170, merge="deco", res=0.006, detail=0.5)
    bm.add(Cylinder(bp, 0.11, 0.025, frame(out, (0, 1, 0)) @ euler((0, 0, 90)), round=0.01))
    bm.paint(Sphere(bp + out * 0.03, 0.085), "#efe6cf")
    # lantern by the door
    lp, out = sh.at("front", 0.2, 2.2, 0.05)
    br = m.piece(color=TP["iron"], gloss=80, merge="deco", res=0.007, detail=0.3)
    br.add(Tube([lp, lp + out * 0.18 + np.array([0, 0.05, 0]), lp + out * 0.3]), 0.013, samples=4) if False else None
    br.add(Tube([lp, lp + out * 0.18 + np.array([0, 0.05, 0]), lp + out * 0.3], 0.013, samples=4))
    lights.append(np.array(KP.hanging_lantern(m, T(lp + out * 0.3), merge="deco", glass="glass", drop=0.1, size=0.85)))
    # life ring on the right wall (faces the pier)
    rp, out = sh.at("right", 2.9, 1.5, 0.02)
    KP.life_ring(m, T(rp, 90), merge="deco")

    # windows
    for side, s, wdt in (("back", 2.1, 0.8), ("right", 1.7, 0.6), ("left", 1.8, 0.6)):
        c, out = sh.at(side, s, 1.48, 0.02)
        lights.append(window(m, mg, c, out, wdt, 0.6, frame_color=trim, curtain="#b9a98a" if side != "back" else None, shutters=TP["teal_dk"] if side == "left" else None))

    # lookout cupola on the ridge with a fish weathervane
    cy = RIDGE - 0.15
    cu = m.piece(color=paint, merge="walls", res=0.012, lumps=0.003, detail=1.0)
    cu.add(Box((0, cy + 0.35, 0), (0.48, 0.38, 0.48), round=0.03))
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cu.sub(Box((sx * 0.48, cy + 0.42, sz * 0.48), (0.3 if sz else 0.06, 0.18, 0.06 if sz else 0.3), round=0.02), k=0.01, color=TP["iron"])
    cu.paint(band(cy + 0.66, cy + 0.8, 0, 1), trim)
    cu.paint(band(cy - 0.1, cy + 0.06, 0, 1), trim)
    gl = m.piece(color=TP["glass"], gloss=235, mat=1, merge="glass", res=0.012, ao=False, detail=0.3)
    gl.add(Box((0, cy + 0.42, 0), (0.44, 0.17, 0.44), round=0.02))
    cr = m.piece(color=TP["red_dk"], gloss=40, merge="roof", res=0.012, lumps=0.003, detail=0.8)
    cr.add(Box((0, cy + 0.78, 0), (0.6, 0.04, 0.6), round=0.03))
    cr.add(Capsule((0, cy + 0.8, 0), (0, cy + 1.1, 0), 0.45, 0.06), k=0.03)
    cr.paint(patches(3, 0.1, 5), TP["rust"], feather=0.01)
    vane = m.piece(color=TP["copper"], gloss=120, merge="roof", res=0.006, detail=0.6)
    vt = np.array([0, cy + 1.15, 0])
    vane.add(Capsule(vt, vt + (0, 0.5, 0), 0.014))
    vane.add(Ellipsoid(vt + (0.02, 0.48, 0), (0.24, 0.07, 0.015), euler((0, 20, 0))), k=0.01)
    vane.add(Ellipsoid(vt + (-0.22, 0.48, -0.08), (0.06, 0.08, 0.012), euler((0, 20, 0))), k=0.01)
    vane.add(Capsule(vt + (-0.12, 0.36, 0), vt + (0.12, 0.36, 0), 0.008), k=0.004)
    vane.add(Capsule(vt + (0, 0.36, -0.12), vt + (0, 0.36, 0.12), 0.008), k=0.004)
    vane.paint(patches(4, 0.0, 9), "#6f9a83", feather=0.01)  # verdigris
    smoke = stovepipe(m, "roof", (1.5, RIDGE - 0.55, -0.8), 1.0, lean=(0.08, -0.05))
    m.socket("smoke", None, smoke)

    # flagpole with a windsock on the porch corner
    fp = np.array([2.75, 0.0, 3.8])
    post(m, "deco", fp, fp + (0.05, 4.6, -0.03), 0.045, TP["white"], square=False, detail=0.5)
    ws = m.piece(color=TP["red"], gloss=40, merge="deco", res=0.008, lumps=0.003, detail=0.6)
    top = fp + (0.05, 4.4, -0.03)
    ws.add(Capsule(top + (0.08, 0, 0), top + (0.75, -0.25, 0.25), 0.13, 0.06))
    ws.sub(Capsule(top + (0.0, 0, 0), top + (0.8, -0.27, 0.27), 0.11, 0.045), k=0.01)
    ws.paint(Sphere(top + (0.32, -0.1, 0.1), 0.12), TP["white"], feather=0.01)
    ws.paint(Sphere(top + (0.62, -0.2, 0.2), 0.09), TP["white"], feather=0.01)
    m.socket("windsock", None, top + (0.08, 0, 0))

    # chalk forecast board on the porch, facing the street
    bc = np.array([-2.15, 0.0, 3.45])
    for sx in (-1, 1):
        post(m, "deco", bc + (sx * 0.55, 0, -0.06), bc + (sx * 0.55, 1.95, -0.06), 0.04, TP["wood_dk"], detail=0.5)
    bf = m.piece(color="#363d3f", gloss=30, merge="deco", res=0.01, lumps=0.0015, detail=1.0)
    bf.add(Box(bc + (0, 1.3, 0), (0.6, 0.45, 0.025), round=0.012))
    bf.add(Box(bc + (0, 1.3, -0.01), (0.66, 0.51, 0.02), round=0.02), color=TP["wood_br"])
    bf.paint(Box(bc + (0, 1.3, 0.03), (0.57, 0.42, 0.05)), "#3a4245")
    bf.paint(patches(2.5, 0.25, 33), "#596163", feather=0.02)  # chalk smudges
    for sx in (-1, 1):
        board(m, "deco", bc + (-0.68, 1.3 + sx * 0.53, 0.0), bc + (0.68, 1.3 + sx * 0.53, 0.0), 0.08, 0.05, (0, 0, 1), TP["wood"], paint=trim, peel=0.3, nails=1)
    # little roof over the board
    board(m, "deco", bc + (-0.75, 1.98, -0.1), bc + (0.75, 1.98, -0.1), 0.3, 0.035, (0, 1, 0.5), TP["wood_dk"], nails=1)
    # chalk ledge with chalk + a cloth
    board(m, "deco", bc + (-0.55, 0.82, 0.06), bc + (0.55, 0.82, 0.06), 0.08, 0.03, (0, 1, 0), TP["wood_br"], nails=0, detail=0.3)
    ck = m.piece(color="#f0ecdf", merge="deco", res=0.004, detail=0.2)
    ck.add(Capsule(bc + (0.2, 0.85, 0.07), bc + (0.28, 0.85, 0.08), 0.008))
    m.socket("board_text", None, bc + (0, 1.3, 0.04))

    # porch dressing: crab pots, barrel, rope coil, bench, buoys on the wall
    KP.crab_pot_stack(m, T((2.25, 0.0, -0.4 + 3.3), -80), merge="props", net="net", n=2)
    KP.barrel(m, T((-2.6, 0.0, 2.15), 0), merge="props")
    KP.rope_coil(m, T((-1.5, 0.0, 3.6), 30), merge="props")
    KP.bench(m, T((2.55, 0.0, 0.2), -90), merge="props", L=1.1)
    for i, z in enumerate((-1.2, -0.6)):
        bp, out = sh.at("left", 0.6 + i * 0.5, 1.75, 0.15)
        KP.painted_buoy(m, T(bp + np.array([0, -0.25, 0]), -90), merge="props")
    m.socket("walter", None, (0.85, 0.0, 1.15), (0, 0, 0))
    for i, l in enumerate(lights):
        if i < 2:
            m.socket(f"light_{i}", None, l)
        else:
            m.socket(f"win_{i - 2}", None, l)
    return m


MODELS["town/harbor_office"] = office
