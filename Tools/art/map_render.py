"""
Paper charts for the in-game map, drawn from the same data the world is built from:

  map_town.png   the harbour and the town: terrain with contour lines and hill shading, roofs in their own colours
                 (footprints from each building's clay mesh), boardwalks and piers from their deck planks, trees,
                 rocks and boats, all over a cream paper grain
  map_sea.png    the sea chart: the coast and the mainland hills, the fishing grounds as dashed rings round the
                 harbour mouth, and the fog bank at the edge of the world

  Tools/.venv/bin/python Tools/art/map_render.py      -> Game/Assets/Saltmoss/Art/UI/map_town.png, map_sea.png

Place names, markers and the player are drawn live by MapUI (Scripts/Runtime/UI/MapUI.cs), which shares the RECTS
below: keep them in step.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
from skimage.measure import find_contours

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
sys.path[:0] = [os.path.join(ROOT, "Tools/clay"), os.path.join(ROOT, "Tools/clay/models")]
from clay import read_claymesh, fbm  # noqa: E402
import town_terrain as TT  # noqa: E402
import far_land as FL  # noqa: E402

OUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Art/UI")
LAYOUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Data/town_layout.json")
MODELS = os.path.join(ROOT, "Game/Assets/Saltmoss/Models")

# world rects (minX, minZ, maxX, maxZ) and image widths; MapUI.cs has the same numbers
RECTS = {
    "town": ((-160.0, -64.0, 160.0, 96.0), 2048),            # 2048 x 1024 px: power-of-two sides, or Unity won't
    "sea": ((-960.0, -105.0, 960.0, 855.0), 2048),           # block-compress them once they have mipmaps
}
MOUTH = (0.0, 75.0)
ZONES = (160.0, 380.0)          # Shallows | Kelp Reach | Grey Deep (BoatController.ZoneAt)
WORLD_R = 780.0                 # BoatController.worldRadius

INK = np.array([0.33, 0.25, 0.19])
PAPER = np.array([0.95, 0.91, 0.82])


def rgbf(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


class Chart:
    def __init__(self, rect, width):
        self.x0, self.z0, self.x1, self.z1 = rect
        self.W = width
        self.H = int(round(width * (self.z1 - self.z0) / (self.x1 - self.x0)))
        assert self.W & (self.W - 1) == 0 and self.H & (self.H - 1) == 0, "chart sizes must be powers of two to compress"
        self.ppm = self.W / (self.x1 - self.x0)

    def px(self, x, z):
        return ((np.asarray(x) - self.x0) * self.ppm, (self.z1 - np.asarray(z)) * self.ppm)

    def grid(self, step=1):
        xs = self.x0 + (np.arange(0, self.W, step) + 0.5) / self.ppm
        zs = self.z1 - (np.arange(0, self.H, step) + 0.5) / self.ppm
        return np.meshgrid(xs, zs)


def ground(X, Z):
    """Ground height anywhere: the town patch's own heightmap inside it, the mainland outside."""
    inside = (np.abs(X) < FL.PATCH) & (np.abs(Z) < FL.PATCH)
    H = np.empty(X.shape)
    H[inside] = TT.height(X[inside], Z[inside])
    out = ~inside
    if out.any():
        H[out] = FL.height(X[out], Z[out])
    return H


def heights(ch, coarse):
    if coarse > 1:
        X, Z = ch.grid(coarse)
        Hc = ground(X, Z)
        H = ndimage.zoom(Hc, (ch.H / Hc.shape[0], ch.W / Hc.shape[1]), order=1)
        return H[:ch.H, :ch.W]
    X, Z = ch.grid(1)
    return ground(X, Z)


def paper_grain(h, w, seed):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    P = np.stack([xx / 9.0, yy / 9.0, np.full(xx.shape, seed * 0.37, np.float32)], -1).reshape(-1, 3)
    fine = fbm(P, 3, seed).reshape(h, w)
    P2 = np.stack([xx / 140.0, yy / 140.0, np.full(xx.shape, seed * 0.11, np.float32)], -1).reshape(-1, 3)
    blot = fbm(P2, 3, seed + 1).reshape(h, w)
    return 1.0 + 0.045 * fine + 0.06 * blot


