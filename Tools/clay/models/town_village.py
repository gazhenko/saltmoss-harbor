"""
Saltmoss Harbor density pass — "the village": everything that turns six buildings round a pier into a crowded,
lived-in fishing town.

  * colour / hand-jitter variants of the cottages and the net shed (cottage_a_red, cottage_b_mustard, ...): the
    original builders in town_bldg.py re-run under a different model name (-> different board jitter seed), a smaller
    triangle budget (they sit further up the slope) and a colour remap. Their smoke socket is renamed `chimney` and
    only the first few window sockets are kept (fewer night lamps).
  * fishermen's shacks on stilts (stilt_shack_a/b/c) for the edges of the cove, floor y = 0 placed at the boardwalk
    deck height (1.8), pilings to the seabed, a porch on +Z that meets the boardwalk.
  * rowboats: afloat (origin = keel bottom, waterline ~0.2), beached (heeled over on the sand), upturned on chocks.
  * boardwalk pieces with an opening in a side rail (for branches off the promenade / east boardwalk).
  * yard clutter: washing line, fish-drying rack, woodpile, buoys on a wall plank, dry-stone terrace wall, picket
    fence, a little tarred smokehouse (two chimney sockets), and lighter "_lo" copies of the common town_props
    (crate, barrel, crab pots, lantern post, bench ...) for the many extra instances.

Conventions as everywhere (Docs/DESIGN.md §5.1): x right, y up, z forward, metres; buildings face +Z.
"""
import math

import numpy as np
import clay as C
from clay import Prim, Func, Box, Sphere, Ellipsoid, Capsule, Cylinder, Torus, Tube, HalfSpace, euler, shade, mix
from kit_town import *  # noqa: F401,F403
import kit_town as KT
import kit_props as KP
import town_bldg as TB
from town_pier import _deck_cross, _structure, _rails

MODELS = {}


# ----------------------------------------------------------------------------------------------------------------
# variants of existing buildings


class palette:
    """Scoped colour remap: every '#rrggbb' string that reaches clay.rgb (piece colours, paints, shade(), mix()) is
    swapped through `remap` while building."""

    def __init__(self, remap):
        self.remap = {k.lower(): v for k, v in (remap or {}).items()}

    def __enter__(self):
        self.orig = C.rgb
        orig, remap = self.orig, self.remap

        def rgb_(c):
            if isinstance(c, str):
                c = remap.get(c.lower(), c)
            return orig(c)
        C.rgb = rgb_
        return self

    def __exit__(self, *exc):
        C.rgb = self.orig


def finish_sockets(m, max_win=3):
    """smoke -> chimney (AmbientLife puffs from any socket named *chimney*); keep only the first max_win windows."""
    out, nwin = [], 0
    for s in m.sockets:
        name = s[0]
        if name in ("smoke", "stovepipe"):
            s = ("chimney",) + tuple(s[1:])
        elif name.startswith("win_"):
            if nwin >= max_win:
                continue
            s = (f"win_{nwin}",) + tuple(s[1:])
            nwin += 1
        out.append(s)
    m.sockets = out
    return m


def variant(base, name, budget, remap, max_win=3):
    """Register town/<name>: town_bldg's `base` builder under a new name/seed, budget and colour remap."""
    def fn():
        orig_tm = TB.TownModel

        class _TM(KT.TownModel):
            def __init__(self, _name, budget=60000, res=0.02, seed=None):
                super().__init__(name, budget=fn.budget, res=res, seed=seed)
        TB.TownModel = _TM
        try:
            with palette(remap):
                m = TB.MODELS[f"town/{base}"]()
        finally:
            TB.TownModel = orig_tm
        return finish_sockets(m, max_win)
    fn.budget = budget
    fn.__name__ = name
    MODELS[f"town/{name}"] = fn
    return fn


# faded paints for the variants (dusty plasticine, like TP)
VP = dict(
    brick="#a0574a", brick_dk="#82463b", oxblood="#7b3f3a", slate="#5f7486", slate_dk="#4d5f6f", sky="#7f9cab",
    sage="#7f9a78", moss="#6d8558", lilac="#8f8098", buttery="#d3b768", chalk="#dcd5c3", shell="#e4d8c2",
    tin_blue="#64788a", tin_blue_dk="#53667a", tin_green="#5f7a62", tin_green_dk="#4c6550", ochre_dk="#9a6a3a",
)

# cottage_a: mustard clapboard, red tin roof (+ red shutters / flower boxes), teal door
variant("cottage_a", "cottage_a_red", 30000, {TP["mustard"]: VP["brick"], TP["red"]: VP["slate"], TP["red_dk"]: VP["slate_dk"],
                                              "#a35a48": VP["tin_blue"], TP["teal"]: TP["mustard"]})
variant("cottage_a", "cottage_a_sky", 30000, {TP["mustard"]: VP["sky"], TP["red"]: VP["brick_dk"], TP["red_dk"]: VP["oxblood"],
                                              TP["teal"]: TP["cream"], TP["cream"]: VP["shell"]})
variant("cottage_a", "cottage_a_chalk", 28000, {TP["mustard"]: VP["chalk"], TP["red"]: VP["tin_green"], TP["red_dk"]: VP["tin_green_dk"],
                                                "#a35a48": TP["rust"], TP["teal"]: TP["red"]})
