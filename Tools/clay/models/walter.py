"""Walter — walrus harbormaster. Barrel-chested in a navy double-breasted peacoat, captain's cap, a vast droopy
mustache over the mouth and two ivory tusks. Gruff but kind. 1.6 m to the top of the cap."""
import numpy as np
from clay import *
from kit import *
from kit_chars import *

OUT = "chars/walter"

SKIN = "#8e6250"       # dusty walrus brown-pink
SKIN_LT = "#b88a74"    # muzzle
SKIN_DK = "#664537"
STACHE = "#d6c49c"     # oatmeal bristles
STACHE_DK = "#a38c66"
NAVY = "#222d49"
NAVY_LT = "#2a3756"
NAVY_DK = "#161d31"
BRASS = "#c9993a"
IVORY = "#ece0c2"
CAP_W = "#e9e3d4"
CAP_K = "#24252a"
GOLD = "#d4a83e"

EYE_C = (0.118, 1.292, 0.3)
EYE_R = 0.035


def build():
    m = Model("walter", res=0.009)
    m.weight_softness = 0.035
    biped_rig(m, hip_y=0.46, chest_y=0.84, neck_y=1.04, head_y=1.2, shoulder_x=0.36, shoulder_y=0.96, hand_y=0.48,
              hip_x=0.17, knee_y=0.2, foot_y=0.06, foot_z=0.05, elbow_out=0.14, head_z=0.09)
    face_bones(m, EYE_C, EYE_R, brow_up=1.5, mouth_c=(0, 0.99, 0.39), hat_c=(0, 1.41, 0.08))
    m.bone("stache", "head", (0, 1.11, 0.37))

    hd = head(m)
    stache(m)
    face(m, EYE_C, EYE_R, lid=SKIN, brow_col=STACHE, look=(0, -0.02, 1), pupil_frac=0.55, toe_in=4, brow_kw=False,
         blush_c=(0.2, 1.215, 0.3), blush_r=0.038, blush_on=hd._eval_shape)
    bushy_brows(m)
    mouths(m, c=np.array([0.0, 0.99, 0.395]), w=0.1, lip="#6e3530", normal=(0, -0.2, 1), lip_r=0.0085)
    coat(m)
    arms(m)
    legs(m)
    cap(m)
    budget(m, {"coat": 10000, "collar": 4200, "pockets": 1200, "head": 9000, "stache": 6000, "buttons": 2600, "sleeve_*": 2800,
               "flipper_*": 2000, "leg_*": 1300, "foot_*": 1800, "tusks": 1500, "nose": 1000, "brow_*": 1200,
               "cap_crown": 3000, "cap_band": 1200, "cap_peak": 1200, "cap_badge": 1300, "mouth_*": 650, "eyeball_*": 1000,
               "lidhalf_*": 1000, "lidclosed_*": 1000, "eyehappy_*": 900, "pupil_*": 700, "blush_*": 300})

    m.socket("prop_R", "hand_R", (0.58, 0.36, 0.1))
    m.socket("bust", "head", (0, 1.2, 0.38))
    m.socket("talk", "head", (0, 1.84, 0.05))
    return m


# ---------------------------------------------------------------------------------------------------------------


