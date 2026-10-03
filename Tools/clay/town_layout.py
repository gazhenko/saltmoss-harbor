"""
Generate Game/Assets/Saltmoss/Data/town_layout.json — every placed set piece of Saltmoss Harbor plus gameplay anchors.

World frame = Unity: x right, y up, z forward (+Z = open sea, -Z = land), metres, sea level y = 0. yaw in degrees
(Quaternion.Euler(0, yaw, 0): yaw 90 turns a model's +Z front toward world +X).

  Tools/.venv/bin/python Tools/clay/town_layout.py [--check]

Ground heights come from the terrain heightmap (models/town_terrain.py); light anchors come from the sockets of the
built models (light_*, win_*, lamp), so rebuild models before regenerating.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
sys.path[:0] = [HERE, os.path.join(HERE, "models")]
from clay import read_claymesh, euler  # noqa: E402
import town_terrain as TT  # noqa: E402

MODELS = os.path.join(ROOT, "Game/Assets/Saltmoss/Models")
OUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Data/town_layout.json")
DECK = 1.8

inst = []
anchors = {}
_sock_cache = {}


def R(yaw):
    return euler((0, yaw, 0))


def world(pos, yaw, local):
    return (np.asarray(pos, float) + R(yaw) @ np.asarray(local, float)).tolist()


def sockets(model):
    if model not in _sock_cache:
        p = os.path.join(MODELS, model + ".claymesh")
        _sock_cache[model] = {s[0]: (np.array(s[2]), s[3]) for s in read_claymesh(p)["sockets"]} if os.path.exists(p) else {}
    return _sock_cache[model]


def gy(x, z, off=0.0):
    return round(float(TT.height(x, z)) + off, 3)


def add(model, pos, yaw=0.0, collide="box", tag="", scale=1.0):
    pos = [round(float(v), 3) for v in pos]
    inst.append(dict(model=model, pos=pos, yaw=round(float(yaw), 2), scale=scale, collide=collide, tag=tag))
    return pos


def sock_world(model, pos, yaw, name, scale=1.0):
    s = sockets(model).get(name)
    if s is None:
        return None
    return [round(v, 3) for v in world(pos, yaw, s[0] * scale)]


def anchor(name, pos, yaw=0.0):
    anchors[name] = dict(pos=[round(float(v), 3) for v in pos], yaw=round(float(yaw), 2))


def sock_anchor(name, model, place, sock, fallback_local, yaw_off=0.0, out=0.0):
    """Anchor at a model socket (pushed `out` metres along the socket's facing), else at a local fallback point."""
    pos, yaw = place
    s = sockets(model).get(sock)
    if s is not None:
        q = s[1]
        # socket facing: +Z of the socket rotation
        x, y, z, w = q
        fz = np.array([2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)])
        local = s[0] + fz * out
        local[1] = s[0][1]
        anchor(name, world(pos, yaw, local), yaw + yaw_off)
    else:
        anchor(name, world(pos, yaw, fallback_local), yaw + yaw_off)


# =================================================================================================================
# waterfront: seawall, pier, platforms, berth

for x in np.arange(-14.5, 19.0, 4.0):
    add("town/seawall", (x, TT.STREET_Y + 0.03, -9.0), 0, "mesh", "quay")

PIER = [  # (z centre, model, yaw)
    (-7, "town/boardwalk_rail2", 0), (-3, "town/boardwalk_rail1", 0), (1, "town/boardwalk_rail1", 0), (5, "town/boardwalk_rail2", 0),
    (9, "town/boardwalk_rail2", 0), (13, "town/boardwalk_rail2", 0), (17, "town/boardwalk_rail1", 180), (21, "town/boardwalk_rail2", 0),
    (25, "town/boardwalk_gap", 0), (29, "town/boardwalk_rail2", 0),
]
for z, mdl, yaw in PIER:
    add(mdl, (0, DECK, z), yaw, "mesh", "pier")
add("town/pier_head", (0, DECK, 35), 0, "mesh", "pier")
add("town/pier_platform", (3.2, DECK, 17), 0, "mesh", "pier")
add("town/gangway", (1.2, DECK, 25), 90, "mesh", "berth")
add("town/floating_dock", (5.8, 0.5, 25), 0, "mesh", "berth")
add("town/crane", (3.4, DECK, 17.6), 35, "box", "crane")
anchor("boat_berth", (9.0, 0.0, 25.0), 0)
anchor("boat_board_point", (6.65, 0.5, 25.0), 90)

# ladders + bollards on the pier
add("town/ladder", (-1.25, DECK, 11.0), -90, "box", "pier")
add("town/ladder", (4.0, DECK, 39.05), 0, "box", "pier")
for p in ((-3.5, DECK, 38.3), (3.4, DECK, 38.3), (-3.5, DECK, 31.8), (4.7, 0.5, 21.0), (4.7, 0.5, 29.2)):
    add("town/bollard", p, 0, "box", "pier")

# =================================================================================================================
# buildings

SHOP = ((-5.8, DECK, 0.0), 90)
add("town/fish_shop", SHOP[0], SHOP[1], "mesh", "shop")
sock_anchor("shop_counter", "town/fish_shop", SHOP, "serve", (0, 0.25, 0.85))   # Pip serves from the step, facing customers
anchor("nell_post", world(*SHOP, (-1.4, 0.25, 0.75)), SHOP[1] + 15)
counter_front = world(*SHOP, (0.3, 0.0, 2.45))
QUEUE = [counter_front, world(*SHOP, (1.3, 0, 3.4)), [-0.1, DECK, -1.6], [-0.1, DECK, -3.0], [-0.1, DECK, -4.4], [-0.1, DECK, -5.8]]
anchors["queue"] = [[round(v, 3) for v in q] for q in QUEUE]
anchor("pip_shop_door", world(*SHOP, (3.4, 0, 0.78)), SHOP[1] - 90)

