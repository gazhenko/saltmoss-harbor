"""Professor Inkwell — octopus curator of the Tidewrack Museum. A big bulbous dusty-rose mantle sagging back like a
heavy nightcap and freckled with darker spots, large wise eyes in raised sockets (gold monocle on the right), bushy
white professor's brows, a tweed waistcoat over a shirt-front with a plum bow tie and a pocket-watch chain. Two front
tentacles act as arms; six walking tentacles splay from under the body, each skinned along its own
4-bone chain with pale suckers. 1.3 m."""
import numpy as np
from scipy.spatial import cKDTree
from clay import *
from kit import *
from kit_chars import *

OUT = "chars/inkwell"

SKIN = "#8c565c"        # dusty rose
SKIN_DK = "#673540"
SKIN_LT = "#d6a69c"     # pale peachy underside / suckers
SKIN_SP = "#5a2733"     # deep freckles
SKIN_MZ = "#9e6569"     # lighter muzzle
TWEED = "#80704f"
TWEED_DK = "#54462f"
TWEED_CHK = "#a4562f"   # rust windowpane check
SATIN = "#4e2c45"
SHIRT = "#ece4d2"
BOW = "#7a2236"
GOLD = "#d2a443"
BROW = "#e2dcd6"

EYE_C = (0.108, 0.878, 0.212)
EYE_R = 0.055

# six walking tentacles: angle around Y from the front (+Z), reach, curl, length tweak (hand-made asymmetry)
TENTS = [(30, 1.0, 1.05, 1.0), (88, 1.04, 0.8, 1.03), (147, 0.95, 1.15, 0.95), (-150, 1.0, 0.9, 1.0), (-91, 1.02, 1.12, 1.02), (-27, 0.97, 0.88, 0.98)]
TENT_R = np.array([0.088, 0.077, 0.061, 0.047, 0.036, 0.026, 0.018, 0.011])


def tentacle_path(theta_deg, reach=1.0, curl=1.0, length=1.0, base_r=0.11, base_y=0.33):
    t = np.radians(theta_deg)
    L = 0.9 * length * reach

    def rad(r):
        return np.sin(t) * r, np.cos(t) * r
    prof = [(base_r, base_y), (0.24 * L, 0.2), (0.35 * L, 0.088), (0.46 * L, 0.05), (0.56 * L, 0.05 + 0.01 * curl),
            (0.62 * L, 0.09 * curl + 0.02), (0.6 * L, 0.14 * curl + 0.02), (0.555 * L, 0.125 * curl + 0.02)]
    pts = []
    for r, y in prof:
        x, z = rad(r)
        pts.append((x, y, z))
    return np.array(pts), TENT_R.copy()


