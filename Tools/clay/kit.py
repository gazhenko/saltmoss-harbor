"""
Shared sculpting helpers for critters: stop-motion faces (eyes, replacement eyelids, brows, blush, mouths),
the standard biped rig and colour palette. All characters use these so the dialogue/expression system can drive any
of them the same way (Docs/DESIGN.md §5.3).
"""
import numpy as np
from clay import *

# shared palette (sRGB) — slightly dusty, saturated plasticine
PAL = dict(
    black="#24262b", white="#efe9dc", cream="#e8dcc0", grey="#8c8f95", pink="#e79a9c", blush="#ef8f8f",
    eye_white="#f4f1ea", pupil="#121214", red="#c7352c", orange="#e8742a", yellow="#f2c230", navy="#26345a",
    brass="#c99a3b", brown="#7a5236", tan="#c49a6c", teal="#3f8a87", sea="#3d6f86", rust="#a2532c",
)


def biped_rig(m: Model, hip_y, chest_y, neck_y, head_y, shoulder_x, shoulder_y, hand_y, hip_x, knee_y, foot_y,
              foot_z=0.03, elbow_out=0.04, head_z=0.0, tail=None):
    """Standard bone chain. Positions are rest-pose joint locations (feet at origin, facing +Z)."""
    m.bone("root")
    m.bone("hips", "root", (0, hip_y, 0))
    m.bone("spine", "hips", (0, (hip_y + chest_y) / 2, 0))
    m.bone("chest", "spine", (0, chest_y, 0))
    m.bone("neck", "chest", (0, neck_y, head_z * 0.5))
    m.bone("head", "neck", (0, head_y, head_z))
    for sx, s in ((-1, "L"), (1, "R")):
        m.bone(f"arm_{s}", "chest", (sx * shoulder_x, shoulder_y, 0))
        ey = (shoulder_y + hand_y) / 2
        m.bone(f"elbow_{s}", f"arm_{s}", (sx * (shoulder_x + elbow_out), ey, 0))
        m.bone(f"hand_{s}", f"elbow_{s}", (sx * (shoulder_x + elbow_out * 1.3), hand_y, 0.0))
        m.bone(f"leg_{s}", "hips", (sx * hip_x, hip_y * 0.85, 0))
        m.bone(f"knee_{s}", f"leg_{s}", (sx * hip_x, knee_y, 0.01))
        m.bone(f"foot_{s}", f"knee_{s}", (sx * hip_x, foot_y, foot_z))
    if tail:
        m.bone("tail", "hips", tail[0])
        m.bone("tail2", "tail", tail[1])


def face_bones(m: Model, eye_c, eye_r, brow_up=1.25, mouth_c=None, jaw_c=None, hat_c=None):
    """eye_c: the RIGHT eye centre (x > 0). Creates eye/pupil/brow (+mouth/jaw/hat) bones under head."""
    ex, ey, ez = eye_c
    for sx, s in ((-1, "L"), (1, "R")):
        m.bone(f"eye_{s}", "head", (sx * ex, ey, ez))
        m.bone(f"pupil_{s}", f"eye_{s}", (sx * ex, ey, ez))
        m.bone(f"brow_{s}", "head", (sx * ex, ey + eye_r * brow_up, ez + eye_r * 0.2))
    if jaw_c is not None:
        m.bone("jaw", "head", jaw_c)
    if mouth_c is not None:
        m.bone("mouth", "jaw" if jaw_c is not None else "head", mouth_c)
    if hat_c is not None:
        m.bone("hat", "head", hat_c)


def _dir(look):
    d = np.asarray(look, float)
    return d / np.linalg.norm(d)


