"""
The Saltmoss Harbor logo, sculpted: each letter of the title becomes a chunky, rounded, hand-pressed slab of
plasticine (font outline -> 2D distance field -> rounded 3D extrusion with lumps and thumb dents), mixed colours
like a real clay title card, then rendered in Blender with a transparent background.

  Tools/.venv/bin/python Tools/art/logo.py          -> Docs/media/logo.png, Game/Assets/Saltmoss/Art/UI/logo.png,
                                                       Tools/art/out/logo.claymesh
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt, map_coordinates

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "Tools/clay"))
from clay import Model, Func, Sphere, Tube, rgb  # noqa: E402

FONT = os.path.join(ROOT, "Game/Assets/Saltmoss/Art/Fonts/LilitaOne-Regular.ttf")
OUT = os.path.join(ROOT, "Tools/art/out")
PX = 400  # raster pixels per metre (letters are ~0.3 m tall)


def glyph_field(ch, size_m, font_px=420):
    """Signed distance (metres, negative inside) of one glyph, plus its width."""
    font = ImageFont.truetype(FONT, font_px)
    bbox = font.getbbox(ch)
    pad = 60
    w, h = bbox[2] - bbox[0] + pad * 2, font_px + pad * 2
    img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(img).text((pad - bbox[0], pad), ch, font=font, fill=255)
    a = np.asarray(img, float) > 127
    inside = distance_transform_edt(a)
    outside = distance_transform_edt(~a)
    sd = (outside - inside)  # pixels
    scale = size_m / font_px
    return sd * scale, scale, w, h, bbox, pad


def letter_sdf(ch, origin, size_m, thick, roundness, seed, tilt=0.0, lift=0.0):
    sd, scale, w, h, bbox, pad = glyph_field(ch, size_m)
    ox, oy = origin
    oy += lift
    cx, cy = ox + w * scale * 0.5, oy + size_m * 0.55
    ca, sa = np.cos(np.radians(tilt)), np.sin(np.radians(tilt))

    def f(P):
        # hand-placed: each letter sits at its own little angle
        X = cx + (P[:, 0] - cx) * ca + (P[:, 1] - cy) * sa
        Y = cy - (P[:, 0] - cx) * sa + (P[:, 1] - cy) * ca
        # glyph plane: x right, y up; raster row 0 is the top
        u = (X - ox) / scale
        v = (oy + size_m * 1.2 - Y) / scale
        d2 = map_coordinates(sd, [v, u], order=1, mode="nearest")
        # outside the raster: far away
        out = (u < 0) | (u > w - 1) | (v < 0) | (v > h - 1)
        d2 = np.where(out, 0.5, d2)
        # rounded extrusion: pillow-like slab, edges rolled over like pressed clay
        dz = np.abs(P[:, 2]) - thick
        r = roundness
        q = np.stack([np.maximum(d2 + r, 0), np.maximum(dz + r, 0)], axis=1)
        return np.linalg.norm(q, axis=1) + np.minimum(np.maximum(d2 + r, dz + r), 0) - r

    lo = np.array([ox - 0.02, oy - size_m * 0.4, -thick - 0.03])
    hi = np.array([ox + w * scale + 0.02, oy + size_m * 1.3, thick + 0.03])
    adv = (bbox[2] - bbox[0]) * scale
    return Func(f, lo, hi), adv


def build():
    m = Model("logo", res=0.0035)
    m.decimate_ratio = 0.35
    colours_top = ["#d99a1e", "#c2412a", "#2f7f7b", "#ece0c2", "#d99a1e", "#c2412a", "#2f7f7b", "#ece0c2"]
    rng = np.random.default_rng(5)
    x = 0.0
    size, gap = 0.30, 0.012
    for i, ch in enumerate("Saltmoss"):
        prim, adv = letter_sdf(ch, (x, 0.0), size, 0.035, 0.022, i, tilt=rng.uniform(-6, 6), lift=rng.uniform(-0.012, 0.012))
        p = m.piece(f"top_{i}", color=colours_top[i % len(colours_top)], gloss=60, lumps=0.0022, lump_freq=14.0,
                    dents=10, dent_size=0.018, dent_depth=0.0025, mottle=0.07, res=0.0035)
        p.add(prim)
        # each letter is pressed at a slightly different angle, like hand-placed clay
        x += adv + gap
    top_w = x
    x = top_w * 0.5 - 0.0
    # second line, smaller, centred
    word = "HARBOR"
    size2 = 0.17
    widths = []
    for ch in word:
        _, adv = letter_sdf(ch, (0, 0), size2, 0.03, 0.017, 0)
        widths.append(adv)
    total = sum(widths) + gap * (len(word) - 1)
    x = (top_w - total) / 2
    for i, ch in enumerate(word):
        prim, adv = letter_sdf(ch, (x, -0.24), size2, 0.03, 0.017, 20 + i, tilt=rng.uniform(-4, 4), lift=rng.uniform(-0.008, 0.008))
        p = m.piece(f"bot_{i}", color="#24395a", gloss=70, lumps=0.0018, lump_freq=16.0, dents=6, dent_size=0.014, dent_depth=0.002, mottle=0.06, res=0.003)
        p.add(prim)
        x += adv + gap
    # a little rope squiggle under the top line and two sea-foam dots, all clay
    rope = m.piece("rope", color="#c9a46a", gloss=40, lumps=0.0015, res=0.003)
    pts = [(-0.02, -0.05, 0.0)] + [(t * top_w, -0.05 + 0.012 * np.sin(t * 18), 0.0) for t in np.linspace(0.05, 0.95, 9)] + [(top_w + 0.02, -0.05, 0.0)]
    rope.add(Tube(pts, 0.011, samples=5))
    for k, xx in enumerate([-0.06, top_w + 0.06]):
        d = m.piece(f"dot_{k}", color="#efe9dc", gloss=80, lumps=0.001, res=0.003)
        d.add(Sphere((xx, -0.05, 0.0), 0.024))
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    m = build()
    path = os.path.join(OUT, "logo.claymesh")
    m.save(path)
    # render: front, slightly from below the key light, transparent
    script = os.path.join(ROOT, "Tools/art/logo_render.py")
    png = os.path.join(OUT, "logo_render.png")
    r = subprocess.run(["blender", "-b", "--factory-startup", "--python", script, "--", path, png], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(png):
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit("render failed")
    im = Image.open(png).convert("RGBA")
    bbox = im.getbbox()
    im = im.crop((max(0, bbox[0] - 30), max(0, bbox[1] - 30), min(im.width, bbox[2] + 30), min(im.height, bbox[3] + 30)))
    # soft contact shadow so the clay letters read over a bright sky or a white page
    from PIL import ImageFilter
    pad = 40
    canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    a = im.split()[3]
    sh = Image.new("RGBA", canvas.size, (28, 22, 18, 0))
    shadow_a = Image.new("L", canvas.size, 0)
    shadow_a.paste(a, (pad + 8, pad + 14))
    shadow_a = shadow_a.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.55))
    sh.putalpha(shadow_a)
    canvas.alpha_composite(sh)
    canvas.alpha_composite(im, (pad, pad))
    im = canvas
    im.save(os.path.join(ROOT, "Docs/media/logo.png"))
    ui = im.copy()
    ui.thumbnail((1400, 700), Image.LANCZOS)
    ui.save(os.path.join(ROOT, "Game/Assets/Saltmoss/Art/UI/logo.png"))
    print("[logo]", im.size)


if __name__ == "__main__":
    main()
