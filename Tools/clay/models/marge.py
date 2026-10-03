"""Marge — pelican postmistress. Prim and upright: pale plumage, a long pale-orange bill resting down over a saggy
throat pouch, round gold wire glasses, a navy postal cap with a brass badge, and a leather mail satchel slung across
the chest with a letter poking out. 1.4 m to the top of the cap."""
import numpy as np
from clay import *
from kit import *
from kit_chars import *

OUT = "chars/marge"

WHITE = "#ebe7de"
GREY = "#c8c5bf"
GREY_DK = "#8f8d89"
TIPS = "#3a3a3f"
BILL = "#ec9a50"
BILL_DK = "#d4703f"
POUCH = "#eba27a"
FOOT = "#e9843b"
CAP = "#283860"
GOLD = "#cda24a"
LEATHER = "#8b512d"
LEATHER_DK = "#5f3519"
CREST = "#efe0a8"

EYE_C = (0.08, 1.198, 0.102)
EYE_R = 0.032
BILL_ROT = (36, 0, 0)                     # local +z -> bill direction (down and forward)


def bill_dir():
    return euler(BILL_ROT) @ np.array([0, 0, 1.0])


def build():
    m = Model("marge", res=0.0065)
    m.weight_softness = 0.025
    biped_rig(m, hip_y=0.36, chest_y=0.64, neck_y=0.84, head_y=1.12, shoulder_x=0.18, shoulder_y=0.76, hand_y=0.42,
              hip_x=0.1, knee_y=0.17, foot_y=0.05, foot_z=0.04, elbow_out=0.08, head_z=0.0,
              tail=((0, 0.3, -0.22), (0, 0.27, -0.3)))
    face_bones(m, EYE_C, EYE_R, brow_up=2.0, jaw_c=(0, 1.11, 0.12), hat_c=(0, 1.275, -0.01))
    m.bone("pouch", "jaw", (0, 0.98, 0.22))

    body = plumage(m)
    f = body._eval_shape
    bill(m)
    face(m, EYE_C, EYE_R, lid=WHITE, brow_col=GREY_DK, look=(0, -0.02, 1), pupil_frac=0.52, ring="#efc2a0", toe_in=4,
         brow_kw=dict(length=1.7, thick=0.22, lift=1.75, tilt=-12, forward=0.75),
         blush_c=(0.085, 1.15, 0.09), blush_r=0.022, blush_on=f)
    glasses(m)
    wings(m)
    legs(m)
    cap(m)
    satchel(m, f)
    budget(m, {"body": 15000, "bill": 4000, "pouch": 3000, "glasses": 2200, "wing_*": 3200, "leg_*": 900, "foot_*": 1500,
               "cap": 3500, "satchel": 3800, "strap": 2400, "letter": 600,
               "eyeball_*": 900, "lidhalf_*": 900, "lidclosed_*": 900, "eyehappy_*": 900, "pupil_*": 600,
               "brow_*": 500, "blush_*": 300})

    m.socket("prop_R", "hand_R", (0.29, 0.36, 0.0))
    m.socket("bust", "head", (0, 1.15, 0.16))
    m.socket("talk", "head", (0, 1.62, 0.0))
    return m


