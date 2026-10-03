"""Customer crabs. A red rock crab (broad fan-shaped brick-red carapace with a scalloped, toothed front edge, granular
bumps, black-tipped claws held up like a boxer) and a '_b' blue crab (olive shell with long lateral spines, blue legs
and claws with red fingertips, slimmer). 0.5 m to the brows.

Rig: carapace on head (eyestalks stalk_L/R > eye_L/R), claws on the arm chains, four pairs of walking legs: pair 1 on
leg_/knee_/foot_, pair 2 on leg2_, pairs 3 and 4 ride on leg_ and leg2_ so the gait alternates like a real crab's.
Hidden accessory pieces (acc_*) are little hats perched on the shell and a bow tie."""
import numpy as np
from clay import *
from kit import *
from kit_chars import *

VARIANTS = {
    "a": dict(name="cust_crab", shell="#ad3d27", shell_dk="#7d2b1c", shell_lt="#d9744a", under="#efc79a", legs="#c0502f", claw="#bf4a2c",
              tips="#1f1b1c", spines=False, width=1.0, claw_s=1.28, seed=1,
              acc=dict(bowler="#2b2a2e", flatcap="#7a6a4e", beanie=("#3d6f99", "#efe4cc", "#e4b33a"), bowtie=("#2e5a8c", "#f2ead6"))),
    "b": dict(name="cust_crab_b", shell="#5f6f4c", shell_dk="#3f4c33", shell_lt="#8a9663", under="#efe3c2", legs="#4a7fbf", claw="#3f73b8",
              tips="#d2442e", spines=True, width=0.92, claw_s=1.1, seed=2,
              acc=dict(bowler="#5a3a26", flatcap="#4d5a6b", beanie=("#c2552c", "#ecdcc0", "#3e6d8e"), bowtie=("#b23a33", "#f2ead6"))),
}

EYE_C = (0.05, 0.405, 0.17)
EYE_R = 0.033
STALK_B = (0.034, 0.31, 0.165)


def build_a():
    return build(VARIANTS["a"])


def build_b():
    return build(VARIANTS["b"])


MODELS = {"chars/cust_crab": build_a, "chars/cust_crab_b": build_b}


def build(V):
    m = Model(V["name"], res=0.006)
    m.weight_softness = 0.015
    w = V["width"]
    m.bone("root")
    m.bone("hips", "root", (0, 0.22, 0.0))
    m.bone("spine", "hips", (0, 0.235, 0.0))
    m.bone("chest", "spine", (0, 0.25, 0.0))
    m.bone("neck", "chest", (0, 0.26, 0.0))
    m.bone("head", "neck", (0, 0.27, 0.0))
    stalk_face_bones(m, EYE_C, EYE_R, STALK_B, brow_up=1.3, mouth_c=(0, 0.232, 0.17), hat_c=(0, 0.35, -0.055))
    claws_pts = {}
    for sx, s in ((-1, "L"), (1, "R")):
        pts = [(sx * 0.15 * w, 0.235, 0.12), (sx * 0.27 * w, 0.215, 0.19), (sx * 0.235 * w, 0.24, 0.285)]
        claws_pts[s] = pts
        m.bone(f"arm_{s}", "chest", pts[0])
        m.bone(f"elbow_{s}", f"arm_{s}", pts[1])
        m.bone(f"hand_{s}", f"elbow_{s}", pts[2])
    legs = {}
    for sx, s in ((-1, "L"), (1, "R")):
        L = []
        for j, z in enumerate((0.075, 0.005, -0.065, -0.125)):
            spread = 1.0 + 0.06 * j
            L.append([(sx * 0.165 * w, 0.215, z), (sx * 0.265 * w * spread, 0.285 - 0.008 * j, z * 1.3 + 0.01),
                      (sx * 0.33 * w * spread, 0.12, z * 1.55 + 0.015), (sx * 0.35 * w * spread, 0.004, z * 1.7 + 0.02)])
        legs[s] = L
        m.bone(f"leg_{s}", "hips", L[0][0])
        m.bone(f"knee_{s}", f"leg_{s}", L[0][1])
        m.bone(f"foot_{s}", f"knee_{s}", L[0][2])
        m.bone(f"leg2_{s}", "hips", L[1][0])

    body = carapace(m, V)
    f = body._eval_shape
    stalks(m, V)
    face(m, EYE_C, EYE_R, lid=V["shell"], brow_col="#3a1c18" if not V["spines"] else "#2a3020", look=(0, -0.03, 1), pupil_frac=0.55, toe_in=5,
         brow_kw=dict(length=1.6, thick=0.24, lift=1.3, tilt=2, forward=0.25),
         blush_c=(0.075, 0.232, 0.16), blush_r=0.018, blush_on=f, eye_budget=750)
    mp, mn = onsurf(f, [(0.0, 0.232, 0.25)])
    mouths(m, c=mp[0] + mn[0] * 0.002, w=0.064, lip="#5a1d18", normal=mn[0], lip_r=0.0045)
    claws(m, V, claws_pts)
    walking_legs(m, V, legs)
    accessories(m, V, f)
    budget(m, {"body": 7500, "stalk_*": 400, "claw_*": 3000, "leg_*": 2300, "leg2_*": 2300,
               "eyeball_*": 750, "lidhalf_*": 600, "lidclosed_*": 600, "eyehappy_*": 500, "pupil_*": 450, "brow_*": 350, "blush_*": 200,
               "mouth_*": 400, "acc_bowler": 1600, "acc_flatcap": 1800, "acc_beanie": 1800, "acc_bowtie": 900})

    m.socket("prop_R", "hand_R", (0.2 * w, 0.24, 0.42))
    m.socket("bust", "head", (0, 0.33, 0.23))
    m.socket("talk", "head", (0, 0.68, 0.0))
    return m