OFFICE = ((8.2, DECK, -5.0), 180)
add("town/harbor_office", OFFICE[0], OFFICE[1], "mesh", "office")
sock_anchor("walter_post", "town/harbor_office", OFFICE, "walter", (0.85, 0.0, 1.15))   # inside, behind the window counter
sock_anchor("walter_counter", "town/harbor_office", OFFICE, "counter", (0.9, 0.0, 2.55), 180, out=0.0)
anchor("board", world(*OFFICE, (-2.15, 0.0, 4.6)), OFFICE[1] + 180)      # stand here (on the promenade) to read the forecast board

PIP = ((21.3, DECK, 8.2), -90)
add("town/pip_house", PIP[0], PIP[1], "mesh", "pip_house")
sock_anchor("pip_door", "town/pip_house", PIP, "door", (0.0, 0.0, 1.9), 0, out=0.0)
anchor("player_spawn", world(*PIP, (0.0, 0.0, 2.6)), PIP[1])

# east boardwalk: street -> north along x = 16 -> corner -> Pip's porch
for z in (-7, -3, 1, 5):   # the z = 1 piece has an opening in its east rail for the walk out to the east stilt shack
    add("town/boardwalk_rail2" if z != 1 else "town/boardwalk_branch2", (15.2, DECK, z), 0, "mesh", "boardwalk")
add("town/boardwalk_corner", (15.2, DECK, 8.2), -90, "mesh", "boardwalk")
add("town/boardwalk_short", (17.6, DECK, 8.2), 90, "mesh", "boardwalk")   # 2.4 m link to the porch

# plank promenade along the seawall (rail on the sea side, open to the street); openings where the pier, the office
# porch, the east boardwalk and (west end) the walk out to the west stilt shacks join
PZ = -10.3
for x0, x1, mdl in ((-17.2, -13.2, "town/boardwalk_branch1"), (-13.2, -9.2, "town/boardwalk_rail1"), (-9.2, -5.2, "town/boardwalk_rail1"),
                    (-5.2, -1.2, "town/boardwalk_rail1"), (-1.2, 1.2, "town/boardwalk_square"), (1.2, 5.2, "town/boardwalk_rail1"),
                    (5.2, 9.2, "town/boardwalk"), (9.2, 11.6, "town/boardwalk_square"), (11.6, 14.0, "town/boardwalk_short_rail1"),
                    (14.0, 16.4, "town/boardwalk_square"), (16.4, 20.4, "town/boardwalk_rail1")):
    add(mdl, ((x0 + x1) / 2, DECK, PZ), -90, "mesh", "promenade")

POST = ((-17.0, TT.STREET_Y, -14.6), 0)
add("town/post_office", POST[0], POST[1], "mesh", "post")
sock_anchor("marge_post", "town/post_office", POST, "counter", (0.0, 0.0, 2.3))

NET = ((-24.5, gy(-24.5, -7.5), -7.5), 60)
add("town/net_shed", NET[0], NET[1], "mesh", "net_shed")

MUS = ((-32.0, gy(-32.0, 7.5), 7.5), 155)
add("town/museum_hull", MUS[0], MUS[1], "mesh", "museum")
sock_anchor("museum_door", "town/museum_hull", MUS, "door", (-0.6, 0.0, 4.7), 180)
sock_anchor("inkwell_post", "town/museum_hull", MUS, "inkwell", (1.6, 0.65, 0.75))

COTTAGES = [("town/cottage_a", -6.0, -24.0, 8), ("town/cottage_b", 12.5, -27.5, -14), ("town/cottage_c", -23.5, -30.0, 18),
            ("town/cottage_a_teal", 27.0, -21.0, -32), ("town/cottage_b_chalk", 3.5, -39.0, 4)]   # second copies recoloured (town_village)
for mdl, x, z, yaw in COTTAGES:
    add(mdl, (x, gy(x, z), z), yaw + 180 * 0, "mesh", "cottage")

LH = ((71.0, gy(71.0, 40.0), 40.0), -130)
add("town/lighthouse", LH[0], LH[1], "mesh", "lighthouse")

anchor("harbor_mouth", (0.0, 0.0, 75.0), 0)
anchor("customer_spawn", (2.0, TT.STREET_Y, -14.5), 0)
anchors["customer_path"] = [[2.0, TT.STREET_Y, -14.5], [0.5, TT.STREET_Y, -11.0], [0.0, DECK, -8.5], [-0.1, DECK, -6.4]]
anchor("shelby_post", (-27.5, gy(-27.5, 0.5), 0.5), 30)
anchors["shelby_wander"] = dict(center=[-27.0, gy(-27.0, 2.0), 2.0], radius=6.0)


# =================================================================================================================
# set dressing

rng = np.random.default_rng(20261002)
EXCL = []   # (x, z, half_x, half_z, yaw) footprints nothing should be scattered into


def excl(x, z, hx, hz, yaw=0.0):
    EXCL.append((x, z, hx, hz, yaw))


