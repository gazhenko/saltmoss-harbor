"""
Procedural, tileable surface textures for the clay look.

  Tools/.venv/bin/python Tools/art/clay_textures.py

Writes Game/Assets/Saltmoss/Art/Textures/:
  clay_finger_n.png  fingerprints (whorls/loops), thumb smears and soft dents      (Clay shader, ~14 cm tile)
  clay_tool_n.png    loop-tool scrapes, smoothing strokes, air pits, dust          (Clay shader, ~45 cm tile)
  sea_ripple_n.png   thumb-pushed crescent ripples for the clay sea               (Sea shader, ~4.5 m tile)
  sky_clouds.png     painted gouache cloud band (R = light, A = coverage), tiles horizontally
  paper.png          watercolour paper grain
Normal maps are tangent-space, OpenGL convention (+Y up), 8-bit.
"""
import os
import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Art/Textures")
rng = np.random.default_rng(1729)


def grid(n):
    y, x = np.mgrid[0:n, 0:n].astype(np.float64) / n
    return x, y


def wrap_d(a, c):
    return (a - c + 0.5) % 1.0 - 0.5


def periodic_noise(n, cells, seed, octaves=4, gain=0.5):
    """Tileable value noise via bicubic upsampling of random lattices."""
    out = np.zeros((n, n))
    amp, tot = 1.0, 0.0
    r = np.random.default_rng(seed)
    for o in range(octaves):
        c = cells * (2 ** o)
        lat = r.uniform(-1, 1, (c, c))
        # periodic smooth interpolation
        x = np.arange(n) / n * c
        i0 = np.floor(x).astype(int)
        f = x - i0
        f = f * f * (3 - 2 * f)
        i1 = (i0 + 1) % c
        i0 %= c
        a = lat[i0][:, i0] * (1 - f)[None, :] + lat[i0][:, i1] * f[None, :]
        b = lat[i1][:, i0] * (1 - f)[None, :] + lat[i1][:, i1] * f[None, :]
        out += amp * (a * (1 - f)[:, None] + b * f[:, None])
        tot += amp
        amp *= gain
    return out / tot


def height_to_normal(h, strength):
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)   # image rows go down; +Y up in tangent space
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], axis=-1)
    return Image.fromarray(np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8), "RGB")


def blur(h, r):
    """Cheap periodic box-blur x3 (approx gaussian)."""
    for _ in range(3):
        k = 2 * r + 1
        c = np.cumsum(np.pad(h, ((0, 0), (r + 1, r)), mode="wrap"), axis=1)
        h = (c[:, k:] - c[:, :-k]) / k
        c = np.cumsum(np.pad(h, ((r + 1, r), (0, 0)), mode="wrap"), axis=0)
        h = (c[k:, :] - c[:-k, :]) / k
    return h