def carapace(m, V):
    w = V["width"]
    b = xpiece(m, "body", color=V["shell"], gloss=95, bone="head", res=0.0045, lumps=0.0018, lump_freq=12, dents=14, dent_size=0.025, dent_depth=0.002)
    # broad fan-shaped shield, front lifted so the face shows
    b.add(Ellipsoid((0, 0.275, 0.0), (0.24 * w, 0.08, 0.16), rot=(-10, 0, 0)), bone="head")
    b.add(Ellipsoid((0, 0.282, 0.06), (0.235 * w, 0.072, 0.115), rot=(-14, 0, 0)), k=0.04, bone="head")     # wide front
    b.add(Ellipsoid((0, 0.262, -0.09), (0.165 * w, 0.068, 0.1)), k=0.05, bone="head")                       # narrower back
    b.add(Ellipsoid((0, 0.215, 0.0), (0.16 * w, 0.055, 0.13)), k=0.04, bone="hips")                         # underside / sternum
    b.add(Ellipsoid((0, 0.235, 0.135), (0.1, 0.05, 0.05)), k=0.03, bone="head")                             # face / mouthparts
    # toothed front edge: a row of rounded teeth along the antero-lateral margin, a little notch between the eyes
    rim = []
    for t in np.linspace(0.12, 1.0, 9):
        a = t * np.radians(78)
        for sx in (-1, 1):
            rim.append((sx * np.sin(a) * 0.236 * w, 0.285 - 0.02 * t, 0.06 + np.cos(a) * 0.12 - 0.05 * t * t))
    rim = np.array(rim)
    f0 = b._eval_shape
    rim = snap(f0, rim, offset=-0.004)
    b.add(Segs(rim, rim, 0.017), k=0.008, bone="head")
    if V["spines"]:
        for sx in (-1, 1):                                                                                   # blue crab: long lateral spines
            a = np.array([sx * 0.2 * w, 0.278, 0.0])
            b.add(Capsule(a, a + np.array([sx * 0.12, 0.012, 0.01]), 0.02, 0.003), k=0.015, bone="head")
    for sx in (-1, 1):
        b.sub(Sphere((sx * 0.03, 0.315, 0.165), 0.018), k=0.008)                                           # orbits for the stalks
    f0 = b._eval_shape
    # the H-groove on the back, granular bumps, colour: darker centre, paler rim, cream underside and face
    for sx in (-1, 1):
        pts = surface_curve(f0, [(sx * 0.05, 0.36, 0.08), (sx * 0.07, 0.36, 0.0), (sx * 0.05, 0.35, -0.08)], 10)
        b.sub(Tube(pts, 0.0035), k=0.004)
    pts = surface_curve(f0, [(-0.06, 0.36, 0.0), (0.0, 0.362, 0.0), (0.06, 0.36, 0.0)], 8)
    b.sub(Tube(pts, 0.003), k=0.003)
    rng = np.random.default_rng(V["seed"])
    A = []
    for _ in range(60):
        A.append((rng.uniform(-0.2, 0.2) * w, 0.4, rng.uniform(-0.14, 0.15)))
    A = snap(f0, np.array(A))
    A = A[A[:, 1] > 0.28]
    b.add(Segs(A, A, rng.uniform(0.003, 0.0055, len(A))), k=0.003, color=V["shell_lt"], bone="head")
    b.paint(Ellipsoid((0, 0.33, -0.01), (0.15 * w, 0.06, 0.12)), V["shell_dk"], feather=0.04)
    b.paint(HalfSpace((0, 0.245, 0), (0, 1, 0)), V["under"], feather=0.02)
    b.paint(Ellipsoid((0, 0.235, 0.16), (0.09, 0.035, 0.04)), V["under"], feather=0.015)
    b.pattern(specks(70.0, 0.66, seed=V["seed"] + 4), V["shell_lt"])
    return b