def build():
    m = Model("inkwell", res=0.0065)
    m.weight_softness = 0.022
    m.bone("root")
    m.bone("hips", "root", (0, 0.36, 0))
    m.bone("spine", "hips", (0, 0.48, 0))
    m.bone("chest", "spine", (0, 0.6, 0.01))
    m.bone("neck", "chest", (0, 0.7, 0.02))
    m.bone("head", "neck", (0, 0.84, 0.0))
    # front tentacles = arms, emerging from the waistcoat's armholes
    arm_pts = {}
    for sx, s in ((-1, "L"), (1, "R")):
        pts = np.array([(sx * 0.16, 0.6, 0.02), (sx * 0.25, 0.54, 0.06), (sx * 0.315, 0.45, 0.09), (sx * 0.345, 0.35, 0.12),
                        (sx * 0.34, 0.26, 0.16), (sx * 0.31, 0.22, 0.21), (sx * 0.285, 0.25, 0.24), (sx * 0.295, 0.285, 0.228)])
        arm_pts[s] = pts
        m.bone(f"arm_{s}", "chest", pts[0])
        m.bone(f"elbow_{s}", f"arm_{s}", pts[2])
        m.bone(f"hand_{s}", f"elbow_{s}", pts[4])
    # walking tentacles
    paths = []
    for k, (th, reach, curl, ln) in enumerate(TENTS):
        P, R = tentacle_path(th, reach, curl, ln)
        paths.append((P, R))
        m.bone(f"tent{k}_0", "hips", P[0])
        m.bone(f"tent{k}_1", f"tent{k}_0", P[1])
        m.bone(f"tent{k}_2", f"tent{k}_1", P[2])
        m.bone(f"tent{k}_3", f"tent{k}_2", P[4])
    face_bones(m, EYE_C, EYE_R, brow_up=1.55, mouth_c=(0, 0.776, 0.235))

    body = mantle(m, paths)
    f = body._eval_shape
    face(m, EYE_C, EYE_R, lid=SKIN, brow_col=BROW, look=(0, -0.01, 1), pupil_frac=0.5, ring="#d6a640", toe_in=4, brow_kw=False,
         blush_c=(0.165, 0.775, 0.19), blush_r=0.036, blush_on=f)
    bushy_brows(m, EYE_C, EYE_R, BROW, scale=1.05, lift=1.42, fwd=0.35, droop=1.2, seed=5)
    mp, mn = onsurf(f, [(0.0, 0.776, 0.3)])
    mouths(m, c=mp[0] + mn[0] * 0.003, w=0.096, lip="#5a2236", normal=mn[0], lip_r=0.0076)
    monocle(m)
    for k, (P, R) in enumerate(paths):
        tentacle(m, f"tentacle_{k}", P, R, [f"tent{k}_0", f"tent{k}_1", f"tent{k}_2", f"tent{k}_3"], seed=k)
    for s in ("L", "R"):
        P = arm_pts[s]
        R = np.array([0.064, 0.058, 0.05, 0.042, 0.032, 0.023, 0.016, 0.011])
        tentacle(m, f"arm_{s}", P, R, [f"arm_{s}", f"arm_{s}", f"elbow_{s}", f"hand_{s}"], seed=10 + (s == "R"), arm=True)
    waistcoat(m, body_base)
    budget(m, {"body": 15000, "waistcoat": 12000, "shirt": 1600, "bowtie": 1100, "watch_chain": 1100, "buttons": 1400, "monocle": 1300,
               "tentacle_*": 2900, "arm_*": 2500, "brow_*": 1300,
               "eyeball_*": 1100, "lidhalf_*": 1000, "lidclosed_*": 1000, "eyehappy_*": 900, "pupil_*": 700,
               "blush_*": 300, "mouth_*": 600})

    m.socket("prop_R", "hand_R", (0.3, 0.25, 0.23))
    m.socket("bust", "head", (0, 0.86, 0.3))
    m.socket("talk", "head", (0, 1.5, -0.08))
    return m


# the body's big forms (prim, smooth-k, bone): mantle sack sagging back, face, neck, pot belly, hips
BODY = [(Ellipsoid((0, 1.04, -0.1), (0.285, 0.28, 0.3), rot=(-22, 0, 3)), 0.0, "head"),        # crown of the mantle
        (Ellipsoid((0, 0.99, -0.27), (0.262, 0.245, 0.235), rot=(10, 0, -4)), 0.12, "head"),   # heavy bulb sagging back
        (Ellipsoid((0, 0.845, 0.045), (0.25, 0.17, 0.215)), 0.1, "head"),                     # face
        (Ellipsoid((0, 0.74, -0.06), (0.215, 0.11, 0.2)), 0.08, "neck"),                      # nape: no pinch at the back
        (Ellipsoid((0, 0.5, 0.025), (0.218, 0.205, 0.205)), 0.09, "spine"),                   # pot belly
        (Ellipsoid((0, 0.36, 0.0), (0.2, 0.1, 0.19)), 0.06, "hips")]


def body_base(P):
    """Cheap copy of the body's smooth union (no eye mounds/wrinkles): the surface garments are pressed onto."""
    d = BODY[0][0](P)
    for prim, k, _ in BODY[1:]:
        d = smin_np(d, prim(P), k)
    return d