def fingerprints(n=1024):
    x, y = grid(n)
    h = np.zeros((n, n))
    warp_x = periodic_noise(n, 6, 11, 3) * 0.012
    warp_y = periodic_noise(n, 6, 12, 3) * 0.012
    for k in range(11):
        cx, cy = rng.uniform(0, 1, 2)
        rx = rng.uniform(0.12, 0.24)
        ry = rx * rng.uniform(1.15, 1.5)
        ang = rng.uniform(0, np.pi)
        dx, dy = wrap_d(x + warp_x, cx), wrap_d(y + warp_y, cy)
        ca, sa = np.cos(ang), np.sin(ang)
        u = (dx * ca + dy * sa) / rx
        v = (-dx * sa + dy * ca) / ry
        r = np.sqrt(u * u + v * v)
        theta = np.arctan2(v, u)
        period = rng.uniform(0.045, 0.06)  # ridges per unit radius
        kind = rng.integers(0, 3)
        if kind == 0:      # whorl
            phase = r / period + theta / (2 * np.pi) * rng.choice([-1, 1])
        elif kind == 1:    # loop
            phase = np.sqrt(u * u + (v * 1.6 - 0.25 * np.sign(u) * np.abs(u)) ** 2) / period + 0.6 * np.cos(theta)
        else:              # arch
            phase = (v + 0.35 * u * u) / period * 0.5 + r * 2
        ridges = np.sin(2 * np.pi * phase)
        mask = np.clip(1.0 - r, 0, 1) ** 0.8
        # the print is pressed unevenly: stronger in the middle of the pad, broken at its edge
        broken = np.clip(periodic_noise(n, 10, 100 + k, 3) * 1.4 + 0.55, 0, 1)
        strength = rng.uniform(0.35, 1.0)
        h += ridges * mask * broken * strength * 0.5
        # the pad also leaves a soft hollow
        h -= mask ** 2 * rng.uniform(0.6, 1.4)
    # thumb smears: elongated soft dents
    for k in range(9):
        cx, cy = rng.uniform(0, 1, 2)
        ang = rng.uniform(0, np.pi)
        L, W = rng.uniform(0.15, 0.35), rng.uniform(0.05, 0.1)
        dx, dy = wrap_d(x, cx), wrap_d(y, cy)
        u = (dx * np.cos(ang) + dy * np.sin(ang)) / L
        v = (-dx * np.sin(ang) + dy * np.cos(ang)) / W
        h -= np.exp(-(u * u + v * v) * 2.5) * rng.uniform(0.5, 1.2)
        # smear streaks along the stroke
        h += np.sin(v * rng.uniform(18, 30)) * np.exp(-(u * u + v * v) * 2.0) * 0.12
    h += periodic_noise(n, 8, 5, 4) * 0.6     # gentle lumpiness
    h += periodic_noise(n, 64, 6, 2) * 0.05   # micro grain
    return height_to_normal(h, 3.0)


def tool_marks(n=1024):
    x, y = grid(n)
    h = periodic_noise(n, 5, 21, 4) * 0.9
    for k in range(26):
        cx, cy = rng.uniform(0, 1, 2)
        ang = rng.uniform(0, np.pi)
        L, W = rng.uniform(0.08, 0.25), rng.uniform(0.025, 0.07)
        dx, dy = wrap_d(x, cx), wrap_d(y, cy)
        u = (dx * np.cos(ang) + dy * np.sin(ang)) / L
        v = (-dx * np.sin(ang) + dy * np.cos(ang)) / W
        env = np.exp(-(u * u) * 3.0) * np.exp(-(v * v) * 4.0)
        # loop-tool drag: several fine parallel grooves
        grooves = np.sin(v * W * n * rng.uniform(0.18, 0.32)) * 0.5 + 0.5
        h -= env * (grooves ** 2) * rng.uniform(0.35, 0.8)
        # flattened facet where the tool smoothed
        h += env * rng.uniform(-0.25, 0.25)
    # air pits and dust specks
    for k in range(260):
        cx, cy = rng.uniform(0, 1, 2)
        r = rng.uniform(0.0018, 0.006)
        dx, dy = wrap_d(x, cx), wrap_d(y, cy)
        d2 = (dx * dx + dy * dy) / (r * r)
        sgn = -1 if rng.uniform() < 0.8 else 0.6
        h += sgn * np.exp(-d2) * rng.uniform(0.4, 1.0)
    h += periodic_noise(n, 96, 22, 2) * 0.04
    return height_to_normal(h, 4.0)


def sea_ripples(n=1024):
    x, y = grid(n)
    h = periodic_noise(n, 4, 31, 3) * 0.6
    for k in range(170):
        cx, cy = rng.uniform(0, 1, 2)
        ang = rng.normal(0.0, 0.45)           # crests mostly across one direction
        R = rng.uniform(0.05, 0.14)
        w = rng.uniform(0.008, 0.016)
        dx, dy = wrap_d(x, cx), wrap_d(y, cy)
        u = dx * np.cos(ang) + dy * np.sin(ang)
        v = -dx * np.sin(ang) + dy * np.cos(ang)
        # crescent: a ring segment curving away from the wind
        rr = np.sqrt(u * u + (v + R) ** 2)
        seg = np.exp(-(u / (R * 0.8)) ** 2 * 2.0) * (v > -R * 0.9)
        ridge = np.exp(-((rr - R) / w) ** 2)
        # thumb-pushed: steep front, soft back
        back = np.exp(-((rr - R + w * 1.6) / (w * 2.2)) ** 2) * 0.5
        h += (ridge + back) * seg * rng.uniform(0.5, 1.0)
    h = blur(h, 1)
    return height_to_normal(h, 5.0)