def excluded(x, z, pad=0.0):
    for (cx, cz, hx, hz, yaw) in EXCL:
        a = math.radians(yaw)
        lx = (x - cx) * math.cos(a) - (z - cz) * math.sin(a)
        lz = (x - cx) * math.sin(a) + (z - cz) * math.cos(a)
        if abs(lx) < hx + pad and abs(lz) < hz + pad:
            return True
    return False


# footprints (buildings, walkways, the street, paths are handled by the path mask)
excl(-5.8, 0.0, 4.2, 4.6, 90)
excl(8.2, -5.0, 3.2, 3.4, 180)
excl(21.3, 8.2, 2.4, 2.6, -90)
excl(-17.0, -14.6, 3.6, 3.2)
excl(-24.5, -7.5, 3.4, 3.0, 60)
excl(-32.0, 7.5, 7.8, 5.2, 155)
for mdl, x, z, yaw in COTTAGES:
    excl(x, z, 4.0, 4.0, yaw)
excl(71.0, 40.0, 5.5, 5.5)
excl(0.0, 15.0, 1.6, 24.5)
excl(15.2, -1.0, 1.6, 9.0)
excl(1.6, -10.3, 19.0, 1.4)
excl(*TT.STREET[:1], 0, 0) if False else None
excl((TT.STREET[0] + TT.STREET[1]) / 2, (TT.STREET[2] + TT.STREET[3]) / 2, (TT.STREET[1] - TT.STREET[0]) / 2 + 0.5,
     (TT.STREET[3] - TT.STREET[2]) / 2 + 0.3)


def prop(model, x, z, yaw=None, y=None, collide="box", tag="prop", scale=1.0, sink=0.0):
    yaw = rng.uniform(0, 360) if yaw is None else yaw
    y = gy(x, z, -sink) if y is None else y
    return add(model, (x, y, z), yaw, collide, tag, scale)


# -- pier: lanterns, benches, barrels, pots, crates, buoys, life rings
for x, z, yaw in ((0.95, -5.5, -90), (-0.95, 6.5, 90), (0.95, 13.0, -90), (-0.95, 21.0, 90), (0.95, 30.5, -90)):
    add("town/lantern_post", (x, DECK, z), yaw, "box", "lantern")
for x, z, yaw in ((3.2, 37.6, 180), (-3.2, 37.6, 180), (-3.55, 34.0, 90)):
    add("town/lantern_post" if False else "town/bench", (x, DECK, z), yaw, "box", "bench")
add("town/lantern_post", (3.6, DECK, 32.3), -45, "box", "lantern")
add("town/lantern_post", (-3.6, DECK, 32.3), 45, "box", "lantern")
for (x, z, mdl, yaw) in ((2.8, 33.4, "town/crab_pot_stack", 15), (3.3, 35.2, "town/barrel", 0), (2.6, 35.6, "town/barrel", 40),
                         (-2.9, 35.9, "town/crate", 10), (-2.6, 36.4, "town/crate", -25), (-3.3, 32.6, "town/rope_coil", 0),
                         (1.6, 38.3, "town/fish_crate", 80), (-0.6, 38.4, "town/anchor", 160), (4.2, 15.6, "town/crate", 5),
                         (4.4, 16.3, "town/fish_crate", -15), (2.0, 18.6, "town/rope_coil", 0), (4.6, 18.4, "town/barrel", 0),
                         (-0.75, 9.6, "town/fish_crate", 92), (0.7, 2.5, "town/rope_coil", 0), (0.75, 26.6, "town/crate", 30)):
    add(mdl, (x, DECK, z), yaw, "box", "prop")
for (x, z, yaw) in ((4.07, 34.0, 90), (-4.07, 36.5, -90), (0.0, 39.0, 0)):
    add("town/buoy_cluster", (x, DECK + 0.9, z), yaw, "none", "prop")
for (x, z, yaw) in ((-1.17, 3.0, -90), (1.17, 11.0, 90), (3.9, 39.0, 0)):
    add("town/life_ring", (x, DECK + 0.78, z), yaw, "none", "prop")
add("town/fish_crate", (4.9, 0.5, 22.0), 10, "box", "prop")
add("town/crab_pot_stack", (5.0, 0.5, 28.4), -80, "box", "prop")
add("town/rope_coil", (6.2, 0.5, 26.5), 0, "box", "prop")

# -- quay street
for x in (-12.5, -3.0, 4.5, 14.5):
    add("town/lantern_post", (x, TT.STREET_Y, -15.7), 0, "box", "lantern")
for x, yaw in ((-9.0, 0), (11.8, 0), (-14.5, 20)):
    add("town/bench", (x, TT.STREET_Y, -10.0), yaw, "box", "bench")
for (x, z, mdl, yaw) in ((2.2, -10.4, "town/barrel", 0), (2.8, -10.0, "town/barrel", 30), (2.5, -10.9, "town/crate", 12), (-2.3, -10.3, "town/fish_crate", -8),
                         (-2.2, -10.4, "town/crate", 80), (13.4, -10.3, "town/crab_pot_stack", 5), (17.9, -14.8, "town/rope_coil", 0),
                         (-6.0, -15.6, "town/crate", 20), (-5.4, -15.8, "town/barrel", 0),
                         (-19.8, -11.0, "town/flower_pot", 0), (-14.2, -11.2, "town/flower_pot", 40), (-11.0, -15.6, "town/ice_chest", 10),
                         (0.4, -15.8, "town/flower_pot", 0), (6.9, -10.2, "town/mailbox", 180)):
    add(mdl, (x, TT.STREET_Y, z), yaw, "box", "prop")
