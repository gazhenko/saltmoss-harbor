"""
Where the town's bunting hangs: each string runs between two real supports, so it is built at exactly that length
(models/town_props.py registers one `town/bunting_<decimetres>` model per span) and placed by town_layout.py.

An end is either a lantern post already in the layout ("post": its centreline, tied on 2.35 m above its foot, just
under the cap) or a free-standing bunting pole that the layout adds there ("pole").
"""
import math

TIE = 2.35          # height of the tie-on point above the post/pole foot
STREET_Y = 1.72     # town_terrain.STREET_Y
DECK = 1.8          # town_layout.DECK

# (end A, end B, tier); an end is (x, foot_y, z, "post" | "pole"); foot_y None = ground height at that point
LINES = [
    # across the quay street, lantern post to lantern post (once the harbour is restored)
    ((-12.5, STREET_Y, -15.7, "post"), (-3.0, STREET_Y, -15.7, "post"), 2),
    ((-3.0, STREET_Y, -15.7, "post"), (4.5, STREET_Y, -15.7, "post"), 2),
    ((4.5, STREET_Y, -15.7, "post"), (14.5, STREET_Y, -15.7, "post"), 2),
    # down the main boardwalk
    ((0.9, DECK, -5.5, "post"), (-0.9, DECK, 6.5, "post"), 2),
    # over the new walks once the lanterns are relit
    ((-16.1, DECK, 5.0, "post"), (-14.2, DECK, -5.6, "post"), 1),
    ((18.4, DECK, 1.9, "post"), (23.4, DECK, 0.1, "post"), 1),
    # on the hillside between the cottages: on level ground, so both poles stand at the same height
    ((10.6, None, -32.78, "pole"), (16.4, None, -31.22, "pole"), 1),
    ((-20.9, None, -40.28, "pole"), (-15.1, None, -38.72, "pole"), 1),
]


def span(a, b):
    return math.hypot(b[0] - a[0], b[2] - a[2])


def span_id(s):
    """Model id for a string of length s (decimetre steps)."""
    return f"town/bunting_{int(round(s * 10))}"


def spans():
    return sorted({round(span(a, b), 1) for a, b, _ in LINES})