def sky_clouds(w=2048, hgt=512):
    """Gouache cumulus painted on the cyclorama: heaps of overlapping round dabs with flat undersides, lit from the
    top (shade = how much cloud is above a point), soft brushy edges. Tiles horizontally.
    R = light (0 shadow .. 1 lit), A = coverage."""
    X, Y = np.meshgrid(np.arange(w) / w, np.arange(hgt) / hgt)   # Y = 0 at the horizon edge (flipped at the end)
    cov = np.zeros((hgt, w))
    r = np.random.default_rng(77)
    aspect = w / hgt
    for c in range(15):
        cx = r.uniform(0, 1)
        cw = r.uniform(0.04, 0.11)
        ch = r.uniform(0.3, 0.75)
        base = r.uniform(0.04, 0.22)
        cloud = np.zeros((hgt, w))
        for k in range(int(r.integers(9, 18))):
            fx = r.uniform(-1, 1)
            dx = cx + fx * cw
            rad = r.uniform(0.28, 0.5) * ch * (1.0 - abs(fx) * 0.45)
            dy = base + rad * r.uniform(0.55, 1.05) * (1.0 - abs(fx) * 0.35)
            ddx = ((X - dx + 0.5) % 1.0 - 0.5) * aspect
            dd = np.sqrt(ddx ** 2 + (Y - dy) ** 2) / rad
            cloud = np.maximum(cloud, np.clip((1.0 - dd) * 6.0, 0, 1))
        cloud *= np.clip((Y - base) * 30.0 + 0.5, 0, 1)   # its own flat underside
        cov = np.maximum(cov, cloud)
    brush = periodic_noise(w, 90, 44, 2)[:hgt, :]
    cov = np.clip(cov * (0.94 + brush * 0.2), 0, 1)
    # shading: cloud mass above a point shades it (tops lit, bellies blue-grey), softened
    above = np.zeros_like(cov)
    for s_ in range(4, 64, 6):
        above += np.roll(cov, -s_, axis=0) * (np.arange(hgt)[:, None] + s_ < hgt)
    above /= 10.0
    light = np.clip(1.05 - above * 0.75, 0, 1)
    light = blur(light, 3)
    light = np.clip(light + periodic_noise(w, 24, 45, 2)[:hgt, :] * 0.06, 0, 1)
    img = np.stack([light, light, light, cov], axis=-1)[::-1]
    return Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA")


def paper(n=512):
    h = periodic_noise(n, 32, 51, 4) * 0.6 + periodic_noise(n, 128, 52, 2) * 0.4
    fib = np.zeros((n, n))
    x, y = grid(n)
    for k in range(400):
        cx, cy = rng.uniform(0, 1, 2)
        ang = rng.uniform(0, np.pi)
        dx, dy = wrap_d(x, cx), wrap_d(y, cy)
        u = dx * np.cos(ang) + dy * np.sin(ang)
        v = -dx * np.sin(ang) + dy * np.cos(ang)
        fib += np.exp(-(u / 0.03) ** 2 - (v / 0.0015) ** 2) * rng.uniform(-1, 1)
    g = np.clip(0.5 + h * 0.35 + fib * 0.15, 0, 1)
    return Image.fromarray((g * 255).astype(np.uint8), "L")


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [("clay_finger_n.png", fingerprints), ("clay_tool_n.png", tool_marks), ("sea_ripple_n.png", sea_ripples),
            ("sky_clouds.png", sky_clouds), ("paper.png", paper)]
    for name, fn in jobs:
        img = fn()
        img.save(os.path.join(OUT, name))
        print("[tex]", name, img.size)


if __name__ == "__main__":
    main()
