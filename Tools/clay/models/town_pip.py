"""
Pip's house — Gran's tiny shack on crooked stilts over the water: steep front gable with the door (socket `door`),
a round porthole window, crooked stone-and-tin chimney, a porch with a bench, boots, rod and buoys, a dinghy tied
below. Mustard paint (Pip's sou'wester yellow) faded and peeling, rusty-red patched tin roof.

Local frame: house |x| <= 1.6, |z| <= 1.3, porch z 1.3..2.5, platform x -2.1..2.1, z -1.8..2.5, floor y = 0, front +Z.
Placed at (22.1, 1.8, 8.2) yaw -90: the porch edge (z = 2.5) meets the boardwalk at world x = 19.6.
"""
import numpy as np
from kit_town import *
import kit_props as KP

MODELS = {}
HX, HZ, EAVE, RIDGE = 1.6, 1.3, 2.25, 3.75
SEA = -1.8


def pip_house():
    m = TownModel("pip_house", budget=52000)
    rng = m.rng
    mg = dict(trim="trim", glass="glass", deco="deco", door="trim")
    paint, trim = TP["mustard"], TP["cream"]

    # platform: deck + crooked stilts with braces, a ladder down to the dinghy
    deck(m, "floor", -2.1, 2.1, -1.8, 2.5, 0.0, along="x", pw=(0.18, 0.26), t=0.075, nails=1)
    for x in (-1.75, 0.0, 1.75):
        post(m, "floor", (x, -0.15, -1.75), (x, -0.15, 2.45), 0.085, TP["wood_dk"], detail=0.5)
    for z in (-1.6, 0.4, 2.3):
        post(m, "floor", (-2.15, -0.3, z), (2.15, -0.3, z), 0.1, TP["wood_dk"], detail=0.5)
    tops = []
    for x in (-1.85, 0.0, 1.85):
        for z in (-1.6, 0.4, 2.3):
            top = (x + rng.normal() * 0.04, -0.35, z + rng.normal() * 0.04)
            piling(m, "piles", top, -5.0, rng.uniform(0.12, 0.16), lean=(rng.normal() * 0.18, rng.normal() * 0.18), sea_y=SEA, barnacles=9, detail=1.3)
            tops.append(top)
    for x in (-1.85, 1.85):
        board(m, "floor", (x + 0.15, -0.5, -1.6), (x + 0.15, -1.6, 2.3), 0.15, 0.06, (1, 0, 0), TP["wood_dk"], nails=0, detail=0.4, knot=0)
    board(m, "floor", (-1.85, -0.5, 2.45), (1.85, -1.5, 2.45), 0.15, 0.06, (0, 0, 1), TP["wood_dk"], nails=0, detail=0.4, knot=0)
    # porch rails on the sides; the front stays open to the boardwalk
    for sx in (-1, 1):
        rail_run(m, "floor", [(sx * 2.03, 0, -1.75), (sx * 2.03, 0, 2.45)], h=0.82, post_every=1.4, foot_y=-0.3)
    rail_run(m, "floor", [(-2.03, 0, -1.75), (2.03, 0, -1.75)], h=0.82, post_every=1.4, foot_y=-0.3, start_post=False, end_post=False)

    # body: steep front gable, door in the middle-left, porthole up in the gable
    door_s = (0.75, 1.65)
    ops = {"front": [(door_s[0], door_s[1], -1, 1.95), (2.2, 2.85, 1.0, 1.7)],
           "right": [(0.8, 1.55, 1.05, 1.75)],
           "left": [(0.9, 1.6, 1.05, 1.75)],
           "back": [(1.25, 1.95, 1.1, 1.75)]}
    sh = Shack(m, HX, HZ, EAVE, RIDGE, ridge="z", walls="h", colors=[TP["wood"], TP["wood_lt"]], paint=paint, peel=0.3, trim=trim,
               openings=ops, roof="tin", roof_colors=[TP["red"], TP["red_dk"], TP["rust"]], rust=0.35, sag=0.08, ov=0.32, ov_gable=0.55,
               lean=0.0)
    lights = []
    dc, out = sh.at("front", sum(door_s) / 2, 0.0, 0.0)
    door(m, mg, dc, out, 0.82, 1.92, paint=TP["teal"], peel=0.3, trim=trim, crooked=-1.5)
    m.socket("door", None, dc + out * 0.12 + np.array([0, 0.0, 0]), (0, 0, 0))
    # porthole in the gable (round brass ring + glass)
    pc, out = sh.at("front", HX, 2.75, 0.06)
    po = m.piece(color=TP["brass"], gloss=170, merge="deco", res=0.007, lumps=0.0015, detail=1.0)
    Rp = frame((1, 0, 0), out)
    po.add(Torus(pc, 0.2, 0.045, Rp))
    for k in range(6):
        a = k * np.pi / 3
        po.add(Sphere(pc + np.array([np.cos(a) * 0.2, np.sin(a) * 0.2, 0.0]) + out * 0.04, 0.016), k=0.004)
    g = m.piece(color=TP["glass"], gloss=235, mat=1, merge="glass", res=0.008, ao=False, detail=0.3)
    g.add(Cylinder(pc - out * 0.02, 0.17, 0.02, frame(out, (0, 1, 0)) @ euler((0, 0, 90))))
    lights.append(pc)
    # windows
    for side, s, w_ in (("front", 2.52, 0.55), ("right", 1.18, 0.55), ("left", 1.25, 0.55), ("back", 1.6, 0.55)):
        c, out = sh.at(side, s, 1.38, 0.02)
        lights.append(window(m, mg, c, out, w_, 0.58, frame_color=trim, curtain="#c2574b" if side == "front" else "#d8c8a4",
                             shutters=TP["teal"] if side in ("front", "left") else None, panes=(2, 2)))
    # flower box under the front window
    c, out = sh.at("front", 2.52, 1.0, 0.03)
    KP.flower_box(m, T(c, 0), merge="props", L=0.7)
    # crooked chimney: stone base on the right side, tin pipe on top, leaning
    ch_base = np.array([HX + 0.28, -0.05, -0.35])
    smoke = stone_chimney(m, "roof", ch_base, 3.2, w=0.46, lean=0.06)
    pipe_top = stovepipe(m, "roof", smoke + np.array([0, -0.18, 0]), 0.7, r=0.09, lean=(0.12, 0.05))
    m.socket("smoke", None, pipe_top)
    # lantern by the door
    lp, out = sh.at("front", door_s[1] + 0.18, 2.05, 0.05)
    br = m.piece(color=TP["iron"], gloss=80, merge="deco", res=0.007, detail=0.3)
    br.add(Tube([lp, lp + out * 0.16 + np.array([0, 0.05, 0]), lp + out * 0.28], 0.013, samples=4))
    lights.insert(0, np.array(KP.hanging_lantern(m, T(lp + out * 0.28), merge="deco", glass="glass", drop=0.1, size=0.8)))
    # house number plaque / gran's horseshoe over the door
    hs = m.piece(color=TP["iron"], gloss=90, merge="deco", res=0.006, detail=0.3)
    hc = dc + out * 0.07 + np.array([0, 2.12, 0])
    hs.add(Torus(hc, 0.07, 0.014, frame((1, 0, 0), out)))
    hs.sub(Box(hc + np.array([0, -0.06, 0]), (0.05, 0.05, 0.05)), k=0.005)

    # porch dressing
    KP.bench(m, T((-1.1, 0.0, 1.95), 180), merge="props", L=1.0)
    KP.flower_pot(m, T((1.75, 0.0, 2.25), 20), merge="props")
    KP.flower_pot(m, T((1.45, 0.0, 2.35), 50), merge="props", kind="thrift", r=0.1)
    KP.barrel(m, T((1.7, 0.0, 1.55), 10), merge="props", h=0.72, r=0.24)
    # rain barrel under the eave on the left
    KP.barrel(m, T((-1.85, 0.0, 0.7), 0), merge="props", h=0.7, r=0.25, lid=False)
    # boots by the door
    for i, x in enumerate((0.35, 0.55)):
        b = m.piece(color="#2f3a3e", gloss=150, merge="props", res=0.007, lumps=0.002, detail=0.4)
        bc = np.array([x, 0.0, 1.55 + i * 0.05])
        b.add(Capsule(bc + (0, 0.05, 0), bc + (0, 0.32, -0.02), 0.06, 0.055))
        b.add(Ellipsoid(bc + (0, 0.05, 0.07), (0.06, 0.05, 0.12)), k=0.03)
        b.paint(band(0.29, 0.4, 0, 1), TP["red"])
    # fishing rod leaning on the wall + net
    rod = m.piece(color=TP["wood_br"], gloss=90, merge="props", res=0.006, detail=0.3)
    rod.add(Capsule((1.05, 0.02, 1.38), (1.35, 2.3, 1.36), 0.016, 0.007))
    rod.add(Cylinder((1.1, 0.45, 1.39), 0.04, 0.03, look_rot((0.13, 1, 0)), round=0.01), k=0.01, color=TP["iron"])
    # buoys hung on the left wall
    for i in range(2):
        bp, out = sh.at("left", 0.25 + i * 0.35, 1.7 - i * 0.1, 0.14)
        KP.painted_buoy(m, T(bp, -90), merge="props")
    KP.life_ring(m, T(sh.at("right", 2.15, 1.55, 0.02)[0], 90), merge="props")

    # dinghy tied to the stilts below the porch (floats at y = SEA)
    dz = np.array([0.2, SEA + 0.05, 3.6])
    hull = m.piece(color=TP["teal_dk"], gloss=80, merge="boat", res=0.012, lumps=0.003, dents=5, detail=1.4)
    Rb = euler((0, 82, -4))
    gun = dz + np.array([0, 0.28, 0])
    hull.add(Rowboat(gun, 1.45, 0.62, 0.42, Rb))
    hull.paint(below(SEA + 0.07, 0.02, 3), TP["red_dk"])
    hull.paint(band(SEA + 0.2, SEA + 0.3, 0, 1), TP["cream"])
    hull.paint(Func(lambda P: (P - gun) @ Rb[:, 1] + 0.05, (-99,) * 3, (99,) * 3), TP["wood_br"], feather=0.01)
    hull.add(Tube([gun + Rb @ np.array([sx, 0.0, z]) for sx, z in ((0.0, -1.42), (0.55, -1.0), (0.62, 0.0), (0.42, 0.9), (0.0, 1.43))], 0.03, samples=4), k=0.01,
             color=TP["wood_dk"])
    hull.add(Tube([gun + Rb @ np.array([sx, 0.0, z]) for sx, z in ((0.0, -1.42), (-0.55, -1.0), (-0.62, 0.0), (-0.42, 0.9), (0.0, 1.43))], 0.03, samples=4), k=0.01,
             color=TP["wood_dk"])
    for k in (-0.5, 0.3):
        bc = gun + Rb @ np.array([0, -0.14, k])
        board(m, "boat", bc + Rb @ np.array([-0.55, 0, 0]), bc + Rb @ np.array([0.55, 0, 0]), 0.18, 0.035, Rb @ np.array([0, 1.0, 0]), TP["wood"], nails=1, detail=0.4)
    oar = m.piece(color=TP["wood_lt"], gloss=50, merge="boat", res=0.008, detail=0.3)
    oar.add(Capsule(gun + Rb @ np.array([-0.3, -0.12, -0.9]), gun + Rb @ np.array([0.2, -0.1, 0.9]), 0.02))
    oar.add(Ellipsoid(gun + Rb @ np.array([0.24, -0.1, 1.05]), (0.07, 0.015, 0.18), Rb), k=0.01)
    rope(m, "boat", [gun + Rb @ np.array([0, 0.0, 1.3]), (0.6, SEA + 0.6, 2.8), (0.0, -0.35, 2.32)], 0.014, detail=0.3)
    # ladder down from the porch side
    for sx in (-1, 1):
        post(m, "floor", (2.2, 0.55, 1.3 + sx * 0.22), (2.28, SEA - 0.3, 1.3 + sx * 0.22), 0.03, TP["wood_dk"], detail=0.4)
    for y in np.arange(SEA - 0.1, 0.4, 0.32):
        post(m, "floor", (2.24, y, 1.06), (2.24, y, 1.54), 0.02, TP["wood"], square=False, detail=0.3)

    for i, l in enumerate(lights):
        if i == 0:
            m.socket("light_0", None, l)
        else:
            m.socket(f"win_{i - 1}", None, l)
    m.socket("porch", None, (0.0, 0.0, 2.1), (0, 0, 0))
    return m


MODELS["town/pip_house"] = pip_house
