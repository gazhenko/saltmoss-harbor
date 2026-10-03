"""Pip — a young Atlantic puffin skipper. Yellow sou'wester, red knitted scarf, big orange feet. 0.9 m with hat."""
import numpy as np
from clay import *
from kit import *
from kit_chars import pupil_pivots

OUT = "chars/pip"


def build():
    m = Model("pip", res=0.007)
    BLACK, FACE = "#25272d", "#ece6d8"
    BEAK_O, BEAK_Y, BEAK_B = "#e2562b", "#f0b532", "#7f8a97"
    FOOT = "#ec7a2c"
    HAT, SCARF = "#f2c12e", "#c23a2e"

    biped_rig(m, hip_y=0.2, chest_y=0.42, neck_y=0.53, head_y=0.62, shoulder_x=0.17, shoulder_y=0.46, hand_y=0.25,
              hip_x=0.085, knee_y=0.1, foot_y=0.035, foot_z=0.03, elbow_out=0.05, head_z=0.02,
              tail=((0, 0.22, -0.17), (0, 0.19, -0.24)))
    eye_c = (0.078, 0.665, 0.13)
    face_bones(m, eye_c, 0.042, jaw_c=(0, 0.6, 0.15), mouth_c=(0, 0.58, 0.2), hat_c=(0, 0.75, 0.0))

    # body + head: one lump of black clay, white belly and face pressed in (painted), black collar left between
    body = m.piece("body", color=BLACK, bone="chest", lumps=0.005, dents=22, dent_size=0.03, dent_depth=0.0035)
    body.add(Ellipsoid((0, 0.34, -0.01), (0.215, 0.25, 0.2)), bone="spine")
    body.add(Ellipsoid((0, 0.43, 0.02), (0.19, 0.17, 0.18)), k=0.08, bone="chest")
    body.add(Ellipsoid((0, 0.62, 0.025), (0.16, 0.155, 0.155)), k=0.09, bone="head")
    body.add(Ellipsoid((0, 0.2, -0.01), (0.17, 0.11, 0.16)), k=0.06, bone="hips")
    body.add(Ellipsoid((0, 0.2, -0.205), (0.075, 0.022, 0.075), rot=(-30, 0, 0)), k=0.035, bone="tail")
    # white belly
    body.paint(Ellipsoid((0, 0.3, 0.1), (0.17, 0.2, 0.17)), "#f1ece2")
    # face mask: pale grey-white disc on each side of the head, joined under the beak
    body.paint(Ellipsoid((0, 0.62, 0.11), (0.15, 0.085, 0.11)), FACE)
    body.paint(Ellipsoid((0, 0.585, 0.12), (0.12, 0.06, 0.08)), FACE)
    # black cap/collar re-asserted on top and back of head and throat band
    body.paint(Ellipsoid((0, 0.74, -0.02), (0.17, 0.08, 0.16)), BLACK)
    body.paint(Box((0, 0.515, 0.13), (0.14, 0.022, 0.06), round=0.02), BLACK, feather=0.008)
    # grey eye markings (the puffin "eye shadow" triangles)
    for sx in (-1, 1):
        body.paint(Ellipsoid((sx * 0.1, 0.69, 0.1), (0.02, 0.012, 0.01)), "#7d7f86")

    # beak: upper mandible on the head, lower on the jaw; base plate grey-blue, yellow ridge, orange-red tip
    beak = m.piece("beak", color=BEAK_O, gloss=110, bone="head", lumps=0.0015, dents=4, dent_size=0.015, dent_depth=0.0015)
    # deep, laterally flattened triangle: tall at the face, curving down to a hooked tip
    beak.add(Ellipsoid((0, 0.625, 0.175), (0.034, 0.08, 0.06), rot=(10, 0, 0)), bone="head")
    beak.add(Ellipsoid((0, 0.62, 0.23), (0.028, 0.06, 0.06), rot=(28, 0, 0)), k=0.035, bone="head")
    beak.add(Ellipsoid((0, 0.598, 0.272), (0.02, 0.03, 0.03), rot=(40, 0, 0)), k=0.025, bone="head")
    beak.add(Ellipsoid((0, 0.555, 0.19), (0.03, 0.04, 0.065), rot=(-14, 0, 0)), k=0.015, bone="jaw")
    beak.sub(Box((0, 0.585, 0.235), (0.05, 0.0035, 0.075), rot=(-12, 0, 0)), k=0.003)
    beak.paint(Ellipsoid((0, 0.63, 0.14), (0.05, 0.1, 0.03)), BEAK_B)
    beak.paint(Box((0, 0.635, 0.183), (0.05, 0.1, 0.009), rot=(12, 0, 0), round=0.004), BEAK_Y, feather=0.003)
    beak.paint(Box((0, 0.665, 0.2), (0.05, 0.03, 0.03), rot=(30, 0, 0), round=0.004), BEAK_Y, feather=0.003)  # ridge
    beak.paint(Box((0, 0.56, 0.16), (0.05, 0.03, 0.012), round=0.004), BEAK_Y, feather=0.003)

    eyes(m, eye_c, 0.04, lid_color=FACE, look=(0, 0.02, 1), ring="#e0683a", toe_in=4)
    pupil_pivots(m, eye_c, 0.04, look=(0, 0.02, 1), toe_in=4)   # runtime pupil scale dilates in place
    brows(m, eye_c, 0.04, color=BLACK, length=1.6, thick=0.2, lift=1.3, tilt=10)
    blush(m, (0.115, 0.6, 0.12), 0.025, normal=(0.7, 0, 0.7))

    # wings (arms): flat black flippers pressed onto the sides
    for sx, s in ((-1, "L"), (1, "R")):
        w = m.piece(f"wing_{s}", color=BLACK, bone=f"elbow_{s}", lumps=0.003, dents=4, dent_size=0.02)
        w.add(Ellipsoid((sx * 0.185, 0.42, -0.01), (0.04, 0.085, 0.1), rot=(0, 0, sx * -12)), bone=f"arm_{s}")
        w.add(Ellipsoid((sx * 0.215, 0.33, -0.02), (0.032, 0.08, 0.08), rot=(0, 0, sx * -8)), k=0.04, bone=f"elbow_{s}")
        w.add(Ellipsoid((sx * 0.225, 0.25, -0.03), (0.024, 0.055, 0.05), rot=(0, 0, sx * -4)), k=0.04, bone=f"hand_{s}")
        w.paint(Ellipsoid((sx * 0.2, 0.3, 0.06), (0.04, 0.1, 0.02)), "#33363d")

    # legs and big webbed feet
    for sx, s in ((-1, "L"), (1, "R")):
        lg = m.piece(f"leg_{s}", color=FOOT, gloss=60, bone=f"knee_{s}", lumps=0.0015)
        lg.add(Capsule((sx * 0.085, 0.16, 0.0), (sx * 0.085, 0.09, 0.01), 0.032, 0.026), bone=f"leg_{s}")
        lg.add(Capsule((sx * 0.085, 0.09, 0.01), (sx * 0.085, 0.035, 0.03), 0.026, 0.022), k=0.02, bone=f"knee_{s}")
        ft = m.piece(f"foot_{s}", color=FOOT, gloss=60, rigid=f"foot_{s}", lumps=0.0015, dents=3, dent_size=0.015)
        base = np.array([sx * 0.085, 0.018, 0.07])
        ft.add(Ellipsoid(base + (0, 0, -0.02), (0.045, 0.02, 0.05)))
        for t in (-1, 0, 1):
            tip = base + np.array([t * 0.045, -0.004, 0.08 - abs(t) * 0.012])
            ft.add(Capsule(base + (0, 0, -0.01), tip, 0.016, 0.011), k=0.02)
        # webbing between toes, pressed flat
        ft.add(Ellipsoid(base + (0, -0.005, 0.045), (0.06, 0.009, 0.045)), k=0.015)

    # knitted scarf: a fat ring round the neck with a dangling end; knit ribs pressed in with a tool
    sc = m.piece("scarf", color=SCARF, bone="neck", lumps=0.002, dents=6, dent_size=0.015, dent_depth=0.002)
    sc.add(Torus((0, 0.52, 0.02), 0.158, 0.042, rot=(10, 0, 0)), bone="neck")
    sc.add(Tube([(0.09, 0.505, 0.15), (0.13, 0.44, 0.19), (0.135, 0.37, 0.19), (0.13, 0.3, 0.175)], [0.036, 0.033, 0.031, 0.03], samples=6), k=0.025, bone="chest")
    sc.add(Ellipsoid((0.075, 0.5, 0.17), (0.045, 0.04, 0.03)), k=0.02, bone="neck")  # the knot
    for i in range(22):
        a = i / 22 * 2 * np.pi
        sc.sub(Capsule((np.sin(a) * 0.205, 0.47, 0.02 + np.cos(a) * 0.205), (np.sin(a) * 0.205, 0.575, 0.02 + np.cos(a) * 0.205), 0.0055), k=0.004)
    for y in (0.42, 0.37, 0.32):
        sc.paint(Box((0.13, y, 0.18), (0.06, 0.007, 0.06)), "#8f241d", feather=0.003)
    sc.paint(Box((0.13, 0.285, 0.17), (0.06, 0.014, 0.06)), "#ead9b0", feather=0.003)  # cream fringe stripe

    # sou'wester: domed crown, broad brim swooping low at the back, glossy oilskin
    hat = m.piece("hat", color=HAT, gloss=150, rigid="hat", lumps=0.0025, dents=8, dent_size=0.025, dent_depth=0.003)
    hat.add(Ellipsoid((0, 0.77, -0.01), (0.14, 0.09, 0.14)))
    # brim: short and turned up at the front, long and drooping over the neck at the back
    hat.add(Ellipsoid((0, 0.715, -0.07), (0.215, 0.026, 0.27), rot=(-24, 0, 0)), k=0.045)
    hat.add(Ellipsoid((0, 0.74, 0.07), (0.19, 0.02, 0.12), rot=(-14, 0, 0)), k=0.04)
    hat.sub(Ellipsoid((0, 0.67, -0.0), (0.15, 0.085, 0.15)), k=0.01)
    hat.add(Torus((0, 0.745, -0.01), 0.135, 0.012, rot=(-6, 0, 0)), k=0.008)  # seam band
    for a in range(0, 360, 45):
        r = np.radians(a)
        hat.sub(Sphere((np.sin(r) * 0.07, 0.835, -0.01 + np.cos(r) * 0.07), 0.006), k=0.003)  # stitched panels

    m.socket("prop_R", "hand_R", (0.24, 0.22, 0.0))
    m.socket("bust", "head", (0, 0.63, 0.06))
    m.socket("talk", "head", (0, 0.98, 0))
    return m