# cottage_b: teal board & batten, mossy shake roof, mustard shutters, red door
variant("cottage_b", "cottage_b_mustard", 30000, {TP["teal"]: TP["mustard"], TP["mustard"]: TP["navy"], TP["red"]: TP["teal"]})
variant("cottage_b", "cottage_b_rose", 28000, {TP["teal"]: TP["rose"], TP["mustard"]: TP["sage"], TP["red"]: TP["navy"]})
# cottage_c: rose clapboard saltbox, grey tin roof, sage shutters, navy door
variant("cottage_c", "cottage_c_green", 30000, {TP["rose"]: VP["sage"], TP["sage"]: TP["mustard"], TP["navy"]: TP["red"]})
variant("cottage_c", "cottage_c_slate", 28000, {TP["rose"]: VP["slate"], TP["sage"]: VP["buttery"], TP["navy"]: VP["oxblood"],
                                                TP["tin"]: TP["rust_lt"], TP["tin_dk"]: TP["rust"]})
# second copies of cottage_a / cottage_b already in town (27, -21) / (3.5, -39) get their own colours too
variant("cottage_a", "cottage_a_teal", 30000, {TP["mustard"]: TP["teal"], TP["teal"]: VP["brick"], TP["red"]: TP["rust_lt"],
                                               TP["red_dk"]: TP["rust"]})
variant("cottage_b", "cottage_b_chalk", 30000, {TP["teal"]: VP["chalk"], TP["mustard"]: TP["navy"], TP["red"]: TP["mustard"]})
# net shed: oxide red board & batten -> blue / mustard sheds
variant("net_shed", "net_shed_blue", 26000, {"#86453a": VP["slate"]})
variant("net_shed", "net_shed_ochre", 26000, {"#86453a": TP["ochre"], TP["wood_lt"]: TP["cream"]})


# ----------------------------------------------------------------------------------------------------------------
# fishermen's shacks on stilts