def head(m):
    ex, ey, ez = EYE_C
    h = xpiece(m, "head", color=SKIN, bone="head", res=0.0075, lumps=0.0035, dents=18, dent_size=0.035, dent_depth=0.003)
    h.add(Ellipsoid((0, 1.27, 0.08), (0.28, 0.235, 0.26)), bone="head")
    h.add(Ellipsoid((0, 1.14, 0.13), (0.315, 0.165, 0.245)), k=0.09, bone="head")         # heavy jowls
    h.add(Ellipsoid((0, 1.13, 0.29), (0.22, 0.13, 0.13)), k=0.06, bone="head")            # muzzle under the stache
    h.add(Ellipsoid((0, 0.995, 0.3), (0.12, 0.072, 0.1)), k=0.045, bone="head")           # chin / lower lip
    h.add(Ellipsoid((0, 1.05, 0.04), (0.315, 0.14, 0.285)), k=0.07, bone="neck")           # neck fills the collar
    # puffy lower lids / eye bags: kind, a little tired
    for sx in (-1, 1):
        h.sub(Sphere((sx * ex, ey + 0.004, ez + 0.012), EYE_R * 1.08), k=0.022)
        h.add(Ellipsoid((sx * (ex + 0.004), ey - EYE_R * 0.95, ez + 0.006), (EYE_R * 1.25, EYE_R * 0.42, EYE_R * 0.55), rot=(0, sx * 25, sx * -8)), k=0.012, bone="head")
        h.add(Ellipsoid((sx * (ex + 0.002), ey + EYE_R * 0.62, ez + 0.004), (EYE_R * 1.22, EYE_R * 0.5, EYE_R * 0.98), rot=(-12, sx * 18, sx * 8)), k=0.012, bone="head")
    f = h._eval_shape
    h.paint(Ellipsoid((0, 1.11, 0.3), (0.23, 0.14, 0.13)), SKIN_LT, feather=0.03)
    h.paint(Ellipsoid((0, 0.99, 0.36), (0.09, 0.05, 0.08)), "#ad7466", feather=0.02)     # pink lower lip
    # forehead wrinkles and crow's feet, tool-scored
    for y in (1.395, 1.418):
        pts = surface_curve(f, [(-0.12, y, 0.32), (0.0, y + 0.01, 0.34), (0.12, y - 0.004, 0.32)], 12)
        h.sub(Tube(pts, 0.0038), k=0.004)
    for sx in (-1, 1):
        for dy in (-0.012, 0.004, 0.02):
            pts = surface_curve(f, [(sx * (ex + 0.05), ey + dy, ez - 0.03), (sx * (ex + 0.085), ey + dy * 1.6, ez - 0.07)], 6)
            h.sub(Tube(pts, 0.0032), k=0.003)
    for y in (1.035, 1.0, 0.965):
        pts = surface_curve(f, [(-0.22, y + 0.02, 0.12), (0, y - 0.01, 0.2), (0.22, y + 0.02, 0.12)], 14)
        h.sub(Tube(pts, 0.005), k=0.005)
    # sparse bristle pits on the cheeks
    h.detail(strokes((0, 1.2, 0.1), (0.29, 0.22, 0.25), cells=28, length=0.2, width=0.0042, density=0.5,
                     region=Ellipsoid((0, 1.16, 0.22), (0.33, 0.1, 0.17)), seed=4), depth=0.0016, darken=0.15)
    h.pattern(specks(14.0, 0.62, region=Ellipsoid((0, 1.34, 0.0), (0.3, 0.16, 0.26)), seed=8), shade(SKIN, 0.92))

    _nose(m)
    return h


def _nose(m):
    nose = xpiece(m, "nose", color="#53312b", gloss=95, rigid="head", res=0.005, lumps=0.0015, dents=3, dent_size=0.02)
    nose.add(Ellipsoid((0, 1.205, 0.37), (0.088, 0.052, 0.058), rot=(-15, 0, 0)))
    nose.add(Ellipsoid((0, 1.235, 0.34), (0.062, 0.036, 0.042), rot=(-25, 0, 0)), k=0.03)
    for sx in (-1, 1):
        nose.sub(Ellipsoid((sx * 0.036, 1.205, 0.423), (0.017, 0.01, 0.02), rot=(30, sx * 20, 0)), k=0.006, color="#24150f")
    nose.paint(Ellipsoid((-0.022, 1.24, 0.395), (0.026, 0.013, 0.02)), "#80544a", gloss=170)

    t = xpiece(m, "tusks", color=IVORY, gloss=110, rigid="head", res=0.0045, lumps=0.0012, dents=4, dent_size=0.015, dent_depth=0.0015)
    for sx in (-1, 1):
        x0 = sx * 0.078
        pts = [(x0, 1.07, 0.33), (x0 + sx * 0.01, 0.98, 0.385), (x0 + sx * 0.008, 0.89, 0.425), (x0 - sx * 0.006, 0.82, 0.45)]
        t.add(Tube(pts, [0.032, 0.027, 0.019, 0.009], samples=8), k=0.01)
        for y in (0.985, 0.95, 0.915):
            t.sub(Torus((x0 + sx * 0.01, y, 0.385 + (0.985 - y) * 0.45), 0.026, 0.0022, rot=(-25, 0, 0)), k=0.002)
    t.paint(Box((0, 1.02, 0.36), (0.2, 0.05, 0.1)), "#d6c394", feather=0.03)


