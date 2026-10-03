"""Shelby — hermit-crab kid. A whelk shell far too big for her, wound from one fat coil of off-white/peach clay with
spiral cords and a knobbly shoulder, plastered with colourful paper stickers. A small red-orange crab peeks out of the
aperture: big white eyes on stalks, long feelers, one big right claw (held up proudly), a little left claw and two
pairs of jointed walking legs. 0.6 m to the antenna tips."""
import numpy as np
from clay import *
from kit import *
from kit_chars import *

OUT = "chars/shelby"

CRAB = "#d4532b"
CRAB_DK = "#a2361f"
CRAB_LT = "#f09a68"
FACE = "#f2b083"
CREAM = "#f3e2c3"
TIP = "#3b2320"
SHELL = "#ecd6bd"
SHELL_PEACH = "#eca07a"
SHELL_STREAK = "#b9774f"
INSIDE = "#f29a86"

AP = np.array([0.0, 0.205, 0.035])        # mouth of the shell (the crab peeks out here)
EYE_C = (0.052, 0.378, 0.128)
EYE_R = 0.036
STALK_B = (0.028, 0.262, 0.112)


AX = np.array([0.13, 0.74, -0.66]) / np.linalg.norm([0.13, 0.74, -0.66])     # shell axis, towards the apex (up and back)
D_OPEN = np.array([0.0, -0.22, 1.0]) / np.linalg.norm([0.0, -0.22, 1.0])        # the mouth faces forward, a touch down
R_BW = 0.21                                                                      # body whorl radius
O_BW = AP - D_OPEN * R_BW * 0.72 + np.array([0.03, 0.0, 0.0])                   # body whorl centre (shell sits a touch to her right)


def spire():
    """The spire: one coil of clay along a logarithmic conical helix rising out of the body whorl to a fine point.
    Returns centre points, radii and the helix frame."""
    rho1, R1, C, N, rho0 = 0.115, 0.082, 0.33, 4.6, 0.0065
    k = np.log(rho1 / rho0)
    a = AX
    e1 = np.cross(a, np.array([1.0, 0, 0]))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(a, e1)
    s = np.linspace(0, 1, 160)
    g = np.exp(k * (s - 1))
    th = 2 * np.pi * N * (s - 1) + 2.2
    base = O_BW + a * 0.12
    P = base + a[None] * (C * (1 - g))[:, None] + (R1 * g)[:, None] * (np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2)
    return P, rho1 * g, e1, e2


def build():
    m = Model("shelby", res=0.005)
    m.weight_softness = 0.012
    m.bone("root")
    m.bone("hips", "root", (0, 0.17, 0.0))
    m.bone("spine", "hips", (0, 0.18, 0.03))
    m.bone("chest", "spine", (0, 0.19, 0.05))
    m.bone("neck", "chest", (0, 0.2, 0.06))
    m.bone("head", "neck", (0, 0.215, 0.07))
    m.bone("shell", "hips", tuple(AP))
    stalk_face_bones(m, EYE_C, EYE_R, STALK_B, brow_up=1.3, mouth_c=(0, 0.196, 0.135))
    # big claw on the right, little one on the left
    arm = {"R": [(0.066, 0.185, 0.105), (0.135, 0.158, 0.145), (0.13, 0.145, 0.19)], "L": [(-0.066, 0.185, 0.1), (-0.112, 0.15, 0.14), (-0.102, 0.13, 0.18)]}
    for s in ("L", "R"):
        a0, a1, a2 = arm[s]
        m.bone(f"arm_{s}", "chest", a0)
        m.bone(f"elbow_{s}", f"arm_{s}", a1)
        m.bone(f"hand_{s}", f"elbow_{s}", a2)
    legs = {}
    for sx, s in ((-1, "L"), (1, "R")):
        l1 = [(sx * 0.066, 0.165, 0.085), (sx * 0.142, 0.2, 0.118), (sx * 0.178, 0.08, 0.148), (sx * 0.188, 0.004, 0.158)]
        l2 = [(sx * 0.066, 0.155, 0.045), (sx * 0.152, 0.186, 0.04), (sx * 0.198, 0.075, 0.02), (sx * 0.208, 0.004, 0.01)]
        legs[s] = (l1, l2)
        m.bone(f"leg_{s}", "hips", l1[0])
        m.bone(f"knee_{s}", f"leg_{s}", l1[1])
        m.bone(f"foot_{s}", f"knee_{s}", l1[2])
        m.bone(f"leg2_{s}", "hips", l2[0])

    shell_piece(m)
    body = crab_body(m)
    f = body._eval_shape
    stalks(m)
    face(m, EYE_C, EYE_R, lid=CRAB, brow_col="#5b231b", look=(0, -0.02, 1), pupil_frac=0.6, toe_in=4,
         brow_kw=dict(length=1.5, thick=0.22, lift=1.32, tilt=-10, forward=0.25),
         blush_c=(0.064, 0.205, 0.12), blush_r=0.017, blush_on=f, eye_budget=900)
    mp, mn = onsurf(f, [(0.0, 0.192, 0.2)])
    mouths(m, c=mp[0] + mn[0] * 0.002, w=0.044, lip="#6a231d", normal=mn[0], lip_r=0.0042)
    feelers(m)
    claws(m, arm)
    walking_legs(m, legs)
    budget(m, {"shell": 11000, "body": 5200, "stalk_*": 500, "feelers": 1400, "claw_R": 4200, "claw_L": 2400,
               "leg_*": 1500, "leg2_*": 1100, "sticker_*": 1100, "sticker_smiley": 1800,
               "eyeball_*": 900, "lidhalf_*": 800, "lidclosed_*": 800, "eyehappy_*": 700, "pupil_*": 600,
               "brow_*": 400, "blush_*": 200, "mouth_*": 450})

    m.socket("prop_R", "hand_R", (0.1, 0.13, 0.33))
    m.socket("bust", "head", (0, 0.29, 0.2))
    m.socket("talk", "head", (0, 0.72, 0.0))
    return m