def stilt_shack(name, *, hx, hz, eave, ridge, ridge_dir="x", walls="v", paint=None, trim=None, door_paint=None,
                roof="tin", roof_colors=None, plat=(-2.6, 2.6, -2.3, 3.0), sea=-1.8, bottom=-5.0, lean_to=False,
                net_side=None, budget=30000, peel=0.4, wood=None):
    """A fisherman's shack on a planked platform over the water. Floor y = 0; the porch (z hz..plat z1) is open on
    its front edge so a 2.4 m boardwalk can meet it head-on; rails on the sides and back. Sockets: door, chimney,
    light_0, win_*."""
    def fn():
        m = TownModel(name, budget=budget)
        rng = m.rng
        mg = dict(trim="trim", glass="glass", deco="deco", door="trim")
        x0, x1, z0, z1 = plat
        trim_c = trim or TP["cream"]
        # --- platform: deck, joists, beams, pilings with braces, a ladder down to the water
        deck(m, "floor", x0, x1, z0, z1, 0.0, along="x", pw=(0.18, 0.27), t=0.075, nails=1, missing=0.02)
        for x in np.linspace(x0 + 0.3, x1 - 0.3, 3):
            post(m, "floor", (x, -0.15, z0 + 0.05), (x, -0.15, z1 - 0.05), 0.085, TP["wood_dk"], detail=0.5)
        zs = np.linspace(z0 + 0.25, z1 - 0.25, 3)
        xs = np.linspace(x0 + 0.25, x1 - 0.25, 3)
        for z in zs:
            post(m, "floor", (x0 - 0.06, -0.3, z), (x1 + 0.06, -0.3, z), 0.1, TP["wood_dk"], detail=0.5)
        for x in xs:
            for z in zs:
                top = (x + rng.normal() * 0.04, -0.35, z + rng.normal() * 0.04)
                piling(m, "piles", top, bottom, rng.uniform(0.12, 0.16), lean=(rng.normal() * 0.16, rng.normal() * 0.16), sea_y=sea,
                       barnacles=8, detail=1.2)
        for x in (xs[0], xs[-1]):
            board(m, "floor", (x + 0.15, -0.5, zs[0]), (x + 0.15, max(sea + 0.3, -1.7), zs[-1]), 0.15, 0.06, (1, 0, 0), TP["wood_dk"], nails=0,
                  detail=0.4, knot=0)
        board(m, "floor", (xs[0], -0.5, zs[0] - 0.14), (xs[-1], max(sea + 0.3, -1.6), zs[0] - 0.14), 0.15, 0.06, (0, 0, -1), TP["wood_dk"],
              nails=0, detail=0.4, knot=0)
        # rails: both sides and the back; the front edge stays open for the boardwalk
        rail_run(m, "floor", [(x0 + 0.06, 0, z1 - 0.06), (x0 + 0.06, 0, z0 + 0.06), (x1 - 0.06, 0, z0 + 0.06), (x1 - 0.06, 0, z1 - 0.06)],
                 h=0.82, post_every=1.4, foot_y=-0.3)
        # --- the shack
        door_x = -hx * 0.38
        win_x = hx * 0.48
        ops = {"front": [(door_x + hx - 0.47, door_x + hx + 0.47, -1, 1.97), (win_x + hx - 0.34, win_x + hx + 0.34, 1.0, 1.72)],
               "right": [(hz - 0.33, hz + 0.33, 1.05, 1.7)], "back": [(hx - 0.3, hx + 0.3, 1.1, 1.65)]}
        sh = Shack(m, hx, hz, eave, ridge, ridge=ridge_dir, walls=walls, colors=wood or [TP["wood"], TP["wood_dk"], TP["wood_silver"], TP["wood_lt"]],
                   paint=paint, peel=peel, trim=trim_c, openings=ops, roof=roof, roof_colors=roof_colors, rust=0.55, sag=0.09, ov=0.32,
                   ov_gable=0.38, lean=0.008, moss=0.4)
        dc, out = sh.at("front", door_x + hx, 0.0, 0.0)
        door(m, mg, dc, out, 0.84, 1.92, paint=door_paint, color=TP["wood_dk"], peel=0.35, trim=trim_c, crooked=rng.normal() * 1.5)
        m.socket("door", None, dc + out * 0.12)
        wins = []
        for side, s, w_, h_ in (("front", win_x + hx, 0.6, 0.64), ("right", hz, 0.58, 0.56), ("back", hx, 0.52, 0.48)):
            c, out = sh.at(side, s, 1.36 if side != "back" else 1.38, 0.02)
            wins.append(window(m, mg, c, out, w_, h_, frame_color=trim_c, panes=(2, 2) if side == "front" else (2, 1),
                               curtain=rng.choice(["#c9b48f", "#b8796f", "#a9b59a", "#d8cdb0"]) if side == "front" else None,
                               shutters=door_paint if (side == "front" and door_paint) else None))
        # lantern on a bracket beside the door
        lp, out = sh.at("front", door_x + hx + 0.62, 2.0, 0.04)
        br = m.piece(color=TP["iron"], gloss=80, merge="deco", res=0.007, detail=0.3)
        br.add(Tube([lp, lp + out * 0.15 + np.array([0, 0.05, 0]), lp + out * 0.27], 0.013, samples=4))
        light = KP.hanging_lantern(m, T(lp + out * 0.27), merge="deco", glass="glass", drop=0.08, size=0.85)
        m.socket("light_0", None, light)
        # stovepipe through the back slope -> chimney socket
        cx, cz = (hx * 0.45, -hz * 0.45) if ridge_dir == "x" else (-hx * 0.45, -hz * 0.4)
        smoke = stovepipe(m, "roof", (cx, sh.roof_y(cx, cz) - 0.12, cz), 0.95, lean=(rng.normal() * 0.08, -0.06), bends=1)
        m.socket("chimney", None, smoke)
        for i, w in enumerate(wins):
            m.socket(f"win_{i}", None, w)
        # --- lean-to store on the right (open toward the front), single-slope tin roof
        if lean_to:
            lx0, lx1 = hx + 0.02, min(x1 - 0.12, hx + 1.35)
            lz0, lz1 = -hz + 0.05, hz * 0.55
            vboard_wall(m, "walls", (lx1, lz1), (lx1, lz0), 0.0, 1.65, (1, 0, 0), [TP["wood"], TP["wood_dk"], TP["wood_silver"]], replace=0.18,
                        battens=False)
            vboard_wall(m, "walls", (lx1, lz0), (lx0, lz0), 0.0, lambda s: 1.65 + 0.45 * s / (lx1 - lx0), (0, 0, -1),
                        [TP["wood"], TP["wood_dk"], TP["wood_silver"]], replace=0.18, battens=False)
            post(m, "trim", (lx1, 0.0, lz1), (lx1, 1.72, lz1), 0.05, TP["wood_dk"], detail=0.4)
            tin_roof(m, "roof", (lx1 + 0.25, 1.68, lz1 + 0.3), (lx1 + 0.25, 1.68, lz0 - 0.25), (lx0, 2.15, lz1 + 0.3), (lx0, 2.15, lz0 - 0.25),
                     rust=0.6, sag=0.03, patch=0.3)
            KP.crab_pot(m, T(((lx0 + lx1) / 2, 0.0, lz0 + 0.5), 88), merge="props", net="net", size=(0.7, 0.34, 0.6))
            KP.crab_pot(m, T(((lx0 + lx1) / 2, 0.344, lz0 + 0.5), 95), merge="props", net="net", size=(0.7, 0.34, 0.6))
            TB.oar(m, "props", ((lx0 + lx1) / 2 - 0.25, 0.02, lz1 - 0.1), ((lx0 + lx1) / 2 - 0.35, 1.55, lz0 + 0.35))
        # --- dressing: buoys hung on the left wall, life ring, pots, barrel, rope, fish box, net over the rail
        for i in range(3):
            bp, out = sh.at("left", 0.45 + i * 0.42, 1.75 - (i % 2) * 0.12, 0.13)
            if i == 1:
                KP.glass_float(m, T(bp + np.array([0, -0.05, 0]), -90), "props", r=0.11)
            else:
                KP.painted_buoy(m, T(bp, -90), "props", size=1.1)
            nail = bp + np.array([0, 0.26, 0]) - out * 0.1
            KP.laid_rope(m, "props", [nail, bp + np.array([0, 0.2, 0]) + out * 0.02], 0.008, detail=0.3)
        KP.life_ring(m, T((x0 + 0.08, 0.7, (hz + z1) / 2 - 0.1), -90), merge="props")
        KP.crab_pot_stack(m, T((x1 - 0.55, 0.0, z1 - 0.6), 12 + rng.normal() * 8), merge="props", net="net", n=2)
        KP.barrel(m, T((x0 + 0.42, 0.0, hz + 0.45), 20), merge="props", h=0.76, r=0.24)
        KP.rope_coil(m, T((x0 + 0.65, 0.0, z1 - 0.45), rng.uniform(0, 360)), merge="props")
        KP.fish_crate(m, T((x1 - 0.6, 0.0, hz + 0.35), -8), merge="props")
        if net_side is not None:
            sx = 1 if net_side == "right" else -1
            KP.net_rack(m, T((sx * (x1 - 0.35 if sx > 0 else -x0 - 0.35), 0.0, (z0 + (-hz)) / 2), 90), merge="props", net="net", width=1.0, h=1.6)
        # ladder down the side to the water
        lxl = x1 + 0.08
        for s in (-1, 1):
            post(m, "floor", (lxl, 0.6, z0 + 0.9 + s * 0.22), (lxl + 0.06, sea - 0.3, z0 + 0.9 + s * 0.22), 0.03, TP["wood_dk"], detail=0.4)
        for y in np.arange(sea - 0.1, 0.3, 0.32):
            post(m, "floor", (lxl + 0.03, y, z0 + 0.66), (lxl + 0.03, y, z0 + 1.14), 0.02, TP["wood"], square=False, detail=0.3)
        m.socket("porch", None, (0.0, 0.0, z1 - 0.4))
        return m
    fn.__name__ = name
    return fn