def stache(m):
    s = xpiece(m, "stache", color=STACHE, rigid="stache", res=0.0065, lumps=0.002, lump_freq=7, dents=8, dent_size=0.03, dent_depth=0.003)
    s.add(Ellipsoid((0, 1.115, 0.37), (0.14, 0.072, 0.075)))
    for sx in (-1, 1):
        s.add(Tube([(sx * 0.03, 1.12, 0.39), (sx * 0.13, 1.11, 0.38), (sx * 0.215, 1.05, 0.335), (sx * 0.255, 0.96, 0.29), (sx * 0.25, 0.87, 0.265)],
                   [0.072, 0.078, 0.064, 0.044, 0.024], samples=8), k=0.05)
        s.add(Ellipsoid((sx * 0.09, 1.125, 0.4), (0.092, 0.068, 0.062), rot=(0, 0, sx * -16)), k=0.04)
    # a slight parting under the nose and a lifted lower fringe
    s.sub(Capsule((0, 1.17, 0.46), (0, 1.07, 0.47), 0.012), k=0.02)

    def flow(P):
        sx = np.sign(P[:, 0] + 1e-6)
        return np.stack([sx * (0.6 + np.abs(P[:, 0]) * 2.5), -np.ones(len(P)), np.zeros(len(P))], axis=1)
    s.detail(combed((0, 1.3, 0.37), (0, 0, 1), n=78, sharp=2.6, wobble=0.45, wfreq=6, seed=2), depth=0.006, darken=0.24)
    s.detail(combed((0, 1.3, 0.37), (0, 0, 1), n=31, sharp=8, wobble=0.6, wfreq=5, seed=7), depth=0.004, darken=0.1)
    s.paint(Ellipsoid((0, 1.0, 0.36), (0.3, 0.07, 0.2)), "#e3d6b6", feather=0.05)      # sun-bleached tips
    s.paint(Ellipsoid((0, 1.17, 0.37), (0.18, 0.04, 0.1)), STACHE_DK, feather=0.04)    # darker roots by the nose


def bushy_brows(m):
    ex, ey, ez = EYE_C
    r = EYE_R * 1.3
    for sx, side in ((-1, "L"), (1, "R")):
        b = xpiece(m, f"brow_{side}", color=STACHE, gloss=35, rigid=f"brow_{side}", res=0.0042, lumps=0.0012, lump_freq=30, mottle=0.05)
        base = np.array([sx * (ex + 0.006), ey + EYE_R * 1.75, ez + EYE_R * 0.25])
        b.add(Tube([base + (-sx * r * 1.15, r * 0.1, r * 0.1), base + (0, r * 0.25, r * 0.2), base + (sx * r * 1.3, -r * 0.3, -r * 0.4)],
                   [r * 0.36, r * 0.46, r * 0.3], samples=6))
        b.add(Tube([base + (-sx * r * 0.7, r * 0.45, -r * 0.05), base + (sx * r * 0.5, r * 0.5, -r * 0.05), base + (sx * r * 1.7, r * 0.1, -r * 0.7)],
                   [r * 0.3, r * 0.32, r * 0.12], samples=6), k=r * 0.15)
        b.add(Tube([base + (sx * r * 0.3, -r * 0.05, r * 0.1), base + (sx * r * 1.2, -r * 0.35, -r * 0.25), base + (sx * r * 1.8, -r * 0.75, -r * 0.75)],
                   [r * 0.27, r * 0.24, r * 0.1], samples=6), k=r * 0.15)
        b.detail(combed(base + (-sx * r * 1.6, -r * 1.6, 0), (0, 0, 1), n=70, sharp=2.5, wobble=0.4, wfreq=60, seed=3 if sx > 0 else 4),
                 depth=0.0024, darken=0.2)