def mantle(m, paths):
    b = xpiece(m, "body", color=SKIN, gloss=75, bone="head", lumps=0.003, lump_freq=8, dents=26, dent_size=0.035, dent_depth=0.0035)
    for prim, k, bone in BODY:
        b.add(prim, k=k, bone=bone)
    # cheeks either side of the mouth: jowly old professor
    for sx in (-1, 1):
        b.add(Ellipsoid((sx * 0.095, 0.765, 0.17), (0.075, 0.055, 0.06), rot=(0, sx * 20, 0)), k=0.04, bone="head")
    # raised eye mounds with heavy, wise upper lids
    ex, ey, ez = EYE_C
    for sx in (-1, 1):
        c = np.array([sx * ex, ey, ez])
        b.add(Sphere(c + np.array([sx * 0.008, 0.0, -0.022]), EYE_R * 1.28), k=0.04, bone="head")
        b.sub(Sphere(c + np.array([0, 0.0, 0.01]), EYE_R * 1.04), k=0.012)
        b.add(Ellipsoid(c + np.array([sx * 0.004, EYE_R * 0.62, -0.002]), (EYE_R * 1.18, EYE_R * 0.5, EYE_R * 1.0), rot=(-14, sx * 14, sx * 6)), k=0.014, bone="head")
    f0 = b._eval_shape
    # forehead wrinkles (it is a thinking brow), sag folds where the bulb hangs over the nape
    for i, (y, z) in enumerate(((1.2, 0.13), (1.155, 0.175), (1.11, 0.205))):
        pts = surface_curve(f0, [(-0.19 + i * 0.01, y - 0.03, z - 0.06), (0.01, y + 0.004 * i, z), (0.2 - i * 0.012, y - 0.02, z - 0.06)], 14)
        b.sub(Tube(pts, 0.0048), k=0.005)
    for i, y in enumerate((0.8, 0.765)):
        pts = surface_curve(f0, [(-0.17, y + 0.03, -0.2), (0.0, y, -0.29 + i * 0.02), (0.17, y + 0.03, -0.2)], 14)
        b.sub(Tube(pts, 0.0052), k=0.006)
    b.paint(Ellipsoid((0, 0.24, 0.0), (0.24, 0.06, 0.23)), SKIN_LT, feather=0.04)                    # pale underside
    b.paint(Ellipsoid((0, 0.76, 0.17), (0.13, 0.065, 0.08)), SKIN_MZ, feather=0.04)                 # lighter muzzle
    b.paint(Ellipsoid((0, 1.0, -0.2), (0.3, 0.3, 0.3)), shade(SKIN, 0.94), feather=0.12)            # slightly deeper crown
    # darker freckles: pressed-in blobs of a deeper clay, bigger and denser on the back of the mantle
    rng = np.random.default_rng(11)
    sp, rr = [], []
    while len(sp) < 120:
        th = rng.uniform(0.0, 2.2)
        ph = rng.uniform(0, 2 * np.pi)
        d = np.array([np.sin(th) * np.sin(ph), np.cos(th), np.sin(th) * np.cos(ph)])
        p = np.array([0, 1.0, -0.14]) + d * 0.32
        if p[2] > 0.08 and p[1] < 1.08:       # keep the face clean
            continue
        if p[1] < 0.75:
            continue
        sp.append(p)
        back = np.clip(-p[2] / 0.3, 0, 1)
        rr.append(rng.uniform(0.007, 0.016) + back * rng.uniform(0.0, 0.012))
    sp = snap(f0, np.array(sp))
    # a few clusters: a big freckle with satellites
    extra, er = [], []
    for p, r in zip(sp, rr):
        if r > 0.02:
            for _ in range(3):
                extra.append(p + rng.normal(0, 0.03, 3))
                er.append(r * rng.uniform(0.3, 0.5))
    if extra:
        sp = np.vstack([sp, snap(f0, np.array(extra))])
        rr = list(rr) + er
    b.paint(Segs(sp, sp, np.array(rr)), SKIN_SP, feather=0.003)
    fr = Segs(sp, sp, np.array(rr) * 0.9)
    b.detail(lambda P: np.clip(-fr(P) / 0.004, 0, 1), depth=0.0006, darken=0.0)     # pressed in a hair
    return b


def monocle(m):
    ex, ey, ez = EYE_C
    c = np.array([ex + 0.004, ey - 0.002, ez + EYE_R * 0.86])
    n = np.array([0.18, 0.0, 1.0])
    n /= np.linalg.norm(n)
    mo = xpiece(m, "monocle", color=GOLD, gloss=225, rigid="eye_R", res=0.0028, lumps=0.0, mottle=0.04, ao=False)
    mo.add(Torus(c, EYE_R * 1.1, 0.0075, rot=look_rot(n)))
    mo.add(Torus(c - n * 0.002, EYE_R * 1.1, 0.0045, rot=look_rot(n)), k=0.002)
    lp = c + np.array([EYE_R * 0.95, -EYE_R * 0.55, 0.0])
    mo.add(Torus(lp + np.array([0.008, -0.008, 0]), 0.008, 0.0028, rot=(0, 0, 90)), k=0.002)        # loop for the cord
    # short cord dangling from the loop (the rest tucks behind the bow tie)
    cord = [lp + np.array([0.012, -0.014, 0]), lp + np.array([0.02, -0.06, -0.005]), lp + np.array([0.005, -0.1, -0.012]), lp + np.array([-0.02, -0.12, -0.03])]
    mo.add(Tube(cord, 0.0032, samples=6), k=0.002, color="#2b2326", gloss=60)