with_calm = TB.calmed
MODELS["town/stilt_shack_a"] = with_calm(stilt_shack("stilt_shack_a", hx=2.0, hz=1.7, eave=2.3, ridge=3.45, ridge_dir="x", walls="v",
                                                     paint=VP["slate"], trim=TP["cream"], door_paint=TP["mustard"], roof="tin",
                                                     plat=(-2.6, 3.65, -2.3, 3.0), lean_to=True, budget=30000), jitter=0.8)
MODELS["town/stilt_shack_b"] = with_calm(stilt_shack("stilt_shack_b", hx=1.6, hz=1.85, eave=2.2, ridge=3.7, ridge_dir="z", walls="v",
                                                     paint=None, trim=TP["mustard"], door_paint=TP["red"], roof="shake",
                                                     roof_colors=[TP["wood_dk"], TP["wood"], "#5f5a52"], plat=(-2.2, 2.2, -2.45, 3.15),
                                                     budget=28000, net_side=None), jitter=0.85)
MODELS["town/stilt_shack_c"] = with_calm(stilt_shack("stilt_shack_c", hx=2.15, hz=1.6, eave=2.25, ridge=3.4, ridge_dir="x", walls="h",
                                                     paint=VP["sage"], trim=TP["white"], door_paint=TP["red"], roof="tin",
                                                     roof_colors=[TP["red"], TP["red_dk"], TP["rust"]], plat=(-2.75, 2.75, -2.4, 2.95),
                                                     budget=30000, peel=0.3), jitter=0.75)
# the east-shore shack stands lower (floor 1.3 above the water) so its porch meets the lighthouse walk
MODELS["town/stilt_shack_d"] = with_calm(stilt_shack("stilt_shack_d", hx=1.9, hz=1.65, eave=2.25, ridge=3.5, ridge_dir="z", walls="v",
                                                     paint="#86453a", trim=TP["wood_lt"], door_paint=TP["teal"], roof="tin",
                                                     plat=(-2.5, 2.5, -2.3, 2.9), sea=-1.3, bottom=-4.6, budget=28000, lean_to=False),
                                         jitter=0.8)


# ----------------------------------------------------------------------------------------------------------------
# rowboats


class Moved(Prim):
    """Wrap a primitive: world = R @ local + off."""

    def __init__(self, inner, off=(0, 0, 0), R=None):
        super().__init__()
        self.inner = inner
        self.o = np.asarray(off, float)
        self.Rm = np.eye(3) if R is None else np.asarray(R, float)

    def sdf(self, P):
        return self.inner((P - self.o) @ self.Rm)

    def bounds(self):
        lo, hi = self.inner.bounds()
        lo, hi = np.maximum(lo, -1e4), np.minimum(hi, 1e4)
        Cc = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        W = Cc @ self.Rm.T + self.o
        return W.min(0), W.max(0)


def xform_since(m, n0, R, off):
    """Rigidly move every op of the pieces created since index n0: world = R @ p + off."""
    for p in m.pieces[n0:]:
        for op in p.ops:
            op.prim = Moved(op.prim, off, R)


HL, HB, HD, HT = 1.48, 0.66, 0.44, 0.035    # half length, half beam, depth, plank thickness -> a ~3 m clinker boat