add("town/sign_post", (3.2, TT.STREET_Y, -11.2), 0, "box", "sign")
# bunting strung across the street between lantern posts (shows once the harbour is restored)
for x in (-7.75, 0.75, 9.5):
    inst.append(dict(model="town/bunting", pos=[x, TT.STREET_Y + 2.35, -15.5], yaw=0.0, scale=1.0, collide="none", tag="bunting tier2", tier=2))
inst.append(dict(model="town/bunting", pos=[0.0, DECK + 2.3, -1.0], yaw=90.0, scale=1.0, collide="none", tag="bunting tier2", tier=2))

# -- beach & museum surroundings
for (x, z, mdl) in ((-27.0, 9.5, "town/driftwood"), (-38.5, 14.0, "town/driftwood"), (-44.0, 17.5, "town/seaweed_pile"), (-34.5, 13.6, "town/seaweed_pile"),
                    (-25.0, 6.5, "town/seaweed_pile"), (-40.0, 17.0, "town/tide_pool"), (-29.5, 12.8, "town/tide_pool"), (-23.0, 1.5, "town/rope_coil"),
                    (-27.5, -2.8, "town/net_rack"), (-21.5, -4.5, "town/crab_pot_stack"), (-36.0, 4.0, "town/anchor"), (-26.0, -0.5, "town/barrel"),
                    (-28.6, 3.0, "town/sign_post"), (-30.2, 2.6, "town/lantern_post"), (-47.0, 19.5, "town/driftwood")):
    prop(mdl, x, z, collide="box", tag="beach", sink=0.05)

# -- cottages: mailboxes, pots, lanterns by the paths
for mdl, x, z, yaw in COTTAGES:
    a = math.radians(yaw)
    fx, fz = math.sin(a), math.cos(a)
    sx, sz = math.cos(a), -math.sin(a)
    mx, mz = x + fx * 4.6 + sx * 1.8, z + fz * 4.6 + sz * 1.8
    prop("town/mailbox", mx, mz, yaw + 180, tag="cottage")
    prop("town/flower_pot", x + fx * 4.2 - sx * 1.2, z + fz * 4.2 - sz * 1.2, tag="cottage")
for (x, z) in ((-3.4, -19.2), (4.5, -23.4), (-13.0, -24.4), (21.5, -17.6), (5.4, -32.0)):
    prop("town/lantern_post", x, z, tag="lantern")
for (x, z, yaw) in ((-4.6, -19.0, 0), (22.0, -6.0, 30), (64.0, 33.0, -120), (40.0, 2.0, 40)):
    prop("town/sign_post" if (x, z) != (64.0, 33.0) else "town/bench", x, z, yaw, tag="path")
prop("town/bench", 62.5, 36.5, -130, tag="bench")
prop("town/bench", -11.0, -27.6, 0, tag="bench")      # on the terrace lane above the street, facing the harbour


# =================================================================================================================
# density pass: a hillside village behind the street, stilt shacks round the cove, rowboats, and the clutter of a
# lived-in harbour. Models: models/town_village.py (colour/seed variants of the cottages + net shed, stilt shacks,
# boats, yard clutter). Their pads, lanes and the graded runs under the boardwalk ramps/stairs live in
# models/town_terrain.py (PADS / PATHS / FLIGHTS), so rebuild the terrain tiles after changing positions there.

vrng = np.random.default_rng(20261003)


def wxz(x, z, yaw, lx, lz):
    """World (x, z) of the local offset (lx, lz) from a placement at (x, z) with `yaw`."""
    a = math.radians(yaw)
    return x + math.cos(a) * lx + math.sin(a) * lz, z - math.sin(a) * lx + math.cos(a) * lz


VILLAGE = [  # model, x, z, yaw, scale (their pads: the last len(VILLAGE) entries of town_terrain.PADS, same order)
    ("town/net_shed_ochre", -25.0, -15.5, 30, 1.0),
    ("town/net_shed_blue", 9.0, -19.0, 0, 0.95),
    ("town/cottage_a_sky", 22.5, -32.5, -22, 1.0),
    ("town/cottage_b_rose", -13.5, -33.0, 12, 0.95),
    ("town/cottage_a_chalk", -3.5, -33.5, 4, 1.05),
    ("town/cottage_c_slate", 15.5, -40.5, -6, 0.95),
    ("town/cottage_b_mustard", -10.5, -42.5, 10, 1.05),
    ("town/cottage_a_red", 5.0, -47.5, 90, 1.0),
    ("town/cottage_c_green", 36.0, -25.0, -50, 1.0),
    ("town/smokehouse", 1.5, -18.6, 0, 1.0),
]
for mdl, x, z, yaw, sc in VILLAGE:
    add(mdl, (x, gy(x, z), z), yaw, "mesh", "cottage", sc)
for (px, pz, hx, hz, yaw, _, _) in TT.PADS[-len(VILLAGE):]:
    excl(px, pz, hx + 0.2, hz + 0.2, yaw)

# boardwalk ramps and stairs climbing between the terraces (terrain graded under them)
FLIGHT_MODEL = {"ramp": "town/boardwalk_ramp", "stairs": "town/boardwalk_stairs", "square": "town/boardwalk_square"}
for kind, x, z, yaw, y in TT.FLIGHTS:
    add(FLIGHT_MODEL[kind], (x, y, z), yaw, "mesh", "steps")
    excl(x, z, 1.5, 2.3 if kind != "square" else 1.4, yaw)