# ---------------------------------------------------------------------------------------------------------------


def coat_base():
    return [Ellipsoid((0, 0.5, 0.0), (0.44, 0.3, 0.38)), Ellipsoid((0, 0.71, 0.015), (0.455, 0.27, 0.395)),
            Ellipsoid((0, 0.84, 0.07), (0.415, 0.22, 0.39)), Ellipsoid((0, 0.97, 0.02), (0.37, 0.12, 0.3)),
            Ellipsoid((0, 0.3, 0.0), (0.42, 0.09, 0.365))]


def coat(m):
    c = xpiece(m, "coat", color=NAVY, bone="spine", res=0.0095, lumps=0.0035, lump_freq=7, dents=26, dent_size=0.045, dent_depth=0.004, mottle=0.06)
    e = coat_base()
    for prim, k, bone in zip(e, (0, 0.1, 0.12, 0.08, 0.09), ("hips", "spine", "chest", "chest", "hips")):
        c.add(prim, k=k, bone=bone)
    c.inter(HalfSpace((0, 0.245, 0), (0, -1, 0)), k=0.012)
    c.sub(Ellipsoid((0, 0.245, 0.0), (0.385, 0.2, 0.33)), k=0.02)                     # hollow: sheet thickness at hem
    f = c._eval_shape

    def overlap(P):  # double-breasted: the wearer's left panel lies over the right
        edge = 0.075 + (P[:, 1] - 0.6) * 0.04
        w = np.clip((edge - P[:, 0]) / 0.006 + 0.5, 0, 1)
        front = np.clip((P[:, 2] - 0.12) / 0.05, 0, 1)
        top = np.clip((0.8 - P[:, 1]) / 0.02, 0, 1)
        return -w * front * top
    c.detail(overlap, depth=0.007, darken=0)
    edge = surface_curve(f, [(0.078, 0.8, 0.39), (0.075, 0.55, 0.41), (0.07, 0.255, 0.37)], 30)
    c.sub(Tube(edge + np.array([0.004, 0, 0]), 0.0045), k=0.003, color=NAVY_DK)
    hem = snap(f, [(np.sin(a) * 0.43, 0.28, np.cos(a) * 0.37) for a in np.linspace(-np.pi * 0.97, np.pi * 0.97, 30)])
    c.sub(stitches(hem, 76, length=0.014, r=0.0028), k=0.002, color=NAVY_DK)
    back = surface_curve(f, [(0, 1.0, -0.28), (0, 0.72, -0.39), (0, 0.42, -0.36)], 24)
    c.sub(Tube(back, 0.004), k=0.003, color=NAVY_DK)
    c.sub(Box((0, 0.31, -0.36), (0.0045, 0.075, 0.06)), k=0.003, color=NAVY_DK)          # back vent
    for sx in (-1, 1):                                                                     # side seams
        side = surface_curve(f, [(sx * 0.37, 0.9, -0.02), (sx * 0.455, 0.65, -0.03), (sx * 0.42, 0.28, -0.03)], 20)
        c.sub(Tube(side, 0.0035), k=0.003, color=NAVY_DK)
    c.pattern(specks(70.0, 0.62, seed=12), NAVY_LT)

    # pocket flaps: conforming sheets (slightly uneven)
    pk = xpiece(m, "pockets", color=NAVY, bone="hips", res=0.006, lumps=0.0015, mottle=0.06, merge=None)
    for sx, y, ang in ((-1, 0.45, -7), (1, 0.44, 5)):
        a = np.radians(ang)
        cx = sx * 0.27
        pts = [(cx + dx * np.cos(a) - dy * np.sin(a), y + dx * np.sin(a) + dy * np.cos(a)) for dx, dy in ((-0.1, 0.03), (0.1, 0.03), (0.1, -0.035), (-0.1, -0.035))]
        pk.add(Shell(f, -0.006, 0.011, Poly2D(pts, depth=(0.0, 0.6)), round=0.009), bone="hips")
        st = [(cx - 0.085 * np.cos(a), y - 0.085 * np.sin(a) - 0.024, 0.45), (cx + 0.085 * np.cos(a), y + 0.085 * np.sin(a) - 0.024, 0.45)]
        st = snap(f, st, offset=0.011)
        pk.sub(stitches(st, 10, length=0.011, r=0.0022), k=0.0015, color=NAVY_DK)
    pk.pattern(specks(70.0, 0.62, seed=19), NAVY_LT)

    # turned-up collar: a standing band, higher at the back, with a rolled lip; lapels as rolled sheets on the chest
    col = xpiece(m, "collar", color=NAVY_LT, bone="chest", res=0.0075, lumps=0.0025, dents=8, dent_size=0.03, dent_depth=0.003, mottle=0.07)
    col.add(Ellipsoid((0, 1.03, 0.04), (0.37, 0.4, 0.34)), bone="chest")
    col.sub(Ellipsoid((0, 1.03, 0.05), (0.305, 0.6, 0.275)), k=0.012)
    col.inter(HalfSpace((0, 1.165, 0.05), (0, 1, 0.28)), k=0.02)
    col.inter(HalfSpace((0, 0.96, 0), (0, -1, 0)), k=0.02)
    col.sub(Poly2D([(-0.15, 0.9), (0.15, 0.9), (0.11, 1.4), (-0.11, 1.4)], frame=euler((0, 0, 0)), depth=(0.12, 0.6)), k=0.04)
    lip = []
    for a in np.linspace(0.3, 1.7, 15) * np.pi:
        x, z = np.sin(a) * 0.37, 0.04 + np.cos(a) * 0.34
        y = 1.165 - 0.28 * (z - 0.05) / np.sqrt(1 + 0.28 ** 2) * np.sqrt(1 + 0.28 ** 2)
        fct = np.sqrt(max(0.0, 1 - ((y - 1.03) / 0.4) ** 2))
        lip.append((x * fct - np.sin(a) * 0.012, y - 0.008, 0.04 + (z - 0.04) * fct - np.cos(a) * 0.012))
    col.add(Tube(lip, 0.024, samples=4), k=0.025, bone="neck")
    for sx in (-1, 1):
        o = 1 if sx > 0 else 0
        pts = [(0.13, 1.06), (0.3, 1.0), (0.27, 0.925), (0.31, 0.9), (0.105 - 0.03 * o, 0.79), (0.08, 0.88)]
        pts = [(sx * x, y) for x, y in pts]
        if sx < 0:
            pts = pts[::-1]
        col.add(Shell(f, -0.01, 0.014 + 0.004 * (sx < 0), Poly2D(pts, depth=(0.1, 0.7)), round=0.012), k=0.02, bone="chest")
        ed = snap(f, [(sx * 0.27, 0.925, 0.3), (sx * 0.31, 0.9, 0.3), (sx * 0.12, 0.8, 0.38)], offset=0.014)
        col.sub(stitches(ed, 12, length=0.012, r=0.0022), k=0.0015, color=NAVY_DK)
    col.pattern(specks(70.0, 0.62, seed=13), "#34436a")

    # brass buttons: two rows of three, a little uneven
    b = xpiece(m, "buttons", color=BRASS, gloss=170, bone="spine", res=0.0038, lumps=0.0006, mottle=0.05)
    rows = [(0.74, "chest"), (0.6, "spine"), (0.46, "hips")]
    for j, (y, bone) in enumerate(rows):
        for sx in (-1, 1):
            x = sx * (0.14 - j * 0.004) + (0.004 if (j == 1 and sx > 0) else 0)
            p0, n0 = onsurf(f, [(x, y + (0.006 if sx < 0 and j == 2 else 0), 0.4)])
            p0, n0 = p0[0], n0[0]
            lift = 0.007 if x < 0.075 else 0.0
            button(b, p0 + n0 * (0.004 + lift), n0, 0.029, BRASS, holes=0, bone=bone)
            pc = p0 + n0 * (0.017 + lift)
            R = surf_frame(n0)
            dk = "#86621f"
            b.sub(Capsule(pc + R @ np.array([0, 0.012, 0]), pc + R @ np.array([0, -0.012, 0]), 0.0028), k=0.001, color=dk)
            b.sub(Tube([pc + R @ np.array([-0.011, -0.004, 0]), pc + R @ np.array([0, -0.014, 0]), pc + R @ np.array([0.011, -0.004, 0])], 0.0026, samples=4), k=0.001, color=dk)
            b.sub(Capsule(pc + R @ np.array([-0.006, 0.007, 0]), pc + R @ np.array([0.006, 0.007, 0]), 0.0024), k=0.001, color=dk)
    # the top pair half-hidden under the lapels: one more pair peeking at chest level
    for sx in (-1, 1):
        p0, n0 = onsurf(f, [(sx * 0.15, 0.86, 0.36)])
        button(b, p0[0] + n0[0] * 0.003, n0[0], 0.022, BRASS, holes=0, bone="chest", rim=False)


