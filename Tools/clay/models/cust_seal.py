"""Customer seals. A harbour seal standing up on its hind flippers like a fat grey sack of flour: silver-grey with
dark spots, a paler belly, a round head with a dog-like muzzle, whisker pads with rolled clay whiskers, V nostrils and
big dark eyes; short front flippers (arms) with little dark claws. '_b' is the dark colour morph (dark brown-grey with
pale ring spots), a little plumper with a longer muzzle. 1.1 m.

Hidden accessory pieces (acc_*): flat cap, bowler, sou'wester, knitted scarf and a bow tie."""
import numpy as np
from clay import *
from kit import *
from kit_chars import *

VARIANTS = {
    "a": dict(name="cust_seal", base="#7a7f87", back="#585d65", belly="#b2b0a9", spot="#33363c", ring=None, muzzle="#a3a19b",
              flip="#555a61", plump=1.0, snout=1.0, seed=1,
              acc=dict(flatcap="#7b6b4d", bowler="#2b2a2e", souwester="#f2c12e", scarf=("#2f6f9a", "#efe4cc"), bowtie=("#a8323a", "#f2ead6"))),
    "b": dict(name="cust_seal_b", base="#55504c", back="#3e3a37", belly="#8a837b", spot="#2c2927", ring="#857d74", muzzle="#7a736b",
              flip="#3e3a37", plump=1.06, snout=1.12, seed=2,
              acc=dict(flatcap="#5b6a78", bowler="#4a3424", souwester="#e9a72d", scarf=("#c2552c", "#ecdcc0"), bowtie=("#2e5a8c", "#f2ead6"))),
}

EYE_R = 0.04


def build_a():
    return build(VARIANTS["a"])


def build_b():
    return build(VARIANTS["b"])


MODELS = {"chars/cust_seal": build_a, "chars/cust_seal_b": build_b}


def build(V):
    m = Model(V["name"], res=0.008)
    m.weight_softness = 0.03
    pl = V["plump"]
    biped_rig(m, hip_y=0.24, chest_y=0.56, neck_y=0.78, head_y=0.9, shoulder_x=0.2 * pl, shoulder_y=0.62, hand_y=0.46,
              hip_x=0.11, knee_y=0.09, foot_y=0.035, foot_z=-0.06, elbow_out=0.06, head_z=0.04,
              tail=((0, 0.12, -0.2), (0, 0.06, -0.28)))
    eye_c = (0.075, 0.955, 0.168)
    face_bones(m, eye_c, EYE_R, brow_up=1.35, mouth_c=(0, 0.835, 0.25), hat_c=(0, 1.06, 0.04))

    body = sack(m, V, eye_c)
    f = body._eval_shape
    snout(m, V, f)
    face(m, eye_c, EYE_R, lid=V["base"], brow_col=shade(V["back"], 0.7), look=(0, -0.03, 1), pupil_frac=0.68, toe_in=5,
         brow_kw=dict(length=1.5, thick=0.2, lift=1.36, tilt=7, forward=0.25),
         blush_c=(0.12, 0.865, 0.16), blush_r=0.03, blush_on=f, eye_budget=850)
    mp, mn = onsurf(f, [(0.0, 0.832, 0.32)])
    mouths(m, c=mp[0] + mn[0] * 0.003, w=0.082, lip="#3a2a2a", normal=mn[0], lip_r=0.006)
    flippers(m, V)
    accessories(m, V, f)
    budget(m, {"body": 12500, "muzzle": 1600, "nose": 500, "whiskers": 900, "flipper_*": 1300, "hindflipper_*": 1000,
               "eyeball_*": 850, "lidhalf_*": 700, "lidclosed_*": 700, "eyehappy_*": 600, "pupil_*": 500, "brow_*": 400, "blush_*": 200,
               "mouth_*": 420, "acc_flatcap": 1500, "acc_bowler": 1400, "acc_sou_wester": 1700, "acc_scarf": 1800, "acc_bowtie": 700})

    m.socket("prop_R", "hand_R", (0.27 * pl, 0.38, 0.14))
    m.socket("bust", "head", (0, 0.9, 0.3))
    m.socket("talk", "head", (0, 1.4, 0.03))
    return m