# west walk: off the promenade's west end (boardwalk_branch1) north behind the fish shop; a T to the first shack, the
# second shack at the end. East walk: off the east boardwalk (boardwalk_branch2) out to a shack on the shoreline.
WALKS = [("town/boardwalk_rail2", -15.2, -7.1, 0), ("town/boardwalk_rail2", -15.2, -3.1, 0), ("town/boardwalk_t", -15.2, 0.1, 90),
         ("town/boardwalk_rail2", -15.2, 3.3, 0), ("town/boardwalk_rail2", -15.2, 7.3, 0),
         ("town/boardwalk_rail2", 18.4, 1.0, 90), ("town/boardwalk_rail2", 22.4, 1.0, 90)]
for mdl, x, z, yaw in WALKS:
    add(mdl, (x, DECK, z), yaw, "mesh", "boardwalk")
excl(-15.2, 0.1, 1.5, 9.4)
excl(20.4, 1.0, 4.1, 1.5)
SHACKS = [  # model, x, floor y, z, yaw — porch fronts meet the walks; stilt_shack_d's floor is at the lighthouse-walk level
    ("town/stilt_shack_b", -19.55, DECK, 0.1, 90),
    ("town/stilt_shack_c", -15.2, DECK, 12.25, 180),
    ("town/stilt_shack_a", 27.4, DECK, 1.0, -90),
    ("town/stilt_shack_d", 41.06, 1.3, 9.63, 131.2),
]
for mdl, x, y, z, yaw in SHACKS:
    add(mdl, (x, y, z), yaw, "mesh", "shack")
    excl(x, z, 3.0, 3.0, yaw)

# rowboats: two moored (keel just under the water), three pulled up on the west beach
add("town/rowboat", (-2.35, -0.18, 11.6), 3, "box", "boat_moored")
add("town/rowboat_red", (-19.6, -0.18, 12.4), -6, "box", "boat_moored")
for mdl, x, z, yaw in (("town/rowboat_beached", -40.0, 15.4, 205), ("town/rowboat_upturned", -44.0, 13.2, 80),
                       ("town/rowboat_beached", -47.0, 16.8, 160)):
    prop(mdl, x, z, yaw, collide="box", tag="beach", sink=0.04)
    excl(x, z, 1.0, 1.7, yaw)


# -- density pass clutter ------------------------------------------------------------------------------------------
# (light "_lo" copies of the common props from town_village.py; tier tags: tier1 = more bunting once the lanterns are
# relit, tier2 = flower pots / boxes with the fresh paint)


def deck_prop(model, x, z, yaw, y=DECK, tag="prop", collide="box", scale=1.0):
    return add(model, (x, y, z), yaw, collide, tag, scale)


def at_house(model, house, lx, lz, yaw=0.0, tag="cottage", collide="box", sink=0.0, y=None):
    """Prop at a local offset (lx, lz) of a VILLAGE / COTTAGES house (local yaw), on the ground."""
    _, hx_, hz_, hyaw = house
    x, z = wxz(hx_, hz_, hyaw, lx, lz)
    return prop(model, x, z, hyaw + yaw, y=y, tag=tag, collide=collide, sink=sink)


HOUSES = {m.split("/")[1]: (m, x, z, yaw) for m, x, z, yaw, _ in VILLAGE}

# lanterns at the lane corners, the foot / landing / top of the stairs and both ends of the ramps
for (x, z, yaw) in ((8.3, -28.3, 200), (-9.0, -27.9, 180), (-17.0, -24.6, 160), (1.4, -34.6, 170), (-7.6, -36.7, 185), (11.6, -38.6, -90),
                    (11.8, -42.6, -90), (11.6, -49.0, -90), (21.75, -18.7, -90), (21.8, -28.4, -90), (30.0, -17.0, 200), (16.3, -35.9, 180)):
    prop("town/lantern_post_lo", x, z, yaw, tag="lantern")
# lanterns along the new walks (posts on the deck edge, arms over the planks)
for (x, z, yaw) in ((-14.25, -5.6, -90), (-16.15, 5.0, 90), (18.4, 1.95, 180), (23.4, 0.05, 0)):
    deck_prop("town/lantern_post_lo", x, z, yaw, tag="lantern")
prop("town/lantern_post_lo", 45.5, 5.75, 131, tag="lantern")       # where the lighthouse walk meets the east shack
at_house("town/picket_fence", ("town/smokehouse", 1.5, -18.6, 0), -2.6, 0.9, 90, tag="yard")

# benches with a view over the harbour
for (x, z, yaw) in ((-0.6, -27.6, 0), (13.4, -49.4, 20), (25.0, -27.6, -20), (-20.8, -24.8, 25)):
    prop("town/bench_lo", x, z, yaw, tag="bench")
deck_prop("town/bench_lo", -14.6, -3.2, -90, tag="bench")                               # west walk, facing the shop's back