def plumage(m):
    b = xpiece(m, "body", color=WHITE, bone="spine", lumps=0.0025, lump_freq=8, dents=22, dent_size=0.03, dent_depth=0.003)
    b.add(Ellipsoid((0, 0.39, -0.03), (0.225, 0.24, 0.22)), bone="hips")
    b.add(Ellipsoid((0, 0.56, 0.01), (0.215, 0.22, 0.21)), k=0.08, bone="spine")
    b.add(Ellipsoid((0, 0.69, 0.055), (0.18, 0.15, 0.175)), k=0.08, bone="chest")      # proud, puffed chest
    b.add(Tube([(0, 0.78, 0.02), (0, 0.9, -0.035), (0, 1.0, -0.035), (0, 1.08, -0.01)], [0.105, 0.078, 0.07, 0.075], samples=6), k=0.06, bone="neck")
    b.add(Ellipsoid((0, 1.165, -0.005), (0.138, 0.132, 0.145)), k=0.05, bone="head")
    b.add(Ellipsoid((0, 1.125, 0.06), (0.1, 0.075, 0.09)), k=0.05, bone="head")             # cheeks into the bill root
    b.add(Ellipsoid((0, 0.29, -0.23), (0.09, 0.03, 0.08), rot=(-25, 0, 0)), k=0.04, bone="tail")
    for sx in (-1, 1):
        b.sub(Sphere((sx * EYE_C[0], EYE_C[1], EYE_C[2] + 0.01), EYE_R * 1.02), k=0.015)
    # crest curls at the nape, peeking from under the cap
    for i, (x, y, z, cx) in enumerate(((0.0, 1.235, -0.125, 0.0), (-0.04, 1.22, -0.128, -0.02), (0.04, 1.225, -0.126, 0.02))):
        b.add(Tube([(x, y, z), (x + cx, y + 0.02, z - 0.04), (x + cx * 1.5, y - 0.005, z - 0.07)], [0.02, 0.016, 0.008], samples=5), k=0.015, color=CREST, bone="head")
    b.paint(Ellipsoid((0, 0.32, -0.05), (0.24, 0.12, 0.23)), GREY, feather=0.05)             # grey-dusted lower body
    b.paint(Ellipsoid((0, 0.62, 0.13), (0.13, 0.12, 0.08)), "#f0dcc8", feather=0.05)        # peachy breast flush
    b.paint(Ellipsoid((0, 0.62, -0.17), (0.2, 0.3, 0.1)), "#dcd8d0", feather=0.06)           # pearl-grey back
    b.detail(feathers((0, 0.6, 0.05), (0.2, 0.26, 0.2), cells=16, width=0.0042, flow=(0, -1, 0.2), size=0.6,
                      region=Ellipsoid((0, 0.6, 0.12), (0.17, 0.17, 0.14)), seed=3), depth=0.0018, darken=0.08)
    b.detail(strokes((0, 0.95, -0.02), (0.09, 0.18, 0.08), cells=9, length=1.3, width=0.005, flow=(0, -1, 0), ridge=0.2, seed=5,
                     region=Box((0, 0.95, -0.02), (0.15, 0.13, 0.15))), depth=0.0008, darken=0.05)
    return b


def bill(m):
    R = euler(BILL_ROT)
    d = bill_dir()
    up = R @ np.array([0, 1.0, 0])
    root = np.array([0, 1.122, 0.128])
    L = 0.41
    tip = root + d * L

    def B(t, h=0.0, x=0.0):
        return root + d * (L * t) + up * h + np.array([x, 0, 0])

    u = xpiece(m, "bill", color=BILL, gloss=95, bone="head", res=0.0045, lumps=0.0012, dents=6, dent_size=0.02, dent_depth=0.0015)
    u.add(Ellipsoid(B(0.5), (0.045, 0.021, L * 0.52), rot=R), bone="head")
    u.add(Ellipsoid(B(0.06, 0.008), (0.06, 0.04, 0.06), rot=R), k=0.04, bone="head")         # broad root into the face
    u.add(Capsule(B(0.08, 0.016), B(0.92, 0.012), 0.012, 0.008), k=0.012, bone="head")       # culmen ridge
    u.add(Ellipsoid(B(1.0, -0.006), (0.017, 0.02, 0.026), rot=R @ euler((35, 0, 0))), k=0.012, color=BILL_DK, bone="head")  # hooked nail
    u.inter(HalfSpace(B(0.5, -0.016), -up), k=0.006)                                          # flat underside
    # lower mandible on the jaw: two thin rami meeting at the tip
    for sx in (-1, 1):
        u.add(Tube([B(0.04, -0.022, sx * 0.04), B(0.5, -0.025, sx * 0.034), B(0.96, -0.02, sx * 0.012)], [0.013, 0.011, 0.008], samples=6), k=0.006, bone="jaw")
    u.add(Ellipsoid(B(0.97, -0.024), (0.016, 0.01, 0.022), rot=R), k=0.008, bone="jaw")
    u.paint(Box(B(0.5, 0.03), (0.011, 0.01, L * 0.5), rot=R), "#f2b77a", feather=0.008)      # sun-bleached ridge
    u.paint(Ellipsoid(B(0.0, 0.0), (0.06, 0.05, 0.05), rot=R), "#e6a46a", feather=0.02)
    # nostril slit
    for sx in (-1, 1):
        u.sub(Capsule(B(0.1, 0.006, sx * 0.03), B(0.2, 0.003, sx * 0.028), 0.0035), k=0.002, color=BILL_DK)

    p = xpiece(m, "pouch", color=POUCH, gloss=85, bone="pouch", res=0.0045, lumps=0.0012, dents=5, dent_size=0.03, dent_depth=0.002)
    for sx in (-1, 1):
        p.add(Tube([B(0.04, -0.03, sx * 0.036), B(0.5, -0.032, sx * 0.031), B(0.93, -0.026, sx * 0.01)], [0.011, 0.01, 0.007], samples=6), bone="jaw")
    down = np.array([0, -1.0, 0])
    for t in np.linspace(0.06, 0.88, 9):
        depth = 0.15 * np.sin(np.pi * min(1.0, (t + 0.08) / 1.0)) ** 1.3 * (1.15 - t * 0.6)
        cc = B(t, -0.028) + down * depth * 0.5
        bone = "pouch" if depth > 0.05 else "jaw"
        p.add(Ellipsoid(cc, (0.04 * (1.05 - 0.45 * t) + depth * 0.06, depth * 0.5 + 0.012, L * 0.085), rot=euler((BILL_ROT[0] * 0.4, 0, 0))), k=0.05, bone=bone)
    # loose skin creases curving along the bag
    for sx in (-1, 1):
        for h in (0.035, 0.07):
            pts = surface_curve(p._eval_shape, [B(0.12, -0.03) + down * h * 1.4 + np.array([sx * 0.05, 0, 0]),
                                               B(0.4, -0.03) + down * h * 1.8 + np.array([sx * 0.05, 0, 0]),
                                               B(0.7, -0.03) + down * h * 0.7 + np.array([sx * 0.04, 0, 0])], 10)
            p.sub(Tube(pts, 0.0025), k=0.003)
    p.paint(Func(lambda P: P[:, 1] - (B(0.3)[1] - 0.17), *Box(B(0.4), (0.2, 0.3, 0.3)).bounds()), "#e08f6c", feather=0.04)