def _boat(m, hull_c, stripe_c, bottom_c, name_seed, oars="in", water=None, bilge=False):
    """Upright rowboat, keel bottom at y = 0, bow +Z. Returns gunwale height."""
    rng = m.rng
    gun = np.array([0.0, HD, 0.0])
    hull = KT.Rowboat(gun, HL, HB, HD, None, HT)

    def outer(P):
        return hull.outer(P - gun)
    p = m.piece(color=TP["wood_br"], gloss=45, merge="hull", res=0.011, lumps=0.0025, dents=7, dent_size=0.04, dent_depth=0.004, mottle=0.1)
    p.add(hull)
    # transom board closing the stern
    p.add(Func(lambda P: np.maximum(outer(P), np.maximum(np.abs(P[:, 2] + HL * 0.98 - HT * 0.5) - HT * 0.6, P[:, 1] - HD)),
               (-HB, -0.05, -HL - 0.05), (HB, HD + 0.02, -HL + 0.2)), k=0.006)
    # clinker laps: shallow steps painted a shade darker along the outside
    on_out = Func(lambda P: -(outer(P) + HT * 0.45), (-9,) * 3, (9,) * 3)
    p.paint(on_out, hull_c, feather=0.006)
    for yy in (0.13, 0.22, 0.31):
        p.paint(Func(lambda P, yy=yy: np.maximum(np.abs(P[:, 1] - yy - 0.012 * np.sin(P[:, 2] * 2.0)) - 0.009, -(outer(P) + HT * 0.45)),
                     (-9,) * 3, (9,) * 3), shade(hull_c, 0.7), feather=0.004)
    p.paint(Func(lambda P: np.maximum(-(outer(P) + HT * 0.45), np.abs(P[:, 1] - (HD - 0.06)) - 0.04), (-9,) * 3, (9,) * 3), stripe_c, feather=0.006)
    p.paint(Func(lambda P: np.maximum(-(outer(P) + HT * 0.45), P[:, 1] - (0.09 + 0.02 * np.sin(P[:, 2] * 3))), (-9,) * 3, (9,) * 3), bottom_c,
            feather=0.01)
    # paint worn off: patches of bare grey wood on the outside, a bow name blob
    p.paint(Func(lambda P: np.maximum(-(outer(P) + HT * 0.45), (0.4 - fbm(P * 3.5, 2, name_seed)) * 0.06), (-9,) * 3, (9,) * 3),
            mix(hull_c, TP["wood_silver"], 0.55), feather=0.005)
    p.paint(Func(lambda P: np.maximum(-(outer(P) + HT * 0.45), np.maximum(np.abs(P[:, 1] - (HD - 0.17)) - 0.035, np.abs(P[:, 2] - HL * 0.6) - 0.17)),
                 (-9,) * 3, (9,) * 3), TP["cream"], feather=0.004)
    # keel strip, stem post (after the paints so they stay bare timber)
    p.add(Tube([(0, 0.02, -HL * 0.96), (0, -0.01, 0.0), (0, 0.06, HL * 0.82), (0, HD * 0.8, HL * 1.02), (0, HD + 0.1, HL * 1.04)],
               [0.035, 0.04, 0.04, 0.035, 0.03], samples=4), k=0.015, color=TP["wood_dk"])
    # gunwale rails
    for sx in (-1, 1):
        pts = [(0.0, HD + 0.01, -HL * 0.98), (sx * HB * 0.84, HD + 0.005, -HL * 0.65), (sx * HB * 1.0, HD, 0.0), (sx * HB * 0.66, HD + 0.02, HL * 0.62),
               (0.0, HD + 0.07, HL * 1.0)]
        p.add(Tube(pts, 0.03, samples=5), k=0.01, color=shade(TP["wood_dk"], 1.05))
    # thwarts + stern seat
    for z, w in ((-0.55, 0.2), (0.25, 0.2)):
        bw = HB * (1 - 0.55 * (z / HL) ** 4 if z < 0 else (1 - (z / HL) ** 2) ** 0.6) - 0.04
        board(m, "inside", (-bw, HD - 0.12, z), (bw, HD - 0.12, z), w, 0.04, (0, 1, 0), TP["wood"], nails=2, detail=0.5)
    board(m, "inside", (-0.28, HD - 0.14, -HL * 0.83), (0.28, HD - 0.14, -HL * 0.83), 0.3, 0.04, (0, 1, 0), TP["wood_lt"], nails=1, detail=0.4)
    # bottom boards
    deck(m, "inside", -0.24, 0.24, -1.0, 0.95, 0.085, along="z", pw=(0.11, 0.14), t=0.025, nails=0, detail=0.4, overhang=0.0)
    # oarlocks
    ol = m.piece(color=TP["iron"], gloss=90, merge="inside", res=0.005, lumps=0.0008, detail=0.3)
    for sx in (-1, 1):
        c = np.array([sx * (HB * 0.985), HD + 0.05, -0.2])
        ol.add(Capsule(c - (0, 0.05, 0), c + (0, 0.03, 0), 0.012))
        ol.add(Torus(c + (0, 0.05, 0), 0.03, 0.009, euler((0, 0, 90))), k=0.004)
    # oars: shipped inside along the thwarts, or out on the gunwales
    if oars == "in":
        for sx in (-1, 1):
            a = np.array([sx * 0.2, HD - 0.07, -HL * 0.8])
            b = np.array([sx * 0.28, HD - 0.05, HL * 0.55])
            TB.oar(m, "inside", b, a, blade_color=stripe_c)
    elif oars == "out":
        for sx in (-1, 1):
            c = np.array([sx * HB * 0.985, HD + 0.06, -0.2])
            TB.oar(m, "inside", c + np.array([sx * 1.25, -0.5, 0.25]), c + np.array([-sx * 0.55, 0.12, -0.12]), blade_color=stripe_c)
    # a bit of clutter inside: bailer, rope, rainwater
    KP.rope_coil(m, T((0.08, 0.1, 0.85), 30), merge="inside", r0=0.04, turns=2.5, rr=0.022, tail=0.25)
    bl = m.piece(color=TP["tin"], gloss=80, merge="inside", res=0.006, detail=0.3)
    bl.add(Cylinder((-0.18, 0.16, -0.95), 0.09, 0.07, euler((10, 0, 8)), round=0.01))
    bl.sub(Cylinder((-0.18, 0.2, -0.95), 0.075, 0.07, euler((10, 0, 8))), k=0.005)
    if bilge:
        w = m.piece(color="#4d5b55", gloss=230, merge="inside", res=0.012, lumps=0.001, detail=0.3, ao=False)
        w.add(Func(lambda P: np.maximum(np.maximum(outer(P) + HT * 1.2, P[:, 1] - 0.13), 0.06 - P[:, 1]), (-HB, 0.0, -HL), (HB, 0.15, HL)))
    # painter rope from the bow ring
    br_ = np.array([0, HD + 0.06, HL * 0.98])
    ring = m.piece(color=TP["iron"], gloss=80, merge="inside", res=0.005, detail=0.2)
    ring.add(Torus(br_, 0.03, 0.008, euler((90, 0, 0))))
    return HD


