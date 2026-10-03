"""Customer gulls. A herring gull (white head and breast, silver-grey wings with black, white-spotted tips, a fat
yellow bill with the red gonys spot on the lower mandible, pale staring eyes with an orange ring, pink legs) and a
'_b' lesser black-backed gull (slate wings, yellow legs, red eye-ring, a touch plumper). 0.8 m.

Wings are the arm chains and hang flat at the sides with their span pointing down, so the ambient flock can rotate
arm_L/arm_R ~95 degrees about Z to spread them: the grey top faces up, the pale underwing faces down. Hidden accessory
pieces (acc_*) are hats and a scarf; the shop shows one at random."""
import numpy as np
from clay import *
from kit import *
from kit_chars import *

EYE_R = 0.028

VARIANTS = {
    "a": dict(name="cust_gull", white="#efece4", grey="#a9b0b8", grey_dk="#7f8791", tips="#202125", legs="#e9a3a0", beak="#f0c233",
              spot="#d8432c", sclera="#f2e8bf", ring="#e57b3e", plump=1.0, head=1.1, seed=1,
              acc=dict(beanie=("#2f6f9a", "#f1ead8", "#d84a3a"), bowler="#2b2a2e", scarf=("#c9442f", "#efe1c0"), souwester="#f2c12e")),
    "b": dict(name="cust_gull_b", white="#f1eee6", grey="#5b616d", grey_dk="#3c414b", tips="#18191c", legs="#e7bd3a", beak="#f2b52a",
              spot="#d23a2a", sclera="#f3e2a0", ring="#d64a33", plump=1.07, head=1.05, seed=2,
              acc=dict(beanie=("#c2552c", "#e9dcc0", "#3a6d8c"), bowler="#4a3424", scarf=("#2f6f6a", "#e8d9b4"), souwester="#e9a72d")),
}


def build_a():
    return build(VARIANTS["a"])


def build_b():
    return build(VARIANTS["b"])


MODELS = {"chars/cust_gull": build_a, "chars/cust_gull_b": build_b}


def build(V):
    m = Model(V["name"], res=0.006)
    m.weight_softness = 0.02
    pl, hs = V["plump"], V["head"]
    hy = 0.655
    biped_rig(m, hip_y=0.27, chest_y=0.45, neck_y=0.56, head_y=hy - 0.03, shoulder_x=0.135 * pl, shoulder_y=0.5, hand_y=0.27,
              hip_x=0.065, knee_y=0.12, foot_y=0.035, foot_z=0.03, elbow_out=0.035, head_z=0.03,
              tail=((0, 0.27, -0.14), (0, 0.24, -0.22)))
    for sx, sd in ((-1, "L"), (1, "R")):
        S, d = wing_line(V, sx)
        for nm, t in (("elbow", 0.17), ("hand", 0.29)):
            i = m.bone_index(f"{nm}_{sd}")
            m.bones[i] = (m.bones[i][0], m.bones[i][1], S + d * t)
    eye_c = (0.06 * hs, hy + 0.02, 0.112)
    face_bones(m, eye_c, EYE_R, brow_up=1.35, jaw_c=(0, hy - 0.022, 0.118), hat_c=(0, hy + 0.09 * hs, 0.02))

    body = plumage(m, V, hy)
    f = body._eval_shape
    beak(m, V, hy)
    face(m, eye_c, EYE_R, lid=V["white"], brow_col="#73777f", look=(0, -0.02, 1), pupil_frac=0.44, ring=V["ring"], toe_in=6,
         sclera=V["sclera"], brow_kw=dict(length=2.0, thick=0.27, lift=1.32, tilt=-12, forward=0.3),
         blush_c=(0.07 * hs, hy - 0.028, 0.09), blush_r=0.018, blush_on=f, eye_budget=800)
    wings(m, V)
    legs(m, V)
    accessories(m, V, hy, f)
    budget(m, {"body": 8500, "beak": 2600, "wing_*": 2600, "leg_*": 500, "foot_*": 700,
               "eyeball_*": 800, "lidhalf_*": 650, "lidclosed_*": 650, "eyehappy_*": 550, "pupil_*": 450, "brow_*": 400, "blush_*": 200,
               "acc_beanie": 2400, "acc_bowler": 1800, "acc_sou_wester": 2200, "acc_scarf": 2400})

    m.socket("prop_R", "hand_R", (0.2, 0.3, 0.06))
    m.socket("bust", "head", (0, hy - 0.005, 0.15))
    m.socket("talk", "head", (0, 1.0, 0.0))
    return m


