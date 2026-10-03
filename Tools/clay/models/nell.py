"""Nell — sea otter, runs the counter of The Salty Puffin. Warm brown fur, pale cream face, whisker pads with clay
whiskers, black button nose, a striped blue-and-white butcher's apron and a red polka-dot bandana knotted on top.
1.15 m to the top of the knot."""
import numpy as np
from clay import *
from kit import *
from kit_chars import *

OUT = "chars/nell"

FUR = "#7a4c31"
FUR_DK = "#563321"
FUR_LT = "#9a6847"
CREAM = "#e8d7b6"
CREAM_DK = "#cdb48e"
NOSE = "#1f1b1c"
APRON_W = "#ebe4d4"
APRON_B = "#3d5f98"
RED = "#c3392d"
PAD = "#3b2620"

EYE_C = (0.084, 0.922, 0.183)
EYE_R = 0.032


def build():
    m = Model("nell", res=0.0065)
    m.weight_softness = 0.025
    biped_rig(m, hip_y=0.34, chest_y=0.58, neck_y=0.7, head_y=0.8, shoulder_x=0.16, shoulder_y=0.62, hand_y=0.37,
              hip_x=0.1, knee_y=0.15, foot_y=0.05, foot_z=0.04, elbow_out=0.075, head_z=0.03,
              tail=((0, 0.24, -0.17), (0, 0.11, -0.34)))
    face_bones(m, EYE_C, EYE_R, brow_up=1.4, mouth_c=(0, 0.768, 0.21), hat_c=(0, 1.0, 0.03))

    body = fur_body(m)
    f = body._eval_shape
    face_parts(m)
    face(m, EYE_C, EYE_R, lid=CREAM, brow_col=FUR_DK, look=(0, 0.0, 1), pupil_frac=0.55, toe_in=4,
         brow_kw=dict(length=1.7, thick=0.24, lift=1.45, tilt=-6, forward=0.3),
         blush_c=(0.13, 0.85, 0.17), blush_r=0.026, blush_on=f)
    mouths(m, c=np.array([0.0, 0.768, 0.212]), w=0.066, lip="#4a2622", normal=(0, -0.35, 1), lip_r=0.0055)
    arms(m)
    legs(m)
    tail(m)
    apron(m, f)
    bandana(m, f)
    budget(m, {"body": 15000, "apron": 12000, "bandana": 5000, "muzzle": 2200, "nose": 700, "whiskers": 1500,
               "arm_*": 2000, "leg_*": 1000, "foot_*": 1400, "tail": 2400, "ears": 1000, "pencil": 500,
               "eyeball_*": 900, "lidhalf_*": 900, "lidclosed_*": 900, "eyehappy_*": 900, "pupil_*": 600,
               "brow_*": 500, "blush_*": 300, "mouth_*": 700})

    m.socket("prop_R", "hand_R", (0.24, 0.33, 0.07))
    m.socket("bust", "head", (0, 0.88, 0.2))
    m.socket("talk", "head", (0, 1.32, 0.03))
    return m