# ---------------------------------------------------------------------------------------------------------------


def shell_piece(m):
    Q, r, e1, e2 = spire()
    n = len(Q)
    ax = AX
    sh = xpiece(m, "shell", color=SHELL, gloss=95, rigid="shell", res=0.0048, lumps=0.0024, lump_freq=10, dents=24, dent_size=0.03,
                dent_depth=0.003, mottle=0.05)
    # body whorl: a big rounded lump, a little egg-shaped along the axis and swelling at the shoulder
    Rb = np.stack([e1, ax, e2], axis=1)
    sh.add(Ellipsoid(O_BW, (R_BW, R_BW * 0.92, R_BW), rot=Rb))
    sh.add(Ellipsoid(O_BW + ax * 0.05, (R_BW * 1.02, R_BW * 0.6, R_BW * 1.02), rot=Rb), k=0.04)            # the shoulder
    sh.add(Ellipsoid(O_BW - ax * 0.13, (R_BW * 0.55, R_BW * 0.5, R_BW * 0.55), rot=Rb), k=0.06)            # siphonal end
    # the spire coil (hard union between turns leaves the sutures as real creases)
    # one Tube per half-turn, softly unioned: the sutures become rounded scored grooves rather than knife creases
    per = max(4, int(n / 4.5 / 2))
    for j, i0 in enumerate(range(0, n - 1, per)):
        i1 = min(n - 1, i0 + per)
        sh.add(Tube(Q[i0:i1 + 1], r[i0:i1 + 1]), k=0.025 if j == (n - 2) // per else max(0.002, float(r[i1]) * 0.12))
    sh.add(Sphere(Q[0] + (Q[0] - Q[3]) / (np.linalg.norm(Q[0] - Q[3]) + 1e-9) * 0.003, 0.0085), k=0.005)       # spire tip bead
    f0 = sh._eval_shape
    # a scored spiral line carrying the coil on round the body whorl, and knobs along the shoulder
    hel = []
    for t in np.linspace(0, 1, 60):
        ang = 2.2 + t * 2 * np.pi * 1.05
        hgt = 0.075 - t * 0.2
        hel.append(O_BW + ax * hgt + (np.cos(ang) * e1 + np.sin(ang) * e2) * 0.3)
    hel = snap(f0, np.array(hel))
    sh.sub(Tube(hel, 0.0055), k=0.006)
    for t in np.linspace(0.04, 0.96, 13):
        ang = 2.2 + t * 2 * np.pi
        q = snap(f0, [O_BW + ax * 0.095 + (np.cos(ang) * e1 + np.sin(ang) * e2) * 0.3])[0]
        sh.add(Sphere(q, 0.016), k=0.016)
    # the mouth: a round opening at the front of the body whorl, glossy pink inside, with a rolled flared lip
    Rm = look_rot(D_OPEN) @ euler((90, 0, 0))                  # local z -> D_OPEN
    cav_c = AP - D_OPEN * 0.045
    sh.sub(Ellipsoid(cav_c, (0.105, 0.11, 0.11), rot=Rm), k=0.012)
    sh.paint(Ellipsoid(cav_c, (0.112, 0.117, 0.117), rot=Rm), INSIDE, gloss=170, feather=0.008)
    f_cut = sh._eval_shape
    X, Y = Rm[:, 0], Rm[:, 1]
    rim = [cav_c + (X * np.cos(t) * 0.098 + Y * np.sin(t) * 0.103) + D_OPEN * 0.05 for t in np.linspace(0, 2 * np.pi, 40, endpoint=False)]
    rim = snap(f_cut, np.array(rim), offset=0.004)
    sh.add(Tube(np.vstack([rim, rim[:1]]), 0.012, samples=3), k=0.01, color="#f5d3bd")
    # spiral cords (bands across the shell axis) and fine growth lines (around it)
    sh.detail(bands(ax, period=0.017, width=0.28, soft=0.35), depth=0.0016, darken=0.06)
    sh.detail(ribs(O_BW, ax, n=70, sharp=6), depth=0.0007, darken=0.03)
    # colour: peach bands following the coil, a few brown flame streaks
    sh.pattern(bands(ax, period=0.06, width=0.42, offset=0.01, soft=0.35), SHELL_PEACH)
    sh.pattern(lambda P: 0.65 * ribs(O_BW, ax, n=9, sharp=8)(P) * np.clip((vnoise(P * 18.0, 4) + 0.2) * 2, 0, 1), SHELL_STREAK)
    sh.pattern(specks(60.0, 0.68, seed=9), "#d9b79c")
    sh.pattern(lambda P: 0.55 * np.clip(((P - O_BW) @ ax - 0.12) / 0.2, 0, 1), "#efb08c")          # spire blushes peach
    f = sh._eval_shape
    stickers(m, f, O_BW + ax * 0.05)
    return sh


def stickers(m, f, body_c):
    def spot(d, k=0.4):
        d = np.asarray(d, float)
        d /= np.linalg.norm(d)
        return body_c + d * k

    smile = [(np.cos(t) * 0.028, np.sin(t) * 0.028 - 0.005) for t in np.linspace(np.radians(200), np.radians(340), 9)]
    smile += [(np.cos(t) * 0.019, np.sin(t) * 0.019 - 0.003) for t in np.linspace(np.radians(340), np.radians(200), 9)]
    sticker(m, "sticker_star", f, spot((1.0, 0.1, 0.35)), [(star_pts(0.056), "#f4c22b", 0.0)], "shell", spin=12)
    sticker(m, "sticker_heart", f, spot((0.3, 1.0, 0.25)), [(heart_pts(0.052), "#e8567a", 0.0)], "shell", spin=-18)
    eye_dot = circle_pts(0.0068, 12)
    sticker(m, "sticker_smiley", f, spot((-1.0, 0.35, 0.2)),
            [(circle_pts(0.048), "#3f8fd6", 0.0),
             ([(x - 0.014, y + 0.011) for x, y in eye_dot], "#1e2433", 0.0007),
             ([(x + 0.014, y + 0.011) for x, y in eye_dot], "#1e2433", 0.0007),
             (smile, "#1e2433", 0.0007)], "shell", spin=8)
    sticker(m, "sticker_bolt", f, spot((0.2, -0.1, -1.0)), [(bolt_pts(0.056), "#6cc04a", 0.0)], "shell", spin=-10)
    sticker(m, "sticker_flower", f, spot((0.9, 0.2, -0.55)),
            [(flower_pts(0.054), "#a065c9", 0.0), (circle_pts(0.017, 16), "#f6d23a", 0.0007)], "shell", spin=20)
    body = [(-0.008 + np.cos(t) * 0.03, np.sin(t) * 0.019) for t in np.radians(np.linspace(25, 335, 22))]
    fish = body + [(0.042, -0.02), (0.035, 0.0), (0.042, 0.02)]
    sticker(m, "sticker_fish", f, spot((-0.75, 0.1, -0.7)),
            [(fish, "#2fb3a6", 0.0), ([(x - 0.022, y + 0.005) for x, y in circle_pts(0.0045, 10)], "#1e2433", 0.0007)], "shell", spin=0)
    sticker(m, "sticker_glass", f, spot((-0.45, 0.95, -0.1)),
            [([(0.03, 0.006), (0.012, 0.026), (-0.02, 0.022), (-0.032, -0.004), (-0.012, -0.026), (0.022, -0.02)], "#7fd0b8", 0.0),
             ([(0.012, 0.012), (0.004, 0.018), (-0.006, 0.006), (0.002, 0.0)], "#dff5ee", 0.0007)], "shell", spin=0)


def crab_body(m):
    b = xpiece(m, "body", color=CRAB, gloss=90, bone="head", res=0.004, lumps=0.0014, lump_freq=16, dents=10, dent_size=0.016, dent_depth=0.0018)
    b.add(Ellipsoid((0, 0.218, 0.055), (0.088, 0.07, 0.084)), bone="head")                     # carapace shield
    b.add(Ellipsoid((0, 0.232, 0.108), (0.058, 0.044, 0.04)), k=0.03, bone="head")             # brow lobe between the stalks
    b.add(Ellipsoid((0, 0.18, 0.06), (0.074, 0.048, 0.07)), k=0.03, bone="chest")              # chest / mouthparts
    b.add(Ellipsoid((0, 0.205, -0.03), (0.08, 0.075, 0.09)), k=0.04, bone="hips")              # soft abdomen inside the shell
    for sx in (-1, 1):                                                                          # cheeks
        b.add(Ellipsoid((sx * 0.05, 0.197, 0.112), (0.034, 0.03, 0.026)), k=0.02, bone="head")
    f0 = b._eval_shape
    # cervical groove across the shield, and a pair of shallow scoops
    pts = surface_curve(f0, [(-0.08, 0.232, 0.02), (0.0, 0.29, 0.035), (0.08, 0.232, 0.02)], 14)
    b.sub(Tube(pts, 0.0032), k=0.003)
    for sx in (-1, 1):
        pts = surface_curve(f0, [(sx * 0.03, 0.28, 0.06), (sx * 0.06, 0.262, 0.08), (sx * 0.075, 0.235, 0.085)], 8)
        b.sub(Tube(pts, 0.0026), k=0.003)
    # pale face (where the mouth sits) and a darker cap
    b.paint(Ellipsoid((0, 0.192, 0.125), (0.075, 0.038, 0.045)), FACE, feather=0.02)
    b.paint(Ellipsoid((0, 0.29, 0.03), (0.1, 0.045, 0.1)), CRAB_DK, feather=0.03)
    # tiny tubercles on the shield
    rng = np.random.default_rng(3)
    A = []
    for _ in range(26):
        th, ph = rng.uniform(0.15, 1.0), rng.uniform(-1.2, 1.2)
        A.append((np.sin(th) * np.sin(ph) * 0.1, 0.218 + np.cos(th) * 0.08, 0.055 + np.sin(th) * np.cos(ph) * 0.1))
    A = snap(f0, np.array(A))
    b.add(Segs(A, A, rng.uniform(0.0025, 0.004, len(A))), k=0.002, color=CRAB_LT, bone="head")
    b.pattern(specks(90.0, 0.66, seed=5), CRAB_LT)
    return b


def stalks(m):
    ex, ey, ez = EYE_C
    bx, by, bz = STALK_B
    for sx, s in ((-1, "L"), (1, "R")):
        st = xpiece(m, f"stalk_{s}", color=CRAB, gloss=85, rigid=f"stalk_{s}", res=0.003, lumps=0.0008, lump_freq=30, mottle=0.04)
        a = np.array([sx * bx, by - 0.012, bz - 0.006])
        e = np.array([sx * ex, ey - EYE_R * 0.75, ez - 0.004])
        mid = (a + e) / 2 + np.array([sx * -0.004, 0, 0.008])
        st.add(Tube([a, mid, e], [0.0135, 0.0105, 0.0125], samples=6))
        st.add(Ellipsoid(e + np.array([0, 0.004, 0]), (0.02, 0.012, 0.02)), k=0.006)              # cup under the eyeball
        for t in (0.35, 0.6):
            q = a + (e - a) * t
            st.paint(Ellipsoid(q, (0.02, 0.004, 0.02)), CRAB_LT, feather=0.003)


def feelers(m):
    fe = xpiece(m, "feelers", color=CRAB, gloss=80, rigid="head", res=0.0024, lumps=0.0004, lump_freq=40, mottle=0.04, ao=False)
    for sx in (-1, 1):
        # long antennae sweeping up and out, drooping at the ends
        pts = [(sx * 0.012, 0.248, 0.148), (sx * 0.06, 0.268, 0.2), (sx * 0.122, 0.318, 0.215), (sx * 0.178, 0.44, 0.18), (sx * 0.212, 0.55, 0.12), (sx * 0.232, 0.585, 0.07)]
        fe.add(Tube(pts, [0.0048, 0.004, 0.0034, 0.0028, 0.0022, 0.0016], samples=6), k=0.002)
        # short forked antennules
        b0 = np.array([sx * 0.008, 0.245, 0.148])
        b1 = b0 + np.array([sx * 0.012, 0.022, 0.03])
        fe.add(Tube([b0, b1], [0.004, 0.0035]), k=0.002)
        for dz in (-1, 1):
            fe.add(Tube([b1, b1 + np.array([sx * (0.016 + 0.006 * dz), 0.018, 0.012 * dz + 0.014])], [0.003, 0.0018]), k=0.0015, color=CRAB_LT)
    fe.pattern(lambda P: bands((0, 1, 0), period=0.03, width=0.3, soft=0.3)(P) * (P[:, 1] > 0.3), CREAM)


def claws(m, arm):
    # big right claw, held up proudly beside her face
    a0, a1, a2 = [np.array(p) for p in arm["R"]]
    c = xpiece(m, "claw_R", color=CRAB, gloss=95, bone="hand_R", res=0.0036, lumps=0.0012, lump_freq=18, dents=6, dent_size=0.014, dent_depth=0.0015)
    jointed(c, [a0, a1, a2], [0.03, 0.029, 0.027], bones=["arm_R", "elbow_R"], band=CRAB_LT, bristles=5, bristle_col=shade(CRAB, 0.86), seed=1)
    fwd = np.array([-0.5, 0.22, 0.85])
    piv = claw(c, a2, fwd, (0.15, 1.0, 0.0), 0.155, 0.1, 0.066, CRAB, TIP, bone_hand="hand_R", bone_finger="claw_R", gape=14,
               teeth=5, tubercles=34, tub_col=CRAB_LT, seed=4, finger_col=CRAB_LT)
    c.paint(Ellipsoid(a2 + fwd / np.linalg.norm(fwd) * 0.04 + np.array([0.0, -0.03, 0]), (0.05, 0.03, 0.05)), CREAM, feather=0.02)
    m.bone("claw_R", "hand_R", tuple(piv))
    # little left claw
    a0, a1, a2 = [np.array(p) for p in arm["L"]]
    c = xpiece(m, "claw_L", color=CRAB, gloss=95, bone="hand_L", res=0.003, lumps=0.0009, lump_freq=22, dents=3, dent_size=0.01, dent_depth=0.001)
    jointed(c, [a0, a1, a2], [0.018, 0.017, 0.016], bones=["arm_L", "elbow_L"], band=CRAB_LT, bristles=3, bristle_col=shade(CRAB, 0.86), seed=2)
    claw(c, a2, (0.25, 0.1, 1.0), (-0.1, 1.0, 0.0), 0.075, 0.045, 0.032, CRAB, TIP, bone_hand="hand_L", gape=8, teeth=4,
         tubercles=12, tub_col=CRAB_LT, seed=5, finger_col=CRAB_LT)


def walking_legs(m, legs):
    for sx, s in ((-1, "L"), (1, "R")):
        l1, l2 = legs[s]
        p = xpiece(m, f"leg_{s}", color=CRAB, gloss=90, bone=f"foot_{s}", res=0.003, lumps=0.0008, lump_freq=25, dents=3, dent_size=0.01, dent_depth=0.001)
        jointed(p, l1, [0.023, 0.021, 0.015, 0.0045], bones=[f"leg_{s}", f"knee_{s}", f"foot_{s}"], band=CRAB_LT, tip=TIP, tip_len=0.3,
                bristles=4, bristle_col=shade(CRAB, 0.86), seed=10 + int(sx))
        q = xpiece(m, f"leg2_{s}", color=CRAB, gloss=90, rigid=f"leg2_{s}", res=0.003, lumps=0.0008, lump_freq=25, dents=3, dent_size=0.01, dent_depth=0.001)
        jointed(q, l2, [0.021, 0.019, 0.014, 0.0045], band=CRAB_LT, tip=TIP, tip_len=0.3, bristles=4, bristle_col=shade(CRAB, 0.86), seed=20 + int(sx))