def rowboat_afloat():
    """Origin at the keel bottom; float it at y ~ -0.18 (waterline ~0.2 m up the hull). Painter rope runs off the bow."""
    m = TownModel("rowboat", budget=5200)
    _boat(m, TP["teal"], TP["cream"], TP["red_dk"], 11, oars="in", bilge=True)
    laid = KP.laid_rope(m, "inside", [(0, HD + 0.06, HL * 0.98), (0.05, HD - 0.05, HL * 1.25), (0.1, 0.12, HL * 1.55), (0.12, 0.2, HL * 1.9)], 0.012,
                        detail=0.3)
    m.socket("bow", None, (0, HD + 0.06, HL * 0.98))
    return m


def rowboat_red():
    m = TownModel("rowboat_red", budget=5200)
    _boat(m, "#9a5246", TP["white"], "#3d3a37", 23, oars="out", bilge=True)
    m.socket("bow", None, (0, HD + 0.06, HL * 0.98))
    return m


def rowboat_beached():
    """Heeled over ~11 degrees, resting on the sand (origin = ground contact under the keel). Oars inside."""
    m = TownModel("rowboat_beached", budget=5200)
    n0 = len(m.pieces)
    _boat(m, TP["mustard"], TP["navy"], "#6b3a2c", 37, oars="in")
    R = euler((0, 0, 11)) @ euler((-3, 0, 0))
    xform_since(m, n0, R, (0, 0.035, 0))
    # sand mounded against the low side + a strand of weed
    s = m.piece(color="#c4ad86", gloss=20, merge="sand", res=0.02, lumps=0.012, lump_freq=5, detail=0.4)
    s.add(Ellipsoid((-0.45, -0.05, 0.1), (0.45, 0.11, 1.3)), k=0.0)
    s.add(Ellipsoid((0.0, -0.06, 0.0), (0.5, 0.08, 1.4)), k=0.1)
    s.paint(patches(3, 0.2, 4), "#b39d78", feather=0.02)
    return m


def rowboat_upturned():
    """Keel up on two log chocks (winter storage / being painted); barnacled, peeling white and blue."""
    m = TownModel("rowboat_upturned", budget=5000)
    n0 = len(m.pieces)
    _boat(m, TP["white"], VP["slate"], "#2f4a4c", 51, oars=None)
    R = euler((0, 0, 180))
    xform_since(m, n0, R, (0, HD + 0.2 + 0.06, 0))
    # chocks
    for z in (-0.8, 0.7):
        post(m, "chocks", (-0.75, 0.13, z), (0.75, 0.13, z + 0.04), 0.12, TP["wood_dk"], square=False, detail=0.5)
    # barnacle crust on the bottom (now on top)
    bc = m.piece(color=TP["barnacle"], gloss=50, merge="hull_b", res=0.008, lumps=0.003, lump_freq=20, detail=0.5)
    rng = m.rng
    hullp = m.pieces[n0]
    for i in range(26):
        z = rng.uniform(-1.1, 1.0)
        x = float(np.clip(rng.normal() * 0.2, -0.45, 0.45))
        y = KP.surface_y(hullp, x, z, HD + 0.6, 0.2)
        bc.add(Ellipsoid((x, y - 0.004, z), (0.025, 0.018, 0.025)), k=0.006)
    # a pair of oars laid against it, a paint tin
    TB.oar(m, "props", (0.9, 0.02, -0.9), (0.62, 0.62, 0.7), blade_color=VP["slate"])
    can = m.piece(color=VP["slate"], gloss=80, merge="props", res=0.006, detail=0.3)
    can.add(Cylinder((0.95, 0.09, 0.85), 0.085, 0.09, round=0.01))
    can.paint(band(0.06, 0.13), TP["white"])
    return m


MODELS["town/rowboat"] = rowboat_afloat
MODELS["town/rowboat_red"] = rowboat_red
MODELS["town/rowboat_beached"] = rowboat_beached
MODELS["town/rowboat_upturned"] = rowboat_upturned


# ----------------------------------------------------------------------------------------------------------------
# boardwalk pieces with an opening in a side rail (same kit dimensions as town_pier: 4 m x 2.4 m, deck top y = 0)


def boardwalk_branch(name, full_rail=None, budget=3000, gap=1.22):
    """4 m straight with a 2.44 m opening (z -gap..gap) in the +X rail; full_rail=-1 also rails the -X side."""
    def fn():
        m = TownModel(name, budget=budget)
        _deck_cross(m, -1.2, 1.2, -2.0, 2.0, 0.0)
        _structure(m, -1.2, 1.2, -2.0, 2.0, -0.08)
        _rails(m, [(1.12, 0, -2.0), (1.12, 0, -gap)], end_post=True)
        _rails(m, [(1.12, 0, gap), (1.12, 0, 2.0)], end_post=False)
        if full_rail:
            _rails(m, [(-1.12, 0, -2.0), (-1.12, 0, 2.0)], end_post=False)
        return m
    return fn


MODELS["town/boardwalk_branch1"] = boardwalk_branch("boardwalk_branch1")
MODELS["town/boardwalk_branch2"] = boardwalk_branch("boardwalk_branch2", full_rail=-1)


# ----------------------------------------------------------------------------------------------------------------
# yard clutter