BODY = None


def sack(m, V, eye_c):
    pl = V["plump"]
    b = xpiece(m, "body", color=V["base"], gloss=85, bone="spine", res=0.0065, lumps=0.0024, lump_freq=6, dents=16, dent_size=0.045, dent_depth=0.0028)
    b.add(Ellipsoid((0, 0.235, -0.03), (0.225 * pl, 0.245, 0.23 * pl)), bone="hips")                 # bottom of the sack
    b.add(Ellipsoid((0, 0.5, 0.015), (0.238 * pl, 0.27, 0.222 * pl)), k=0.1, bone="spine")           # big round belly
    b.add(Ellipsoid((0, 0.75, 0.03), (0.18 * pl, 0.15, 0.17 * pl)), k=0.09, bone="chest")            # shoulders
    b.add(Ellipsoid((0, 0.915, 0.05), (0.16, 0.148, 0.158)), k=0.08, bone="head")                    # round head
    b.add(Ellipsoid((0, 0.06, -0.21), (0.11, 0.055, 0.12), rot=(-15, 0, 0)), k=0.07, bone="tail")    # tail end between the flippers
    b.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.01)                                               # sits flat on the table
    for sx in (-1, 1):
        b.sub(Sphere((sx * eye_c[0], eye_c[1], eye_c[2] + 0.004), EYE_R * 1.03), k=0.014)
        # brow ridges over the eyes
        b.add(Ellipsoid((sx * (eye_c[0] + 0.005), eye_c[1] + EYE_R * 0.7, eye_c[2] - 0.005), (EYE_R * 1.2, EYE_R * 0.45, EYE_R * 0.9), rot=(-15, sx * 15, sx * 8)),
              k=0.015, bone="head")
    f0 = b._eval_shape
    # neck roll, belly creases (tool-scored)
    pts = surface_curve(f0, [(-0.17, 0.79, 0.06), (0.0, 0.775, 0.2), (0.17, 0.79, 0.06)], 16)
    b.sub(Tube(pts, 0.006), k=0.008)
    for i, y in enumerate((0.36, 0.31)):
        pts = surface_curve(f0, [(-0.15, y + 0.02, 0.15), (0.0, y, 0.24 - 0.01 * i), (0.15, y + 0.02, 0.15)], 12)
        b.sub(Tube(pts, 0.0045), k=0.006)
    # colour: darker back, pale belly and throat, spots
    b.paint(Ellipsoid((0, 0.55, -0.16), (0.26 * pl, 0.5, 0.14)), V["back"], feather=0.08)
    b.paint(Ellipsoid((0, 0.45, 0.17), (0.17 * pl, 0.34, 0.1)), V["belly"], feather=0.07)
    b.paint(Ellipsoid((0, 0.8, 0.14), (0.11, 0.07, 0.07)), V["belly"], feather=0.05)
    rng = np.random.default_rng(V["seed"] + 20)
    P, R = [], []
    while len(P) < 46:
        y = rng.uniform(0.08, 1.02)
        a = rng.uniform(-np.pi, np.pi)
        if abs(a) < 0.5 and 0.7 < y < 1.0:   # keep the face clean
            continue
        P.append((np.sin(a) * 0.4, y, 0.02 + np.cos(a) * 0.4))
        R.append(rng.uniform(0.018, 0.034) * (1.2 if abs(a) > 1.6 else 1.0))
    P = snap(f0, np.array(P))
    R = np.array(R)
    # irregular spots: each a small cluster of 2-3 dabs
    A, RR = [P], [R]
    for _ in range(2):
        A.append(P + rng.normal(0, 0.012, P.shape))
        RR.append(R * rng.uniform(0.55, 0.8, len(R)))
    A = snap(f0, np.vstack(A))
    RR = np.concatenate(RR)
    # spots are thin dabs of a different clay pressed on: a hair proud of the skin, so their round edges survive
    # decimation (vertex colour alone breaks into shards on big triangles)
    spots = Segs(A, A, RR)
    b.paint(spots, V["ring"] if V["ring"] is not None else V["spot"], feather=0.004)
    b.detail(lambda P: -np.clip(-spots(P) / 0.003, 0, 1), depth=0.0016, darken=0.0)
    return b


