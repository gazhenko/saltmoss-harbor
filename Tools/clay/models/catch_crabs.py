"""
Crabs (and the urchin) of Saltmoss Harbor: dungeness, snow_crab, red_king, golden_king, sea_urchin.
Bottom-centred (dactyl tips on y=0), facing +Z. Simple rig so Unity can wiggle them when they tumble onto the deck:
root > body > claw_L/R > pincer_L/R, body > leg{i}_L/R (coxa). Pieces are rigid to those bones.
Sockets: belly (underside centre), top (carapace top).
"""
import numpy as np
from clay import *
from kit_catch import *

UP = np.array([0.0, 1.0, 0.0])


def _n(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


# --------------------------------------------------------------------------------------------------------------
# local helpers


class FlatCapsule(Prim):
    """Round cone a->b squashed across its horizontal perpendicular (crab leg segments are flattened fore-aft)."""

    def __init__(self, a, b, ra, rb=None, flat=0.7, axis=None):
        super().__init__()
        self.a, self.b = np.asarray(a, float), np.asarray(b, float)
        self.cap = Capsule(self.a, self.b, ra, rb)
        d = _n(self.b - self.a)
        w = np.cross(UP, d) if axis is None else np.asarray(axis, float)
        if np.linalg.norm(w) < 1e-6:
            w = np.array([1.0, 0, 0])
        self.w = _n(w - d * (w @ d))
        self.flat = flat

    def sdf(self, P):
        cw = (P - self.a) @ self.w
        return self.cap.sdf(P + np.outer(cw * (1.0 / self.flat - 1.0), self.w)) * self.flat

    def bounds(self):
        return self.cap.bounds()


def raycast(piece, o, dirs, tmax=0.6, iters=30):
    """Surface points + normals of a piece's current shape along rays from an inside point o."""
    d = np.atleast_2d(np.asarray(dirs, float))
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    o = np.broadcast_to(np.asarray(o, float), d.shape)
    lo = np.zeros(len(d))
    hi = np.full(len(d), tmax)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        inside = piece._eval_shape(o + d * mid[:, None]) < 0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    p = o + d * lo[:, None]
    n = gradient(piece._eval_shape, p)
    return p, n


def leg_pts(sx, phi, rys, sweep=0.0, jitter=None):
    """Joint points for a leg fanning out at angle phi (deg, from +x toward +z) given (radius, height) per joint."""
    pts = []
    for j, (r, y) in enumerate(rys):
        a = np.radians(phi + sweep * j)
        p = np.array([sx * r * np.cos(a), y, r * np.sin(a)])
        if jitter is not None and j > 1:
            p = p + jitter[j % len(jitter)]
        pts.append(p)
    pts = np.array(pts)
    pts[-1, 1] = rys[-1][1]
    return pts


class Crab:
    def __init__(self, name, res, body_c, shell, under, gloss=170, seed=0):
        self.m = Model(name, res=res)
        self.m.bone("root")
        self.m.bone("body", "root", body_c)
        self.res = res
        self.shell, self.under, self.gloss = shell, under, gloss
        self.rng = np.random.default_rng(seed)
        self.body = None

    # ---- articulated limb: segments pressed together with knuckle bulges ----
    def limb(self, piece, pts, radii, flat=0.7, top=None, joint=None, tip=None, tip_len=0.35, gap=0.12, knuckle=0.78,
             spines=None, spine_color=None):
        """pts: joints (coxa .. dactyl tip); radii per joint. Adds FlatCapsule segments + knuckles to `piece`;
        paints the upper side `top`, joints `joint`, dactyl tip `tip`. spines=(n_per_seg, length, radius) on top."""
        pts = np.asarray(pts, float)
        n = len(pts) - 1
        for i in range(n):
            a, b = pts[i], pts[i + 1]
            d = b - a
            L = np.linalg.norm(d)
            ra, rb = radii[i], radii[i + 1]
            g0 = 0.0 if i == 0 else gap * min(L, 0.05)
            g1 = 0.0 if i == n - 1 else gap * min(L, 0.05)
            a2, b2 = a + d / L * g0, b - d / L * g1
            last = i == n - 1
            seg = FlatCapsule(a2, b2, ra, max(rb, 0.0009) if last else rb * 0.96, flat=flat if not last else min(1.0, flat + 0.15))
            piece.add(seg, k=0.0018)
            if top is not None:
                v = _n(UP - _n(d) * (UP @ _n(d)))
                piece.paint(FlatCapsule(a2 + v * ra * 0.75, b2 + v * rb * 0.75, ra * 1.02, rb * 1.02, flat=flat * 1.4), top,
                            feather=ra * 0.35)
            if i < n - 1:
                kr = min(radii[i + 1], radii[i + 2] if i + 2 < len(radii) else radii[i + 1]) * knuckle + radii[i + 1] * 0.1
                piece.add(Sphere(b, kr), k=0.0025)
                if joint is not None:
                    piece.paint(Sphere(b, kr * 1.02), joint, feather=kr * 0.3)
            if spines and not last and i >= 1:
                ns, sl, sr = spines
                dd = _n(d)
                w = _n(np.cross(UP, dd)) if np.linalg.norm(np.cross(UP, dd)) > 1e-6 else np.array([1.0, 0, 0])
                v = _n(np.cross(dd, w))
                if v[1] < 0:
                    v = -v
                for t in np.linspace(0.22, 0.82, ns):
                    for side in (-1, 1):
                        rr = ra * (1 - t) + rb * t
                        base = a + d * t + v * rr * 0.55 + w * side * rr * flat * 0.55
                        out = _n(v * 0.85 + w * side * 0.45 + dd * 0.35 + self.rng.normal(0, 0.12, 3))
                        ln = sl * self.rng.uniform(0.7, 1.15)
                        piece.add(Capsule(base, base + out * (ln + rr * 0.4), sr, sr * 0.18), k=sr * 0.5)
                        if spine_color is not None:
                            piece.paint(Sphere(base + out * (ln + rr * 0.4), sr * 1.2), spine_color, feather=sr * 0.6)
        if tip is not None:
            a, b = pts[-2], pts[-1]
            piece.paint(Capsule(b + (a - b) * tip_len, b, radii[-2] * 1.5, radii[-2] * 1.5), tip, feather=0.002)

    def leg(self, name, pts, radii, flat=0.7, top=None, joint=None, tip=None, color=None, dec=520, res=None, spines=None,
            spine_color=None, lumps=0.0009, gloss=None):
        self.m.bone(name, "body", tuple(pts[0]))
        p = self.m.piece(name, color=color or self.under, gloss=gloss or self.gloss, rigid=name, lumps=lumps, lump_freq=60,
                         dents=3, dent_size=radii[1] * 1.2, dent_depth=radii[1] * 0.12, mottle=0.05, res=res or self.res,
                         decimate=dec, seed=int(self.rng.integers(1e5)))
        self.limb(p, pts, radii, flat=flat, top=top, joint=joint, tip=tip, spines=spines, spine_color=spine_color)
        return p

    def claw(self, sx, S, E, W, H, r_m, r_c, r_p, finger_len, finger_r, top=None, joint=None, finger=None, tip=None,
             flat=0.75, palm_flat=0.68, inward=0.55, gape=0.18, teeth=4, dec=(1100, 380), res=None, spines=None,
             spine_color=None, knobs=None, lumps=0.0012):
        s = "R" if sx > 0 else "L"
        m = self.m
        m.bone(f"claw_{s}", "body", tuple(S))
        S, E, W, H = (np.asarray(v, float) for v in (S, E, W, H))
        dp = _n(H - W)
        v = _n(UP - dp * (UP @ dp))
        side = _n(np.cross(UP, dp))  # horizontal perpendicular
        hinge = H + v * r_p * 0.42
        m.bone(f"pincer_{s}", f"claw_{s}", tuple(hinge))
        arm = m.piece(f"claw_{s}", color=self.under, gloss=self.gloss, rigid=f"claw_{s}", lumps=lumps, lump_freq=40,
                      dents=5, dent_size=r_p * 0.8, dent_depth=r_p * 0.06, mottle=0.05, res=res or self.res, decimate=dec[0],
                      seed=int(self.rng.integers(1e5)))
        self.limb(arm, [S, E, W], [r_m, r_m * 1.05, r_c], flat=flat, top=top, joint=joint, spines=spines,
                  spine_color=spine_color)
        # palm: swollen, laterally compressed
        pc = 0.5 * (W + H) + v * r_p * 0.05
        hl = np.linalg.norm(H - W) * 0.62
        R = np.column_stack([side, dp, np.cross(side, dp)])
        arm.add(Ellipsoid(pc, (r_p * palm_flat, hl, r_p), rot=R), k=r_c * 0.6)
        arm.add(Sphere(W, r_c * 0.85), k=0.003)
        if joint is not None:
            arm.paint(Sphere(W, r_c * 0.9), joint, feather=r_c * 0.3)
        if top is not None:
            arm.paint(Ellipsoid(pc + v * r_p * 0.7 + side * sx * r_p * 0.15, (r_p * palm_flat * 1.4, hl * 1.15, r_p * 0.9), rot=R),
                      top, feather=r_p * 0.4)
        if knobs:
            nk, kr = knobs
            for i in range(nk):
                t = self.rng.uniform(-0.6, 0.6)
                a = self.rng.uniform(0.2, 2.9)
                q = pc + dp * hl * t + (np.cos(a) * v * r_p + np.sin(a) * side * sx * r_p * palm_flat) * 0.92
                o = _n(np.cos(a) * v + np.sin(a) * side * sx)
                arm.add(Capsule(q, q + o * kr * 2.2, kr, kr * 0.25), k=kr * 0.6)
                if spine_color is not None:
                    arm.paint(Sphere(q + o * kr * 2.2, kr * 0.9), spine_color, feather=kr * 0.5)
        # fixed finger (pollex): continues the palm forward, curving inward toward the midline
        inn = np.array([-sx, 0.0, 0.0])
        base = H - v * r_p * 0.35
        tipP = base + dp * finger_len + inn * finger_len * inward * 0.5 - v * finger_len * 0.08
        mid = base + dp * finger_len * 0.55 + inn * finger_len * inward * 0.12 - v * finger_len * 0.06
        arm.add(Tube([base - dp * r_p * 0.3, mid, tipP], [finger_r * 1.25, finger_r, finger_r * 0.32], samples=6), k=r_p * 0.35)
        # dactyl (moving finger), hinged above
        dac = m.piece(f"pincer_{s}", color=finger or self.under, gloss=self.gloss + 10, rigid=f"pincer_{s}", lumps=lumps * 0.6,
                      lump_freq=50, mottle=0.04, res=(res or self.res) * 0.9, decimate=dec[1], seed=int(self.rng.integers(1e5)))
        dbase = hinge
        dtip = tipP + v * finger_len * (0.08 + gape * 0.6) + dp * finger_len * 0.02
        dmid = dbase + dp * finger_len * 0.55 + inn * finger_len * inward * 0.12 + v * finger_len * (0.1 + gape * 0.5)
        dac.add(Tube([dbase - dp * r_p * 0.25, dmid, dtip], [finger_r * 1.2, finger_r * 0.95, finger_r * 0.3], samples=6))
        # little crushing teeth on the inner edges
        for i in range(teeth):
            t = 0.22 + 0.6 * i / max(teeth - 1, 1)
            q1 = base + (tipP - base) * t + v * finger_r * 0.75
            arm.add(Sphere(q1, finger_r * 0.32), k=finger_r * 0.25)
            q2 = dbase + (dtip - dbase) * t - v * finger_r * 0.75
            dac.add(Sphere(q2, finger_r * 0.3), k=finger_r * 0.25)
        if finger is not None:
            arm.paint(Capsule(base, tipP, finger_r * 1.6), finger, feather=finger_r * 0.5)
        if tip is not None:
            arm.paint(Sphere(tipP, finger_len * 0.38), tip, feather=finger_len * 0.12)
            dac.paint(Sphere(dtip, finger_len * 0.38), tip, feather=finger_len * 0.12)
        return arm, dac

    def eyes(self, orbit, ec, r, stalk_r, iris="#1d1418", ring=None, pupil_frac=0.7, out=None):
        for sx, s in ((1, "R"), (-1, "L")):
            o = np.array([sx * orbit[0], orbit[1], orbit[2]])
            c = np.array([sx * ec[0], ec[1], ec[2]])
            self.body.add(Capsule(o, c - _n(c - o) * r * 0.4, stalk_r * 1.15, stalk_r), k=stalk_r * 0.9)
            self.body.add(Sphere(c - _n(c - o) * r * 0.55, stalk_r * 1.25), k=stalk_r * 0.5)  # cup under the eyeball
            d = out if out is not None else (sx * 0.55, 0.45, 0.7)
            d = np.array([sx * abs(d[0]), d[1], d[2]])
            fish_eye(self.m, c, r, d, iris=iris, ring=ring, pupil_frac=pupil_frac, side=s, toe=0.0, up=0.0, merge="eyes")
        for p in self.m.pieces:
            if p.merge == "eyes":
                p.rigid = "body"
                p.decimate = 230 if p.name.endswith("pupil") else 260


# ==============================================================================================================
# dungeness — broad oval purple-brown carapace with a serrated front edge, white-tipped claws


def dungeness():
    SHELL, SHELL_DK, RIM = "#7d4c3f", "#5c3247", "#b8713d"
    UNDER, LEG_TOP, JOINT = "#ead6ae", "#7a4644", "#f0c896"
    C = Crab("dungeness", res=0.0034, body_c=(0, 0.06, 0), shell=SHELL, under=UNDER, gloss=170, seed=11)
    m = C.m
    b = m.piece("body", color=SHELL, gloss=170, rigid="body", lumps=0.0012, lump_freq=7, dents=10, dent_size=0.024,
                dent_depth=0.0012, mottle=0.06, res=0.0032, decimate=4400)
    C.body = b
    cc = np.array([0, 0.062, -0.006])
    b.add(Ellipsoid(cc, (0.112, 0.034, 0.076)))
    b.add(Ellipsoid(cc + (0, -0.004, 0.002), (0.116, 0.011, 0.078)), k=0.008)  # the rim shelf
    b.add(Ellipsoid(cc + (0, -0.018, 0.0), (0.082, 0.024, 0.06)), k=0.02, color=UNDER)  # underside / sternum
    b.add(Ellipsoid(cc + (0, 0.007, 0.012), (0.062, 0.03, 0.05)), k=0.03)  # raised gastric hump
    # serrated front margin: ~10 teeth each side, last one big
    angs = np.radians(np.linspace(16, 96, 10))
    for sx in (1, -1):
        dirs = np.column_stack([sx * np.sin(angs), np.zeros(len(angs)), np.cos(angs)])
        P, N = raycast(b, cc + (0, -0.004, 0), dirs)
        for i, (p, n, a) in enumerate(zip(P, N, angs)):
            nh = _n(np.array([n[0], 0, n[2]]))
            fwd = _n(nh + np.array([0, 0, 0.35 if i < 9 else 0.1]))
            ln = 0.0075 if i < 9 else 0.016
            rr = 0.006 if i < 9 else 0.0078
            b.add(Capsule(p - nh * 0.004, p + fwd * ln, rr, 0.0015), k=0.003)
    # frontal teeth between the eyes
    for x in (-0.012, 0.0, 0.012):
        p = np.array([x, 0.064, 0.072 - abs(x) * 0.2])
        b.add(Capsule(p - (0, 0, 0.004), p + (0, -0.001, 0.007), 0.0042, 0.0013), k=0.002)
    # carapace grooves, pressed with a round tool: the H between gastric and branchial regions
    for sx in (1, -1):
        P, _ = raycast(b, cc, [(sx * 0.42, 1, 0.45), (sx * 0.5, 1, 0.2), (sx * 0.5, 1, -0.05), (sx * 0.42, 1, -0.3),
                               (sx * 0.3, 1, -0.5)])
        score(b, P + (0, 0.0016, 0), r=0.0032, k=0.004, samples=4)
    P, _ = raycast(b, cc, [(-0.32, 1, -0.1), (0, 1, -0.16), (0.32, 1, -0.1)])
    score(b, P + (0, 0.0016, 0), r=0.003, k=0.004, samples=4)
    # a couple of soft thumb smears
    P, _ = raycast(b, cc, [(-0.6, 0.8, -0.5), (0.75, 0.6, 0.2)])
    thumbprints(b, P + (0, 0.008, 0), 0.014)
    # mouthparts (third maxillipeds) under the front edge + a dark mouth slit
    for sx in (1, -1):
        b.add(Ellipsoid((sx * 0.009, 0.044, 0.063), (0.0085, 0.013, 0.005), rot=(-35, 0, sx * 6)), k=0.004, color="#d9a372")
    b.paint(Box((0, 0.044, 0.067), (0.0015, 0.012, 0.008), rot=(-35, 0, 0)), "#3b2326", feather=0.0015)
    # abdomen flap tucked under (seen when flipped): scored segments
    b.add(Ellipsoid((0, 0.04, -0.02), (0.03, 0.008, 0.045)), k=0.01, color="#efe0c0")
    for z in (-0.045, -0.03, -0.015, 0.0):
        b.sub(Box((0, 0.031, z), (0.03, 0.0015, 0.0012)), k=0.001)
    # colour: brown-purple dome, purple mottles, orange rim, cream belly
    b.paint(HalfSpace((0, 0.058, 0), (0, 1, 0)), RIM, feather=0.006)
    b.paint(HalfSpace((0, 0.048, 0), (0, 1, 0)), UNDER, feather=0.006)
    b.paint(inter_prim(blotch_prim(30, 0.1, seed=4), HalfSpace((0, 0.064, 0), (0, -1, 0))), SHELL_DK, feather=0.012)
    b.paint(inter_prim(blotch_prim(22, 0.25, seed=8), HalfSpace((0, 0.06, 0), (0, -1, 0))), "#8c5a45", feather=0.014)
    # eyes on short stalks
    C.eyes(orbit=(0.02, 0.066, 0.06), ec=(0.031, 0.095, 0.08), r=0.0135, stalk_r=0.0058, iris="#1e1416", ring="#3a2a28",
           pupil_frac=0.72)
    # walking legs: 4 pairs fanning from front to back; merus nearly level, then down to the tips
    phis = [42, 14, -14, -44]
    for i, phi in enumerate(phis):
        sc = [0.92, 1.0, 1.0, 0.9][i]
        rys = [(0.055, 0.046), (0.08, 0.05), (0.08 + 0.05 * sc, 0.066), (0.08 + 0.068 * sc, 0.062),
               (0.08 + 0.09 * sc, 0.034), (0.08 + 0.1 * sc, 0.0)]
        for sx, s in ((1, "R"), (-1, "L")):
            jit = [C.rng.normal(0, 0.0025, 3) * (1, 0.4, 1) for _ in range(6)]
            pts = leg_pts(sx, phi, rys, sweep=5.0 * np.sign(phi) if i != 1 else 2, jitter=jit)
            rad = [0.013, 0.0135, 0.0125, 0.011, 0.0088, 0.0016] if i < 3 else [0.013, 0.0135, 0.013, 0.0115, 0.0098, 0.0028]
            C.leg(f"leg{i}_{s}", pts, rad, flat=0.6 if i < 3 else 0.46, top=LEG_TOP, joint=JOINT, tip="#3e2424", color="#d6925a",
                  dec=440)
    # claws: chunky, held forward, cream fingers with white tips
    for sx in (1, -1):
        S = (sx * 0.056, 0.048, 0.048)
        E = (sx * 0.1, 0.054, 0.072)
        W = (sx * 0.097, 0.058, 0.108)
        H = (sx * 0.06, 0.06, 0.15)
        C.claw(sx, S, E, W, H, r_m=0.0145, r_c=0.0165, r_p=0.032, finger_len=0.05, finger_r=0.0098, top=LEG_TOP,
               joint=JOINT, finger="#e2b58c", tip="#f6f1e6", knobs=(6, 0.0038), palm_flat=0.62, dec=(1000, 340))
    m.socket("belly", "body", (0, 0.034, -0.01), rot=(180, 0, 0))
    m.socket("top", "body", (0, 0.1, -0.006))
    return m


# ==============================================================================================================
# snow crab — small round tan-orange carapace with tubercles, very long thin flattened legs, small slender claws


def snow_crab():
    SHELL, SHELL_DK, UNDER = "#c2672f", "#9a4521", "#f1dcbc"
    LEG_TOP, JOINT, TIP = "#bd622c", "#f3d3a6", "#6e321c"
    C = Crab("snow_crab", res=0.003, body_c=(0, 0.09, 0), shell=SHELL, under=UNDER, gloss=165, seed=23)
    m = C.m
    b = m.piece("body", color=SHELL, gloss=165, rigid="body", lumps=0.001, lump_freq=9, dents=8, dent_size=0.018,
                dent_depth=0.001, mottle=0.06, res=0.003, decimate=3700)
    C.body = b
    cc = np.array([0, 0.092, -0.004])
    b.add(Ellipsoid(cc, (0.072, 0.036, 0.076)))
    b.add(Ellipsoid(cc + (0, 0.004, 0.024), (0.046, 0.033, 0.048)), k=0.025)  # gastric region bulge
    for sx in (1, -1):
        b.add(Ellipsoid(cc + (sx * 0.03, 0.002, -0.018), (0.035, 0.03, 0.045)), k=0.025)  # branchial lobes
    b.add(Ellipsoid(cc + (0, -0.02, 0.0), (0.05, 0.02, 0.05)), k=0.02, color=UNDER)
    # rostrum: two little horns between the eyes
    for sx in (1, -1):
        b.add(Capsule((sx * 0.004, 0.1, 0.06), (sx * 0.007, 0.104, 0.082), 0.0055, 0.0018), k=0.003)
    # tubercles: a sprinkle of small pressed beads over the shell
    rng = np.random.default_rng(5)
    dirs = rng.normal(size=(70, 3))
    dirs[:, 1] = np.abs(dirs[:, 1]) * 1.1 + 0.15
    P, N = raycast(b, cc, dirs)
    for p, nn in zip(P, N):
        r = rng.uniform(0.0024, 0.0036)
        b.add(Sphere(p + nn * r * 0.15, r), k=0.0018)
    # scored grooves between regions
    for sx in (1, -1):
        P, _ = raycast(b, cc, [(sx * 0.35, 1, 0.55), (sx * 0.45, 1, 0.2), (sx * 0.4, 1, -0.15), (sx * 0.22, 1, -0.45)])
        score(b, P + (0, 0.0012, 0), r=0.0024, k=0.003, samples=4)
    P, _ = raycast(b, cc, [(-0.7, 0.6, -0.5)])
    thumbprints(b, P + (0, 0.007, 0), 0.012)
    for sx in (1, -1):
        b.add(Ellipsoid((sx * 0.007, 0.072, 0.056), (0.0065, 0.011, 0.004), rot=(-35, 0, sx * 6)), k=0.004, color="#e7b98d")
    b.paint(Box((0, 0.072, 0.06), (0.0012, 0.01, 0.007), rot=(-35, 0, 0)), "#3b2326", feather=0.0012)
    b.paint(HalfSpace((0, 0.082, 0), (0, 1, 0)), UNDER, feather=0.007)
    b.paint(inter_prim(blotch_prim(26, 0.12, seed=2), HalfSpace((0, 0.09, 0), (0, -1, 0))), SHELL_DK, feather=0.012)
    b.paint(cavity_prim(b, 0.005, 0.05), shade(SHELL_DK, 0.8), feather=0.08)
    C.eyes(orbit=(0.015, 0.098, 0.058), ec=(0.024, 0.12, 0.073), r=0.0128, stalk_r=0.005, iris="#1e1416", ring="#3a2a28",
           pupil_frac=0.72)
    phis = [46, 16, -14, -42]
    for i, phi in enumerate(phis):
        sc = [0.92, 1.0, 0.98, 0.86][i]
        rys = [(0.042, 0.078), (0.064, 0.082), (0.064 + 0.122 * sc, 0.132), (0.064 + 0.155 * sc, 0.126),
               (0.064 + 0.25 * sc, 0.05), (0.064 + 0.29 * sc, 0.0)]
        for sx, s in ((1, "R"), (-1, "L")):
            jit = [C.rng.normal(0, 0.004, 3) * (1, 0.4, 1) for _ in range(6)]
            pts = leg_pts(sx, phi, rys, sweep=4.0 * np.sign(phi) if i != 1 else 1.5, jitter=jit)
            rad = [0.0095, 0.0098, 0.0094, 0.008, 0.0066, 0.0012]
            C.leg(f"leg{i}_{s}", pts, rad, flat=0.52, top=LEG_TOP, joint=JOINT, tip=TIP, color="#e3b085", res=0.0028, dec=520)
    for sx in (1, -1):
        S = (sx * 0.036, 0.078, 0.045)
        E = (sx * 0.072, 0.088, 0.075)
        W = (sx * 0.07, 0.09, 0.108)
        H = (sx * 0.045, 0.088, 0.142)
        C.claw(sx, S, E, W, H, r_m=0.0098, r_c=0.0105, r_p=0.0175, finger_len=0.043, finger_r=0.0068, top=LEG_TOP,
               joint=JOINT, finger="#e9c39a", tip=TIP, palm_flat=0.7, dec=(900, 320), res=0.0026, teeth=3)
    m.socket("belly", "body", (0, 0.068, -0.004), rot=(180, 0, 0))
    m.socket("top", "body", (0, 0.13, -0.004))
    return m


# ==============================================================================================================
# king crabs — heart-shaped spiny carapace, three pairs of long spiny walking legs, right claw bigger


def king(name, s, SHELL, SHELL_DK, UNDER, LEG_TOP, JOINT, SPINE_TIP, gloss, n_spines, spine_len, spine_r, seed,
         leg_spines, lumps=0.0016):
    C = Crab(name, res=0.0048 * s, body_c=(0, 0.14 * s, 0), shell=SHELL, under=UNDER, gloss=gloss, seed=seed)
    m = C.m
    V = lambda *a: np.array(a, float) * s
    b = m.piece("body", color=SHELL, gloss=gloss, rigid="body", lumps=lumps * s, lump_freq=8 / s, dents=10,
                dent_size=0.026 * s, dent_depth=0.0016 * s, mottle=0.06, res=0.0046 * s, decimate=3700)
    C.body = b
    cc = V(0, 0.142, -0.012)
    b.add(Ellipsoid(cc, V(0.114, 0.059, 0.106)))
    for sx in (1, -1):
        b.add(Ellipsoid(cc + V(sx * 0.057, -0.004, -0.03), V(0.076, 0.057, 0.082)), k=0.035 * s)  # branchial lobes
    b.add(Ellipsoid(cc + V(0, 0.006, 0.068), V(0.058, 0.048, 0.056)), k=0.04 * s)  # gastric region, narrowing forward
    b.add(Ellipsoid(cc + V(0, -0.028, 0.0), V(0.088, 0.03, 0.085)), k=0.03 * s, color=UNDER)
    # rostrum spike with two side spines
    b.add(Capsule(cc + V(0, 0.01, 0.095), cc + V(0, 0.024, 0.135), 0.0085 * s, 0.0022 * s), k=0.006 * s)
    for sx in (1, -1):
        b.add(Capsule(cc + V(sx * 0.012, 0.012, 0.094), cc + V(sx * 0.02, 0.02, 0.118), 0.0055 * s, 0.0016 * s), k=0.004 * s)
    # grooves around the gastric and cardiac regions
    for sx in (1, -1):
        P, _ = raycast(b, cc, [(sx * 0.25, 1, 0.75), (sx * 0.42, 1, 0.3), (sx * 0.3, 1, -0.05), (sx * 0.12, 1, -0.25)])
        score(b, P + V(0, 0.0015, 0), r=0.0034 * s, k=0.004 * s, samples=4)
    P, _ = raycast(b, cc, [(-0.26, 1, -0.3), (0, 1, -0.42), (0.26, 1, -0.3)])
    score(b, P + V(0, 0.0015, 0), r=0.0032 * s, k=0.004 * s, samples=4)
    # conical spines all over the top (jittered grid, raycast up), plus a ring of longer ones round the margin
    rng = np.random.default_rng(seed)
    step = 0.19 / np.sqrt(n_spines) * s * 1.9
    xs = np.arange(-0.14 * s, 0.14 * s, step)
    zs = np.arange(-0.13 * s, 0.13 * s, step * 0.92)
    starts, dirs = [], []
    for iz, z in enumerate(zs):
        for x in xs + (step * 0.5 if iz % 2 else 0):
            x2, z2 = x + rng.uniform(-0.3, 0.3) * step, z + rng.uniform(-0.3, 0.3) * step
            o = cc + np.array([x2, -0.015 * s, z2])
            if b._eval_shape(o[None])[0] < -0.004 * s:
                starts.append(o)
                dirs.append((0, 1, 0))
    P, N = [], []
    for o in starts:
        pp, nn = raycast(b, o, [(0, 1, 0)], tmax=0.2 * s)
        P.append(pp[0]); N.append(nn[0])
    angs = np.radians(np.linspace(-150, 150, 16))
    Pm, Nm = raycast(b, cc + np.array([0, 0.004 * s, 0]), np.column_stack([np.sin(angs), np.full(16, 0.25), np.cos(angs)]))
    P = np.vstack([P, Pm]); N = np.vstack([N, Nm])
    tips = []
    for i, (p, nn) in enumerate(zip(P, N)):
        marg = i >= len(P) - 16
        ln = spine_len * s * rng.uniform(0.75, 1.2) * (1.45 if marg else 1.0)
        rr = spine_r * s * rng.uniform(0.85, 1.15) * (1.15 if marg else 1.0)
        o = _n(nn + rng.normal(0, 0.12, 3) + np.array([0, 0, 0.12]))
        b.add(Capsule(p - nn * rr * 0.6, p + o * ln, rr, rr * 0.13), k=rr * 0.5)
        tips.append(p + o * ln)
    b.paint(spots_prim(tips, spine_r * s * 1.4), SPINE_TIP, feather=spine_r * s * 0.8)
    # mouthparts + slit
    for sx in (1, -1):
        b.add(Ellipsoid(cc + V(sx * 0.011, -0.03, 0.074), V(0.011, 0.017, 0.006), rot=(-35, 0, sx * 6)), k=0.005 * s, color="#e7c39a")
    b.paint(Box(cc + V(0, -0.03, 0.079), V(0.0018, 0.016, 0.01), rot=(-35, 0, 0)), "#3b2326", feather=0.0018 * s)
    b.paint(HalfSpace(cc + V(0, -0.02, 0), (0, 1, 0)), UNDER, feather=0.008 * s)
    b.paint(inter_prim(blotch_prim(18 / s, 0.12, seed=seed + 1), HalfSpace(cc + V(0, 0.01, 0), (0, -1, 0))), SHELL_DK,
            feather=0.012)
    b.paint(cavity_prim(b, 0.006 * s, 0.05), shade(SHELL_DK, 0.75), feather=0.08)
    C.eyes(orbit=(0.02 * s, cc[1] + 0.008 * s, cc[2] + 0.094 * s), ec=(0.033 * s, cc[1] + 0.032 * s, cc[2] + 0.114 * s),
           r=0.0178 * s, stalk_r=0.0074 * s, iris="#1e1416", ring="#3a2a28", pupil_frac=0.72)
    # three pairs of walking legs: high arching knees, spiny
    phis = [36, 2, -34]
    for i, phi in enumerate(phis):
        sc = [0.95, 1.0, 0.96][i]
        rys = [(0.074, 0.118), (0.108, 0.13), (0.108 + 0.14 * sc, 0.205), (0.108 + 0.185 * sc, 0.197),
               (0.108 + 0.29 * sc, 0.078), (0.108 + 0.33 * sc, 0.0)]
        rys = [(r * s, y * s) for r, y in rys]
        for sx, sd in ((1, "R"), (-1, "L")):
            jit = [C.rng.normal(0, 0.005 * s, 3) * (1, 0.4, 1) for _ in range(6)]
            pts = leg_pts(sx, phi, rys, sweep=4.0 * np.sign(phi), jitter=jit)
            rad = [r * s for r in (0.023, 0.0245, 0.0232, 0.0195, 0.0158, 0.0034)]
            C.leg(f"leg{i}_{sd}", pts, rad, flat=0.72, top=LEG_TOP, joint=JOINT, tip="#3a1d1a", color=UNDER, res=0.0042 * s,
                  dec=640, spines=leg_spines, spine_color=SPINE_TIP, lumps=0.0012 * s)
    # claws: right (crusher) bigger
    for sx in (1, -1):
        big = 1.42 if sx > 0 else 1.0
        S = V(sx * 0.062, 0.118, 0.066)
        E = V(sx * 0.128, 0.132, 0.108)
        W = V(sx * 0.12, 0.13, 0.17)
        H = V(sx * 0.07, 0.12, 0.222 + 0.03 * (big - 1))
        C.claw(sx, S, E, W, H, r_m=0.02 * s, r_c=0.022 * s, r_p=0.033 * s * big, finger_len=0.056 * s * big,
               finger_r=0.0108 * s * big, top=LEG_TOP, joint=JOINT, finger=SHELL, tip="#3a1d1a", palm_flat=0.72,
               dec=(1150, 360), res=0.004 * s, spines=(3, leg_spines[1], leg_spines[2]), knobs=(10, leg_spines[2] * 1.05),
               spine_color=SPINE_TIP, teeth=4)
    m.socket("belly", "body", tuple(cc + V(0, -0.055, 0)), rot=(180, 0, 0))
    m.socket("top", "body", tuple(cc + V(0, 0.07, 0)))
    return m


def red_king():
    return king("red_king", 1.0, SHELL="#962722", SHELL_DK="#681620", UNDER="#ecd9b4", LEG_TOP="#a02c25", JOINT="#e8b98a",
                SPINE_TIP="#d8653d", gloss=170, n_spines=46, spine_len=0.02, spine_r=0.0066, seed=31,
                leg_spines=(3, 0.014, 0.0047))


def golden_king():
    return king("golden_king", 0.84, SHELL="#c8701c", SHELL_DK="#93460f", UNDER="#f1d9a8", LEG_TOP="#cc7622", JOINT="#f6d39a",
                SPINE_TIP="#f6c75a", gloss=218, n_spines=80, spine_len=0.0145, spine_r=0.0056, seed=47,
                leg_spines=(4, 0.011, 0.0041), lumps=0.0012)


# ==============================================================================================================
# sea urchin — purple spiky ball, flattened underneath, glossy dark spine tips, tube feet peeking between


def sea_urchin():
    TEST, SPINE, TIP, FEET = "#45194d", "#5f2472", "#220e29", "#c47aa8"
    m = Model("sea_urchin", res=0.003)
    m.bone("root")
    m.bone("body", "root", (0, 0.055, 0))
    c = np.array([0, 0.056, 0])
    t = m.piece("test", color=TEST, gloss=150, rigid="body", lumps=0.0012, lump_freq=30, dents=8, dent_size=0.014,
                dent_depth=0.0012, mottle=0.07, res=0.003, decimate=1900)
    t.add(Ellipsoid(c, (0.062, 0.047, 0.062)))
    t.inter(HalfSpace((0, 0.016, 0), (0, -1, 0)), k=0.012)
    # five ambulacral bands (paler, rows of tube feet) and a mouth ring underneath
    for i in range(5):
        a = np.radians(i * 72 + 8)
        for j, el in enumerate(np.linspace(-0.6, 1.25, 9)):
            d = np.array([np.cos(a) * np.cos(el), np.sin(el), np.sin(a) * np.cos(el)])
            P, N = raycast(t, c, [d])
            t.add(Sphere(P[0] + N[0] * 0.0012, 0.0035), k=0.002, color=FEET, gloss=200)
        t.paint(Capsule(c + np.array([np.cos(a), -0.3, np.sin(a)]) * 0.07, c + np.array([0, 1, 0]) * 0.06, 0.011, 0.004),
                shade(TEST, 1.25), feather=0.006)
    t.add(Torus((0, 0.016, 0), 0.014, 0.004), k=0.004, color="#7a4a6a")
    for i in range(5):
        a = np.radians(i * 72)
        t.add(Capsule((np.cos(a) * 0.006, 0.014, np.sin(a) * 0.006), (np.cos(a) * 0.002, 0.009, np.sin(a) * 0.002), 0.0028, 0.0012),
              k=0.002, color="#f1ebdc", gloss=200)
    # spines: fibonacci-spread, varied lengths and tilts; short splayed ones underneath so it sits
    sp = m.piece("spines", color=SPINE, gloss=190, rigid="body", lumps=0.0, mottle=0.04, res=0.0021, decimate=9800, ao=True)
    rng = np.random.default_rng(13)
    N_SP = 92
    gold = np.pi * (3 - np.sqrt(5))
    tips = []
    dirs = []
    for i in range(N_SP):
        y = 1 - (i + 0.5) / N_SP * 1.75  # stop short of the very bottom
        r = np.sqrt(max(0.0, 1 - y * y))
        a = gold * i
        dirs.append((np.cos(a) * r, y, np.sin(a) * r))
    P, N = raycast(t, c, dirs)
    for p, nn, d in zip(P, N, dirs):
        low = d[1] < -0.35
        ln = rng.uniform(0.036, 0.052) * (0.55 if low else 1.0) * (0.85 if d[1] > 0.9 else 1.0)
        o = _n(nn + rng.normal(0, 0.16, 3) + (np.array([0, -0.6, 0]) if low else 0))
        rb = rng.uniform(0.0052, 0.0062)
        tip = p + o * ln
        if tip[1] < 0.0022:  # rest on the table, don't poke through it
            f = (p[1] - 0.0022) / max(p[1] - tip[1], 1e-6)
            tip = p + (tip - p) * f
        sp.add(Capsule(p - nn * 0.003, tip, rb, rb * 0.36), k=0.0015)
        t.add(Sphere(p, rb * 1.35), k=0.002)  # tubercle under each spine
        tips.append((p, tip))
    tipc = np.array([q for _, q in tips])
    sp.paint(spots_prim(tipc, 0.016), shade(SPINE, 0.8), gloss=210, feather=0.01)
    sp.paint(spots_prim(tipc, 0.0085), TIP, gloss=235, feather=0.004)
    sp.paint(spots_prim(np.array([q for q, _ in tips]), 0.008), shade(SPINE, 1.15), feather=0.005)
    m.socket("belly", "body", (0, 0.004, 0), rot=(180, 0, 0))
    m.socket("top", "body", (0, 0.16, 0))
    return m


MODELS = {
    "crabs/dungeness": dungeness,
    "crabs/snow_crab": snow_crab,
    "crabs/red_king": red_king,
    "crabs/golden_king": golden_king,
    "crabs/sea_urchin": sea_urchin,
}