def arms(m):
    for sx, s in ((-1, "L"), (1, "R")):
        sl = xpiece(m, f"sleeve_{s}", color=NAVY, bone=f"elbow_{s}", res=0.0085, lumps=0.003, dents=6, dent_size=0.035, dent_depth=0.003, mottle=0.06)
        sh = np.array([sx * 0.33, 0.965, 0.02])
        el = np.array([sx * 0.495, 0.72, 0.03])
        wr = np.array([sx * 0.545, 0.53, 0.06])
        sl.add(Ellipsoid(sh + (sx * 0.02, -0.02, 0), (0.125, 0.135, 0.135)), bone=f"arm_{s}")
        sl.add(Capsule(sh + (sx * 0.02, -0.03, 0), el, 0.115, 0.102), k=0.05, bone=f"arm_{s}")
        sl.add(Capsule(el, wr, 0.102, 0.094), k=0.05, bone=f"elbow_{s}")
        d = (wr - el) / np.linalg.norm(wr - el)
        sl.add(Cylinder(wr - d * 0.01, 0.104, 0.04, rot=look_rot(d), round=0.025), k=0.012, bone=f"hand_{s}")  # turned-back cuff
        sl.sub(Capsule(wr - d * 0.02, wr + d * 0.2, 0.072), k=0.01)
        sl.sub(Torus(wr - d * 0.05, 0.103, 0.004, rot=look_rot(d)), k=0.003, color=NAVY_DK)
        for i in range(3):
            pa = el + np.array([sx * -0.02, 0.025 - i * 0.022, 0.1])
            sl.sub(Capsule(pa + (sx * 0.05, 0.012, -0.03), pa + (-sx * 0.045, -0.006, 0.0), 0.0055), k=0.006)
        f = sl._eval_shape
        for i in range(2):
            p0, n0 = onsurf(f, [wr - d * (0.005 + i * 0.03) + (sx * 0.07, 0, -0.06)])
            sl.add(Sphere(p0[0] + n0[0] * 0.005, 0.012), k=0.002, color=BRASS, gloss=170)
        sl.pattern(specks(70.0, 0.62, seed=14 + int(sx)), NAVY_LT)

        fl = xpiece(m, f"flipper_{s}", color=SKIN, bone=f"hand_{s}", res=0.0065, lumps=0.003, dents=5, dent_size=0.02, dent_depth=0.0025)
        fl.add(Capsule(wr - d * 0.06, wr + d * 0.05, 0.074, 0.07), bone=f"hand_{s}")
        pc = wr + d * 0.15 + np.array([sx * 0.005, 0, 0.02])
        fl.add(Ellipsoid(pc, (0.058, 0.135, 0.105), rot=(8, 0, sx * -10)), k=0.045, bone=f"hand_{s}")
        for i, dz in enumerate((-0.06, -0.03, 0.0, 0.03, 0.06)):
            a = pc + np.array([0, 0.08, dz * 0.7])
            b = pc + np.array([sx * 0.012, -0.1 + abs(dz) * 0.45, dz * 1.05])
            fl.add(Capsule(a, b, 0.019, 0.016), k=0.014, bone=f"hand_{s}")
            if i < 4:
                g0 = pc + np.array([sx * 0.045, 0.04, dz + 0.015])
                fl.sub(Capsule(g0, g0 + np.array([sx * 0.006, -0.11, 0.002]), 0.0042), k=0.003)
            fl.add(Ellipsoid(b + np.array([sx * 0.006, -0.014, 0]), (0.012, 0.013, 0.01)), k=0.004, color="#33241f", gloss=120, bone=f"hand_{s}")
        fl.paint(Ellipsoid(pc + np.array([-sx * 0.045, 0, 0]), (0.03, 0.14, 0.11)), SKIN_DK, feather=0.02)


