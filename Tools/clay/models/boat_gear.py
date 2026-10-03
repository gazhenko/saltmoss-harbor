"""
Fishing gear for The Sally Mae (Docs/DESIGN.md §3, §5.4): crab pot, pot buoy, dredge, ice mallet, rod, bobber and the
cockpit sonar screen. Props pivot bottom-centre unless noted (buoy/bobber: waterline at y = 0).
"""
import numpy as np
from clay import *
from kit_catch import *

IRON, IRON_DK, RUST = "#3a3c42", "#222327", "#a5532a"


# --------------------------------------------------------------------------------------------------------------
# helpers local to gear (and reused by catch_junk)


class NetPanel(Prim):
    """A hand-laid net on a parallelogram: corner o, edges U, V. Diamond (or square) mesh of rolled-clay strands with
    knots at the crossings, a gentle sag along the panel normal (sign of `sag` picks the side) and a wobble."""

    def __init__(self, o, U, V, cell, r, sag=0.0, knot=None, diamond=True, wobble=0.0, seed=0, wobble_freq=6.0,
                 sag_dir=None):
        super().__init__()
        self.o = np.asarray(o, float)
        self.U, self.V = np.asarray(U, float), np.asarray(V, float)
        self.Ul, self.Vl = np.linalg.norm(self.U), np.linalg.norm(self.V)
        self.u, self.v = self.U / self.Ul, self.V / self.Vl
        self.n = np.asarray(sag_dir, float) if sag_dir is not None else np.cross(self.u, self.v)
        self.n = self.n / np.linalg.norm(self.n)
        self.cell, self.r, self.sag = cell, r, sag
        self.knot = knot if knot is not None else r * 1.7
        self.diamond, self.wobble, self.seed, self.wf = diamond, wobble, seed, wobble_freq
        # non-orthogonal edges: solve for (a, b) coordinates with the dual basis
        M = np.stack([self.U, self.V], axis=1)
        self.pinv = np.linalg.pinv(M)

    def sdf(self, P):
        q = P - self.o
        ab = q @ self.pinv.T  # (N,2) in 0..1
        a, b = ab[:, 0], ab[:, 1]
        x, y = a * self.Ul, b * self.Vl
        w = q @ self.n
        s = self.sag * np.sin(np.pi * np.clip(a, 0, 1)) * np.sin(np.pi * np.clip(b, 0, 1))
        w = w - s
        if self.wobble:
            x = x + self.wobble * vnoise(P * self.wf, self.seed)
            y = y + self.wobble * vnoise(P * self.wf, self.seed + 7)
        if self.diamond:
            p, t = (x + y) * 0.70710678, (x - y) * 0.70710678
        else:
            p, t = x, y
        c = self.cell
        dp = np.abs(p - np.round(p / c) * c)
        dt = np.abs(t - np.round(t / c) * c)
        d1 = np.sqrt(dp * dp + w * w) - self.r
        d2 = np.sqrt(dt * dt + w * w) - self.r
        d = np.minimum(d1, d2)
        dk = np.sqrt(dp * dp + dt * dt + w * w) - self.knot
        d = smin(d, dk, self.r * 0.6)[0]
        e = np.maximum(np.maximum(-x, x - self.Ul), np.maximum(-y, y - self.Vl))
        return np.maximum(d, e)

    def bounds(self):
        C = np.array([self.o, self.o + self.U, self.o + self.V, self.o + self.U + self.V])
        pad = self.r + self.knot + abs(self.sag) + self.wobble + 0.004
        return C.min(0) - pad, C.max(0) + pad


def bar_box(piece, lo, hi, r, k=None, skip=()):
    """Twelve round bars along the edges of an axis-aligned box (centre lines)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    xs, ys, zs = (lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2])
    edges = []
    for y in ys:
        for z in zs:
            edges.append(((xs[0], y, z), (xs[1], y, z)))
        for x in xs:
            edges.append(((x, y, zs[0]), (x, y, zs[1])))
    for x in xs:
        for z in zs:
            edges.append(((x, ys[0], z), (x, ys[1], z)))
    for i, (a, b) in enumerate(edges):
        if i in skip:
            continue
        piece.add(Capsule(a, b, r), k=k if k is not None else r * 0.6)


def chain(piece, a, b, link_r, wire_r, n=None, k=None, start_rot=0.0):
    """A chain of alternating torus links from a to b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    L = np.linalg.norm(d)
    d = d / L
    pitch = link_r * 2.0
    n = n or max(2, int(L / pitch))
    R0 = look_rot(np.cross(d, [0.3, 0.1, 0.9]) if abs(d[1]) > 0.9 else np.cross(d, [0, 1, 0]))
    for i in range(n):
        c = a + d * (i + 0.5) * L / n
        # link lies in a plane containing d; alternate 90 degrees about d
        side = np.cross(d, [0, 1, 0]) if abs(d[1]) < 0.9 else np.cross(d, [1, 0, 0])
        side /= np.linalg.norm(side)
        up = np.cross(side, d)
        ang = start_rot + (np.pi / 2) * (i % 2)
        nrm = np.cos(ang) * side + np.sin(ang) * up  # torus axis
        # elongated link: two tori overlapped along d
        for s in (-1, 1):
            piece.add(Torus(c + d * s * link_r * 0.35, link_r * 0.75, wire_r, rot=look_rot(nrm)), k=k if k is not None else wire_r * 0.3)


def rust_patches(piece, freq=9.0, thresh=0.25, color=RUST, seed=3, gloss=20):
    piece.paint(blotch_prim(freq, thresh, seed=seed), color, gloss=gloss, feather=0.004)
    piece.paint(blotch_prim(freq * 2.3, thresh + 0.15, seed=seed + 5), shade(color, 1.25), gloss=gloss, feather=0.003)


# ==============================================================================================================
# crab pot — 1.05 m square steel frame, teal twine netting, two side tunnels, hinged top door, bait jar