def glasses(m):
    g = xpiece(m, "glasses", color=GOLD, gloss=225, rigid="head", res=0.0026, lumps=0.0, mottle=0.03, ao=False)
    ex, ey, ez = EYE_C
    for sx in (-1, 1):
        c = np.array([sx * (ex + 0.004), ey - 0.002, ez + 0.045])
        nrm = np.array([sx * 0.22, 0.0, 1.0])
        nrm /= np.linalg.norm(nrm)
        g.add(Torus(c, 0.044, 0.0058, rot=look_rot(nrm)), k=0.002)
        # temple arm back to the side of the head, tucked under the cap
        a = c + np.array([sx * 0.043, 0.004, -0.008])
        g.add(Tube([a, a + np.array([sx * 0.016, 0.004, -0.05]), np.array([sx * 0.118, ey + 0.012, -0.05])], 0.0045, samples=5), k=0.002)
    # bridge arching over the bill root
    g.add(Tube([np.array([-ex + 0.036, ey + 0.012, ez + 0.048]), np.array([0, ey - 0.012, ez + 0.07]), np.array([ex - 0.036, ey + 0.012, ez + 0.048])], 0.0048, samples=6), k=0.002)


def wings(m):
    for sx, s in ((-1, "L"), (1, "R")):
        w = xpiece(m, f"wing_{s}", color=WHITE, bone=f"elbow_{s}", res=0.0055, lumps=0.002, dents=5, dent_size=0.02)
        w.add(Ellipsoid((sx * 0.205, 0.68, -0.02), (0.065, 0.135, 0.14), rot=(0, 0, sx * -10)), bone=f"arm_{s}")
        w.add(Ellipsoid((sx * 0.248, 0.54, -0.045), (0.052, 0.14, 0.115), rot=(0, 0, sx * -8)), k=0.05, bone=f"elbow_{s}")
        w.add(Ellipsoid((sx * 0.265, 0.42, -0.07), (0.036, 0.1, 0.075), rot=(8, 0, sx * -4)), k=0.04, color=TIPS, bone=f"hand_{s}")
        for i, dz in enumerate((-0.04, -0.012, 0.016)):                                       # primary "fingers"
            w.add(Capsule((sx * 0.267, 0.43, -0.07 + dz), (sx * (0.275 - i * 0.004), 0.335 + i * 0.012, -0.09 + dz * 1.3), 0.018, 0.011),
                  k=0.015, color=TIPS, bone=f"hand_{s}")
        w.paint(Ellipsoid((sx * 0.26, 0.47, -0.06), (0.06, 0.05, 0.1)), GREY_DK, feather=0.03)
        w.detail(feathers((sx * 0.2, 0.58, -0.03), (0.08, 0.2, 0.12), cells=7, width=0.0042, flow=(0, -1, -0.2), size=0.62,
                          region=Ellipsoid((sx * 0.23, 0.6, -0.03), (0.09, 0.14, 0.14)), seed=8 + int(sx)), depth=0.0022, darken=0.1)
        for i in range(3):                                                                    # long tertial feather lines
            z0 = -0.07 - i * 0.03
            pts = surface_curve(w._eval_shape, [(sx * 0.28, 0.5, z0), (sx * 0.28, 0.42, z0 - 0.01), (sx * 0.27, 0.36, z0 - 0.015)], 8)
            w.sub(Tube(pts, 0.0028), k=0.002)