def washing_line():
    m = TownModel("washing_line", budget=2600)
    TB.washing_line(m, "deco", (-2.0, 0.0, 0.0), (2.0, 0.0, 0.15), h=1.85)
    return m


def woodpile():
    m = TownModel("woodpile", budget=2600)
    TB.woodpile(m, "props", T((0, 0, -0.3), 90), L=1.5, rows=4)
    return m


def _dried_fish(m, merge, top, rng, length=0.34):
    """A split, salted fish hung by the tail from `top` (head down)."""
    col = KP.pick(rng, ["#b9a27a", "#a8906a", "#c4ae86", "#9c8461"])
    p = m.piece(color=col, gloss=60, merge=merge, res=0.006, lumps=0.003, lump_freq=12, mottle=0.12, detail=0.6)
    top = np.asarray(top, float)
    yaw = rng.uniform(-25, 25)
    R = euler((rng.normal() * 4, yaw, rng.normal() * 6))
    tail = top + R @ np.array([0, -0.05, 0])
    body = top + R @ np.array([0, -0.06 - length * 0.55, 0])
    head = top + R @ np.array([0, -0.06 - length, 0])
    p.add(Ellipsoid(tail, (0.06, 0.05, 0.008), R))
    p.add(Capsule(tail, body, 0.014, 0.05), k=0.02)
    p.add(Capsule(body, head, 0.05, 0.03), k=0.02)
    p.add(Ellipsoid(body, (0.06, length * 0.4, 0.016), R), k=0.02)
    p.paint(Func(lambda P, c=body, n=R[:, 2]: -((P - c) @ n) - 0.004, (-9,) * 3, (9,) * 3), shade(col, 0.72), feather=0.01)  # dark skin side
    p.paint(Ellipsoid(head, (0.04, 0.04, 0.03), R), shade(col, 0.6), feather=0.01)
    s = m.piece(color=TP["rope_dk"], merge=merge, res=0.004, detail=0.2)
    s.add(Capsule(top + np.array([0, 0.03, 0]), tail, 0.006))


def fish_rack():
    """Driftwood trestles with two poles of salted fish drying in the wind (2.6 m long)."""
    m = TownModel("fish_rack", budget=3600)
    rng = m.rng
    for x in (-1.2, 1.2):
        for sz in (-1, 1):
            post(m, "frame", (x + rng.normal() * 0.03, -0.05, sz * 0.5), (x, 1.75, sz * 0.04), 0.045, KP.pick(rng, [TP["wood"], TP["wood_dk"], "#9a948a"]),
                 square=False, detail=0.6)
        post(m, "frame", (x, 0.55, -0.36), (x, 0.55, 0.36), 0.03, TP["wood_dk"], square=False, detail=0.3)
    for y, z in ((1.72, 0.0), (1.28, 0.2)):
        post(m, "frame", (-1.45, y, z), (1.45, y - 0.02, z), 0.035, KP.pick(rng, [TP["wood_lt"], "#a39b8c"]), square=False, detail=0.6)
    for y, z, n in ((1.72, 0.0, 9), (1.28, 0.2, 7)):
        for i in range(n):
            x = -1.05 + 2.1 * (i + 0.5) / n + rng.normal() * 0.03
            _dried_fish(m, "fish", (x, y - 0.03, z + rng.normal() * 0.02), rng, length=rng.uniform(0.28, 0.4))
    # a basket of salt and a fish box underneath
    KP.fish_crate(m, T((0.4, 0.0, 0.05), 6), merge="props")
    return m


def wall_buoys():
    """Buoys and a glass float hung from pegs on a weathered plank; origin = back of the plank (the wall) at its centre,
    hangs toward +Z. Put it on a wall about 1.9 m up."""
    m = TownModel("wall_buoys", budget=2400)
    rng = m.rng
    board(m, "props", (-0.6, 0.0, 0.03), (0.6, 0.0, 0.03), 0.16, 0.04, (0, 0, 1), TP["wood_silver"], nails=2, detail=0.6)
    for i, x in enumerate((-0.42, 0.0, 0.4)):
        peg = np.array([x, 0.02, 0.1])
        post(m, "props", peg - (0, 0, 0.06), peg, 0.012, TP["wood_dk"], square=False, detail=0.2)
        drop = rng.uniform(0.15, 0.35)
        if i == 1:
            top = KP.glass_float(m, T(peg + np.array([0, -drop - 0.13, 0.03])), "props", r=0.11)
        else:
            top = KP.painted_buoy(m, T(peg + np.array([0, -drop - 0.24, 0.04]), rng.uniform(-20, 20)), "props", size=1.15)
        KP.laid_rope(m, "props", [peg, (np.asarray(top) + peg) / 2 + np.array([0, 0, 0.01]), top], 0.008, detail=0.2)
    return m


def retaining_wall():
    """4 m of dry-stone terrace wall, top at y = 0.25, buried to y = -1.0 (origin = top-front centre line, face +Z)."""
    m = TownModel("retaining_wall", budget=3200)
    TB.stone_wall(m, "stone", (-2.0, -0.18), (2.0, -0.18), -1.0, 0.25, thick=0.45, stone=(0.4, 0.24))
    gr = m.piece(color=TP["grass"], gloss=20, merge="stone", res=0.02, lumps=0.01, lump_freq=6, detail=0.4)
    gr.add(Box((0, 0.27, -0.25), (2.0, 0.05, 0.16), round=0.04))
    gr.paint(patches(3, 0.2, 5), TP["moss"], feather=0.02)
    return m