def legs(m):
    for sx, s in ((-1, "L"), (1, "R")):
        lg = xpiece(m, f"leg_{s}", color=SKIN, bone=f"knee_{s}", res=0.008, lumps=0.003, dents=4)
        lg.add(Capsule((sx * 0.17, 0.42, 0), (sx * 0.17, 0.2, 0.01), 0.13, 0.118), bone=f"leg_{s}")
        lg.add(Capsule((sx * 0.17, 0.2, 0.01), (sx * 0.175, 0.07, 0.04), 0.118, 0.1), k=0.04, bone=f"knee_{s}")
        lg.inter(HalfSpace((0, 0.006, 0), (0, -1, 0)), k=0.006)     # stays above the table (hidden in the foot)
        for y in (0.19, 0.15):
            p0 = np.array([sx * 0.17, y, 0.13])
            lg.sub(Capsule(p0 + (-0.07, 0, -0.02), p0 + (0.07, -0.004, -0.02), 0.0055), k=0.005)

        ft = xpiece(m, f"foot_{s}", color=SKIN_DK, gloss=50, rigid=f"foot_{s}", res=0.0065, lumps=0.003, dents=5, dent_size=0.025)
        base = np.array([sx * 0.18, 0.045, 0.07])
        ft.add(Ellipsoid(base + (0, 0.01, -0.02), (0.115, 0.05, 0.11)))
        for i, t in enumerate(np.linspace(-1, 1, 5)):
            ang = np.radians(t * 26 + sx * 10)
            tip = base + np.array([np.sin(ang) * 0.19, -0.02, np.cos(ang) * 0.19])
            ft.add(Capsule(base + (0, 0.005, 0.0), tip, 0.034, 0.024), k=0.025)
            ft.add(Ellipsoid(tip + np.array([np.sin(ang) * 0.016, 0.008, np.cos(ang) * 0.016]), (0.013, 0.009, 0.013)), k=0.003, color="#2b201d", gloss=110)
        ft.add(Ellipsoid(base + (0, -0.012, 0.09), (0.16, 0.017, 0.1)), k=0.03)   # webbing
        ft.inter(HalfSpace((0, 0.0, 0), (0, -1, 0)), k=0.004)
        ft.paint(Ellipsoid(base + (0, 0.055, 0.02), (0.13, 0.035, 0.11)), SKIN, feather=0.03)