def base_layers(ch, H, contour_step, seed):
    """Sea, land, hill shade, contours and coastline as a float RGB image."""
    land = H > 0.02
    dist_sea = ndimage.distance_transform_edt(~land) / ch.ppm          # metres out to sea
    # sea: pale shallows to deeper teal, with a couple of depth lines following the coast
    shallow, deep = rgbf("#b9dcd4"), rgbf("#86bcc0")
    sea = shallow * (1 - smoothstep(0, 60, dist_sea))[..., None] + deep * smoothstep(0, 60, dist_sea)[..., None]
    img = sea.copy()
    # land: lowland green, upland straw, moor heather-brown, rock grey on steep ground
    gz, gx = np.gradient(ndimage.gaussian_filter(H, 1.5), 1 / ch.ppm)
    slope = np.hypot(gx, gz)
    low, up, moor, rock, sand = rgbf("#c3d39b"), rgbf("#d6d3a0"), rgbf("#c4ad99"), rgbf("#b0a898"), rgbf("#ead8a8")
    lc = low * (1 - smoothstep(8, 40, H))[..., None] + up * smoothstep(8, 40, H)[..., None]
    lc = lc * (1 - smoothstep(50, 120, H))[..., None] + moor * smoothstep(50, 120, H)[..., None]
    lc = lc * (1 - smoothstep(0.7, 1.2, slope))[..., None] + rock * smoothstep(0.7, 1.2, slope)[..., None]
    dist_land = ndimage.distance_transform_edt(land) / ch.ppm
    beach = (smoothstep(3.0, 1.0, H) * smoothstep(0.9, 0.5, slope))[..., None]
    lc = lc * (1 - beach) + sand * beach
    # hill shade, lit from the north-west like an old engraving
    shade = np.clip(1.0 + (-gx * 0.55 + gz * 0.55) * 0.55, 0.72, 1.18)
    lc = lc * shade[..., None]
    img = np.where(land[..., None], lc, img)
    # paper grain over everything
    img = img * paper_grain(ch.H, ch.W, seed)[..., None]
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    dr = ImageDraw.Draw(im, "RGBA")
    # contour lines on the land, a bolder one every fifth
    hs = ndimage.gaussian_filter(H, 2.0)
    top = float(hs.max())
    k = 1
    while k * contour_step < top:
        lev = k * contour_step
        for c in find_contours(hs, lev):
            pts = [(float(p[1]), float(p[0])) for p in c[::2]]
            if len(pts) > 2:
                dr.line(pts, fill=(120, 92, 60, 120 if k % 5 else 190), width=2 if k % 5 == 0 else 1)
        k += 1
    # depth lines in the sea, parallel to the coast
    for dm, a in ((6.0, 110), (16.0, 70)):
        for c in find_contours(dist_sea, dm * 1.0):
            pts = [(float(p[1]), float(p[0])) for p in c[::2]]
            if len(pts) > 2:
                dr.line(pts, fill=(70, 120, 125, a), width=1)
    # surf: a white line just off the shore, then the inked coastline
    for c in find_contours(dist_sea, 1.2 * max(1.0, 2.0 / ch.ppm)):
        pts = [(float(p[1]), float(p[0])) for p in c[::2]]
        if len(pts) > 2:
            dr.line(pts, fill=(255, 255, 250, 200), width=max(2, int(ch.ppm * 0.6)))
    for c in find_contours(land.astype(float), 0.5):
        pts = [(float(p[1]), float(p[0])) for p in c]
        if len(pts) > 2:
            dr.line(pts, fill=(84, 62, 46, 255), width=max(2, int(round(ch.ppm * 0.35))))
    return im, dist_land