def plumage(m, V, hy):
    pl, hs = V["plump"], V["head"]
    W = V["white"]
    b = xpiece(m, "body", color=W, gloss=45, bone="spine", res=0.0055, lumps=0.0022, lump_freq=9, dents=14, dent_size=0.028, dent_depth=0.0014, mottle=0.03)
    b.add(Ellipsoid((0, 0.39, -0.025), (0.148 * pl, 0.2, 0.158 * pl), rot=(10, 0, 0)), bone="spine")
    b.add(Ellipsoid((0, 0.43, 0.055), (0.128 * pl, 0.15, 0.11 * pl)), k=0.06, bone="chest")          # puffed breast
    b.add(Ellipsoid((0, 0.28, 0.0), (0.118 * pl, 0.095, 0.118 * pl)), k=0.06, bone="hips")
    b.add(Ellipsoid((0, 0.56, 0.015), (0.086, 0.08, 0.088)), k=0.06, bone="neck")
    b.add(Ellipsoid((0, hy + 0.006 * (hs - 1) * 10, 0.03), (0.1 * hs, 0.094 * hs, 0.108 + 0.02 * (hs - 1))), k=0.05, bone="head")
    b.add(Ellipsoid((0, hy + 0.012, 0.08), (0.074 * hs, 0.068 * hs, 0.07)), k=0.04, bone="head")   # forehead into the bill
    b.add(Ellipsoid((0, hy - 0.035, 0.07), (0.07 * hs, 0.045, 0.06)), k=0.03, bone="head")             # chin
    # tail: a white fan of three feathers, slightly lifted
    for i, dx in enumerate((-0.035, 0.0, 0.035)):
        b.add(Squash(Capsule((dx * 0.6, 0.27, -0.13), (dx * 1.4, 0.215 + abs(dx) * 0.3, -0.27 + abs(dx) * 0.4), 0.032, 0.026),
                     (0, 0.24, -0.2), (1.0, 0.45, 1.0)), k=0.02, bone="tail2" if i != 1 else "tail")
    for sx in (-1, 1):  # soft sockets for the eyes
        b.sub(Sphere((sx * 0.06 * hs, hy + 0.02, 0.112 + 0.004), EYE_R * 1.0), k=0.01)
    f0 = b._eval_shape
    # grey mantle across the back between the wings, darker eye smudge (a little stern)
    b.paint(Ellipsoid((0, 0.45, -0.12), (0.13 * pl, 0.13, 0.08)), V["grey"], feather=0.03)
    for sx in (-1, 1):
        b.paint(Ellipsoid((sx * 0.07 * hs, hy + 0.014, 0.075), (0.012, 0.008, 0.012)), "#c9c6c0", feather=0.008)
    # feathering: strokes over the head and neck, overlapping scallops on the breast, combed tail
    b.detail(strokes((0, 0.5, 0.0), (0.14, 0.26, 0.15), cells=22, length=0.9, width=0.0045, flow=(0, -1, -0.15), jitter=16, ridge=0.25,
                     region=Box((0, 0.42, 0), (0.3, 0.14, 0.3)), seed=V["seed"]),
             depth=0.0006, darken=0.0)
    b.detail(feathers((0, 0.4, 0.04), (0.14, 0.2, 0.15), cells=15, width=0.0038, flow=(0, -1, 0.1), size=0.6,
                      region=Ellipsoid((0, 0.4, 0.1), (0.11, 0.13, 0.08)), seed=V["seed"] + 3), depth=0.0009, darken=0.0)
    b.detail(combed((0, 0.24, -0.1), (0, 0.4, -1), n=40, sharp=3, wobble=0.3, wfreq=20, region=Ellipsoid((0, 0.24, -0.22), (0.08, 0.05, 0.08))),
             depth=0.0015, darken=0.06)
    return b