# per-house: mailbox at the lane, a pot of flowers by the steps (tier2: more flowers once the paint is fresh)
DOORSIDE = {"cottage_a": ((2.4, 3.2), (-1.3, 2.9)), "cottage_b": ((-3.0, 2.9), (-0.3, 2.8)), "cottage_c": ((2.1, 3.0), (-1.5, 2.6))}
for key, (mdl, hx_, hz_, hyaw) in HOUSES.items():
    fam = next((f for f in DOORSIDE if mdl.split("/")[1].startswith(f)), None)
    if fam is None:          # the net sheds come with their own pots, nets and buoys
        continue
    sc = next(v[4] for v in VILLAGE if v[0] == mdl)
    (mx, mz), (fx, fz) = DOORSIDE[fam]
    at_house("town/mailbox_lo", (mdl, hx_, hz_, hyaw), mx * sc, mz * sc, 180)
    at_house("town/flower_pot_lo", (mdl, hx_, hz_, hyaw), fx * sc, fz * sc, vrng.uniform(0, 360), tag="cottage tier2")
    at_house("town/flower_pot_lo", (mdl, hx_, hz_, hyaw), (fx + (0.4 if fx > 0 else -0.4)) * sc, (fz - 0.25) * sc, vrng.uniform(0, 360),
             tag="cottage tier2")

# yards: washing lines, woodpiles, picket fences, crab pots, buoys on the walls
for (x, z, yaw) in ((-8.7, -34.3, 92), (20.0, -38.8, 28), (40.2, -21.6, -50), (-19.4, -19.6, 75), (-16.2, -46.8, 160)):
    prop("town/washing_line", x, z, yaw, tag="yard", collide="box")
for (x, z, yaw) in ((-15.6, -43.0, 100), (-0.6, -43.6, 0), (32.2, -27.4, 40), (-27.6, -12.6, 120)):
    prop("town/woodpile", x, z, yaw, tag="yard", collide="box")
H5, H4, H6 = HOUSES["cottage_a_chalk"], HOUSES["cottage_b_rose"], HOUSES["cottage_c_slate"]
for house, lx, lz in ((H5, -2.6, 3.0), (H5, 2.6, 3.0), (H4, 0.9, 2.9), (H6, 2.3, 2.9), (H6, -2.3, 2.9)):
    at_house("town/picket_fence", house, lx, lz, 0, tag="yard")
for (x, z, yaw) in ((5.9, -15.9, 10), (13.8, -21.5, 80), (39.5, -22.4, 30), (-21.6, -18.6, 200), (29.6, -2.8, 60)):
    prop("town/crab_pot_stack_lo", x, z, yaw, tag="yard")
for (x, z, yaw, mdl) in ((13.1, -16.4, 0, "town/barrel_lo"), (13.7, -16.0, 40, "town/barrel_lo"), (12.9, -17.0, 15, "town/crate_lo"),
                         (35.1, -21.3, 0, "town/barrel_lo"), (19.2, -37.0, 30, "town/crate_lo"), (-5.9, -36.7, 0, "town/barrel_lo"),
                         (6.9, -35.0, 10, "town/rope_coil_lo"), (-16.6, -30.8, 0, "town/rope_coil_lo")):
    prop(mdl, x, z, yaw, tag="yard")
# buoys and floats hung on walls (wall_buoys: origin on the wall face, ~1.9 m up)
HOUSES["E2"] = ("town/cottage_b", 12.5, -27.5, -14)
for key, lx, lz, lyaw in (("cottage_c_green", 2.66, -1.2, 90), ("cottage_b_mustard", -2.4, 0.4, -90), ("cottage_b_rose", -2.4, 0.4, -90),
                          ("E2", -2.4, 0.4, -90)):
    mdl, hx_, hz_, hyaw = HOUSES[key]
    sc = next((v[4] for v in VILLAGE if v[0] == mdl), 1.0)
    x, z = wxz(hx_, hz_, hyaw, lx * sc, lz * sc)
    add("town/wall_buoys", (x, gy(hx_, hz_) + 2.5 * sc, z), hyaw + lyaw, "none", "yard")
# dry-stone walls holding the banks cut behind the terrace pads
for (x, z, yaw, y) in ((7.0, -21.75, 0, 1.85), (11.0, -21.75, 0, 1.85), (-26.15, -17.5, 30, 2.15), (1.4, -45.8, 90, 11.2), (1.4, -49.6, 90, 11.2),
                       (23.85, -35.85, -22, 5.8)):
    add("town/retaining_wall", (x, y + 1.0, z), yaw, "mesh", "wall")

# shore: nets on racks, fish drying, pots and crates by the boats and shacks
for (x, z, yaw) in ((-30.6, -4.6, 60), (37.7, -3.3, 41), (-35.8, 10.9, 115), (5.0, -19.4, 80)):
    prop("town/fish_rack", x, z, yaw, tag="beach", collide="box", sink=0.05)
for (x, z, yaw) in ((-23.6, -1.9, 100), (31.5, -2.2, 50), (-42.0, 11.0, 20)):
    prop("town/net_rack", x, z, yaw, tag="beach", collide="box", sink=0.05)
for (x, z, yaw, mdl) in ((-38.5, 13.6, 30, "town/crab_pot_stack_lo"), (-41.6, 14.1, 0, "town/barrel_lo"), (-42.4, 15.6, 70, "town/rope_coil_lo"),
                         (-45.6, 15.9, 10, "town/fish_crate_lo"), (-33.8, 13.0, 0, "town/buoy_cluster_lo"),
                         (35.4, -3.9, 20, "town/barrel_lo"), (35.95, -4.35, 70, "town/crate_lo"), (41.25, 1.25, 0, "town/crab_pot_stack_lo")):
    prop(mdl, x, z, yaw, tag="beach", sink=0.04)