def cap(m):
    hc = np.array([0, 1.41, 0.08])
    Rt = euler((-9, 0, -5))

    def H(x, y, z):
        return hc + Rt @ np.array([x, y, z])

    band = xpiece(m, "cap_band", color=CAP_K, gloss=70, rigid="hat", res=0.006, lumps=0.0015, dents=4, dent_size=0.02, merge="cap")
    band.add(Cylinder(H(0, 0.045, 0), 0.232, 0.048, rot=Rt, round=0.012))
    band.sub(Cylinder(H(0, -0.005, 0), 0.212, 0.05, rot=Rt, round=0.01), k=0.006)
    pk = xpiece(m, "cap_peak", color="#1c1d22", gloss=165, rigid="hat", res=0.0045, lumps=0.001, dents=3, dent_size=0.02, merge="cap")
    pk.add(Cylinder(H(0, 0.008, 0.16), 0.22, 0.011, rot=Rt @ euler((20, 0, 0)), round=0.009))
    pk.inter(HalfSpace(H(0, 0, 0.13), Rt @ np.array([0, 0, -1])), k=0.012)
    pk.inter(Ellipsoid(H(0, 0.0, 0.12), (0.235, 0.2, 0.26), rot=Rt), k=0.01)
    pk.sub(Cylinder(H(0, 0.0, 0.0), 0.214, 0.1, rot=Rt), k=0.006)
    cr = xpiece(m, "cap_crown", color=CAP_W, gloss=55, rigid="hat", res=0.006, lumps=0.0025, dents=7, dent_size=0.04, dent_depth=0.004, merge="cap")
    cr.add(Ellipsoid(H(0, 0.14, 0.015), (0.285, 0.06, 0.275)))
    cr.add(Cylinder(H(0, 0.105, 0.0), 0.226, 0.03, rot=Rt, round=0.015), k=0.04)
    cr.add(Torus(H(0, 0.138, 0.015), 0.258, 0.03, rot=Rt), k=0.02)              # crown welt
    cr.sub(Sphere(H(0.05, 0.28, -0.03), 0.09), k=0.03)                            # pushed-in top
    for a in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        p = H(np.sin(a) * 0.11, 0.197, 0.015 + np.cos(a) * 0.11)
        q = H(np.sin(a) * 0.255, 0.168, 0.015 + np.cos(a) * 0.245)
        cr.sub(Capsule(p, q, 0.0035), k=0.003)
    gd = xpiece(m, "cap_badge", color=GOLD, gloss=200, rigid="hat", res=0.0035, lumps=0.0006, mottle=0.04, merge="cap")
    cord = [H(np.sin(a) * 0.236, 0.022, np.cos(a) * 0.236) for a in np.linspace(-1.2, 1.2, 9)]
    gd.add(Tube(cord, 0.0075, samples=4))
    for sxx in (-1, 1):
        gd.add(Sphere(H(sxx * np.sin(1.2) * 0.238, 0.022, np.cos(1.2) * 0.238), 0.012), k=0.003)
    bc = H(0, 0.06, 0.236)
    R = Rt
    gd.add(Ellipsoid(bc, (0.03, 0.028, 0.008), rot=R), k=0.004)
    for sxx in (-1, 1):
        for i in range(4):
            a = np.radians(-60 + i * 38)
            lp = bc + R @ np.array([sxx * np.cos(a) * 0.044, np.sin(a) * 0.036 + 0.006, -0.002])
            gd.add(Ellipsoid(lp, (0.012, 0.006, 0.005), rot=R @ euler((0, 0, sxx * (np.degrees(a) + 90)))), k=0.003)
    gd.sub(Capsule(bc + R @ np.array([0, 0.017, 0.009]), bc + R @ np.array([0, -0.015, 0.009]), 0.0034), k=0.0015, color="#86621f")
    gd.sub(Tube([bc + R @ np.array([-0.013, -0.006, 0.009]), bc + R @ np.array([0, -0.018, 0.009]), bc + R @ np.array([0.013, -0.006, 0.009])], 0.003, samples=4), k=0.0015, color="#86621f")