def beak(m, V, hy):
    Y = V["beak"]
    k = xpiece(m, "beak", color=Y, gloss=125, bone="head", res=0.0026, lumps=0.0005, lump_freq=30, mottle=0.025)
    # upper mandible: a laterally pressed sweep along the culmen, curving down into a hook that overhangs the lower
    up = Tube([(0, hy - 0.002, 0.128), (0, hy - 0.006, 0.18), (0, hy - 0.011, 0.222), (0, hy - 0.022, 0.244), (0, hy - 0.034, 0.248)],
              [0.025, 0.0165, 0.0135, 0.0095, 0.005], samples=6)
    k.add(Squash(up, (0, hy - 0.01, 0.2), (0.72, 1.0, 1.0)), bone="head")
    k.inter(Func(lambda P: np.where(P[:, 2] < 0.228, (hy - 0.0235) - P[:, 1], -1.0), (-1, -1, -1), (1, 1, 1)), k=0.003)   # flat cutting edge
    # lower mandible on the jaw: slimmer, with the angular gonys where the red spot sits
    lo = Tube([(0, hy - 0.026, 0.13), (0, hy - 0.028, 0.19), (0, hy - 0.035, 0.215), (0, hy - 0.029, 0.235)],
              [0.016, 0.0105, 0.0095, 0.0055], samples=6)
    k.add(Squash(lo, (0, hy - 0.03, 0.19), (0.78, 1.0, 1.0)), k=0.003, bone="jaw")
    k.inter(Func(lambda P: np.where((P[:, 2] < 0.238) & (P[:, 1] < hy - 0.018), P[:, 1] - (hy - 0.0225), -1.0), (-1, -1, -1), (1, 1, 1)), k=0.002)
    # the red spot on the gonys (both sides), nostril slits, pale horn tip, a warmer base
    k.paint(Ellipsoid((0, hy - 0.035, 0.214), (0.02, 0.0085, 0.011)), V["spot"], gloss=140, feather=0.0012)
    for sx in (-1, 1):
        k.sub(Capsule((sx * 0.0105, hy - 0.002, 0.163), (sx * 0.0085, hy - 0.005, 0.186), 0.0015), k=0.001, color="#c4932a")
    k.paint(Sphere((0, hy - 0.03, 0.249), 0.008), "#f4e7b8", feather=0.004)
    k.paint(Ellipsoid((0, hy, 0.13), (0.03, 0.03, 0.018)), shade(Y, 0.94), feather=0.01)


def wing_line(V, sx):
    """Folded wing: shoulder point and span direction (down and swept back ~34 degrees)."""
    x0 = sx * 0.136 * V["plump"]
    S = np.array([x0 + sx * 0.008, 0.5, -0.015])
    T = np.array([x0 * 0.9 + sx * 0.012, 0.15, -0.255])
    d = (T - S) / np.linalg.norm(T - S)
    return S, d


def wings(m, V):
    G, GD, TIP = V["grey"], V["grey_dk"], V["tips"]
    for sx, s in ((-1, "L"), (1, "R")):
        S, d = wing_line(V, sx)
        c = np.cross(d, np.array([1.0, 0, 0]))          # chord direction in the wing plane (towards the leading edge)
        if c[2] < 0:
            c = -c
        Rw = np.stack([np.array([1.0, 0, 0]), d, c], axis=1)     # local x = thickness, y = span, z = chord
        w = xpiece(m, f"wing_{s}", color=G, gloss=45, bone=f"elbow_{s}", res=0.0042, lumps=0.0015, dents=5, dent_size=0.02,
                   dent_depth=0.0012, mottle=0.03)
        # a flat paddle pressed against the side: inner wing on arm_, forearm on elbow_
        w.add(Ellipsoid(S + d * 0.085 - c * 0.005, (0.03, 0.105, 0.115), rot=Rw @ euler((0, 0, -sx * 3))), bone=f"arm_{s}")
        w.add(Ellipsoid(S + d * 0.205 - c * 0.02 - np.array([sx * 0.006, 0, 0]), (0.025, 0.11, 0.09), rot=Rw @ euler((0, 0, -sx * 4))), k=0.04, bone=f"elbow_{s}")
        # primaries: five long black feathers stacked along the chord, the leading one longest, white mirror spots
        for i in range(5):
            a = S + d * 0.25 + c * (0.045 - 0.025 * i) + np.array([sx * (0.006 - 0.003 * i), 0, 0])
            b = S + d * (0.47 - 0.025 * i) + c * (0.012 - 0.012 * i) + np.array([sx * (0.004 - 0.002 * i), 0, 0])
            fe = Squash(Capsule(a, b, 0.024 - 0.0015 * i, 0.011), (a + b) / 2, (0.42, 1.0, 1.0))
            w.add(fe, k=0.008, color=TIP, bone=f"hand_{s}")
            w.paint(Sphere(b - d * 0.022 + np.array([sx * 0.006, 0, 0]), 0.0085), "#f4f1ea", feather=0.003)
        # white trailing edge (secondaries) and a pale underwing on the body side
        w.paint(Ellipsoid(S + d * 0.15 - c * 0.105, (0.05, 0.14, 0.022), rot=Rw), "#ebe9e4", feather=0.01)
        w.paint(Func(lambda P, sx=sx, x0=S[0]: sx * (P[:, 0] - x0 + sx * 0.004), (-1, -1, -1), (1, 1, 1)), "#dddcd8", feather=0.008)
        # coverts: overlapping feather scallops; tool-scored scapular and tertial lines
        w.detail(feathers(S + d * 0.12, (0.04, 0.16, 0.13), cells=8, width=0.0036, flow=d, size=0.6,
                          region=Ellipsoid(S + d * 0.1 + np.array([sx * 0.02, 0, 0]), (0.06, 0.1, 0.12)), seed=V["seed"] + 8 + int(sx)),
                 depth=0.0014, darken=0.02)
        f = w._eval_shape
        pts = surface_curve(f, [S + d * 0.02 + c * 0.08 + np.array([sx * 0.04, 0, 0]), S + d * 0.12 + c * 0.085 + np.array([sx * 0.04, 0, 0]),
                                S + d * 0.22 + c * 0.06 + np.array([sx * 0.04, 0, 0])], 10)
        w.sub(Tube(pts, 0.0024), k=0.002, color=GD)
        for i in range(3):
            o = -0.03 - i * 0.03
            pts = surface_curve(f, [S + d * 0.1 + c * o + np.array([sx * 0.05, 0, 0]), S + d * 0.2 + c * (o - 0.01) + np.array([sx * 0.05, 0, 0]),
                                    S + d * 0.27 + c * (o - 0.02) + np.array([sx * 0.04, 0, 0])], 8)
            w.sub(Tube(pts, 0.002), k=0.002)