def eyes(m: Model, eye_c, r, lid_color, look=(0, 0, 1), pupil_frac=0.55, ring=None, toe_in=12.0, sclera=PAL["eye_white"],
         pupil=PAL["pupil"], lash=PAL["black"], pupil_res=0.004):
    """Bead eyes: sclera ball + glossy pupil with catch-light + replacement lids/happy arcs (hidden).
    eye_c is the RIGHT eye centre (x>0); left is mirrored. Eyes look along `look`, toed in slightly."""
    ex, ey, ez = eye_c
    for sx, s in ((-1, "L"), (1, "R")):
        c = np.array([sx * ex, ey, ez])
        ang = np.radians(toe_in) * sx * -1
        d = _dir(look)
        d = np.array([d[0] * np.cos(ang) + d[2] * np.sin(ang), d[1], -d[0] * np.sin(ang) + d[2] * np.cos(ang)])
        ball = m.piece(f"eyeball_{s}", color=sclera, gloss=150, rigid=f"eye_{s}", lumps=0.0006, mottle=0.02, res=pupil_res)
        ball.add(Sphere(c, r))
        if ring is not None:
            ball.add(Torus(c + d * r * 0.25, r * 0.98, r * 0.12, rot=look_rot(d)), k=0.004, color=ring)
        pr = r * pupil_frac
        pc = c + d * (r - pr * 0.45)
        pu = m.piece(f"pupil_{s}", color=pupil, gloss=235, rigid=f"pupil_{s}", lumps=0.0, mottle=0.0, res=pupil_res, ao=False)
        pu.add(Ellipsoid(pc, (pr, pr * 1.08, pr * 0.55), rot=look_rot(d) @ euler((90, 0, 0))))
        # catch-light: a tiny bead of white clay, upper outer
        up = np.array([0, 1, 0])
        side = np.cross(up, d)
        hl = pc + d * pr * 0.42 + up * pr * 0.42 + side * pr * 0.3 * sx
        pu.add(Sphere(hl, pr * 0.24), k=0.002, color="#ffffff", gloss=255)
        # replacement lids
        lh = m.piece(f"lidhalf_{s}", color=lid_color, gloss=40, rigid=f"eye_{s}", hidden=True, lumps=0.0006, res=pupil_res)
        lh.add(Sphere(c, r * 1.12)).inter(HalfSpace(c + np.array([0, r * 0.12, 0]), (0, -1, 0)), 0.004)
        lh.sub(Sphere(c, r * 1.0), 0.002)
        lh.add(Tube([c + np.array([-r * 1.05, r * 0.1, r * 0.25]), c + np.array([0, r * 0.18, r * 1.08]), c + np.array([r * 1.05, r * 0.1, r * 0.25])],
                    r * 0.11, samples=6), k=0.003, color=lash)
        lc = m.piece(f"lidclosed_{s}", color=lid_color, gloss=40, rigid=f"eye_{s}", hidden=True, lumps=0.0006, res=pupil_res)
        lc.add(Sphere(c, r * 1.1))
        lc.add(Tube([c + np.array([-r * 1.02, -r * 0.05, r * 0.38]), c + np.array([0, -r * 0.18, r * 1.1]), c + np.array([r * 1.02, -r * 0.05, r * 0.38])],
                    r * 0.1, samples=6), k=0.002, color=lash)
        ha = m.piece(f"eyehappy_{s}", color=lash, gloss=60, rigid=f"eye_{s}", hidden=True, lumps=0.0, res=pupil_res)
        ha.add(Tube([c + np.array([-r * 0.85, -r * 0.1, r * 0.75]), c + np.array([0, r * 0.45, r * 1.02]), c + np.array([r * 0.85, -r * 0.1, r * 0.75])],
                    r * 0.16, samples=8))


def brows(m: Model, eye_c, r, color, length=1.5, thick=0.2, lift=1.25, tilt=8.0, forward=0.35):
    ex, ey, ez = eye_c
    for sx, s in ((-1, "L"), (1, "R")):
        c = np.array([sx * ex, ey + r * lift, ez + r * forward])
        a = c + np.array([-sx * r * length * 0.45, -r * 0.05 + r * np.sin(np.radians(tilt)) * 0.3, 0])
        b = c + np.array([sx * r * length * 0.5, -r * np.sin(np.radians(tilt)) * 0.6, -r * 0.18])
        mid = (a + b) / 2 + np.array([0, r * 0.12, r * 0.06])
        br = m.piece(f"brow_{s}", color=color, gloss=50, rigid=f"brow_{s}", lumps=0.0008, res=0.004)
        br.add(Tube([a, mid, b], [r * thick, r * thick * 1.1, r * thick * 0.75], samples=6))