def model_mesh(model):
    p = os.path.join(MODELS, model + ".claymesh")
    if not os.path.exists(p):
        return None
    d = read_claymesh(p)
    vs, fs, cs, base = [], [], [], 0
    for pc in d["pieces"]:
        if pc["hidden"]:
            continue
        vs.append(pc["v"]); cs.append(pc["c"]); fs.append(pc["f"] + base)
        base += len(pc["v"])
    if not vs:
        return None
    return np.concatenate(vs), np.concatenate(fs), np.concatenate(cs)


def place(v, it):
    a = math.radians(it["yaw"])
    s = it.get("scale", 1.0) or 1.0
    # Quaternion.Euler(0, yaw, 0): x' = x cos + z sin, z' = -x sin + z cos
    x = (v[:, 0] * math.cos(a) + v[:, 2] * math.sin(a)) * s + it["pos"][0]
    z = (-v[:, 0] * math.sin(a) + v[:, 2] * math.cos(a)) * s + it["pos"][2]
    y = v[:, 1] * s + it["pos"][1]
    return x, y, z


def hull(xs, zs):
    pts = sorted(set(zip(np.round(xs, 2), np.round(zs, 2))))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


BUILDINGS = ("cottage", "fish_shop", "harbor_office", "post_office", "museum_hull", "net_shed", "smokehouse", "stilt_shack",
             "pip_house", "lighthouse")
DECKS = ("boardwalk", "pier_head", "pier_platform", "floating_dock", "gangway", "seawall", "retaining_wall")
BOATS = ("rowboat",)


def draw_town_features(ch, im):
    lay = json.load(open(LAYOUT))
    dr = ImageDraw.Draw(im, "RGBA")
    cache = {}

    def mesh(m):
        if m not in cache:
            cache[m] = model_mesh(m)
        return cache[m]

    insts = lay["instances"]
    # decks first (plank-coloured, from their upward faces), then rocks and boats, then buildings, then trees
    for it in insts:
        m = it["model"].split("/")[-1]
        if not m.startswith(DECKS):
            continue
        mm = mesh(it["model"])
        if mm is None:
            continue
        v, f, c = mm
        x, y, z = place(v, it)
        P = np.stack([x, y, z], 1)
        n = np.cross(P[f[:, 1]] - P[f[:, 0]], P[f[:, 2]] - P[f[:, 0]])
        up = n[:, 1] / (np.linalg.norm(n, axis=1) + 1e-9) > 0.6
        tri = f[up]
        if len(tri) == 0:
            continue
        px, py = ch.px(x, z)
        col = c[tri][:, :, :3].mean(axis=1)
        order = np.argsort(y[tri].mean(axis=1))
        for t in order:
            a, b, cc = tri[t]
            r, g, bl = (col[t] * 0.55 + np.array([200, 168, 120]) * 0.45).astype(int)
            dr.polygon([(px[a], py[a]), (px[b], py[b]), (px[cc], py[cc])], fill=(r, g, bl, 255))
    # rocks, sea stacks and boats: their outline from above, in their own colours
    for it in insts:
        m = it["model"].split("/")[-1]
        if not (m.startswith("rock") or m.startswith("sea_stack") or m.startswith(BOATS) or m == "wreck"):
            continue
        mm = mesh(it["model"])
        if mm is None:
            continue
        v, f, c = mm
        x, y, z = place(v, it)
        h = hull(*ch.px(x, z))
        if len(h) < 3:
            continue
        top = y > np.percentile(y, 70)
        r, g, bl = c[top][:, :3].mean(axis=0).astype(int)
        dr.polygon(h, fill=(r, g, bl, 255), outline=(84, 62, 46, 255), width=2)
    for it in insts:
        m = it["model"].split("/")[-1]
        if not m.startswith(BUILDINGS):
            continue
        mm = mesh(it["model"])
        if mm is None:
            continue
        v, f, c = mm
        x, y, z = place(v, it)
        h = hull(*ch.px(x, z))
        if len(h) < 3:
            continue
        # roof colour: what you'd see from above, the top quarter of the building
        top = y > np.percentile(y, 75)
        rc = c[top][:, :3].astype(float).mean(axis=0) / 255
        rc = np.clip((rc - rc.mean()) * 1.35 + rc.mean() * 1.18 + 0.04, 0, 1)    # a touch brighter and bolder
        r, g, bl = (rc * 255).astype(int)
        sh = [(p[0] + 4, p[1] + 5) for p in h]
        dr.polygon(sh, fill=(60, 45, 35, 70))
        dr.polygon(h, fill=(r, g, bl, 255), outline=(70, 52, 40, 255), width=3)
        # a ridge line along the long axis, like a little drawn roof
        hh = np.array(h)
        cx, cy = hh.mean(axis=0)
        u, s, vt = np.linalg.svd(hh - [cx, cy], full_matrices=False)
        d = vt[0]
        L = np.abs((hh - [cx, cy]) @ d).max() * 0.8
        dr.line([(cx - d[0] * L, cy - d[1] * L), (cx + d[0] * L, cy + d[1] * L)], fill=(70, 52, 40, 200), width=2)
    for it in insts:
        m = it["model"].split("/")[-1]
        if not m.startswith("tree"):
            continue
        x, z = it["pos"][0], it["pos"][2]
        px, py = ch.px(x, z)
        r = 1.6 * ch.ppm * (it.get("scale", 1.0) or 1.0)
        dr.ellipse([px - r + 3, py - r + 4, px + r + 3, py + r + 4], fill=(50, 60, 40, 70))
        dr.ellipse([px - r, py - r, px + r, py + r], fill=(84, 120, 76, 255), outline=(52, 74, 46, 255), width=2)
        dr.ellipse([px - r * 0.45 - r * 0.25, py - r * 0.45 - r * 0.3, px + r * 0.45 - r * 0.25, py + r * 0.45 - r * 0.3], fill=(110, 146, 96, 255))