def legs(m):
    for sx, s in ((-1, "L"), (1, "R")):
        lg = xpiece(m, f"leg_{s}", color=FOOT, gloss=70, bone=f"knee_{s}", res=0.005, lumps=0.0012)
        lg.add(Capsule((sx * 0.1, 0.24, 0.0), (sx * 0.1, 0.15, 0.01), 0.035, 0.03), bone=f"leg_{s}")
        lg.add(Capsule((sx * 0.1, 0.15, 0.01), (sx * 0.1, 0.05, 0.035), 0.03, 0.026), k=0.02, bone=f"knee_{s}")
        for y in (0.13, 0.1, 0.07):
            lg.sub(Torus((sx * 0.1, y, 0.02), 0.03, 0.0022), k=0.002)
        ft = xpiece(m, f"foot_{s}", color=FOOT, gloss=70, rigid=f"foot_{s}", res=0.0045, lumps=0.0015, dents=3, dent_size=0.015)
        base = np.array([sx * 0.105, 0.022, 0.08])
        ft.add(Ellipsoid(base + (0, 0, -0.025), (0.05, 0.022, 0.055)))
        for t in (-1, 0, 1):
            tip = base + np.array([t * 0.07 + sx * 0.01, -0.006, 0.115 - abs(t) * 0.02])
            ft.add(Capsule(base + (0, 0, -0.01), tip, 0.017, 0.011), k=0.02)
            ft.add(Sphere(tip + np.array([0, 0.002, 0.008]), 0.008), k=0.004, color="#5a4030", gloss=120)
        ft.add(Ellipsoid(base + (0, -0.006, 0.06), (0.085, 0.008, 0.06)), k=0.015)
        ft.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.003)


def cap(m):
    hc = np.array([0, 1.262, -0.005])
    Rt = euler((-6, 0, 9))

    def H(x, y, z):
        return hc + Rt @ np.array([x, y, z])

    c = xpiece(m, "cap", color=CAP, gloss=60, rigid="hat", res=0.0045, lumps=0.0015, dents=6, dent_size=0.025, dent_depth=0.002)
    c.add(Cylinder(H(0, 0.045, 0), 0.118, 0.05, rot=Rt, round=0.012))
    c.add(Ellipsoid(H(0, 0.093, 0.004), (0.126, 0.022, 0.126), rot=Rt), k=0.012)              # crown overhang
    c.inter(HalfSpace(H(0, 0.105, 0), Rt @ np.array([0, 1, 0.18])), k=0.01)
    c.sub(Ellipsoid(H(0, -0.02, 0), (0.112, 0.05, 0.112), rot=Rt), k=0.01)
    c.add(Torus(H(0, 0.012, 0), 0.119, 0.0085, rot=Rt), k=0.004, color="#b23a30")             # red piping band
    c.add(Torus(H(0, 0.086, 0.002), 0.117, 0.005, rot=Rt), k=0.003, color="#b23a30")
    # short glossy peak
    c.add(Cylinder(H(0, 0.006, 0.085), 0.11, 0.008, rot=Rt @ euler((16, 0, 0)), round=0.007), k=0.006, color="#17181c", gloss=170)
    # brass badge: a little post horn on an oval
    bc = H(0, 0.05, 0.119)
    c.add(Ellipsoid(bc, (0.024, 0.02, 0.007), rot=Rt), k=0.003, color=GOLD, gloss=210)
    c.sub(Torus(bc + Rt @ np.array([0.0, 0.0, 0.006]), 0.011, 0.0022, rot=Rt @ euler((90, 0, 0))), k=0.0012, color="#8a6a22")
    c.sub(Capsule(bc + Rt @ np.array([0.011, 0.0, 0.006]), bc + Rt @ np.array([0.02, 0.006, 0.006]), 0.002), k=0.001, color="#8a6a22")
    for a in np.linspace(0, 2 * np.pi, 6, endpoint=False):                                    # panel seams on the crown
        c.sub(Capsule(H(np.sin(a) * 0.02, 0.112, np.cos(a) * 0.02), H(np.sin(a) * 0.112, 0.104, np.cos(a) * 0.112), 0.0025), k=0.002)