def crab_pot():
    m = Model("crab_pot", res=0.008)
    W, H = 1.05, 0.72
    hx, top = W / 2 - 0.025, H - 0.025
    br = 0.03  # frame bar radius (chunky, toy-like)
    NET = "#3d8274"
    m.bone("root")
    hz = -0.36
    m.bone("door", "root", (0, top, hz))

    fr = m.piece("frame", color=IRON, gloss=70, lumps=0.0018, lump_freq=7, dents=26, dent_size=0.025, dent_depth=0.0025,
                 res=0.0075, decimate=2400)
    bar_box(fr, (-hx, br, -hx), (hx, top, hx), br)
    # mid stiffeners on each side + bottom cross
    for s in (-1, 1):
        fr.add(Capsule((0, br, s * hx), (0, top, s * hx), br * 0.8), k=0.012)
    fr.add(Capsule((-hx, br, 0), (hx, br, 0), br * 0.85), k=0.012)
    fr.add(Capsule((0, br, -hx), (0, br, hx), br * 0.85), k=0.012)
    # door opening frame on top and the bait bar
    dz0, dz1, dx = hz, 0.06, 0.25
    for a, b in (((-dx, top, dz0), (dx, top, dz0)), ((-dx, top, dz1), (dx, top, dz1)),
                 ((-dx, top, dz0), (-dx, top, dz1)), ((dx, top, dz0), (dx, top, dz1)),
                 ((-hx, top, 0.24), (hx, top, 0.24))):
        fr.add(Capsule(a, b, br * 0.7), k=0.01)
    # tunnel eye frames on the +-x faces (outer slot) and inner slot frames, joined by short corner bars
    ty0, ty1, tz = 0.2, 0.44, 0.27
    iy0, iy1, ix = 0.27, 0.36, 0.24
    for s in (-1, 1):
        ox = s * hx
        rect = [(ox, ty0, -tz), (ox, ty0, tz), (ox, ty1, tz), (ox, ty1, -tz)]
        for i in range(4):
            fr.add(Capsule(rect[i], rect[(i + 1) % 4], br * 0.75), k=0.008)
        irect = [(s * ix, iy0, -tz * 0.85), (s * ix, iy0, tz * 0.85), (s * ix, iy1, tz * 0.85), (s * ix, iy1, -tz * 0.85)]
        for i in range(4):
            fr.add(Capsule(irect[i], irect[(i + 1) % 4], br * 0.5), k=0.006)
            fr.add(Capsule(rect[i], irect[i], br * 0.45), k=0.006)
    # bridle eye on a top corner (the haul line ties here)
    eye_c = np.array([hx - 0.02, top + 0.045, hx - 0.02])
    fr.add(Torus(eye_c, 0.032, 0.009, rot=(90, 45, 0)), k=0.006)
    fr.add(Capsule((hx, top, hx), eye_c + (0, -0.03, 0), 0.012), k=0.01)
    rust_patches(fr, freq=5.0, thresh=0.3)
    metal(fr, dark=IRON_DK, light="#6c6f76", r=0.02, tarnish=0.04, wear=0.5, light_gloss=140)

    # netting: four sides (minus tunnel slots), bottom, top (minus the door hole)
    cell, sr = 0.155, 0.0075
    sides = [
        ((-hx, br, hx), (2 * hx, 0, 0), (0, top - br, 0), (0, 0, -1)),      # +z face (front)
        ((-hx, br, -hx), (2 * hx, 0, 0), (0, top - br, 0), (0, 0, 1)),      # -z face
        ((hx, br, -hx), (0, 0, 2 * hx), (0, top - br, 0), (-1, 0, 0)),      # +x face
        ((-hx, br, -hx), (0, 0, 2 * hx), (0, top - br, 0), (1, 0, 0)),      # -x face
    ]
    for i, (o, U, V, inward) in enumerate(sides):
        np_ = m.piece(f"net_{i}", color=NET, gloss=45, lumps=0.0008, lump_freq=20, mottle=0.08, res=0.0045, merge="net",
                      decimate=1250)
        np_.add(NetPanel(o, U, V, cell, sr, sag=0.018, wobble=0.006, seed=i, sag_dir=inward))
        if i >= 2:  # tunnel slot
            s = 1 if i == 2 else -1
            np_.sub(Box((s * hx, (ty0 + ty1) / 2, 0), (0.06, (ty1 - ty0) / 2 - 0.004, tz - 0.004)), k=0.004)
    nb = m.piece("net_bottom", color=shade(NET, 0.85), gloss=40, lumps=0.0008, lump_freq=20, mottle=0.08, res=0.006,
                 merge="net", decimate=900)
    nb.add(NetPanel((-hx, br, -hx), (2 * hx, 0, 0), (0, 0, 2 * hx), cell * 1.25, sr * 1.1, sag=0.0, wobble=0.005, seed=9,
                    sag_dir=(0, 1, 0)))
    nt = m.piece("net_top", color=NET, gloss=45, lumps=0.0008, lump_freq=20, mottle=0.08, res=0.0045, merge="net",
                 decimate=1100)
    nt.add(NetPanel((-hx, top, -hx), (2 * hx, 0, 0), (0, 0, 2 * hx), cell, sr, sag=-0.012, wobble=0.006, seed=11,
                    sag_dir=(0, 1, 0)))
    nt.sub(Box((0, top, (dz0 + dz1) / 2), (dx - 0.006, 0.05, (dz1 - dz0) / 2 - 0.006)), k=0.004)
    # tunnel funnels: a sleeve of dense webbing from the outer slot to the inner slot (thin shell, mesh painted on)
    for s_, nm in ((1, "tun_p"), (-1, "tun_n")):
        tp = m.piece(nm, color=shade(NET, 0.42), gloss=45, lumps=0.001, lump_freq=14, mottle=0.08, res=0.005, merge="net",
                     decimate=500)
        x0, x1 = s_ * ix, s_ * hx
        oc, ic = ((ty0 + ty1) / 2, 0.0), ((iy0 + iy1) / 2, 0.0)
        oh, ow = (ty1 - ty0) / 2, tz
        ih, iw = (iy1 - iy0) / 2, tz * 0.85

        def funnel(P, x0=x0, x1=x1):
            t = np.clip((P[:, 0] - x0) / (x1 - x0), 0, 1)
            cyy = ic[0] + (oc[0] - ic[0]) * t
            hh = ih + (oh - ih) * t
            ww = iw + (ow - iw) * t
            q = np.column_stack([np.abs(P[:, 1] - cyy) - hh, np.abs(P[:, 2]) - ww])
            box = np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(axis=1), 0)
            shell = np.abs(box) - 0.006
            xin = np.maximum(np.minimum(x0, x1) - P[:, 0], P[:, 0] - np.maximum(x0, x1))
            return np.maximum(shell, xin)
        lo_ = np.array([min(x0, x1) - 0.02, ty0 - 0.03, -tz - 0.03])
        hi_ = np.array([max(x0, x1) + 0.02, ty1 + 0.03, tz + 0.03])
        tp.add(Func(funnel, lo_, hi_))

        def mesh(P):
            c = 0.042
            a_ = np.abs((P[:, 2] + P[:, 0]) / c - np.round((P[:, 2] + P[:, 0]) / c))
            b_ = np.abs((P[:, 2] - P[:, 0]) / c - np.round((P[:, 2] - P[:, 0]) / c))
            return np.minimum(a_, b_) * c - 0.0045
        tp.paint(Func(mesh, lo_, hi_), shade(NET, 0.9), feather=0.002)

    # the door: its own little frame + net + a red rubber bungee latch; rigid to the hinge bone
    dr = m.piece("door", color=IRON, gloss=70, rigid="door", lumps=0.0015, lump_freq=8, res=0.0045, decimate=1500)
    dy = top + br * 1.35
    door_rect = [(-dx + 0.015, dy, dz0 + 0.01), (dx - 0.015, dy, dz0 + 0.01), (dx - 0.015, dy, dz1 - 0.012), (-dx + 0.015, dy, dz1 - 0.012)]
    for i in range(4):
        dr.add(Capsule(door_rect[i], door_rect[(i + 1) % 4], br * 0.62), k=0.01)
    dr.add(NetPanel((-dx + 0.015, dy, dz0 + 0.01), (2 * dx - 0.03, 0, 0), (0, 0, dz1 - dz0 - 0.022), cell * 0.62, sr,
                    sag=-0.006, wobble=0.004, seed=40, diamond=True, sag_dir=(0, 1, 0)), k=0.004, color=NET, gloss=45)
    # hinge knuckles
    for x in (-0.16, 0.16):
        dr.add(Cylinder((x, top + 0.006, dz0), 0.02, 0.035, rot=(0, 0, 90), round=0.006), k=0.006)
    # bungee: red rubber strap from the door's front edge down over the frame bar, with a hook
    strap = [(0, dy + 0.006, dz1 - 0.02), (0, dy + 0.016, dz1 + 0.02), (0, top + 0.01, dz1 + 0.05), (0, top - 0.04, dz1 + 0.06)]
    dr.add(Tube(strap, 0.011, samples=5), k=0.006, color="#c23a2e", gloss=110)
    dr.add(Torus((0, top - 0.055, dz1 + 0.055), 0.016, 0.0045, rot=(0, 0, 90)), k=0.003, color="#9a9ca2", gloss=170)
    rust_patches(dr, freq=7.0, thresh=0.32, seed=8)
    metal(dr, dark=IRON_DK, r=0.012, tarnish=0.04)

    # bait jar: perforated white jar with an orange lid, hanging from the bait bar on a cord
    bj = m.piece("bait_jar", color="#e6e2d4", gloss=120, lumps=0.0012, lump_freq=14, dents=5, dent_size=0.015,
                 dent_depth=0.0015, res=0.004, decimate=900)
    jc = np.array([0.0, top - 0.3, 0.24])
    bj.add(Cylinder(jc, 0.062, 0.085, round=0.02))
    bj.add(Cylinder(jc + (0, 0.09, 0), 0.068, 0.022, round=0.01), k=0.004, color="#e46a28", gloss=90)
    bj.add(Cylinder(jc + (0, -0.09, 0), 0.066, 0.012, round=0.008), k=0.004, color="#e46a28", gloss=90)
    rng = np.random.default_rng(4)
    for i in range(14):
        a = i * 2 * np.pi / 7 + (i // 7) * np.pi / 7
        y = jc[1] - 0.035 + (i // 7) * 0.07
        p = jc + (np.cos(a) * 0.064, y - jc[1], np.sin(a) * 0.064)
        bj.sub(Sphere(p, 0.011), k=0.003)
        bj.paint(Sphere(p, 0.012), "#5b3a33", gloss=150, feather=0.002)  # chopped herring showing through
    bj.add(Tube([jc + (0, 0.11, 0), jc + (0.01, 0.2, 0.0), (0.0, top - 0.005, 0.24)], 0.006, samples=4), k=0.004,
           color=CP["rope"], gloss=30)
    bj.add(Torus((0, top + 0.002, 0.24), 0.025, 0.0065, rot=(0, 0, 90)), k=0.003, color=CP["rope"], gloss=30)

    # a coil of haul line on top and the yellow ID tag on the frame
    rc = m.piece("line_coil", color=CP["rope"], gloss=30, lumps=0.0015, lump_freq=12, res=0.0045, decimate=1300)
    cpts = coil((0.28, top + br + 0.012, 0.3), 0.12, 0.155, 2.4, 0.02, n_per_turn=12)
    rope(rc, cpts, 0.0115, twist=False, color=None)
    rc.add(Tube([cpts[-1], cpts[-1] + (0.03, 0.01, 0.06), eye_c + (-0.03, 0.0, -0.03), eye_c], 0.0115, samples=4), k=0.005)
    rc.paint(blotch_prim(25, 0.2, seed=2), CP["rope_dk"], feather=0.004)
    tag = m.piece("tag", color="#f2c230", gloss=110, lumps=0.0008, lump_freq=20, res=0.003, decimate=300)
    tc = np.array([-hx - 0.012, top - 0.07, 0.3])
    tag.add(Box(tc, (0.006, 0.04, 0.055), round=0.004))
    tag.add(Torus(tc + (0, 0.05, 0), 0.016, 0.004, rot=(0, 0, 90)), k=0.003)
    tag.paint(Box(tc + (-0.006, 0.0, 0.0), (0.004, 0.012, 0.035)), "#222326", feather=0.002)
    tag.paint(Box(tc + (-0.006, -0.022, 0.0), (0.004, 0.006, 0.025)), "#222326", feather=0.002)

    m.socket("line", None, tuple(eye_c))
    m.socket("bait", None, tuple(jc))
    m.socket("inside", None, (0, 0.12, -0.05))
    return m


# ==============================================================================================================
# buoy — big orange pot float + a high-flyer pole threaded through a red/white marker float, little pennant.
# Waterline at y = 0.


class RingMail(Prim):
    """Chain-mail of overlapping flat rings on a parallelogram panel (o, U, V), with a sag along `sag_dir`."""

    def __init__(self, o, U, V, cell, R, r, sag=0.0, sag_dir=None, tilt=0.25):
        super().__init__()
        self.o = np.asarray(o, float)
        self.U, self.V = np.asarray(U, float), np.asarray(V, float)
        self.Ul, self.Vl = np.linalg.norm(self.U), np.linalg.norm(self.V)
        self.n = np.asarray(sag_dir, float) if sag_dir is not None else np.cross(self.U, self.V)
        self.n = self.n / np.linalg.norm(self.n)
        self.pinv = np.linalg.pinv(np.stack([self.U, self.V], axis=1))
        self.cell, self.R, self.r, self.sag, self.tilt = cell, R, r, sag, tilt

    def sdf(self, P):
        q = P - self.o
        ab = q @ self.pinv.T
        a, b = ab[:, 0], ab[:, 1]
        x, y = a * self.Ul, b * self.Vl
        w = q @ self.n - self.sag * np.sin(np.pi * np.clip(a, 0, 1)) * np.sin(np.pi * np.clip(b, 0, 1))
        c = self.cell
        d = np.full(len(P), 1e9)
        i0, j0 = np.floor(x / c - 0.5), np.floor(y / c - 0.5)
        for di in (0, 1):
            for dj in (0, 1):
                i, j = i0 + di, j0 + dj
                cx_, cy_ = (i + 0.5) * c, (j + 0.5) * c
                dx, dy = x - cx_, y - cy_
                par = np.where((i + j) % 2 == 0, 1.0, -1.0)
                ww = w - par * self.tilt * dx
                ok = (cx_ > 0) & (cx_ < self.Ul) & (cy_ > 0) & (cy_ < self.Vl)
                dd = np.sqrt((np.sqrt(dx * dx + dy * dy) - self.R) ** 2 + ww * ww) - self.r
                d = np.where(ok, np.minimum(d, dd), d)
        return d

    def bounds(self):
        C = np.array([self.o, self.o + self.U, self.o + self.V, self.o + self.U + self.V])
        pad = self.R + self.r + abs(self.sag) + 0.02
        return C.min(0) - pad, C.max(0) + pad


def buoy():
    m = Model("buoy", res=0.006)
    ORANGE, RED = "#e8612a", "#c9302a"
    R = 0.3
    c = np.array([0, 0.1, 0])
    fl = m.piece("float", color=ORANGE, gloss=150, lumps=0.003, lump_freq=6, dents=16, dent_size=0.05, dent_depth=0.004,
                 res=0.0065, decimate=5200)
    fl.add(Ellipsoid(c, (R, R * 0.93, R)))
    fl.add(Torus(c, R * 0.995, 0.009), k=0.006)  # moulding seam
    # top and bottom rope eyes (moulded lugs)
    for s in (1, -1):
        lug = c + (0, s * R * 0.93, 0)
        fl.add(Cylinder(lug + (0, s * 0.01, 0), 0.06, 0.03, round=0.02), k=0.03)
        fl.add(Torus(lug + (0, s * 0.065, 0), 0.034, 0.015, rot=(90, 0, 0)), k=0.012)
    # owner's colours: a cream band and two black stencil dashes; grime + algae at the waterline
    fl.paint(func_prim(lambda P: np.abs(P[:, 1] - (c[1] + 0.13)) - 0.038), "#efe2c4", feather=0.01)
    fl.paint(func_prim(lambda P: np.abs(P[:, 1] - (c[1] + 0.13)) - 0.006 + 0.0 * P[:, 0]), "#d84a26", feather=0.006)
    fl.paint(func_prim(lambda P: P[:, 1] - 0.012 + 0.012 * fbm(P * 18, 2, 3)), "#b4592c", gloss=90, feather=0.014)
    fl.paint(func_prim(lambda P: P[:, 1] + 0.03 + 0.02 * fbm(P * 14, 2, 4)), "#5d6a35", gloss=60, feather=0.016)
    # a few barnacles just under the waterline
    bn = m.piece("barnacles", color="#d8d2c2", gloss=30, lumps=0.0008, lump_freq=40, res=0.003, decimate=500)
    rng = np.random.default_rng(3)
    for i in range(7):
        a = rng.uniform(0, 2 * np.pi)
        y = rng.uniform(-0.06, -0.01)
        rr = np.sqrt(max(R * R - (y - c[1]) ** 2 / 0.93 ** 2, 0.01))
        p = np.array([np.sin(a) * rr, y, np.cos(a) * rr])
        nrm = (p - c) / np.linalg.norm(p - c)
        sz = rng.uniform(0.011, 0.018)
        bn.add(Capsule(p - nrm * 0.004, p + nrm * sz * 0.8, sz, sz * 0.6), k=0.003)
        bn.sub(Sphere(p + nrm * sz * 1.3, sz * 0.5), k=0.002, color="#6b6458")
    # tethered rope stub from the bottom eye (the line goes down from here)
    rp = m.piece("rope", color=CP["rope"], gloss=30, lumps=0.0012, lump_freq=14, res=0.004, decimate=900)
    be = c + (0, -R * 0.93 - 0.065, 0)
    rope(rp, [be + (0, 0.02, 0), be + (0.0, -0.03, 0.02), be + (0.01, -0.11, 0.03), be + (0.02, -0.2, 0.02)], 0.011,
         twist=True, groove=CP["rope_dk"])
    rp.add(Torus(be + (0, 0.005, 0), 0.03, 0.012, rot=(0, 0, 90)), k=0.006)
    # pole (wooden dowel) lashed to the top eye
    te = c + (0, R * 0.93 + 0.065, 0)
    pl = m.piece("pole", color=CP["wood"], gloss=40, lumps=0.0012, lump_freq=10, dents=6, dent_size=0.02, dent_depth=0.0015,
                 res=0.004, decimate=1000)
    top = te + (0, 0.72, 0)
    pl.add(Capsule(te + (0, -0.02, 0), top, 0.019, 0.014))
    pl.paint(blotch_prim(18, 0.15, seed=7, stretch=(3, 0.3, 3)), CP["wood_dk"], feather=0.004)
    for y in (0.0, 0.03):
        pl.add(Torus(te + (0, y + 0.01, 0), 0.02, 0.008, rot=(8, 0, 0)), k=0.004, color=CP["rope"], gloss=30)
    pl.add(Sphere(top, 0.02), k=0.006, color="#2a2a2e")
    # marker float on the pole: a red/white spar bullet
    mk = m.piece("marker", color=RED, gloss=150, lumps=0.0015, lump_freq=10, dents=6, dent_size=0.03, dent_depth=0.002,
                 res=0.004, decimate=1300)
    mc = te + (0, 0.3, 0)
    mk.add(Ellipsoid(mc, (0.1, 0.14, 0.1)))
    mk.add(Torus(mc, 0.098, 0.006), k=0.004)
    mk.paint(func_prim(lambda P: np.abs(P[:, 1] - mc[1]) - 0.03), "#f0ebe0", feather=0.007)
    mk.add(Cylinder(mc + (0, 0.135, 0), 0.03, 0.012, round=0.006), k=0.01)
    mk.add(Cylinder(mc + (0, -0.135, 0), 0.03, 0.012, round=0.006), k=0.01)
    # pennant
    fg = m.piece("flag", color="#f2c230", gloss=60, lumps=0.0008, lump_freq=12, mottle=0.06, res=0.003, decimate=700)
    fa, fb = top + (0, -0.015, 0), top + (0, -0.15, 0)
    flag = Fin(fa, fb, [top + (0.22, -0.1, 0.02)], (0, 0, 1), thick=0.004, edge=0.003, ribs=0.0, scallop=0.0,
               wave=(0.01, 0.12))
    fg.add(flag)
    fg.paint(flag.zone(0.55), "#c9302a", feather=0.004)
    m.socket("line", None, tuple(be + (0.02, -0.2, 0.02)))
    m.socket("top", None, tuple(top + (0, 0.02, 0)))
    return m


# ==============================================================================================================
# dredge — iron cage with a toothed mouth bar, ring-mail belly, bridle arms to a towing ring, chain and shackle


def dredge():
    m = Model("dredge", res=0.007)
    W, H, L = 0.72, 0.3, 0.74
    hw = W / 2
    lift = 0.06  # the ring bag sags below the frame; everything sits on it
    zf, zb = L / 2, -L / 2
    y0 = lift + 0.02
    fr = m.piece("frame", color=IRON, gloss=60, lumps=0.0018, lump_freq=7, dents=26, dent_size=0.03, dent_depth=0.003,
                 res=0.0062, decimate=4600)
    # mouth: heavy flat-bar rectangle, rounded and hammered
    fr.add(Box((0, y0 + H, zf), (hw + 0.03, 0.028, 0.03), round=0.012))
    fr.add(Box((0, y0, zf), (hw + 0.03, 0.03, 0.035), round=0.012), k=0.01)
    # riveted cheek plates on each side (the dredge's "heads")
    for s_ in (-1, 1):
        fr.add(Box((s_ * (hw + 0.015), y0 + H / 2, zf - 0.07), (0.018, H / 2 + 0.03, 0.12), round=0.012), k=0.012)
        fr.add(Cylinder((s_ * (hw + 0.035), y0 + H * 0.62, zf - 0.03), 0.04, 0.014, rot=(0, 0, 90), round=0.006), k=0.006)  # pivot boss
        for (yy, zz) in ((0.05, -0.15), (0.05, 0.02), (H - 0.03, -0.15), (H - 0.03, 0.02)):
            fr.add(Sphere((s_ * (hw + 0.034), y0 + yy, zf - 0.07 + zz * 0.6), 0.012), k=0.004)
        # skid runner
        fr.add(Box((s_ * (hw + 0.012), y0 - 0.005, -0.02), (0.02, 0.022, L / 2 + 0.02), round=0.012), k=0.012)
        fr.add(Capsule((s_ * (hw + 0.012), y0, zb + 0.0), (s_ * (hw + 0.012), y0 + 0.07, zb - 0.06), 0.02), k=0.012)
    # cage: flat straps over the top, side bars, two hoops, a back frame
    Hb = H * 0.85
    for x in np.linspace(-hw + 0.06, hw - 0.06, 5):
        fr.add(Capsule((x, y0 + H, zf - 0.02), (x * 0.94, y0 + Hb, zb), 0.019), k=0.01)
    for s_ in (-1, 1):
        fr.add(Capsule((s_ * hw, y0 + H * 0.5, zf - 0.15), (s_ * hw * 0.94, y0 + Hb * 0.5, zb), 0.019), k=0.01)
        fr.add(Capsule((s_ * hw, y0, zf - 0.15), (s_ * hw * 0.94, y0, zb), 0.022), k=0.01)
    for z in (zf - L * 0.42, zf - L * 0.72):
        t = (zf - z) / L
        x_ = hw * (1 - 0.06 * t)
        y_ = y0 + H * (1 - 0.15 * t)
        hoop = [(-x_, y0, z), (-x_, y_, z), (x_, y_, z), (x_, y0, z)]
        for i in range(3):
            fr.add(Capsule(hoop[i], hoop[i + 1], 0.021), k=0.01)
    back = [(-hw * 0.94, y0, zb), (hw * 0.94, y0, zb), (hw * 0.94, y0 + Hb, zb), (-hw * 0.94, y0 + Hb, zb)]
    for i in range(4):
        fr.add(Capsule(back[i], back[(i + 1) % 4], 0.024), k=0.01)
    # tooth bar with forward-raking tines under the mouth
    for x in np.linspace(-hw + 0.03, hw - 0.03, 10):
        fr.add(Capsule((x, y0 - 0.005, zf + 0.02), (x, y0 - 0.035, zf + 0.12), 0.017, 0.007), k=0.008)
    # bridle yoke: two bars from the pivot bosses to the towing ring
    ring_c = np.array([0, y0 + H + 0.42, zf + 0.1])
    for s_ in (-1, 1):
        fr.add(Capsule((s_ * (hw + 0.04), y0 + H * 0.62, zf - 0.03), ring_c + (s_ * 0.05, -0.04, -0.01), 0.022, 0.018), k=0.012)
    fr.add(Torus(ring_c, 0.055, 0.018, rot=(0, 0, 90)), k=0.012)
    rust_patches(fr, freq=4.0, thresh=0.32, seed=11, color="#8f4322")
    metal(fr, dark=IRON_DK, light="#6a6c72", r=0.02, tarnish=0.04, wear=0.45, light_gloss=130)
    # chain from the ring up to the shackle
    ch = m.piece("chain", color=IRON, gloss=70, lumps=0.0008, lump_freq=14, res=0.0034, decimate=1800)
    sh_b = ring_c + (0, 0.2, 0.0)
    chain(ch, ring_c + (0, 0.05, 0), sh_b, 0.024, 0.0085, n=4)
    rust_patches(ch, freq=9, thresh=0.3, seed=12, color="#8f4322")
    # bow shackle with its pin
    sk = m.piece("shackle", color="#55575d", gloss=120, lumps=0.0008, lump_freq=14, res=0.003, decimate=1200)
    sc = sh_b + (0, 0.05, 0)
    sk.add(Torus(sc + (0, 0.02, 0), 0.042, 0.011, rot=(90, 0, 0)), k=0.004)
    sk.sub(HalfSpace(sc + (0, -0.0, 0), (0, -1, 0)), k=0.004)
    for s_ in (-1, 1):
        sk.add(Capsule(sc + (s_ * 0.042, 0.02, 0), sc + (s_ * 0.042, -0.035, 0), 0.011), k=0.004)
        sk.add(Sphere(sc + (s_ * 0.042, -0.04, 0), 0.017), k=0.004)
    sk.add(Capsule(sc + (-0.062, -0.04, 0), sc + (0.062, -0.04, 0), 0.0085), k=0.003)
    sk.add(Sphere(sc + (-0.068, -0.04, 0), 0.015), k=0.003)
    metal(sk, dark=IRON_DK, r=0.01, tarnish=0.05)
    # ring-mail bag: the belly sags below the frame, the back curls up behind the back frame
    rm = m.piece("rings", color="#5c5e64", gloss=90, lumps=0.0006, lump_freq=20, res=0.0034, decimate=3400)
    rm.add(RingMail((-hw * 0.93, y0 - 0.01, zb + 0.01), (W * 0.93, 0, 0), (0, 0, L - 0.16), 0.085, 0.048, 0.0085,
                    sag=-0.055, sag_dir=(0, 1, 0), tilt=0.18))
    rm.add(RingMail((-hw * 0.9, y0 + 0.01, zb - 0.02), (W * 0.9, 0, 0), (0, Hb - 0.02, 0), 0.085, 0.048, 0.0085,
                    sag=0.03, sag_dir=(0, 0, -1), tilt=0.18))
    rust_patches(rm, freq=8, thresh=0.25, seed=13, color="#8f4322")
    m.socket("shackle", None, tuple(sc + (0, 0.065, 0)))
    m.socket("mouth", None, (0, y0 + H * 0.5, zf))
    return m


# ==============================================================================================================
# mallet — chunky wooden ice mallet, banded head, taped grip. Stands on its handle butt (origin), head up.


def mallet():
    m = Model("mallet", res=0.004)
    hd = m.piece("handle", color=CP["wood_lt"], gloss=50, lumps=0.0012, lump_freq=10, dents=8, dent_size=0.02,
                 dent_depth=0.0015, res=0.0035, decimate=1800)
    hd.add(Capsule((0, 0.02, 0), (0, 0.5, 0), 0.021, 0.017))
    hd.add(Ellipsoid((0, 0.022, 0), (0.03, 0.022, 0.03)), k=0.012)  # butt knob
    hd.paint(blotch_prim(16, 0.15, seed=4, stretch=(3, 0.25, 3)), shade(CP["wood_lt"], 0.8), feather=0.004)
    # friction-tape grip: a wound black ribbon
    tp = m.piece("tape", color="#2b2c30", gloss=70, lumps=0.0006, lump_freq=20, res=0.0025, decimate=1600)
    y = np.linspace(0.06, 0.24, 60)
    a = y / 0.03 * 2 * np.pi
    pts = np.column_stack([np.cos(a) * 0.0215, y, np.sin(a) * 0.0215])
    tp.add(Capsule((0, 0.055, 0), (0, 0.245, 0), 0.0225, 0.0215))
    tp.add(Tube(pts, 0.0035, samples=None), k=0.002)
    tp.add(Tube([(0.021, 0.245, 0.004), (0.026, 0.235, 0.02), (0.03, 0.215, 0.028)], 0.004, samples=4), k=0.003)  # loose end
    # head: a fat wooden barrel with proud iron bands, battered faces, ice crust stuck on one face
    WOOD = "#a9713f"
    he = m.piece("head", color=WOOD, gloss=40, lumps=0.0018, lump_freq=8, dents=14, dent_size=0.022, dent_depth=0.003,
                 res=0.0038, decimate=3000)
    hc = np.array([0, 0.56, 0])
    he.add(Cylinder(hc, 0.07, 0.115, rot=(0, 0, 90), round=0.022))
    he.add(Ellipsoid(hc, (0.1, 0.076, 0.076)), k=0.03)  # barrel belly
    for s_ in (-1, 1):
        he.sub(Sphere(hc + (s_ * 0.16, 0.012, 0.012), 0.05), k=0.015)  # dished, mushroomed striking faces
    he.add(Cylinder(hc + (0, -0.062, 0), 0.03, 0.02, round=0.01), k=0.015)  # collar round the handle
    # grain: dark streaks along the head's axis, scored lines, end-grain rings on the faces
    he.paint(blotch_prim(9, 0.25, seed=6, stretch=(0.25, 3.5, 3.5)), shade(WOOD, 0.72), feather=0.004)
    for z in (-0.045, -0.02, 0.006, 0.032, 0.052):
        score(he, [hc + (-0.06, 0.074, z), hc + (0, 0.079, z + 0.004), hc + (0.06, 0.074, z - 0.002)], 0.0022)
    for s_ in (-1, 1):
        def rings_(P, s_=s_):
            q = P - hc
            d = np.sqrt(q[:, 1] ** 2 + q[:, 2] ** 2)
            return np.where(s_ * q[:, 0] > 0.1, np.abs((d / 0.018) % 1.0 - 0.5) * 0.018 - 0.0065, 1.0)
        he.paint(func_prim(rings_), shade(WOOD, 0.75), feather=0.002)
    bd = m.piece("bands", color="#45464b", gloss=110, lumps=0.0008, lump_freq=12, dents=6, dent_size=0.015,
                 dent_depth=0.0015, res=0.003, decimate=2000)
    for s_ in (-1, 1):
        bc_ = hc + (s_ * 0.088, 0, 0)
        bd.add(Cylinder(bc_, 0.077, 0.013, rot=(0, 0, 90), round=0.005))
        bd.sub(Cylinder(bc_, 0.066, 0.03, rot=(0, 0, 90)), k=0.003)
        for i in range(4):
            a_ = i * np.pi / 2 + 0.4
            bd.add(Sphere(bc_ + (0, np.sin(a_) * 0.078, np.cos(a_) * 0.078), 0.0065), k=0.002)  # rivets
    rust_patches(bd, freq=12, thresh=0.25, seed=21)
    metal(bd, dark="#26272b", light="#8a8d93", r=0.006, tarnish=0.06, wear=0.2)
    ic = m.piece("ice", color="#e4eef2", gloss=210, lumps=0.0015, lump_freq=40, res=0.0026, decimate=900)
    rng = np.random.default_rng(5)
    for i in range(9):
        p = hc + (0.112 + rng.uniform(0, 0.006), rng.uniform(-0.05, 0.04), rng.uniform(-0.05, 0.05))
        ic.add(Ellipsoid(p, rng.uniform(0.008, 0.017, 3), rot=tuple(rng.uniform(0, 90, 3))), k=0.006)
    ic.add(Ellipsoid(hc + (0.1, 0.074, 0.03), (0.02, 0.006, 0.014)), k=0.006)  # a smear of frost on the top
    m.socket("grip", None, (0, 0.15, 0))
    m.socket("head", None, tuple(hc + (0.13, 0, 0)))
    return m


# ==============================================================================================================
# rod — cork grip, enamel reel, green glass-fibre blank with red thread wraps and guides; butt at origin, tip up.


def rod():
    m = Model("rod", res=0.004)
    H = 1.8
    BLANK = "#2f5a3e"
    gr = m.piece("grip", color="#c39a63", gloss=40, lumps=0.001, lump_freq=18, dents=10, dent_size=0.012,
                 dent_depth=0.0012, res=0.0025, decimate=2200)
    gr.add(Capsule((0, 0.02, 0), (0, 0.3, 0), 0.02, 0.019))
    gr.add(Ellipsoid((0, 0.16, 0), (0.0235, 0.11, 0.0235)), k=0.03)
    gr.add(Capsule((0, 0.39, 0), (0, 0.47, 0), 0.0175, 0.014), k=0.004)  # fore grip
    for y in np.arange(0.035, 0.3, 0.022):
        gr.sub(Torus((0, y, 0), 0.0215, 0.0011), k=0.0008)  # cork rings
    gr.paint(blotch_prim(160, 0.38, seed=2), "#9a7646", feather=0.0015)
    gr.paint(blotch_prim(30, 0.3, seed=3), "#b58a55", feather=0.003)
    gr.add(Cylinder((0, 0.012, 0), 0.023, 0.012, round=0.008), k=0.003, color="#2b2b30", gloss=90)  # rubber butt
    # reel seat (brass) and the reel hanging in front (+z)
    rs = m.piece("seat", color=CP["brass"], gloss=170, lumps=0.0005, lump_freq=20, res=0.0022, decimate=1300)
    rs.add(Cylinder((0, 0.345, 0), 0.0185, 0.048, round=0.004))
    for y in (0.3, 0.39):
        rs.add(Cylinder((0, y, 0), 0.021, 0.008, round=0.003), k=0.002)
    rs.add(Cylinder((0, 0.47, 0), 0.016, 0.006, round=0.002), k=0.002)  # winding check
    metal(rs, dark=CP["brass_dk"], light=CP["brass_lt"], r=0.006, tarnish=0.05, wear=0.1)
    rl = m.piece("reel", color="#a3302a", gloss=160, lumps=0.0008, lump_freq=18, dents=5, dent_size=0.012,
                 dent_depth=0.001, res=0.0022, decimate=3600)
    rc = np.array([0, 0.345, 0.07])
    rl.add(Box((0, 0.345, 0.03), (0.008, 0.032, 0.016), round=0.006))  # foot/stem
    rl.add(Cylinder(rc, 0.05, 0.02, rot=(0, 0, 90), round=0.01), k=0.006)
    for s in (-1, 1):
        rl.add(Torus(rc + (s * 0.02, 0, 0), 0.049, 0.004, rot=(0, 0, 90)), k=0.002, color=CP["brass"], gloss=200)
    rl.sub(Cylinder(rc, 0.036, 0.024, rot=(0, 0, 90)), k=0.003)  # spool well
    rl.add(Cylinder(rc, 0.03, 0.017, rot=(0, 0, 90), round=0.004), k=0.002, color="#e9e2cf", gloss=90)  # line on the spool
    for i in range(6):
        a = i * np.pi / 3
        rl.sub(Sphere(rc + (0.022, np.sin(a) * 0.033, np.cos(a) * 0.033), 0.006), k=0.002)  # vent holes
    # crank: arm + knob on the +x side
    rl.add(Capsule(rc + (0.024, 0, 0), rc + (0.03, -0.035, 0.012), 0.006), k=0.003, color=CP["brass"], gloss=200)
    rl.add(Capsule(rc + (0.03, -0.035, 0.012), rc + (0.055, -0.035, 0.012), 0.01, 0.009), k=0.003, color="#efe6cf", gloss=120)
    rl.add(Cylinder(rc + (0.024, 0, 0), 0.01, 0.005, rot=(0, 0, 90), round=0.003), k=0.002, color=CP["brass"], gloss=200)
    metal(rl, dark="#5e1c1a", r=0.006, tarnish=0.06)
    # blank: tapers, built in sections at increasing resolution
    bl = m.piece("blank", color=BLANK, gloss=200, lumps=0.0004, lump_freq=10, res=0.0026, decimate=1500, merge="blank")
    bl.add(Capsule((0, 0.46, 0), (0, 1.0, 0), 0.0125, 0.0085))
    bl2 = m.piece("blank2", color=BLANK, gloss=200, lumps=0.0002, lump_freq=10, res=0.0016, decimate=1500, merge="blank")
    bl2.add(Capsule((0, 0.99, 0), (0, H - 0.01, 0), 0.0086, 0.0032))
    # guides + thread wraps on the +z side (the reel side)
    gys = [0.6, 0.86, 1.1, 1.32, 1.52, 1.68]
    gu = m.piece("guides", color="#bfc4ca", gloss=220, lumps=0.0, res=0.0013, decimate=2400)

    def rad(y):
        return np.interp(y, [0.46, 1.0, H], [0.0125, 0.0085, 0.0032])
    for i, y in enumerate(gys):
        r0 = rad(y)
        rr = 0.024 - i * 0.0028
        gc = np.array([0, y + 0.004, r0 + rr + 0.012])
        gu.add(Torus(gc, rr, 0.0028, rot=(90, 0, 0)), k=0.001)
        gu.add(Capsule((0, y - 0.03, r0 * 0.8), gc - (0, 0, rr), 0.0026), k=0.002)
        gu.add(Capsule((0, y + 0.03, r0 * 0.8), gc - (0, 0, rr), 0.0026), k=0.002)
        wrap = Cylinder((0, y, 0), r0 + 0.0022, 0.016, round=0.0015)
        (bl if y < 1.0 else bl2).add(wrap, k=0.0015, color="#b8322b", gloss=230)
    tc = np.array([0, H + 0.004, 0])
    gu.add(Torus(tc + (0, 0.006, 0.006), 0.007, 0.0022, rot=(90, 0, 0)), k=0.001)
    bl2.add(Cylinder((0, H - 0.012, 0), 0.0048, 0.012, round=0.002), k=0.001, color="#b8322b", gloss=230)
    metal(gu, dark="#6c727c", light="#f2f4f6", r=0.004, tarnish=0.08, wear=0.12)
    # line: off the spool, up through the guides to the tip, a little loose tag end
    pts = [rc + (0, 0.03, 0.0)]
    for i, y in enumerate(gys):
        r0 = rad(y)
        rr = 0.024 - i * 0.0028
        pts.append(np.array([0, y + 0.004, r0 + rr + 0.012 - rr * 0.55]))
    pts.append(tc + (0, 0.006, 0.006))
    ln = m.piece("line", color="#efeadb", gloss=120, lumps=0.0, res=0.0011, decimate=1100)
    ln.add(Tube(np.array(pts), 0.0016, samples=None))
    ln.add(Tube([tc + (0, 0.006, 0.006), tc + (0.0, 0.0, 0.03), tc + (0.004, -0.05, 0.045), tc + (0.006, -0.1, 0.05)],
                0.0016, samples=4), k=0.0006)
    m.socket("tip", None, tuple(tc + (0.006, -0.1, 0.05)))
    m.socket("grip", None, (0, 0.16, 0))
    m.socket("reel", None, tuple(rc))
    return m


# ==============================================================================================================
# bobber — classic red-over-white snap float with a push-button stem; waterline (y=0) at its equator


def bobber():
    m = Model("bobber", res=0.002)
    r = 0.046
    c = np.array([0, 0.004, 0])
    b = m.piece("float", color="#f1ece2", gloss=190, lumps=0.0006, lump_freq=30, dents=7, dent_size=0.012,
                dent_depth=0.0008, res=0.0033, decimate=99999)
    b.add(Sphere(c, r))
    b.add(Torus(c, r * 0.995, 0.0022), k=0.0015)  # the seam where the halves snap together
    b.paint(HalfSpace(c + (0, 0.0005, 0), (0, -1, 0)), "#d8352c", feather=0.0022)
    b.paint(func_prim(lambda P: np.abs(P[:, 1] - c[1]) - 0.0026), "#f6f2ea", feather=0.0008)
    b.paint(func_prim(lambda P: P[:, 1] - (c[1] - r * 0.55) + 0.003 * fbm(P * 120, 2, 1)), "#c9c6b2", gloss=150, feather=0.003)
    # thumb smudges on the red
    for p in ((0.02, 0.035, 0.03), (-0.03, 0.03, -0.015)):
        b.sub(Sphere(np.array(p) * 1.25 + c, 0.012), k=0.004)
    st = m.piece("stem", color="#f6f2ea", gloss=170, lumps=0.0, res=0.0012, decimate=1400)
    st.add(Cylinder(c + (0, r + 0.002, 0), 0.0045, 0.008, round=0.0015))
    st.add(Cylinder(c + (0, r + 0.0115, 0), 0.006, 0.0022, round=0.001), k=0.001)  # push button
    st.add(Torus(c + (0, r + 0.006, 0), 0.0049, 0.0011), k=0.0006, color="#a9adb3", gloss=220)  # spring wire
    wr = m.piece("wire", color="#b9bec4", gloss=230, lumps=0.0, res=0.0011, decimate=900)
    wr.add(Capsule(c + (0, -r + 0.003, 0), c + (0, -r - 0.012, 0), 0.0016), k=0.0005)
    wr.add(Torus(c + (0, -r - 0.017, 0), 0.0055, 0.0015, rot=(90, 0, 0)), k=0.0008)  # hook clip
    wr.add(Capsule(c + (0, r + 0.013, 0), c + (0, r + 0.019, 0), 0.0012), k=0.0004)
    wr.add(Torus(c + (0, r + 0.0225, 0), 0.0038, 0.0012, rot=(90, 0, 0)), k=0.0004)
    m.socket("line", None, tuple(c + (0, r + 0.026, 0)))
    m.socket("hook", None, tuple(c + (0, -r - 0.022, 0)))
    return m


# ==============================================================================================================
# sonar_screen — chunky fish-finder: slate housing, sun hood, round sweep display (emissive), buttons, gimbal bracket


def sonar_screen():
    m = Model("sonar_screen", res=0.003)
    CASE = "#3d4654"
    bw, bh, bd = 0.13, 0.095, 0.055
    bc = np.array([0, 0.085 + bh, 0])
    hs = m.piece("housing", color=CASE, gloss=80, lumps=0.0007, lump_freq=12, dents=10, dent_size=0.022, dent_depth=0.0012,
                 res=0.0026, decimate=4200)
    hs.add(Box(bc, (bw, bh, bd), round=0.025))
    hs.add(Box(bc + (0, 0.005, -bd * 0.75), (bw * 0.82, bh * 0.82, bd * 0.6), round=0.03), k=0.02)  # bulging back
    sc_c = bc + (-0.022, 0.006, bd)
    sw, sh = 0.083, 0.074
    hs.sub(Box(sc_c, (sw + 0.004, sh + 0.004, 0.02), round=0.012), k=0.004)  # screen well
    # sun hood
    hs.add(Box(bc + (-0.022, bh + 0.003, bd + 0.012), (bw * 0.86, 0.008, 0.026), rot=(-8, 0, 0), round=0.006), k=0.006)
    # buttons to the right of the screen
    for i, (col, y) in enumerate((("#d24a3a", 0.045), ("#e8c34a", 0.008), ("#7fae5a", -0.03))):
        hs.add(Cylinder(bc + (0.098, y, bd + 0.002), 0.0115, 0.006, rot=(90, 0, 0), round=0.004), k=0.003, color=col,
               gloss=150)
    hs.add(Box(bc + (0.098, -0.068, bd + 0.001), (0.016, 0.006, 0.004), round=0.003), k=0.003, color="#e9e3d2")  # brand plate
    hs.paint(Box(bc + (0.098, -0.068, bd + 0.003), (0.011, 0.0015, 0.004)), "#3d4654", feather=0.001)
    # cable gland and cable out of the back
    hs.add(Cylinder(bc + (0.05, -0.04, -bd * 1.25), 0.012, 0.02, rot=(90, 0, 0), round=0.004), k=0.004)
    hs.add(Tube([bc + (0.05, -0.04, -bd * 1.4), bc + (0.06, -0.08, -bd * 1.7), (0.07, 0.02, -bd * 1.9), (0.08, 0.008, -bd * 1.6)],
                0.007, samples=4), k=0.003, color="#25262b")
    grime(hs, "#262c36", r=0.01, thresh=0.05)
    # gimbal bracket: base plate + U arms + big knobs
    br = m.piece("bracket", color="#59606b", gloss=100, lumps=0.0007, lump_freq=12, dents=6, dent_size=0.015,
                 dent_depth=0.0012, res=0.0028, decimate=2400)
    br.add(Box((0, 0.008, 0), (0.1, 0.008, 0.06), round=0.006))
    br.add(Cylinder((0, 0.022, 0), 0.04, 0.012, round=0.006), k=0.006)  # swivel
    br.add(Box((0, 0.036, 0), (0.152, 0.007, 0.024), round=0.005), k=0.005)
    for s in (-1, 1):
        br.add(Box((s * 0.152, 0.11, 0), (0.007, 0.08, 0.024), round=0.005), k=0.006)
        br.add(Cylinder((s * 0.172, bc[1] - 0.005, 0), 0.026, 0.012, rot=(0, 0, 90), round=0.006), k=0.004, color="#2e3036",
               gloss=80)
        for i in range(8):  # knurled knob
            a = i * np.pi / 4
            br.sub(Capsule((s * 0.162, bc[1] - 0.005 + np.sin(a) * 0.027, np.cos(a) * 0.027),
                           (s * 0.182, bc[1] - 0.005 + np.sin(a) * 0.027, np.cos(a) * 0.027), 0.0035), k=0.002)
    for p in ((-0.075, 0.016, 0.04), (0.075, 0.016, 0.04), (-0.075, 0.016, -0.04), (0.075, 0.016, -0.04)):
        br.add(Cylinder(p, 0.0065, 0.002, round=0.0015), k=0.002, color="#a3a8ae", gloss=200)  # screws
    metal(br, dark="#30343b", r=0.008, tarnish=0.05)
    # the glowing display: dark sea-green glass, range rings, sweep wedge, pings (emissive)
    sp = m.piece("screen", color="#0c2f2a", gloss=255, mat=1, lumps=0.0, mottle=0.0, res=0.0041, decimate=99999, ao=False)
    sp.add(Box(sc_c + (0, 0, -0.006), (sw, sh, 0.0075), round=0.0065))
    cc = sc_c + (0, -0.004, 0)

    def rings(P):
        d = np.linalg.norm((P - cc)[:, :2], axis=1)
        q = np.min(np.abs(d[:, None] - np.array([0.022, 0.044, 0.066])[None]), axis=1)
        cross = np.minimum(np.abs(P[:, 0] - cc[0]), np.abs(P[:, 1] - cc[1]))
        return np.minimum(q, cross) - 0.0024
    sp.paint(Func(rings, cc - 0.1, cc + 0.1), "#2f8a6c", feather=0.001)

    def sweep(P):
        v = (P - cc)[:, :2]
        ang = np.arctan2(v[:, 1], v[:, 0])
        d = np.linalg.norm(v, axis=1)
        wedge = np.abs(((ang - 0.9) + np.pi) % (2 * np.pi) - np.pi) - 0.5
        return np.maximum(wedge * 0.03, d - 0.07)
    sp.paint(Func(sweep, cc - 0.1, cc + 0.1), "#3fcf8f", feather=0.004)

    def beam(P):
        v = (P - cc)[:, :2]
        ang = np.arctan2(v[:, 1], v[:, 0])
        d = np.linalg.norm(v, axis=1)
        return np.maximum(np.abs(((ang - 1.38) + np.pi) % (2 * np.pi) - np.pi) * d - 0.0026, d - 0.07)
    sp.paint(Func(beam, cc - 0.1, cc + 0.1), "#b9ffd9", feather=0.001)
    sp.paint(spots_prim([cc + (0.03, 0.035, 0), cc + (-0.035, 0.022, 0), cc + (0.012, -0.045, 0)], [0.0075, 0.0055, 0.006]),
             "#ffd45c", feather=0.001)
    sp.paint(Sphere(cc + (0.03, 0.035, 0), 0.0035), "#fff3c2", feather=0.001)
    sp.paint(Sphere(cc, 0.004), "#b9ffd9", feather=0.001)
    # bottom contour strip along the lower edge of the display
    sp.paint(func_prim(lambda P: P[:, 1] - (cc[1] - 0.062 + 0.006 * np.sin((P[:, 0] - cc[0]) * 90))), "#d9733a",
             feather=0.0015)
    m.socket("face", None, tuple(sc_c + (0, 0, 0.004)))
    return m


MODELS = {
    "boat/crab_pot": crab_pot,
    "boat/buoy": buoy,
    "boat/dredge": dredge,
    "boat/mallet": mallet,
    "boat/rod": rod,
    "boat/bobber": bobber,
    "boat/sonar_screen": sonar_screen,
}