def snout(m, V, f):
    s = V["snout"]
    mz = xpiece(m, "muzzle", color=V["muzzle"], gloss=70, rigid="head", res=0.0045, lumps=0.0012, dents=4, dent_size=0.02, dent_depth=0.0015)
    z0 = 0.175
    for sx in (-1, 1):                                                                   # whisker pads
        mz.add(Ellipsoid((sx * 0.043, 0.865, z0 + 0.05 * s), (0.055, 0.045, 0.05), rot=(0, sx * 12, sx * -8)), k=0.02)
    mz.add(Ellipsoid((0, 0.89, z0 + 0.025 * s), (0.068, 0.045, 0.06 * s)), k=0.03)                 # bridge of the nose
    mz.add(Ellipsoid((0, 0.828, z0 + 0.02 * s), (0.052, 0.028, 0.05)), k=0.025)                    # chin
    mz.sub(Capsule((0, 0.875, z0 + 0.1 * s), (0, 0.835, z0 + 0.095 * s), 0.006), k=0.006)        # philtrum groove
    fz = mz._eval_shape
    for sx in (-1, 1):                                                                   # whisker follicle rows
        for row, (y, n) in enumerate(((0.882, 3), (0.866, 4), (0.85, 4))):
            for i in range(n):
                q = snap(fz, [(sx * (0.024 + i * 0.016 + row * 0.004), y, 0.4)])[0]
                mz.sub(Sphere(q, 0.003), k=0.0015, color=shade(V["muzzle"], 0.7))
    mz.paint(Ellipsoid((0, 0.84, z0 + 0.03), (0.06, 0.025, 0.05)), shade(V["muzzle"], 1.06), feather=0.02)
    nose = xpiece(m, "nose", color="#1f1d1f", gloss=200, rigid="head", res=0.0032, lumps=0.0005, mottle=0.03)
    nc = snap(fz, [(0, 0.905, 0.4)])[0]
    for sx in (-1, 1):                                                                   # V-shaped nostrils
        a = nc + np.array([sx * 0.006, 0.006, -0.004])
        b = nc + np.array([sx * 0.024, -0.008, -0.006])
        nose.add(Capsule(a, b, 0.0085, 0.006), k=0.004)
    nose.add(Sphere(nc + np.array([0, 0.0, 0.002]), 0.009), k=0.006)
    nose.add(Sphere(nc + np.array([-0.008, 0.008, 0.006]), 0.0035), k=0.002, color="#6a6668", gloss=255)
    w = m.piece("whiskers", color="#ebe6d8", gloss=80, rigid="head", res=0.0026, lumps=0.0, mottle=0.03, ao=False)
    for sx in (-1, 1):
        for i, (y, ang, ln) in enumerate(((0.876, 16, 0.15), (0.864, 4, 0.17), (0.852, -8, 0.16), (0.842, -18, 0.13))):
            a = snap(fz, [(sx * 0.06, y, 0.4)])[0]
            d = np.array([sx * np.cos(np.radians(ang)), np.sin(np.radians(ang)), 0.35])
            d /= np.linalg.norm(d)
            mid = a + d * ln * 0.55 + np.array([0, 0.01, 0])
            end = a + d * ln + np.array([0, -0.014, -0.012])
            w.add(Tube([a, mid, end], [0.0034, 0.0027, 0.0015], samples=6), k=0.002)