# on the walks and porches
for (x, z, yaw, mdl) in ((-14.4, 0.7, 10, "town/barrel_lo"), (-14.45, 8.4, 0, "town/crab_pot_stack_lo"), (16.9, 0.25, 90, "town/fish_crate_lo"),
                         (21.3, 1.75, 0, "town/rope_coil_lo")):
    deck_prop(mdl, x, z, yaw)
for (x, z, yaw) in ((-14.0, 3.3, 90), (22.4, 2.18, 0)):     # flower boxes hung on the walk rails (tier2)
    deck_prop("town/flower_box", x, z, yaw, y=DECK + 0.6, tag="prop tier2", collide="none")
# bunting strung over the new walks and between hillside houses once the lanterns are relit
for (x, y, z, yaw) in ((-15.2, DECK + 2.3, 2.0, 90), (20.4, DECK + 2.3, 1.0, 0), (0.0, 0.0, -29.7, 0), (-11.5, 0.0, -38.8, 5)):
    yy = y if y else gy(x, z) + 2.6
    inst.append(dict(model="town/bunting", pos=[x, round(yy, 3), z], yaw=float(yaw), scale=1.0, collide="none", tag="bunting tier1"))


# -- procedural scatter: grass tufts, shore rocks, spruces
def scatter(models, n, region, weight, min_d, tag, sink=0.0, scale=(0.8, 1.25), tries=40000, collide="none", yaw=None):
    x0, x1, z0, z1 = region
    pts = []
    k = 0
    while len(pts) < n and k < tries:
        k += 1
        x, z = rng.uniform(x0, x1), rng.uniform(z0, z1)
        w = weight(x, z)
        if w <= 0 or rng.random() > w or excluded(x, z, 0.6):
            continue
        if any((x - px) ** 2 + (z - pz) ** 2 < min_d * min_d for px, pz in pts):
            continue
        pts.append((x, z))
        mdl = models[int(rng.integers(len(models)))]
        prop(mdl, x, z, yaw, tag=tag, collide=collide, scale=round(float(rng.uniform(*scale)), 2), sink=sink)
    return pts


def field(name, x, z):
    return float(TT._interp(name, x, z))


def grass_w(x, z):
    h = field("H", x, z)
    if h < 0.9:
        return 0.0
    rk, sd, pa, st = field("rock", x, z), field("sand", x, z), field("path", x, z), field("street", x, z)
    near = math.exp(-((x - 0) ** 2 + (z + 12) ** 2) / (2 * 45.0 ** 2))
    return max(0.0, (1 - rk * 1.5) * (1 - sd * 1.5) * (1 - pa * 2) * (1 - st * 3)) * (0.25 + 0.75 * near)


def rock_w(x, z):
    h = field("H", x, z)
    if h < -0.8 or h > 30:
        return 0.0
    rk = field("rock", x, z)
    shore = math.exp(-(h - 0.3) ** 2 / 1.5)
    return min(1.0, 0.15 + rk * 0.6 + shore * 0.5) * (1 - field("path", x, z)) * (1 - field("street", x, z))


def tree_w(x, z):
    h = field("H", x, z)
    if h < 4.0:
        return 0.0
    return max(0.0, 1 - field("rock", x, z) * 1.3 - field("path", x, z) * 2) * (0.5 if -30 < z else 1.0)


GRASS = ["town/grass_tuft_a", "town/grass_tuft_b", "town/grass_tuft_c"]
ROCKS = ["town/rock_a", "town/rock_b", "town/rock_c", "town/rock_d", "town/rock_e"]
scatter(GRASS, 125, (-55, 75, -60, 30), grass_w, 1.8, "grass", sink=0.05)
scatter(ROCKS, 38, (-70, 90, -60, 80), rock_w, 4.5, "rock", sink=0.25, scale=(0.7, 1.5), collide="box")
# spruces grow in little wind-bent groves
groves = scatter([], 0, (0, 0, 0, 0), tree_w, 1, "tree") if False else []
k = 0
while len(groves) < 7 and k < 5000:
    k += 1
    gx_, gz_ = rng.uniform(-80, 85), rng.uniform(-85, -22)
    if tree_w(gx_, gz_) > 0.5 and all(math.hypot(gx_ - a, gz_ - b) > 22 for a, b in groves) and not excluded(gx_, gz_, 6):
        groves.append((gx_, gz_))
for (gx_, gz_) in groves:
    for i in range(int(rng.integers(2, 5))):
        x, z = gx_ + rng.normal() * 4.0, gz_ + rng.normal() * 3.0
        if tree_w(x, z) > 0.2 and not excluded(x, z, 1.0):
            prop("town/tree_pine", x, z, rng.uniform(-25, 25) + 200, tag="tree", collide="box", scale=round(float(rng.uniform(0.75, 1.3)), 2), sink=0.15)
# a few spruces close to the cottages and the lighthouse walk
for (x, z) in ((-18.0, -37.5), (27.5, -35.5), (-28.5, -24.0), (33.0, -14.0), (48.0, 6.0), (-1.0, -45.0), (14.0, -47.5)):
    prop("town/tree_pine", x, z, rng.uniform(-25, 25) + 200, tag="tree", collide="box", scale=round(float(rng.uniform(0.85, 1.2)), 2), sink=0.15)