def fur_body(m):
    b = xpiece(m, "body", color=FUR, bone="spine", lumps=0.0022, lump_freq=8, dents=20, dent_size=0.03, dent_depth=0.003)
    b.add(Ellipsoid((0, 0.32, -0.01), (0.215, 0.2, 0.19)), bone="hips")
    b.add(Ellipsoid((0, 0.45, 0.0), (0.21, 0.2, 0.185)), k=0.08, bone="spine")
    b.add(Ellipsoid((0, 0.6, 0.012), (0.18, 0.13, 0.165)), k=0.08, bone="chest")
    b.add(Ellipsoid((0, 0.72, 0.02), (0.15, 0.08, 0.14)), k=0.07, bone="neck")
    b.add(Ellipsoid((0, 0.89, 0.03), (0.215, 0.182, 0.185)), k=0.08, bone="head")
    b.add(Ellipsoid((0, 0.84, 0.07), (0.232, 0.125, 0.158)), k=0.06, bone="head")
    for sx in (-1, 1):  # soft eye sockets
        b.sub(Sphere((sx * EYE_C[0], EYE_C[1], EYE_C[2] + 0.012), EYE_R * 1.05), k=0.02)
    # pale face, throat and chest
    b.paint(Ellipsoid((0, 0.835, 0.13), (0.185, 0.14, 0.12)), CREAM, feather=0.035)
    b.paint(Ellipsoid((0, 0.72, 0.1), (0.12, 0.09, 0.1)), CREAM, feather=0.035)
    b.paint(Ellipsoid((0, 0.6, 0.14), (0.12, 0.12, 0.08)), CREAM_DK, feather=0.04)
    b.paint(Ellipsoid((0, 0.97, 0.12), (0.12, 0.05, 0.08)), mix(CREAM, FUR, 0.45), feather=0.04)

    def head_flow(P):  # fur combs back from the muzzle over the head, and down the body
        d = P - np.array([0, 0.86, 0.3])
        w = np.clip((P[:, 1] - 0.7) / 0.08, 0, 1)[:, None]
        return d * w + np.array([0, -1.0, 0]) * (1 - w)
    b.detail(strokes((0, 0.6, 0.0), (0.21, 0.42, 0.19), cells=22, length=1.0, width=0.0058, flow=head_flow, jitter=18, ridge=0.25,
                     region=Func(lambda P: -Ellipsoid((0, 0.83, 0.16), (0.12, 0.09, 0.08))(P), (-1, -1, -1), (1, 1, 1)), seed=6),
             depth=0.0012, darken=0.1)
    return b


def face_parts(m):
    mz = xpiece(m, "muzzle", color=CREAM, rigid="head", res=0.0042, lumps=0.0012, dents=4, dent_size=0.015, dent_depth=0.0015)
    for sx in (-1, 1):
        mz.add(Ellipsoid((sx * 0.044, 0.822, 0.196), (0.062, 0.05, 0.05), rot=(0, sx * 14, sx * -12)), k=0.02)
    mz.add(Ellipsoid((0, 0.772, 0.168), (0.05, 0.03, 0.042)), k=0.03)            # little chin
    mz.sub(Capsule((0, 0.84, 0.25), (0, 0.79, 0.245), 0.006), k=0.006)           # philtrum groove
    # whisker follicle dots in rows
    for sx in (-1, 1):
        for row, (y, n) in enumerate(((0.84, 3), (0.822, 4), (0.804, 4))):
            for i in range(n):
                x = sx * (0.03 + i * 0.016 + row * 0.005)
                p0, n0 = onsurf(mz._eval_shape, [(x, y, 0.26)])
                mz.sub(Sphere(p0[0], 0.0026), k=0.0015, color=CREAM_DK)
    nose = m.piece("nose", color=NOSE, gloss=210, rigid="head", res=0.0035, lumps=0.0006, mottle=0.03)
    nose.add(Ellipsoid((0, 0.866, 0.232), (0.038, 0.023, 0.026), rot=(-12, 0, 0)))
    nose.add(Ellipsoid((0, 0.854, 0.236), (0.021, 0.017, 0.02)), k=0.012)
    for sx in (-1, 1):
        nose.sub(Ellipsoid((sx * 0.016, 0.86, 0.258), (0.008, 0.005, 0.008), rot=(20, sx * 25, 0)), k=0.003, color="#0d0b0b")
    nose.add(Sphere((-0.012, 0.876, 0.25), 0.005), k=0.003, color="#5a5455", gloss=255)
    # clay whiskers: thin rolled threads, drooping slightly
    w = m.piece("whiskers", color="#efe7d5", gloss=80, rigid="head", res=0.0026, lumps=0.0, mottle=0.03, ao=False)
    for sx in (-1, 1):
        for i, (y, ang, ln) in enumerate(((0.83, 14, 0.13), (0.815, 2, 0.15), (0.8, -10, 0.13))):
            a = np.array([sx * 0.078, y + 0.006, 0.215])
            d = np.array([sx * np.cos(np.radians(ang)), np.sin(np.radians(ang)), 0.25])
            d /= np.linalg.norm(d)
            mid = a + d * ln * 0.55 + np.array([0, 0.008, 0])
            end = a + d * ln + np.array([0, -0.012, -0.01])
            w.add(Tube([a, mid, end], [0.0034, 0.0028, 0.0016], samples=6), k=0.002)
    ears = m.piece("ears", color=FUR, rigid="head", res=0.0045, lumps=0.0012, dents=2)
    for sx in (-1, 1):
        c = np.array([sx * 0.192, 0.925, -0.025])
        R = euler((0, sx * 60, sx * -15))
        ears.add(Ellipsoid(c, (0.036, 0.04, 0.02), rot=R))
        ears.sub(Ellipsoid(c + R @ np.array([0, -0.004, 0.016]), (0.022, 0.026, 0.012), rot=R), k=0.008, color=FUR_DK)