def blush(m: Model, c_right, r, color=PAL["blush"], normal=(0.5, 0, 1)):
    n = _dir(normal)
    for sx, s in ((-1, "L"), (1, "R")):
        c = np.array([sx * c_right[0], c_right[1], c_right[2]])
        nn = np.array([sx * n[0], n[1], n[2]])
        b = m.piece(f"blush_{s}", color=color, gloss=30, rigid="head", hidden=True, lumps=0.0, mottle=0.03, res=0.004, ao=False)
        b.add(Ellipsoid(c, (r, r * 0.7, r * 0.18), rot=look_rot(nn) @ euler((90, 0, 0))))


def mouths(m: Model, c, w, lip, inner="#5a1f24", tongue="#d7676b", bone="mouth", normal=(0, 0, 1), visible="mouth_neutral", lip_r=None):
    """Replacement mouths pressed onto the face at c (a surface point), width w."""
    n = _dir(normal)
    up = np.array([0.0, 1.0, 0.0])
    x = np.cross(up, n)
    x /= np.linalg.norm(x)
    lr = lip_r or w * 0.09

    def P(u, v, d=0.0):
        return c + x * u * w * 0.5 + up * v * w * 0.5 + n * d * w

    def piece(name):
        return m.piece(name, color=lip, gloss=70, rigid=bone, hidden=(name != visible), lumps=0.0, mottle=0.03, res=0.004, ao=False)

    piece("mouth_neutral").add(Tube([P(-0.8, 0.05), P(0, -0.05, 0.03), P(0.8, 0.05)], lr, samples=6))
    piece("mouth_smile").add(Tube([P(-0.95, 0.3), P(-0.5, -0.15, 0.03), P(0, -0.3, 0.05), P(0.5, -0.15, 0.03), P(0.95, 0.3)], lr, samples=5))
    piece("mouth_frown").add(Tube([P(-0.85, -0.3), P(-0.4, 0.05, 0.03), P(0, 0.12, 0.05), P(0.4, 0.05, 0.03), P(0.85, -0.3)], lr, samples=5))
    piece("mouth_wavy").add(Tube([P(-0.85, 0), P(-0.45, 0.14, 0.03), P(0, -0.08, 0.05), P(0.45, 0.14, 0.03), P(0.85, 0)], lr, samples=5))
    op = piece("mouth_open")
    op.add(Ellipsoid(P(0, -0.25, 0.0), (w * 0.42, w * 0.34, w * 0.12), rot=look_rot(n) @ euler((90, 0, 0))), color=inner, gloss=120)
    op.add(Ellipsoid(P(0, -0.45, 0.05), (w * 0.24, w * 0.12, w * 0.06), rot=look_rot(n) @ euler((90, 0, 0))), k=0.004, color=tongue, gloss=160)
    op.add(Torus(P(0, -0.25, 0.03), w * 0.42, lr * 0.9, rot=look_rot(n) @ euler((0, 0, 0))), k=0.003, color=lip)
    o = piece("mouth_o")
    o.add(Ellipsoid(P(0, -0.15, 0.0), (w * 0.2, w * 0.24, w * 0.1), rot=look_rot(n) @ euler((90, 0, 0))), color=inner, gloss=120)
    o.add(Torus(P(0, -0.15, 0.03), w * 0.21, lr * 0.95, rot=look_rot(n)), k=0.003, color=lip)
    g = piece("mouth_grin")
    g.add(Ellipsoid(P(0, -0.15, 0.0), (w * 0.5, w * 0.22, w * 0.1), rot=look_rot(n) @ euler((90, 0, 0))), color=inner, gloss=120)
    g.add(Box(P(0, -0.02, 0.06), (w * 0.38, w * 0.07, w * 0.04), rot=look_rot(n) @ euler((90, 0, 0)), round=w * 0.03), k=0.002, color="#f6f2e8", gloss=200)
    g.add(Tube([P(-1.0, 0.25), P(-0.5, -0.32, 0.03), P(0, -0.42, 0.05), P(0.5, -0.32, 0.03), P(1.0, 0.25)], lr, samples=5), k=0.003, color=lip)