def dashed_circle(dr, ch, cx, cz, r, color, width, dash=0.05):
    n = max(48, int(2 * math.pi * r * ch.ppm / 18))
    for i in range(n):
        if i % 2:
            continue
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        pts = [ch.px(cx + r * math.cos(a), cz + r * math.sin(a)) for a in np.linspace(a0, a1, 4)]
        dr.line([(float(p[0]), float(p[1])) for p in pts], fill=color, width=width)


def compass(dr, cx, cy, R):
    """A little compass rose, north up (the open sea)."""
    ink = (84, 62, 46, 255)
    for k in range(8):
        a = math.radians(k * 45)
        L = R if k % 2 == 0 else R * 0.55
        tip = (cx + math.sin(a) * L, cy - math.cos(a) * L)
        l1 = (cx + math.sin(a + 0.35) * R * 0.18, cy - math.cos(a + 0.35) * R * 0.18)
        l2 = (cx + math.sin(a - 0.35) * R * 0.18, cy - math.cos(a - 0.35) * R * 0.18)
        dr.polygon([tip, l1, (cx, cy)], fill=(194, 74, 58, 255) if k == 0 else ink)
        dr.polygon([tip, l2, (cx, cy)], fill=(240, 228, 200, 255))
        dr.line([tip, l1, (cx, cy), l2, tip], fill=ink, width=2)
    dr.ellipse([cx - R * 0.12, cy - R * 0.12, cx + R * 0.12, cy + R * 0.12], fill=(240, 228, 200, 255), outline=ink, width=2)


def edges(im, seed):
    """Darken and roughen the paper edges a little."""
    w, h = im.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    e = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    P = np.stack([xx / 40.0, yy / 40.0, np.full(xx.shape, seed * 0.5, np.float32)], -1).reshape(-1, 3)
    n = fbm(P, 2, seed).reshape(h, w)
    k = smoothstep(0, 60, e + n * 30)
    a = np.asarray(im).astype(np.float32) / 255
    a = a * (0.8 + 0.2 * k)[..., None] + np.array([0.55, 0.42, 0.3]) * (1 - k)[..., None] * 0.12
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def town_map():
    rect, w = RECTS["town"]
    ch = Chart(rect, w)
    H = heights(ch, 1)
    im, _ = base_layers(ch, H, 3.0, 301)
    draw_town_features(ch, im)
    dr = ImageDraw.Draw(im, "RGBA")
    compass(dr, ch.W - 120, ch.H - 130, 80)
    im = edges(im, 302)
    return im