def arms(m):
    for sx, s in ((-1, "L"), (1, "R")):
        a = xpiece(m, f"arm_{s}", color=FUR, bone=f"elbow_{s}", res=0.0055, lumps=0.0022, dents=4, dent_size=0.02)
        sh = np.array([sx * 0.15, 0.625, 0.01])
        el = np.array([sx * 0.225, 0.505, 0.03])
        wr = np.array([sx * 0.25, 0.405, 0.05])
        a.add(Sphere(sh + (sx * 0.01, -0.01, 0), 0.062), bone=f"arm_{s}")
        a.add(Capsule(sh, el, 0.058, 0.05), k=0.03, bone=f"arm_{s}")
        a.add(Capsule(el, wr, 0.05, 0.045), k=0.03, bone=f"elbow_{s}")
        pc = np.array([sx * 0.258, 0.36, 0.06])
        a.add(Ellipsoid(pc, (0.045, 0.052, 0.042), rot=(10, 0, sx * -8)), k=0.025, bone=f"hand_{s}")
        for i in range(4):  # little finger bumps
            t = (i - 1.5) * 0.019
            a.add(Sphere(pc + np.array([sx * 0.006, -0.042, t + 0.004]), 0.0145), k=0.01, bone=f"hand_{s}")
        a.paint(Ellipsoid(pc + np.array([-sx * 0.03, -0.01, 0]), (0.02, 0.04, 0.035)), PAD, gloss=60, feather=0.012)
        a.detail(strokes((sx * 0.2, 0.5, 0.03), (0.08, 0.16, 0.08), cells=7, length=1.0, width=0.0055, flow=(0, -1, 0), ridge=0.25, seed=11 + int(sx)),
                 depth=0.0012, darken=0.1)


def legs(m):
    for sx, s in ((-1, "L"), (1, "R")):
        lg = xpiece(m, f"leg_{s}", color=FUR, bone=f"knee_{s}", res=0.0055, lumps=0.002)
        lg.add(Capsule((sx * 0.1, 0.27, 0.0), (sx * 0.105, 0.15, 0.02), 0.075, 0.064), bone=f"leg_{s}")
        lg.add(Capsule((sx * 0.105, 0.15, 0.02), (sx * 0.11, 0.06, 0.04), 0.064, 0.05), k=0.03, bone=f"knee_{s}")
        ft = xpiece(m, f"foot_{s}", color="#4d3122", gloss=55, rigid=f"foot_{s}", res=0.0048, lumps=0.0018, dents=3, dent_size=0.015)
        base = np.array([sx * 0.115, 0.03, 0.07])
        ft.add(Ellipsoid(base + (0, 0.008, -0.025), (0.06, 0.032, 0.065)))
        for t in np.linspace(-1, 1, 5):
            ang = np.radians(t * 24 + sx * 8)
            tip = base + np.array([np.sin(ang) * 0.1, -0.012, np.cos(ang) * 0.1])
            ft.add(Capsule(base + (0, 0.004, -0.01), tip, 0.019, 0.013), k=0.015)
        ft.add(Ellipsoid(base + (0, -0.008, 0.045), (0.085, 0.01, 0.06)), k=0.015)   # webbing
        ft.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.003)


