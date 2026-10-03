"""
Clay UI sprites: every panel, button and icon is a little slab of plasticine, rendered from a height field
(rounded bevel, hand-pressed lumps, fingerprints) with a key light and a soft contact shadow.

  Tools/.venv/bin/python Tools/art/ui_sprites.py

Writes Game/Assets/Saltmoss/Art/UI/*.png and ui_sprites.json (9-slice borders, read by the Unity importer rules).
"""
import json
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Art/UI")
rng = np.random.default_rng(7)
BORDERS = {}


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255.0


def noise(w, h, cells, seed, octaves=3):
    r = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = cells * 2 ** o
        lat = r.uniform(-1, 1, (c + 2, c + 2))
        img = Image.fromarray(((lat * 0.5 + 0.5) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += (np.asarray(img, float) / 255.0 * 2 - 1) * amp
        tot += amp
        amp *= 0.5
    return out / tot


def fingerprints(w, h, n, seed, scale=1.0):
    r = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(float)
    out = np.zeros((h, w))
    for k in range(n):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        rx = r.uniform(18, 34) * scale
        ry = rx * r.uniform(1.2, 1.5)
        a = r.uniform(0, math.pi)
        dx, dy = x - cx, y - cy
        u = (dx * math.cos(a) + dy * math.sin(a)) / rx
        v = (-dx * math.sin(a) + dy * math.cos(a)) / ry
        rr = np.sqrt(u * u + v * v)
        th = np.arctan2(v, u)
        rid = np.sin(2 * math.pi * (rr / 0.075 + th / (2 * math.pi)))
        out += rid * np.clip(1 - rr, 0, 1) ** 1.2 * r.uniform(0.3, 1.0)
    return out


def rounded_mask(w, h, rad, inset, wobble, seed):
    """Signed distance (px, negative inside) to a wobbly rounded rectangle."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    hx, hy = w / 2 - inset - rad, h / 2 - inset - rad
    qx = np.abs(x - cx) - hx
    qy = np.abs(y - cy) - hy
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - rad
    d += noise(w, h, 5, seed, 3) * wobble
    return d


def shade(height, base, alpha, gloss=0.25, light=(-0.55, -0.65, 0.75), shadow=True, shadow_off=(5, 8), shadow_blur=8, rim=0.0):
    """Light a height field (pixels) into RGBA with a drop shadow."""
    gy, gx = np.gradient(height)
    n = np.stack([-gx, -gy, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array(light, float)
    L /= np.linalg.norm(L)
    ndl = np.clip((n @ L), 0, 1)
    wrap = np.clip((n @ L + 0.35) / 1.35, 0, 1)
    V = np.array([0, 0, 1.0])
    Hh = (L + V) / np.linalg.norm(L + V)
    spec = np.clip(n @ Hh, 0, 1) ** 28 * gloss
    amb = 0.55 + 0.25 * n[..., 2]
    col = base * (amb[..., None] * 0.55 + wrap[..., None] * 0.6) + spec[..., None]
    col += np.clip(1 - n[..., 2], 0, 1)[..., None] * rim
    col = np.clip(col, 0, 1)
    h, w = height.shape
    out = np.zeros((h, w, 4))
    if shadow:
        sa = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(shadow_blur))
        sa = np.asarray(sa, float) / 255.0
        sa = np.roll(np.roll(sa, shadow_off[1], axis=0), shadow_off[0], axis=1) * 0.42
        out[..., 3] = sa
        out[..., :3] = np.array([0.12, 0.09, 0.08])
    a = alpha[..., None]
    out[..., :3] = out[..., :3] * (1 - a) + col * a
    out[..., 3] = out[..., 3] * (1 - alpha) + alpha
    return out


def slab(name, w, h, color, rad=40, border=None, wobble=3.0, prints=6, thickness=14.0, gloss=0.22, seed=0, inset=14):
    d = rounded_mask(w, h, rad, inset, wobble, seed)
    alpha = np.clip(0.5 - d, 0, 1)
    # bevel: rises over `thickness` px from the edge, then a gently lumpy top
    inner = np.clip(-d / thickness, 0, 1)
    height = (1 - (1 - inner) ** 2.2) * thickness
    height += noise(w, h, 4, seed + 1, 3) * 2.2 * inner
    height += fingerprints(w, h, prints, seed + 2) * 0.7 * inner
    height += noise(w, h, 40, seed + 3, 2) * 0.25
    base = hexc(color)
    base = base * (1 + noise(w, h, 9, seed + 4, 2)[..., None] * 0.035)
    img = shade(height, base, alpha, gloss=gloss)
    save(name, img, border if border is not None else rad + inset + 6)


def circle_icon(name, size, color, inner=None, seed=0, thickness=10.0):
    d = rounded_mask(size, size, size * 0.5 - 12, 12, 1.5, seed)
    alpha = np.clip(0.5 - d, 0, 1)
    inn = np.clip(-d / thickness, 0, 1)
    height = (1 - (1 - inn) ** 2) * thickness + noise(size, size, 4, seed + 1) * 1.2 * inn + fingerprints(size, size, 2, seed + 2, 0.7) * 0.5 * inn
    base = np.tile(hexc(color), (size, size, 1))
    if inner is not None:
        height, base = inner(height, base, size)
    img = shade(height, base, alpha, gloss=0.3, shadow_off=(3, 5), shadow_blur=5)
    save(name, img, 0)


def save(name, rgba, border):
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(OUT, name + ".png"))
    BORDERS[name] = int(border)


def sand_dollar(height, base, size):
    """Sand dollar coin: five-petal pattern pressed in."""
    y, x = np.mgrid[0:size, 0:size].astype(float)
    c = (size - 1) / 2
    dx, dy = (x - c) / size, (y - c) / size
    r = np.sqrt(dx * dx + dy * dy)
    th = np.arctan2(dy, dx)
    petals = np.clip(np.cos(5 * th) * 0.5 + 0.5, 0, 1) ** 3 * np.exp(-((r - 0.17) / 0.07) ** 2)
    height = height - petals * 4.0
    holes = np.exp(-((r - 0.33) / 0.025) ** 2) * (np.cos(5 * th + math.pi) > 0.92)
    height = height - holes * 3
    base = base * (1 - petals[..., None] * 0.18)
    return height, base


def clock_face(height, base, size):
    y, x = np.mgrid[0:size, 0:size].astype(float)
    c = (size - 1) / 2
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / size
    rim = np.exp(-((r - 0.36) / 0.03) ** 2)
    height = height + rim * 3
    return height, base * (1 - rim[..., None] * 0.15)


def arrow(name, size, color, seed=0):
    """Bobbing 'next' arrow: a fat downward clay triangle."""
    img = Image.new("L", (size, size), 0)
    dr = ImageDraw.Draw(img)
    m = size * 0.2
    dr.polygon([(m, size * 0.3), (size - m, size * 0.3), (size / 2, size - m * 0.9)], fill=255)
    img = img.filter(ImageFilter.GaussianBlur(size * 0.06))
    a = np.asarray(img, float) / 255.0
    alpha = np.clip((a - 0.45) * 8, 0, 1)
    height = np.clip((a - 0.45) * 2, 0, 1) * 10 + fingerprints(size, size, 1, seed, 0.5) * 0.4
    out = shade(height, np.tile(hexc(color), (size, size, 1)), alpha, gloss=0.35, shadow_off=(2, 4), shadow_blur=4)
    save(name, out, 0)


def bubble(name, w, h, color, seed=0):
    """Speech bubble with a tail at the bottom centre (customers' requests)."""
    d = rounded_mask(w, h, 48, 14, 2.5, seed)
    y, x = np.mgrid[0:h, 0:w].astype(float)
    tail = np.maximum(np.abs(x - w * 0.5) - (h - 4 - y) * 0.45, -(y - (h - 60)))
    tail = np.where(y > h - 60, tail - 1, 99)
    d = np.minimum(d + 0, np.where(y > h - 70, np.maximum(tail, -1) , 99))
    d = np.minimum(rounded_mask(w, h - 40, 48, 14, 2.5, seed) if False else d, d)
    alpha = np.clip(0.5 - d, 0, 1)
    inn = np.clip(-d / 12.0, 0, 1)
    height = (1 - (1 - inn) ** 2) * 12 + noise(w, h, 4, seed + 1) * 1.5 * inn + fingerprints(w, h, 3, seed + 2) * 0.5 * inn
    out = shade(height, np.tile(hexc(color), (h, w, 1)), alpha, gloss=0.25)
    save(name, out, 70)


def main():
    slab("panel_cream", 384, 384, "#efe3c8", rad=46, seed=1)
    slab("panel_paper", 384, 384, "#f6eedb", rad=30, seed=2, thickness=8, wobble=1.5, prints=3)
    slab("panel_teal", 256, 256, "#3f7f7c", rad=36, seed=3)
    slab("panel_navy", 256, 256, "#2f3d5c", rad=36, seed=4)
    slab("panel_red", 256, 256, "#c24a3a", rad=36, seed=5)
    slab("panel_sand", 256, 256, "#d8c39b", rad=36, seed=6)
    slab("button", 256, 128, "#e9d7b0", rad=34, seed=7, thickness=12, prints=2)
    slab("button_on", 256, 128, "#f2b84b", rad=34, seed=8, thickness=12, prints=2, gloss=0.3)
    slab("tag", 256, 112, "#c24a3a", rad=30, seed=9, thickness=10, prints=2)
    slab("slot", 160, 160, "#d9c8a4", rad=30, seed=10, thickness=-8, prints=1, gloss=0.1)
    slab("bar_back", 256, 64, "#5a4a3c", rad=22, seed=11, thickness=6, prints=0)
    slab("bar_fill", 256, 64, "#f2b84b", rad=22, seed=12, thickness=8, prints=0, gloss=0.35)
    slab("keycap", 128, 128, "#f2ece0", rad=26, seed=13, thickness=12, prints=1, gloss=0.3)
    bubble("bubble", 320, 300, "#fbf6ea", seed=14)
    circle_icon("coin", 128, "#d9c9a6", sand_dollar, seed=15)
    circle_icon("clock", 128, "#f3ead6", clock_face, seed=16)
    circle_icon("dot", 64, "#f2b84b", seed=17, thickness=6)
    circle_icon("stamp", 160, "#c24a3a", seed=18)
    arrow("arrow", 96, "#c24a3a", seed=19)
    with open(os.path.join(OUT, "ui_sprites.json"), "w") as f:
        json.dump(BORDERS, f, indent=1)
    print("[ui]", len(BORDERS), "sprites ->", OUT)


if __name__ == "__main__":
    main()