# -- the harbour: rocks along the arms, kelp, channel markers, sea stacks outside, a wreck, clouds
def arm_rocks(pts, n, side_off):
    for i in range(n):
        t = rng.uniform(0, 1)
        k = min(int(t * (len(pts) - 1)), len(pts) - 2)
        f = t * (len(pts) - 1) - k
        ax, az = pts[k]
        bx, bz = pts[k + 1]
        x, z = ax + (bx - ax) * f, az + (bz - az) * f
        nx, nz = -(bz - az), (bx - ax)
        L = math.hypot(nx, nz)
        o = rng.choice([-1, 1]) * rng.uniform(4.5, side_off)
        x, z = x + nx / L * o, z + nz / L * o
        mdl, sc = ROCKS[int(rng.integers(5))], round(float(rng.uniform(1.0, 2.2)), 2)
        if channel_dist(x, z) < 8.0:      # keep the boat's way out through the harbour mouth clear
            continue
        prop(mdl, x, z, y=min(gy(x, z), -0.3) if gy(x, z) < 0 else None, tag="rock", collide="box", scale=sc, sink=0.3)


BOAT_ROUTE = [(9.0, 25.0), (6.0, 45.0), (0.0, 75.0), (0.0, 100.0)]   # berth -> harbour mouth -> open sea


def channel_dist(x, z):
    best = 1e9
    for (ax, az), (bx, bz) in zip(BOAT_ROUTE[:-1], BOAT_ROUTE[1:]):
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)))
        best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
    return best


arm_rocks(TT.WEST_ARM, 10, 8.0)
arm_rocks(TT.EAST_ARM, 10, 8.0)
for (x, z) in ((-20.0, 60.0), (-35.0, 32.0), (30.0, 54.0), (44.0, 40.0), (-14.0, 40.0), (25.0, 30.0)):
    add("town/kelp_cluster_a" if rng.random() < 0.5 else "town/kelp_cluster_b", (x, 0.0, z), float(rng.uniform(0, 360)), "none", "kelp")
add("town/channel_marker", (-9.0, 0.0, 77.0), 0, "box", "marker")
add("town/channel_marker", (9.5, 0.0, 77.5), 0, "box", "marker")
add("town/sea_stack_a", (-30.0, 0.0, 96.0), 20, "mesh", "scenery")
add("town/sea_stack_b", (38.0, 0.0, 92.0), -40, "mesh", "scenery")
add("town/sea_stack_a", (88.0, 0.0, 70.0), 140, "mesh", "scenery", 0.8)
add("town/wreck", (-62.0, 0.0, 58.0), 35, "mesh", "scenery")
for (x, y, z, mdl, yaw) in ((-40, 42, -60, "town/cloud_1", 0), (35, 48, -75, "town/cloud_2", 40), (90, 40, 20, "town/cloud_3", 80),
                            (-80, 38, 30, "town/cloud_4", 10), (10, 55, 120, "town/cloud_2", 200)):
    add(mdl, (x, y, z), yaw, "none", "sky")
# chimney smoke puffs sit on the `smoke` sockets at runtime; spray is spawned by the sea


# =================================================================================================================
def finish():
    # lights from sockets
    lan, win = [], []
    lamp = None
    for it in inst:
        socks = sockets(it["model"])
        for name, (p, q) in socks.items():
            w = [round(v, 3) for v in world(it["pos"], it["yaw"], p * it["scale"])]
            if name.startswith("light"):
                lan.append(w)
            elif name.startswith("win"):
                win.append(w)
            elif name == "lamp":
                lamp = w
            elif name.startswith("seat"):
                anchors.setdefault("bench_spots", []).append(w)
    anchors["lantern_lights"] = lan
    anchors["window_lights"] = win
    if lamp:
        anchors["lighthouse_lamp"] = dict(pos=lamp, yaw=0.0)
    # restoration: instances with "tier" appear from that harbour tier on; swaps replace a tagged model at a tier
    swaps = [dict(tag="shop", model="town/fish_shop_restored", tier=2)]
    out = dict(version=1, sea_level=0.0, instances=inst, anchors=anchors, swaps=swaps,
               terrain=dict(tiles=sorted(k.split("/")[1] for k in TT.MODELS), tile_size=TT.TILE, origin=[TT.TX0, TT.TZ0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"[layout] {len(inst)} instances, {len(anchors)} anchors -> {OUT}")
    if "--stats" in sys.argv:
        tri = {}
        for it in inst:
            p = os.path.join(MODELS, it["model"] + ".claymesh")
            if it["model"] not in tri:
                tri[it["model"]] = sum(len(pc["f"]) for pc in read_claymesh(p)["pieces"] if not pc["hidden"]) if os.path.exists(p) else 0
        tot = sum(tri[it["model"]] for it in inst)
        town = sum(tri[it["model"]] for it in inst if it.get("tag") not in ("sky", "scenery"))
        ter = 0
        for t in out["terrain"]["tiles"]:
            p = os.path.join(MODELS, "terrain", t + ".claymesh")
            ter += sum(len(pc["f"]) for pc in read_claymesh(p)["pieces"]) if os.path.exists(p) else 0
        print(f"[layout] placed tris: {tot:,} (town without sky/scenery {town:,}); terrain {ter:,}")
        per = {}
        for it in inst:
            per[it["model"]] = per.get(it["model"], 0) + tri[it["model"]]
        for k, v in sorted(per.items(), key=lambda kv: -kv[1])[:15]:
            print(f"   {k:32s} {v:9,}  ({tri[k]:,} each)")
        miss = sorted(k for k, v in tri.items() if v == 0)
        if miss:
            print("[layout] MISSING models:", miss)


if __name__ == "__main__":
    finish()