def picket_fence():
    """3 m of crooked picket fence (origin = base centre), runs along X."""
    m = TownModel("picket_fence", budget=2200)
    rng = m.rng
    for x in (-1.5, 0.0, 1.5):
        post(m, "fence", (x, -0.15, 0), (x + rng.normal() * 0.02, 1.0, rng.normal() * 0.02), 0.045, TP["wood_dk"], detail=0.5)
    for y in (0.3, 0.75):
        board(m, "fence", (-1.55, y, 0.05), (1.55, y + rng.normal() * 0.03, 0.05), 0.08, 0.03, (0, 0, 1), TP["wood"], nails=2, detail=0.5)
    x = -1.42
    while x < 1.45:
        if rng.random() > 0.1:
            h = rng.uniform(0.85, 1.0)
            board(m, "fence", (x, 0.05, 0.085), (x + rng.normal() * 0.02, h, 0.085), 0.075, 0.022, (0, 0, 1),
                  KP.pick(rng, [TP["white"], TP["cream"], TP["wood_silver"]]), nails=0, detail=0.4, ends=(0.03, -0.03))
        x += rng.uniform(0.13, 0.16)
    return m


MODELS["town/washing_line"] = washing_line
MODELS["town/woodpile"] = woodpile
MODELS["town/fish_rack"] = fish_rack
MODELS["town/wall_buoys"] = wall_buoys
MODELS["town/retaining_wall"] = retaining_wall
MODELS["town/picket_fence"] = picket_fence


# ----------------------------------------------------------------------------------------------------------------
# lighter copies of the common clutter props (town_props builders, smaller budgets, own seeds) for the many extra
# instances scattered along the shore and the hillside lanes


def _lo(pid, budget):
    import town_props as TPR
    fn = getattr(TPR, "_" + pid)

    def build():
        m = TownModel(pid + "_lo", budget=budget)
        fn(m)
        return m
    build.__name__ = pid + "_lo"
    MODELS[f"town/{pid}_lo"] = build


for _pid, _b in (("crate", 1800), ("barrel", 2000), ("crab_pot_stack", 2600), ("flower_pot", 1600), ("lantern_post", 2600),
                 ("bench", 2200), ("rope_coil", 1800), ("fish_crate", 2000), ("buoy_cluster", 2200), ("mailbox", 2000)):
    _lo(_pid, _b)


# ----------------------------------------------------------------------------------------------------------------
# a little tarred smokehouse for the gap behind the street (one more chimney puffing over the roofs)


def smokehouse():
    m = TownModel("smokehouse", budget=13000)
    rng = m.rng
    mg = dict(trim="trim", glass="glass", deco="deco", door="trim")
    hx, hz, eave, ridge = 1.15, 0.95, 1.95, 2.75
    ops = {"front": [(hx - 0.42, hx + 0.42, -1, 1.75)], "right": [(hz - 0.25, hz + 0.25, 1.3, 1.6)]}
    sh = Shack(m, hx, hz, eave, ridge, ridge="x", walls="v", colors=[TP["wood_tar"], "#57504a", TP["wood_dk"]], paint=None, trim=TP["wood_dk"],
               openings=ops, roof="tin", rust=0.7, sag=0.06, ov=0.3, ov_gable=0.3, lean=0.012)
    deck(m, "floor", -hx, hx, -hz, hz, 0.06, along="x", nails=0, detail=0.3)
    dc, out = sh.at("front", hx, 0.0, 0.0)
    door(m, mg, dc, out, 0.78, 1.7, color=TP["wood_tar"], peel=0.0, knob=False, crooked=-2.0)
    m.socket("door", None, dc + out * 0.12)
    # louvred vent box on the ridge + a stovepipe -> chimney
    v = m.piece(color=TP["wood_dk"], merge="roof", res=0.012, lumps=0.003, detail=0.5)
    v.add(Box((-0.3, ridge + 0.18, 0.0), (0.28, 0.16, 0.22), round=0.03))
    v.add(Box((-0.3, ridge + 0.38, 0.0), (0.38, 0.03, 0.32), euler((0, 0, 0)), round=0.02), k=0.01, color=TP["tin_dk"])
    for k in range(3):
        v.sub(Box((-0.3, ridge + 0.13 + k * 0.08, 0.23), (0.22, 0.015, 0.05)), k=0.005, color=TP["iron"])
    smoke = stovepipe(m, "roof", (0.55, sh.roof_y(0.55, -0.45) - 0.1, -0.45), 0.85, r=0.065, lean=(0.06, -0.04))
    m.socket("chimney", None, smoke)
    m.socket("chimney_vent", None, (-0.3, ridge + 0.45, 0.0))
    # soot on the walls under the eaves, a little window glow
    w = window(m, mg, *sh.at("right", hz, 1.45, 0.02), 0.42, 0.28, frame_color=TP["wood_dk"], panes=(1, 1), glass_color="#7a6a52")
    m.socket("win_0", None, w)
    # dressing: split logs, a fish box, a stool, a bucket of brine
    TB.woodpile(m, "props", T((-hx - 0.5, 0.0, -0.1), 0), L=1.4, rows=3)
    KP.fish_crate(m, T((0.75, 0.0, hz + 0.45), 12), merge="props")
    KP.barrel(m, T((hx + 0.35, 0.0, hz - 0.2), 0), merge="props", h=0.6, r=0.22, lid=False)
    return m


MODELS["town/smokehouse"] = TB.calmed(smokehouse, jitter=0.8)