def tail(m):
    t = xpiece(m, "tail", color=FUR, bone="tail2", res=0.006, lumps=0.0025, dents=5)
    pts = np.array([(0, 0.3, -0.11), (0, 0.22, -0.21), (0, 0.13, -0.3), (0, 0.075, -0.38), (0, 0.05, -0.46)])
    rad = [0.09, 0.088, 0.075, 0.055, 0.032]
    P, R = catmull(pts, np.array(rad), 6)
    n = len(P)
    t.add(Squash(Tube(P[: n // 2 + 1], R[: n // 2 + 1]), (0, 0.2, -0.25), (1.25, 0.82, 1.0)), bone="tail")
    t.add(Squash(Tube(P[n // 2:], R[n // 2:]), (0, 0.1, -0.4), (1.3, 0.7, 1.0)), k=0.02, bone="tail2")
    t.add(Ellipsoid((0, 0.3, -0.12), (0.1, 0.09, 0.08)), k=0.04, bone="hips")
    t.detail(strokes((0, 0.2, -0.3), (0.1, 0.18, 0.25), cells=10, length=1.0, width=0.0045,
                     flow=lambda P: np.tile([0, -0.6, -1.0], (len(P), 1)), ridge=0.25, seed=14), depth=0.0012, darken=0.1)
    t.paint(Ellipsoid((0, 0.05, -0.46), (0.06, 0.05, 0.07)), FUR_DK, feather=0.04)


def apron(m, f):
    # the apron hangs straight from the belly: base = body shape unioned with a hanging drape
    drape = Ellipsoid((0, 0.3, 0.025), (0.218, 0.42, 0.192))
    base = union_sdf([f, drape], 0.04)
    a = xpiece(m, "apron", color=APRON_W, bone="hips", res=0.0045, lumps=0.0015, dents=10, dent_size=0.02, dent_depth=0.002, mottle=0.04)
    a.add(Shell(base, -0.004, 0.009, Poly2D([(-0.205, 0.33), (0.205, 0.33), (0.235, 0.115), (0.0, 0.105), (-0.235, 0.115)], depth=(0.0, 0.5)), round=0.007), bone="hips")
    a.add(Shell(base, -0.004, 0.009, Poly2D([(-0.2, 0.44), (0.2, 0.44), (0.205, 0.31), (-0.205, 0.31)], depth=(0.0, 0.5)), round=0.007), k=0.004, bone="spine")
    a.add(Shell(f, -0.004, 0.009, Poly2D([(-0.105, 0.635), (0.105, 0.635), (0.135, 0.43), (-0.135, 0.43)], depth=(0.05, 0.5)), round=0.007), k=0.004, bone="chest")
    # waistband all the way round
    a.add(Shell(f, -0.004, 0.013, Box((0, 0.425, 0), (0.4, 0.019, 0.4)), round=0.006), k=0.004, color=APRON_B, bone="spine")
    # neck strap
    strap = snap(f, [(0.095, 0.625, 0.15), (0.12, 0.7, 0.08), (0.07, 0.75, -0.08), (-0.07, 0.75, -0.08), (-0.12, 0.7, 0.08), (-0.095, 0.625, 0.15)], offset=0.008)
    a.add(Tube(curve(strap, 24), 0.0105), k=0.004, color=APRON_B, bone="neck")
    # bow at the back
    bc = snap(f, [(0.0, 0.425, -0.25)], offset=0.012)[0]
    for sx in (-1, 1):
        a.add(Torus(bc + np.array([sx * 0.04, 0.008, -0.012]), 0.03, 0.009, rot=(80, 0, sx * 25)), k=0.006, color=APRON_B, bone="hips")
        a.add(Tube([bc + np.array([sx * 0.008, -0.01, -0.01]), bc + np.array([sx * 0.03, -0.07, -0.02]), bc + np.array([sx * 0.04, -0.12, -0.01])],
                   [0.011, 0.01, 0.009], samples=5), k=0.006, color=APRON_B, bone="hips")
    a.add(Ellipsoid(bc + np.array([0, 0, -0.012]), (0.016, 0.017, 0.013)), k=0.005, color=APRON_B, bone="hips")
    # vertical butcher's stripes on the bib and skirt
    stripes = bands((1, 0, 0), period=0.05, width=0.4, offset=0.01, soft=0.12, region=Box((0, 0.36, 0.12), (0.3, 0.32, 0.2)))
    a.pattern(stripes, APRON_B)
    a.detail(stripes, depth=-0.0012, darken=0)
    # hem fold and stitching
    hem = snap(base, [(x, 0.13 - 0.04 * (abs(x) < 0.01) * 0, 0.3) for x in np.linspace(-0.21, 0.21, 12)], offset=0.009)
    a.sub(stitches(hem, 26, length=0.008, r=0.0018), k=0.0012, color=shade(APRON_B, 0.7))
    # front pocket with horizontal stripes and a stub of pencil
    pk = xpiece(m, "pocket", color=APRON_W, bone="hips", res=0.004, lumps=0.001, mottle=0.04)
    pk.add(Shell(base, 0.006, 0.015, Poly2D([(0.03, 0.31), (0.16, 0.315), (0.165, 0.2), (0.035, 0.195)], depth=(0.0, 0.5)), round=0.006), bone="hips")
    pk.pattern(bands((0, 1, 0), period=0.03, width=0.45, soft=0.1), APRON_B)
    ptop = snap(base, [(0.06, 0.3, 0.3), (0.16, 0.3, 0.3)], offset=0.015)
    pk.sub(stitches([p + np.array([0, -0.012, 0]) for p in ptop], 9, length=0.008, r=0.0016), k=0.001)
    pen = xpiece(m, "pencil", color="#e6b43a", gloss=80, rigid="hips", res=0.0032, lumps=0.0005, mottle=0.03)
    p0 = snap(base, [(0.075, 0.3, 0.3)], offset=0.012)[0]
    pen.add(Capsule(p0 + np.array([0, -0.04, -0.002]), p0 + np.array([-0.012, 0.055, 0.004]), 0.0075))
    pen.add(Capsule(p0 + np.array([-0.012, 0.055, 0.004]), p0 + np.array([-0.014, 0.068, 0.004]), 0.0076), k=0.002, color="#d98c8c")


def bandana(m, f):
    hc = np.array([0, 0.89, 0.03])
    po, pn = np.array([0, 0.958, 0.03]), np.array([0, 1.0, -0.4])
    above = HalfSpace(po, -pn)
    bd = xpiece(m, "bandana", color=RED, gloss=45, rigid="hat", res=0.0042, lumps=0.0015, dents=8, dent_size=0.02, dent_depth=0.002)
    bd.add(Shell(f, -0.005, 0.011, above, bounds_from=Box(hc + (0, 0.1, -0.02), (0.25, 0.15, 0.24)), round=0.006))
    # rolled hem exactly along the cut edge
    ring = plane_ring(f, po + np.array([0, -0.004, 0]), pn, 40, offset=0.008)
    bd.add(Tube(np.vstack([ring, ring[:1]]), 0.0095), k=0.006)
    # Rosie-style knot on top, a little to her right, with two perky flaps
    kc = np.array([0.05, 1.07, 0.085])
    bd.add(Ellipsoid(kc, (0.034, 0.028, 0.03), rot=(0, 0, -20)), k=0.012)
    for sx, ang, ln in ((-1, 28, 0.075), (1, -38, 0.07)):
        tip = kc + np.array([sx * ln, 0.04, -0.01 + sx * 0.006])
        mid = (kc + tip) / 2 + np.array([0, 0.008, 0.004])
        fl = Tube([kc, mid, tip], [0.02, 0.026, 0.01], samples=6)
        bd.add(Squash(fl, mid, (1.0, 1.0, 0.45)), k=0.01)
        bd.sub(Capsule(kc + np.array([sx * 0.022, 0.016, 0.018]), tip + np.array([-sx * 0.006, 0.0, 0.01]), 0.0028), k=0.002)
    # pinch wrinkles radiating from the knot
    for ang in (-150, -110, -60, 160, 120):
        a = np.radians(ang)
        p1 = kc + np.array([np.cos(a) * 0.05, -0.012, np.sin(a) * 0.05])
        p2 = kc + np.array([np.cos(a) * 0.13, -0.06, np.sin(a) * 0.13])
        pts = snap(f, curve([p1, (p1 + p2) / 2, p2], 8), offset=0.011)
        bd.sub(Tube(pts, 0.0035), k=0.004)
    # polka dots pressed on
    pts = []
    rng = np.random.default_rng(4)
    for th in np.linspace(0.1, np.pi * 0.75, 6):
        for ph in np.linspace(0, 2 * np.pi, int(4 + 11 * np.sin(th)), endpoint=False):
            pts.append(hc + 0.25 * np.array([np.sin(th) * np.sin(ph + th), np.cos(th), np.sin(th) * np.cos(ph + th)]) + rng.normal(0, 0.006, 3))
    pts = snap(f, np.array(pts), offset=0.011)
    bd.paint(Segs(pts, pts, 0.011), "#efe4cf", feather=0.002)