def satchel(m, f):
    # mail satchel on her right hip, slung from the left shoulder
    p0, n0 = onsurf(f, [(0.19, 0.43, 0.14)])
    p0, n0 = p0[0], n0[0]
    n0 = (n0 + np.array([0.0, 0.0, 0.25]))
    n0 /= np.linalg.norm(n0)
    Rb = surf_frame(n0) @ euler((0, 0, -8))                       # local z = out of the hip, local y = up
    c = p0 + n0 * 0.045

    def S(x, y, z):
        return c + Rb @ np.array([x, y, z])

    b = xpiece(m, "satchel", color=LEATHER, gloss=70, rigid="hips", res=0.0042, lumps=0.0018, dents=7, dent_size=0.025, dent_depth=0.0025)
    b.add(Box(S(0, 0, 0), (0.105, 0.085, 0.034), rot=Rb, round=0.022))
    b.add(Box(S(0, 0.088, -0.004), (0.1, 0.012, 0.03), rot=Rb, round=0.01), k=0.01)            # top gusset
    # flap over the front with a rolled edge, and a brass buckle
    flap = Box(S(0, 0.035, 0.038), (0.108, 0.062, 0.007), rot=Rb @ euler((-6, 0, 0)), round=0.006)
    b.add(flap, k=0.005, color=shade(LEATHER, 1.08))
    b.add(Tube([S(-0.1, -0.026, 0.041), S(0, -0.032, 0.043), S(0.1, -0.026, 0.041)], 0.0065, samples=6), k=0.004)
    b.add(Box(S(0, -0.03, 0.05), (0.018, 0.013, 0.004), rot=Rb, round=0.003), k=0.002, color=GOLD, gloss=210)
    b.sub(Box(S(0, -0.03, 0.055), (0.009, 0.005, 0.004), rot=Rb, round=0.002), k=0.001, color="#6a5020")
    b.sub(stitches([S(-0.095, 0.085, 0.046), S(-0.098, -0.015, 0.046), S(0.098, -0.015, 0.046), S(0.095, 0.085, 0.046)], 30, length=0.007, r=0.0016),
          k=0.001, color=LEATHER_DK)
    b.paint(Box(S(0, 0, 0), (0.12, 0.1, 0.05), rot=Rb, round=0.02), LEATHER_DK, feather=0.01)
    b.paint(Box(S(0, 0, 0), (0.095, 0.077, 0.06), rot=Rb, round=0.02), LEATHER, feather=0.012)
    # a letter sticking out of the top (merged into the satchel as a separate lump)
    lt = xpiece(m, "letter", color="#f0eadb", gloss=30, rigid="hips", res=0.003, lumps=0.0006, mottle=0.03)
    Rl = Rb @ euler((0, 0, 14))
    lc = S(-0.025, 0.12, 0.012)
    lt.add(Box(lc, (0.065, 0.048, 0.004), rot=Rl, round=0.003))
    lt.paint(Box(lc + Rl @ np.array([0.044, 0.028, 0.0]), (0.012, 0.013, 0.01), rot=Rl), "#c2382c")
    lt.paint(Box(lc + Rl @ np.array([-0.012, 0.003, 0.0]), (0.026, 0.0022, 0.01), rot=Rl), "#4d5f8c")
    lt.paint(Box(lc + Rl @ np.array([-0.008, -0.008, 0.0]), (0.022, 0.0022, 0.01), rot=Rl), "#4d5f8c")
    # strap: a leather band pressed across the chest, over the left shoulder and round the back
    guide = [S(-0.08, 0.06, -0.01), (0.1, 0.56, 0.2), (-0.03, 0.66, 0.2), (-0.13, 0.76, 0.15), (-0.19, 0.83, 0.0),
             (-0.12, 0.78, -0.17), (0.06, 0.62, -0.22), (0.2, 0.5, -0.12), S(0.08, 0.06, -0.02)]
    path = snap(f, curve(guide, 48))
    st = xpiece(m, "strap", color=LEATHER, gloss=70, bone="chest", res=0.004, lumps=0.0012, mottle=0.05)
    n = len(path)
    st.add(Shell(f, -0.004, 0.007, Tube(path[: n // 2 + 2], 0.021), round=0.003), bone="chest")
    st.add(Shell(f, -0.004, 0.007, Tube(path[n // 2 - 2:], 0.021), round=0.003), k=0.003, bone="spine")
    st.sub(stitches(snap(f, path, offset=0.007), 60, length=0.007, r=0.0016), k=0.001, color=LEATHER_DK)