def flippers(m, V):
    pl = V["plump"]
    F = V["flip"]
    for sx, s in ((-1, "L"), (1, "R")):
        fl = xpiece(m, f"flipper_{s}", color=F, gloss=75, bone=f"hand_{s}", res=0.0045, lumps=0.002, dents=5, dent_size=0.02, dent_depth=0.0018)
        sh = np.array([sx * 0.2 * pl, 0.62, 0.06])
        el = np.array([sx * 0.245 * pl, 0.53, 0.1])
        wr = np.array([sx * 0.258 * pl, 0.46, 0.12])
        fl.add(Capsule(sh, el, 0.058, 0.05), bone=f"arm_{s}")
        fl.add(Capsule(el, wr, 0.05, 0.044), k=0.03, bone=f"elbow_{s}")
        # the flat paddle: broad, pressed thin side to side, five dark claws along the tip
        pc = wr + np.array([sx * 0.006, -0.055, 0.02])
        fl.add(Ellipsoid(pc, (0.03, 0.085, 0.08), rot=(18, 0, sx * -10)), k=0.03, bone=f"hand_{s}")
        for i in range(5):
            t = (i - 2) / 2.0
            c = pc + np.array([sx * 0.006, -0.074 + abs(t) * 0.018, t * 0.05 + 0.02])
            fl.add(Ellipsoid(c, (0.009, 0.012, 0.007)), k=0.004, color="#2a2523", gloss=140, bone=f"hand_{s}")
            if i < 4:
                g = pc + np.array([sx * 0.026, -0.01, (t + 0.25) * 0.048])
                fl.sub(Capsule(g + np.array([0, 0.05, 0]), g + np.array([0, -0.07, 0.0]), 0.0032), k=0.003)
        fl.paint(Ellipsoid(pc + np.array([-sx * 0.025, 0, 0]), (0.02, 0.09, 0.07)), shade(F, 0.8), feather=0.015)
        fl.detail(strokes((sh + el) / 2, (0.06, 0.12, 0.06), cells=8, length=0.8, width=0.005, flow=(0, -1, 0), ridge=0.25, seed=3 + int(sx)), depth=0.0008, darken=0.0)

        # hind flippers: two webbed fans spread out behind on the table
        hf = xpiece(m, f"hindflipper_{s}", color=F, gloss=75, rigid=f"foot_{s}", res=0.0045, lumps=0.0018, dents=4, dent_size=0.02, dent_depth=0.0015)
        root = np.array([sx * 0.1, 0.05, -0.17])
        tip_c = np.array([sx * 0.2, 0.022, -0.38])
        d = tip_c - root
        L = np.linalg.norm(d)
        d /= L
        side = np.cross(np.array([0, 1.0, 0]), d)
        hf.add(Capsule(root, root + d * L * 0.4, 0.05, 0.035))
        for i in range(5):
            t = (i - 2) / 2.0
            a = root + d * L * 0.25 + side * t * 0.02
            b = root + d * L * (1.0 - 0.12 * abs(t)) + side * t * 0.075 + np.array([0, -0.004, 0])
            hf.add(Capsule(a, b, 0.024, 0.016), k=0.02)
            hf.add(Ellipsoid(b + d * 0.012, (0.008, 0.006, 0.01)), k=0.003, color="#2a2523", gloss=140)
        hf.add(Squash(Ellipsoid(root + d * L * 0.62, (0.075, 0.05, 0.11), rot=look_rot(d) @ euler((90, 0, 0))), root + d * L * 0.62, (1.0, 0.35, 1.0)), k=0.02)
        hf.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.003)
        hf.paint(HalfSpace((0, 0.025, 0), (0, 1, 0)), shade(F, 0.8), feather=0.01)


def accessories(m, V, f):
    A = V["acc"]
    top = snap(f, [(0.0, 1.2, 0.04)])[0]
    acc_flatcap(m, "acc_flatcap", top + np.array([0, -0.004, 0.0]), 0.15, A["flatcap"], tilt=(-6, 0, 5))
    acc_bowler(m, "acc_bowler", top + np.array([0, 0.004, -0.01]), 0.13, A["bowler"], tilt=(-6, 0, -9))
    acc_souwester(m, "acc_sou_wester", top + np.array([0, 0.006, -0.01]), 0.155, A["souwester"], tilt=(-5, 0, 0))
    sc, st = A["scarf"]
    nc = np.array([0, 0.79, 0.03])
    r_mean, r_max = neck_fit(f, nc)
    acc_scarf(m, "acc_scarf", nc, r_max + 0.014, 0.034, sc, stripe=st, tail_side=1.0, drop=0.24)
    tc, dots = A["bowtie"]
    bp, bn = onsurf(f, [(0.0, 0.76, 0.4)])
    acc_bowtie(m, "acc_bowtie", bp[0] + bn[0] * 0.016, 0.095, tc, dots=dots, bone="chest", normal=bn[0])