def stalks(m, V):
    ex, ey, ez = EYE_C
    bx, by, bz = STALK_B
    for sx, s in ((-1, "L"), (1, "R")):
        st = xpiece(m, f"stalk_{s}", color=V["shell"], gloss=85, rigid=f"stalk_{s}", res=0.003, lumps=0.0008, lump_freq=30, mottle=0.04)
        a = np.array([sx * bx, by - 0.01, bz - 0.004])
        e = np.array([sx * ex, ey - EYE_R * 0.75, ez - 0.003])
        st.add(Tube([a, (a + e) / 2 + np.array([sx * 0.004, 0, 0.006]), e], [0.014, 0.011, 0.013], samples=6))
        st.add(Ellipsoid(e + np.array([0, 0.004, 0]), (0.019, 0.011, 0.019)), k=0.006)
        st.paint(Ellipsoid((a + e) / 2, (0.02, 0.005, 0.02)), V["shell_lt"], feather=0.003)


def claws(m, V, P):
    cs = V["claw_s"]
    for sx, s in ((-1, "L"), (1, "R")):
        a0, a1, a2 = [np.array(p) for p in P[s]]
        c = xpiece(m, f"claw_{s}", color=V["claw"], gloss=100, bone=f"hand_{s}", res=0.0036, lumps=0.0012, lump_freq=18, dents=5, dent_size=0.014, dent_depth=0.0015)
        jointed(c, [a0, a1, a2], [0.034 * cs, 0.032 * cs, 0.03 * cs], bones=[f"arm_{s}", f"elbow_{s}"], band=V["shell_lt"], bristles=4, bristle_col=shade(V["legs"], 0.86),
                seed=V["seed"] + (sx > 0))
        claw(c, a2, (-sx * 0.42, 0.18, 1.0), (sx * 0.15, 1.0, 0.0), 0.15 * cs, 0.095 * cs, 0.062 * cs, V["claw"], V["tips"], bone_hand=f"hand_{s}",
             gape=10 + 6 * (sx > 0), teeth=5, tubercles=26, tub_col=V["shell_lt"], seed=V["seed"] + 7 + int(sx), finger_col=V["claw"])


def walking_legs(m, V, legs):
    for sx, s in ((-1, "L"), (1, "R")):
        L = legs[s]
        # pairs 1 and 3: skinned along leg_/knee_/foot_ (pair 3 rides on the same chain, a beat behind visually)
        p = xpiece(m, f"leg_{s}", color=V["legs"], gloss=95, bone=f"foot_{s}", res=0.0034, lumps=0.0008, lump_freq=25, dents=4, dent_size=0.01, dent_depth=0.001)
        for j, bones in ((0, [f"leg_{s}", f"knee_{s}", f"foot_{s}"]), (2, [f"leg_{s}", f"leg_{s}", f"leg_{s}"])):
            jointed(p, L[j], [0.027, 0.025, 0.018, 0.0055], bones=bones, band=V["under"], tip=V["tips"] if V["spines"] else "#3a2420", tip_len=0.28,
                    bristles=3, bristle_col=shade(V["legs"], 0.86), seed=V["seed"] * 10 + j + int(sx))
        # pairs 2 and 4 on leg2_
        q = xpiece(m, f"leg2_{s}", color=V["legs"], gloss=95, rigid=f"leg2_{s}", res=0.0034, lumps=0.0008, lump_freq=25, dents=4, dent_size=0.01, dent_depth=0.001)
        for j in (1, 3):
            rad = [0.027, 0.025, 0.018, 0.0055] if j == 1 else [0.024, 0.022, 0.016, 0.005]
            if V["spines"] and j == 3:   # blue crab: the last pair are flat swimming paddles
                jointed(q, L[j][:3], rad[:3], band=V["under"], seed=V["seed"] * 10 + j)
                e = np.array(L[j][2])
                d = e - np.array(L[j][1])
                d /= np.linalg.norm(d)
                q.add(Squash(Ellipsoid(e + d * 0.04, (0.03, 0.05, 0.03), rot=look_rot(d)), e + d * 0.04, (1.0, 1.0, 0.35)), k=0.008)
            else:
                jointed(q, L[j], rad, band=V["under"], tip=V["tips"] if V["spines"] else "#3a2420", tip_len=0.28, bristles=3,
                        bristle_col=shade(V["legs"], 0.86), seed=V["seed"] * 10 + j + int(sx))


def accessories(m, V, f):
    A = V["acc"]
    up = np.array([0, 1.0, 0])
    s0, n0 = onsurf(f, [(0.0, 0.5, -0.055)])
    s0 = s0[0]
    acc_bowler(m, "acc_bowler", s0 + up * (0.25 * 0.1 - 0.006), 0.1, A["bowler"], tilt=(-12, 0, -10))
    acc_flatcap(m, "acc_flatcap", s0 + up * (0.42 * 0.115 - 0.008), 0.115, A["flatcap"], tilt=(-10, 0, 5))
    bc, cuff, pom = A["beanie"]
    acc_beanie(m, "acc_beanie", s0 + up * (0.55 * 0.1 - 0.006), 0.1, bc, cuff=cuff, pom=pom, tilt=(-12, 0, 8), stripe=pom)
    tc, dots = A["bowtie"]
    bp, bn = onsurf(f, [(0.0, 0.188, 0.25)])
    acc_bowtie(m, "acc_bowtie", bp[0] + bn[0] * 0.012, 0.05, tc, dots=dots, bone="chest", normal=bn[0])
