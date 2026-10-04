"""Saltmoss Harbor clutter props (one model each). Builders live in Tools/clay/kit_props.py."""
import numpy as np
from kit_town import TownModel, T, TP
import kit_props as K
import bunting_lines as BL

MODELS = {}


def reg(pid, budget=3700):
    def deco(fn):
        def build():
            m = TownModel(pid, budget=budget)
            fn(m)
            return m
        MODELS[f"town/{pid}"] = build
        return fn
    return deco


@reg("crate")
def _crate(m):
    K.crate(m, T(), "wood", lid=False)


@reg("fish_crate")
def _fish_crate(m):
    pts = K.fish_crate(m, T(), "wood")
    for i, (p, yaw) in enumerate(zip(pts, (75, 100, 82))):
        m.socket(f"fish_{i}", pos=p, rot=(0, yaw, 90))


@reg("barrel")
def _barrel(m):
    K.barrel(m, T(), "wood")


@reg("rope_coil")
def _rope_coil(m):
    K.rope_coil(m, T(), "rope")


@reg("lantern_post")
def _lantern_post(m):
    light = K.lantern_post(m, T(), "wood", "metal", "glass")
    m.socket("light", pos=light)


@reg("hanging_lantern")
def _hanging_lantern(m):
    light = K.hanging_lantern(m, T(), "metal", "glass")
    m.socket("light", pos=light)


@reg("life_ring")
def _life_ring(m):
    K.life_ring(m, T(), "ring")


@reg("bench")
def _bench(m):
    seat = K.bench(m, T(), "wood")
    m.socket("seat_0", pos=seat + np.array([-0.3, 0, 0]))
    m.socket("seat_1", pos=seat + np.array([0.3, 0, 0]))


@reg("mailbox")
def _mailbox(m):
    slot = K.mailbox(m, T(), "box")
    m.socket("slot", pos=slot)


@reg("anchor")
def _anchor(m):
    K.anchor(m, T(), "iron")


@reg("net_rack")
def _net_rack(m):
    K.net_rack(m, T(), "frame", "net")


@reg("buoy_cluster")
def _buoy_cluster(m):
    K.buoy_cluster(m, T(), "floats")


@reg("crab_pot_stack")
def _crab_pot_stack(m):
    K.crab_pot_stack(m, T(), "pots", "net")


@reg("ice_chest")
def _ice_chest(m):
    K.ice_chest(m, T(), "chest")


@reg("flower_pot")
def _flower_pot(m):
    K.flower_pot(m, T(), "pot")


@reg("flower_box")
def _flower_box(m):
    K.flower_box(m, T(), "box")


def _reg_bunting(s):
    # one string per span in bunting_lines.py, sagging a little more the longer it is
    @reg(BL.span_id(s)[len("town/"):], budget=int(1800 + 160 * s))
    def _bunting(m):
        K.bunting(m, T(), "bunting", span=s, sag=0.065 * s)


for _s in BL.spans():
    _reg_bunting(_s)


@reg("bunting_pole", budget=2600)
def _bunting_pole(m):
    K.bunting_pole(m, T(), "wood", "metal", h=BL.TIE + 0.2, tie=BL.TIE)


@reg("sign_post")
def _sign_post(m):
    for i, (p, yaw) in enumerate(K.sign_post(m, T(), "post")):
        m.socket(f"sign_{i}", pos=p, rot=(0, yaw, 0))