def legs(m, V):
    L = V["legs"]
    for sx, s in ((-1, "L"), (1, "R")):
        lg = xpiece(m, f"leg_{s}", color=L, gloss=70, bone=f"knee_{s}", res=0.0034, lumps=0.0008)
        lg.add(Capsule((sx * 0.065, 0.21, -0.005), (sx * 0.065, 0.12, 0.005), 0.02, 0.016), bone=f"leg_{s}")
        lg.add(Capsule((sx * 0.065, 0.12, 0.005), (sx * 0.065, 0.035, 0.025), 0.016, 0.0135), k=0.012, bone=f"knee_{s}")
        for y in (0.1, 0.08, 0.06):
            lg.sub(Torus((sx * 0.065, y, 0.012), 0.0135, 0.0016), k=0.0015)
        ft = xpiece(m, f"foot_{s}", color=L, gloss=70, rigid=f"foot_{s}", res=0.0034, lumps=0.0012, dents=3, dent_size=0.012)
        base = np.array([sx * 0.066, 0.016, 0.06])
        ft.add(Ellipsoid(base + (0, 0, -0.025), (0.026, 0.016, 0.03)))
        for t in (-1, 0, 1):
            tip = base + np.array([t * 0.05 + sx * 0.006, -0.006, 0.075 - abs(t) * 0.014])
            ft.add(Capsule(base + (0, 0, -0.01), tip, 0.011, 0.0075), k=0.014)
            ft.add(Sphere(tip + np.array([0, 0.002, 0.006]), 0.0058), k=0.003, color="#3a2c28", gloss=120)
        ft.add(Ellipsoid(base + (0, -0.006, 0.04), (0.05, 0.006, 0.04)), k=0.012)
        ft.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.002)


def accessories(m, V, hy, f):
    hs = V["head"]
    A = V["acc"]
    top = np.array([0, hy + 0.06 * (hs - 1) + 0.092 * hs, 0.024])
    bc, cuff, pom = A["beanie"]
    acc_beanie(m, "acc_beanie", top, 0.1 * hs, bc, cuff=cuff, pom=pom, tilt=(-8, 0, 6), stripe=pom)
    acc_bowler(m, "acc_bowler", top + np.array([0, 0.005, -0.005]), 0.098 * hs, A["bowler"], tilt=(-6, 0, -9))
    acc_souwester(m, "acc_sou_wester", top + np.array([0, 0.004, -0.01]), 0.1 * hs, A["souwester"], tilt=(-6, 0, 0))
    sc, st = A["scarf"]
    nc = np.array([0, 0.585, 0.02])
    r_mean, r_max = neck_fit(f, nc)
    acc_scarf(m, "acc_scarf", nc, r_max + 0.012, 0.026, sc, stripe=st, tail_side=-1.0, drop=0.17)