def sea_map():
    rect, w = RECTS["sea"]
    ch = Chart(rect, w)
    H = heights(ch, 2)
    im, _ = base_layers(ch, H, 25.0, 401)
    X, Z = ch.grid(1)
    r = np.hypot(X - MOUTH[0], Z - MOUTH[1])
    sea = H <= 0.02
    a = np.asarray(im).astype(np.float32) / 255
    # the fishing grounds read as bands of deeper water: Shallows pale, Kelp Reach greener, the Grey Deep slate
    kelp = smoothstep(ZONES[0] - 12, ZONES[0] + 12, r) * (1 - smoothstep(ZONES[1] - 12, ZONES[1] + 12, r))
    deep = smoothstep(ZONES[1] - 12, ZONES[1] + 12, r)
    tint = np.ones(a.shape, np.float32)
    tint = tint * (1 - kelp[..., None] * 0.12) + np.array([0.86, 0.95, 0.84]) * kelp[..., None] * 0.12
    tint = tint * (1 - deep[..., None] * 0.34) + np.array([0.66, 0.72, 0.82]) * deep[..., None] * 0.34
    a = np.where(sea[..., None], a * tint, a)
    # kelp: little olive tick marks scattered through Kelp Reach
    rng = np.random.default_rng(5)
    ticks = []
    for _ in range(900):
        ang, rad = rng.uniform(0, 2 * np.pi), rng.uniform(ZONES[0] + 25, ZONES[1] - 25)
        x, z = MOUTH[0] + rad * np.cos(ang), MOUTH[1] + rad * np.sin(ang)
        px, py = ch.px(x, z)
        if 0 <= px < ch.W and 0 <= py < ch.H and sea[int(py), int(px)] and rng.random() < 0.35:
            ticks.append((px, py))
    # the fog bank beyond the edge of the world: soft cross-hatching outside WORLD_R
    fog = smoothstep(WORLD_R - 30, WORLD_R + 40, r) * sea
    hatch = ((np.mgrid[0:ch.H, 0:ch.W][0] + np.mgrid[0:ch.H, 0:ch.W][1]) % 14 < 2).astype(np.float32)
    a = a * (1 - fog[..., None] * 0.35) + np.array([0.93, 0.93, 0.9]) * fog[..., None] * 0.35
    a = a * (1 - fog * hatch * 0.12)[..., None]
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    dr = ImageDraw.Draw(im, "RGBA")
    for px, py in ticks:
        dr.line([(px, py + 6), (px - 2, py - 1), (px + 1, py - 7)], fill=(96, 112, 60, 150), width=2)
    rings = Image.new("RGBA", im.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rings, "RGBA")
    for rr, col in ((ZONES[0], (60, 110, 120, 210)), (ZONES[1], (60, 90, 120, 210)), (WORLD_R, (110, 110, 110, 170))):
        dashed_circle(rd, ch, MOUTH[0], MOUTH[1], rr, col, 4)
    ra = np.asarray(rings).copy()
    ra[..., 3] = (ra[..., 3] * ndimage.binary_erosion(sea, iterations=3)).astype(np.uint8)    # only on the water
    im = Image.alpha_composite(im.convert("RGBA"), Image.fromarray(ra)).convert("RGB")
    dr = ImageDraw.Draw(im, "RGBA")
    compass(dr, ch.W - 130, 130, 85)
    im = edges(im, 402)
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("map_town", town_map), ("map_sea", sea_map)):
        im = fn()
        p = os.path.join(OUT, name + ".png")
        im.save(p, optimize=True)
        print(f"[map] {p} {im.size}")


if __name__ == "__main__":
    main()