def tentacle(m, name, P, R, bones, seed=0, arm=False):
    """Skin a tentacle along its chain: segments 0-1, 1-2, 2-4, 4-end -> bones[0..3]; suckers on the underside."""
    Pc, Rc = catmull(P, R, 6)
    n = len(Pc)
    per = 6
    t = xpiece(m, name, color=SKIN, gloss=75, bone=bones[-1], res=0.0052, lumps=0.0018, lump_freq=12, dents=6, dent_size=0.02, dent_depth=0.002)
    cuts = [0, per * 1, per * 2, per * 4, n - 1]
    for j in range(4):
        a, b = cuts[j], cuts[j + 1]
        t.add(Tube(Pc[a:b + 1], Rc[a:b + 1]), k=0.02 if j else 0.0, bone=bones[j])
    # oral (sucker) side: walking tentacles start facing the ground, arms face back-and-inward against the body; the
    # frame is parallel-transported along the curve so where a tip rolls up the suckers show on the outside of the curl
    T = np.gradient(Pc, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    u = np.array([-np.sign(P[0][0]) * 0.55, 0.0, -0.85]) if arm else np.array([0, -1.0, 0])
    under = []
    for i in range(n):
        u = u - (u @ T[i]) * T[i]
        u /= np.linalg.norm(u)
        under.append(u.copy())
    under = np.array(under)
    side = np.cross(T, under)
    tree = cKDTree(Pc)

    def underside(Q):
        _, i = tree.query(Q, workers=-1)
        return -((Q - Pc[i]) * under[i]).sum(1) + Rc[i] * 0.35

    t.paint(Func(underside, *t.bounds()), SKIN_LT, feather=0.01)
    # suckers: little pressed discs with a cup, two staggered rows, shrinking toward the tip
    A, rr, cups = [], [], []
    start = per if not arm else per * 2
    for i in range(start, n - 1, 2):
        r = Rc[i]
        for row in (-1, 1):
            if (i // 2 + (row > 0)) % 2:
                continue
            c = Pc[i] + under[i] * r * 0.8 + side[i] * row * r * 0.38
            A.append(c)
            rr.append(max(0.0065, r * 0.38))
            cups.append(c + under[i] * r * 0.22)
    A = np.array(A)
    t.add(Segs(A, A, np.array(rr) * 0.95), k=0.006, color=SKIN_LT, gloss=95)
    cu = np.array(cups)
    t.sub(Segs(cu, cu, np.array(rr) * 0.5), k=0.003, color="#b4807f")
    # a few freckles on the top side
    rng = np.random.default_rng(seed + 50)
    idx = rng.choice(np.arange(2, n - 6), size=7, replace=False)
    fp = np.array([Pc[i] - under[i] * Rc[i] * 0.9 + side[i] * Rc[i] * rng.uniform(-0.6, 0.6) for i in idx])
    fr = np.array([Rc[i] * rng.uniform(0.18, 0.32) for i in idx])
    t.paint(Segs(fp, fp, fr), SKIN_SP, feather=0.003)
    # fine wrinkle rings across the top of the tentacle (it bends!)
    for i in range(4, n - 10, 6):
        ring = [Pc[i] + (np.cos(a) * side[i] - np.sin(a) * under[i]) * Rc[i] * 1.01 for a in np.linspace(-0.9, 0.9, 7)]
        t.sub(Tube(ring, max(0.002, Rc[i] * 0.035), samples=4), k=0.005)
    t.detail(strokes(P.mean(0), np.ptp(P, axis=0) * 0.5 + 0.06, cells=12, length=0.3, width=0.004, density=0.4, ridge=0.2, seed=seed + 30),
             depth=-0.001, darken=0)
    return t


def waistcoat(m, f):
    W = xpiece(m, "waistcoat", color=TWEED, gloss=25, bone="spine", res=0.005, lumps=0.0018, dents=12, dent_size=0.03, dent_depth=0.0025, mottle=0.08)
    vneck = Poly2D([(0.0, 0.495), (0.135, 0.68), (-0.135, 0.68)], depth=(0.05, 0.5), round=0.004)
    points = Poly2D([(-0.17, 0.33), (-0.02, 0.33), (-0.085, 0.255), (-0.11, 0.26)], depth=(0.08, 0.5))
    points2 = Poly2D([(0.02, 0.33), (0.17, 0.33), (0.11, 0.26), (0.085, 0.255)], depth=(0.08, 0.5))

    def band(y0, y1):
        slab = Box((0, (y0 + y1) / 2, 0), (0.4, (y1 - y0) / 2, 0.4))
        return Func(lambda P: np.maximum(slab(P), -vneck(P)), (-0.4, y0 - 0.01, -0.4), (0.4, y1 + 0.01, 0.4))

    low = band(0.315, 0.43)
    W.add(Shell(f, -0.004, 0.012, Func(lambda P: np.minimum(low(P), np.minimum(points(P), points2(P))), (-0.4, 0.24, -0.4), (0.4, 0.44, 0.4)), round=0.008), bone="hips")
    W.add(Shell(f, -0.004, 0.012, band(0.42, 0.54), round=0.008), k=0.004, bone="spine")
    W.add(Shell(f, -0.004, 0.012, band(0.53, 0.665), round=0.008), k=0.004, bone="chest")
    # rolled edges along the V and the hem
    for sx in (-1, 1):
        edge = snap(f, curve([(0.0, 0.495, 0.3), (sx * 0.07, 0.59, 0.3), (sx * 0.135, 0.675, 0.3)], 14), offset=0.012)
        W.add(Tube(edge, 0.0065), k=0.004, bone="chest")
        hem = snap(f, curve([(sx * 0.02, 0.33, 0.3), (sx * 0.085, 0.258, 0.3), (sx * 0.19, 0.33, 0.25)], 10), offset=0.01)
        W.sub(stitches(hem, 10, length=0.008, r=0.0017), k=0.001, color=TWEED_DK)
    # armholes: a rolled binding where the arms come out
    for sx in (-1, 1):
        ring = plane_ring(f, np.array([sx * 0.13, 0.6, 0.0]), np.array([sx * 1.0, 0.25, 0.0]), 28, offset=0.012)
        keep = ring[(ring[:, 1] > 0.53) & (ring[:, 1] < 0.67)]
        if len(keep) > 3:
            W.add(Tube(keep, 0.006), k=0.004, bone="chest")
    # satin back panel and a little buckle strap
    W.paint(Func(lambda P: P[:, 2] + 0.06, (-0.4, 0.2, -0.4), (0.4, 0.7, 0.4)), SATIN, gloss=110, feather=0.01)
    front = HalfSpace((0, 0, -0.06), (0, 0, -1))

    def front_w(P):
        return np.clip(0.5 - front(P) / 0.02, 0, 1)
    # tweed read at puppet scale: coarse dark and rust flecks rolled into the clay (a fine weave aliases away)
    # a soft, low-contrast overcheck in broad bands (vertex colour can carry this; a fine weave aliases away)
    W.pattern(lambda P: 0.8 * bands((1, 0, 0), period=0.075, width=0.28, offset=0.02, soft=0.4)(P) * front_w(P), shade(TWEED, 0.72))
    W.pattern(lambda P: 0.7 * bands((0, 1, 0), period=0.075, width=0.28, offset=0.03, soft=0.4)(P) * front_w(P), shade(TWEED, 0.72))
    W.pattern(specks(48.0, 0.5, region=front, seed=21), TWEED_DK)
    W.pattern(specks(70.0, 0.6, region=front, seed=22), TWEED_CHK)
    W.pattern(specks(90.0, 0.62, region=front, seed=23), "#b7a57c")
    bp, bn = onsurf(f, [(0.0, 0.47, -0.3)])
    Rb = surf_frame(bn[0])
    W.add(Box(bp[0] + bn[0] * 0.014, (0.06, 0.012, 0.004), rot=Rb, round=0.003), k=0.004, color=SATIN, gloss=110, bone="spine")
    W.add(Box(bp[0] + bn[0] * 0.018, (0.014, 0.013, 0.004), rot=Rb, round=0.003), k=0.002, color=GOLD, gloss=200, bone="spine")
    # welt pockets
    for sx in (-1, 1):
        pp = snap(f, [(sx * 0.1, 0.42, 0.3), (sx * 0.17, 0.43, 0.25)], offset=0.012)
        W.sub(Tube(pp, 0.004), k=0.002, color=TWEED_DK)
        W.add(Tube(pp + np.array([0, -0.006, 0]), 0.004), k=0.003, bone="spine")
    # closing edge down the front, and buttons (the bottom one left undone, of course)
    W.sub(Tube(snap(f, curve([(0.004, 0.495, 0.3), (0.006, 0.4, 0.3), (0.004, 0.33, 0.3)], 12), offset=0.012), 0.0032), k=0.003, color=shade(TWEED, 0.78))
    # horn buttons: their own small, finely meshed piece (the bottom one left undone, of course)
    bt0 = xpiece(m, "buttons", color="#5b3b25", gloss=150, bone="spine", res=0.0028, lumps=0.0004, mottle=0.06)
    for i, y in enumerate((0.475, 0.428, 0.381, 0.336)):
        x = -0.012 + (0.006 if i == 3 else 0.0)
        p0, n0 = onsurf(f, [(x, y, 0.3)])
        button(bt0, p0[0] + n0[0] * 0.012, n0[0], 0.0125, "#5b3b25", holes=4, gloss=150, bone="spine" if y > 0.43 else "hips", hole_col="#2a1a10")

    # shirt front and bow tie
    sh = xpiece(m, "shirt", color=SHIRT, gloss=40, bone="chest", res=0.0045, lumps=0.0012, mottle=0.04)
    sh.add(Shell(f, -0.006, 0.006, Poly2D([(0.0, 0.47), (0.15, 0.7), (-0.15, 0.7)], depth=(0.05, 0.5)), round=0.004), bone="chest")
    for i, y in enumerate((0.6, 0.55)):
        p0, n0 = onsurf(f, [(0, y, 0.3)])
        sh.add(Sphere(p0[0] + n0[0] * 0.006, 0.0065), k=0.002, color="#cfc7b6")
    sh.sub(Tube(snap(f, [(0, 0.655, 0.3), (0, 0.5, 0.3)], offset=0.006), 0.0025), k=0.002)
    # little wing collar points
    for sx in (-1, 1):
        p0, n0 = onsurf(f, [(sx * 0.05, 0.675, 0.3)])
        Rc = surf_frame(n0[0]) @ euler((0, 0, sx * 35))
        sh.add(Box(p0[0] + n0[0] * 0.01, (0.02, 0.026, 0.004), rot=Rc, round=0.004), k=0.004, bone="neck")
    bc, bn = onsurf(f, [(0, 0.672, 0.3)])
    bc, bn = bc[0] + bn[0] * 0.025, bn[0]
    bt = xpiece(m, "bowtie", color=BOW, gloss=70, rigid="neck", res=0.0036, lumps=0.001, mottle=0.05)
    Rn = surf_frame(bn)
    X, Y = Rn[:, 0], Rn[:, 1]
    for s in (-1, 1):
        bt.add(Ellipsoid(bc + X * s * 0.045, (0.045, 0.034, 0.016), rot=Rn @ euler((0, 0, s * 10))), k=0.008)
        for dy in (0.012, -0.012):
            bt.sub(Capsule(bc + X * s * 0.022 + Y * dy * 0.6 + bn * 0.014, bc + X * s * 0.075 + Y * dy * 1.6 + bn * 0.01, 0.0028), k=0.002)
    bt.add(Ellipsoid(bc + bn * 0.008, (0.016, 0.022, 0.014), rot=Rn), k=0.004)
    bt.pattern(specks(70.0, 0.62, seed=4), "#e5d6c0")
    # pocket-watch chain: a swag of little links from the third button to the left pocket, fob peeking out
    a = snap(f, [(-0.012, 0.428, 0.3)], offset=0.02)[0]
    b = snap(f, [(-0.13, 0.425, 0.3)], offset=0.016)[0]
    mid = (a + b) / 2 + np.array([0, -0.05, 0.025])
    path = curve([a, mid, b], 28)
    ch = xpiece(m, "watch_chain", color=GOLD, gloss=220, bone="spine", res=0.0024, lumps=0.0, mottle=0.04, ao=False)
    for i in range(len(path) - 1):
        d = path[i + 1] - path[i]
        rot = look_rot(d) @ euler((0, 90 * (i % 2), 0))
        ch.add(Torus((path[i] + path[i + 1]) / 2, 0.0052, 0.0017, rot=rot @ euler((0, 0, 90))), k=0.0, bone="spine")
    ch.add(Cylinder(b + np.array([0.0, 0.012, 0.002]), 0.016, 0.004, rot=(80, 0, 0), round=0.003), k=0.002, bone="spine")
