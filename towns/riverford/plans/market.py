"""Riverford market square (21 x 21): sandstone paving with an orange/white terracotta checker band,
a round fountain with a copper rim and spout, the town bell on an acacia gate-frame where the trade road
comes in from the quay (north), six striped-awning stalls round the edges, potted trees, benches,
copper lanterns on posts, and two shallow steps up to the back street on the south edge.

Villager rules: exactly one bell, no beds, no job blocks (stalls sell from chests, trapdoor crates, wool
sacks, hay, pots, melons and pumpkins)."""

import math

from architect.build import Build
from architect.parts import stamp

S = 21                 # plot size
C = 10                 # centre column (x) where the trade road arrives
FX, FZ = 10, 11        # fountain centre
F_WATER, F_RING = 2.5, 3.5
BELL_Z = 5             # bell frame row (the gate the road passes under)
LANTERN = "waxed_copper_lantern"

AWNINGS = [("orange_wool", "white_wool"), ("red_wool", "white_wool"), ("yellow_wool", "white_wool")]


# ---------------------------------------------------------------- paving
def pave(x, z):
    edge = x in (0, S - 1) or z == 0
    if edge:
        return "orange_terracotta" if (x + z) % 2 == 0 else "white_terracotta"
    d = math.hypot(x - FX, z - FZ)
    if 4.5 <= d < 5.5:
        return "cut_sandstone"                      # ring round the fountain
    if C - 1 <= x <= C + 1 and z < FZ - 4:
        return "cut_sandstone" if x == C else "smooth_sandstone"   # the road comes in
    if x in (1, S - 2) or z == 1:
        return "cut_sandstone"                      # inner border of the checker band
    # terracotta patches: little diamonds in the four quarters
    for px, pz in ((5, 6), (15, 6), (5, 16), (15, 16)):
        m = abs(x - px) + abs(z - pz)
        if m == 0:
            return "orange_glazed_terracotta"
        if m == 1:
            return "orange_terracotta"
    h = (x * 7 + z * 13 + x * z) % 9
    return "sandstone" if h == 0 else "smooth_sandstone"


# ---------------------------------------------------------------- one stall, front to the south (+z)
def stall(colors, back, front, top):
    """5 wide (x 0..4), posts z 0..2, awning overhang at z 3. back/front: 3 blocks each (x 1..3) at y 1;
    top: {x: block} set on the front counter at y 2."""
    p = Build("stall")
    for x in (0, 4):
        for y in range(1, 5):
            p.set(x, y, 0, "birch_log[axis=y]")
        for y in range(1, 4):
            p.set(x, y, 2, "birch_log[axis=y]")
    for i, blk in enumerate(back):
        p.set(1 + i, 1, 0, blk)
    for i, blk in enumerate(front):
        p.set(1 + i, 1, 2, blk)
    for x, blk in top.items():
        p.set(x, 2, 2, blk)
    # trader's banners on the outer sides of the front posts
    banner = colors[0].replace("_wool", "_wall_banner")
    p.set(-1, 3, 2, f"{banner}[facing=west]")
    p.set(5, 3, 2, f"{banner}[facing=east]")
    # striped awning, stepped: back row high, then flat, then dropping over the customers
    for x in range(0, 5):
        c = colors[x % 2]
        p.set(x, 5, 0, c)
        p.set(x, 4, 1, c)
        p.set(x, 4, 2, c)
        p.set(x, 3, 3, c)
    p.set(1, 4, 0, "birch_planks")
    p.set(2, 4, 0, "birch_planks")
    p.set(3, 4, 0, "birch_planks")
    p.set(2, 3, 1, LANTERN + "[hanging=true]")
    return p


CRATE = "spruce_trapdoor[facing=south,half=top,open=false]"
STALLS = [
    # (colors, back row, front counter, top of counter)
    (AWNINGS[0], ["chest[facing=south]", "hay_block[axis=y]", "pumpkin"],
     ["melon", "pumpkin", "melon"], {}),
    (AWNINGS[1], ["white_wool", "brown_wool", "chest[facing=south]"],
     ["cut_sandstone", "cut_sandstone", "cut_sandstone"],
     {1: "potted_red_tulip", 2: "potted_cornflower", 3: "potted_orange_tulip"}),
    (AWNINGS[2], ["hay_block[axis=x]", "hay_block[axis=x]", "chest[facing=south]"],
     ["spruce_planks", "hay_block[axis=y]", "spruce_planks"], {1: CRATE, 3: CRATE}),
    (AWNINGS[1], ["chest[facing=south]", "light_gray_wool", "white_wool"],
     ["red_wool", "yellow_wool", "light_blue_wool"], {}),
    (AWNINGS[0], ["decorated_pot[facing=south]", "chest[facing=south]", "decorated_pot[facing=south]"],
     ["smooth_sandstone", "smooth_sandstone", "smooth_sandstone"],
     {1: "potted_cactus", 2: "decorated_pot[facing=south]", 3: "potted_dandelion"}),
    (AWNINGS[2], ["pumpkin", "chest[facing=south]", "melon"],
     ["spruce_planks", "spruce_planks", "spruce_planks"], {1: "melon", 2: CRATE, 3: "pumpkin"}),
]


# ---------------------------------------------------------------- smaller pieces
def planter(b, cx, cz, kind):
    """A big pot (3 x 3 terracotta rim) with a small tree in it."""
    for x in range(cx - 1, cx + 2):
        for z in range(cz - 1, cz + 2):
            b.set(x, 1, z, "orange_terracotta" if (x, z) != (cx, cz) else "rooted_dirt")
    for x, z in ((cx - 1, cz), (cx + 1, cz), (cx, cz - 1), (cx, cz + 1)):
        b.set(x, 1, z, "white_terracotta")
    if kind == "azalea":
        log, leaves, alt = "oak_log[axis=y]", "azalea_leaves[persistent=true]", "flowering_azalea_leaves[persistent=true]"
        for y in (2, 3):
            b.set(cx, y, cz, log)
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                b.set(cx + dx, 4, cz + dz, alt if (dx + dz) % 2 else leaves)
        for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            b.set(cx + dx, 5, cz + dz, alt if dx else leaves)
    else:  # acacia: bent trunk, flat canopy
        leaves = "acacia_leaves[persistent=true]"
        b.set(cx, 2, cz, "acacia_log[axis=y]")
        b.set(cx, 3, cz, "acacia_log[axis=y]")
        b.set(cx, 4, cz, "acacia_log[axis=y]")
        for dx in range(-2, 3):
            for dz in range(-1, 2):
                if abs(dx) + abs(dz) <= 2:
                    b.set(cx + dx, 5, cz + dz, leaves)
        for dx, dz in ((0, 0), (1, 0), (-1, 0)):
            b.set(cx + dx, 6, cz + dz, leaves)


def lamp_post(b, x, z):
    b.set(x, 1, z, "cut_sandstone")
    b.set(x, 2, z, "birch_fence")
    b.set(x, 3, z, "birch_fence")
    b.set(x, 4, z, LANTERN + "[hanging=false]")


def bench(b, x1, x2, z, facing):
    """A birch bench along x; facing = the tall back side; trapdoor arms at the ends."""
    for x in range(x1, x2 + 1):
        b.set(x, 1, z, f"birch_stairs[facing={facing},half=bottom,shape=straight]")


def bench_z(b, x, z1, z2, facing):
    for z in range(z1, z2 + 1):
        b.set(x, 1, z, f"birch_stairs[facing={facing},half=bottom,shape=straight]")


# ---------------------------------------------------------------- the square
def build():
    b = Build("riverford market")

    # paving at y 0, cleared air above
    for x in range(S):
        for z in range(S):
            b.set(x, 0, z, pave(x, z))

    # south edge: two shallow steps up to the back street
    for x in range(S):
        b.set(x, 0, S - 2, "cut_sandstone")
        b.set(x, 1, S - 2, "smooth_sandstone_slab[type=bottom]")
        b.set(x, 0, S - 1, "cut_sandstone")
        b.set(x, 1, S - 1, "smooth_sandstone")
        b.set(x, 2, S - 1, "smooth_sandstone_slab[type=bottom]")

    # fountain: sunken basin, sandstone wall with a copper rim, a spouting column
    for x in range(FX - 4, FX + 5):
        for z in range(FZ - 4, FZ + 5):
            d = math.hypot(x - FX, z - FZ)
            if d < F_WATER:
                b.set(x, -1, z, "cut_sandstone")
                b.set(x, 0, z, "water")
                b.set(x, 1, z, "water")
            elif d < F_RING:
                b.set(x, 1, z, "cut_sandstone")
                b.set(x, 2, z, "waxed_cut_copper_slab[type=bottom]")
    for y in range(0, 3):
        b.set(FX, y, FZ, "chiseled_sandstone" if y == 2 else "sandstone_wall")
    b.set(FX, 3, FZ, "waxed_cut_copper")
    for dx in (-1, 0, 1):          # a copper bowl the spout spills over
        for dz in (-1, 0, 1):
            if (dx == 0) != (dz == 0):   # a cross, so the water shows between the arms
                b.set(FX + dx, 3, FZ + dz, "waxed_cut_copper_slab[type=bottom]")
    b.set(FX, 4, FZ, "water")
    # pots of flowers on copper posts at the four points of the rim
    for (dx, dz), pot in zip(((3, 0), (-3, 0), (0, 3), (0, -3)),
                             ("potted_orange_tulip", "potted_red_tulip", "potted_flowering_azalea_bush",
                              "potted_dandelion")):
        b.set(FX + dx, 2, FZ + dz, "waxed_cut_copper")
        b.set(FX + dx, 3, FZ + dz, pot)

    # the town bell on an acacia frame over the road where it enters the square
    for x in (C - 2, C + 2):
        b.set(x, 1, BELL_Z, "chiseled_sandstone")
        for y in range(2, 5):
            b.set(x, y, BELL_Z, "stripped_acacia_log[axis=y]")
    for x in range(C - 3, C + 4):
        b.set(x, 5, BELL_Z, "stripped_acacia_log[axis=x]")
    b.set(C, 4, BELL_Z, "bell[attachment=ceiling,facing=north]")
    for x in (C - 3, C + 3):
        b.set(x, 4, BELL_Z, LANTERN + "[hanging=true]")
    for x in range(C - 3, C + 4):
        b.set(x, 6, BELL_Z - 1, "brick_stairs[facing=south,half=bottom,shape=straight]")
        b.set(x, 6, BELL_Z + 1, "brick_stairs[facing=north,half=bottom,shape=straight]")
        b.set(x, 6, BELL_Z, "orange_terracotta" if x % 2 else "white_terracotta")
        b.set(x, 7, BELL_Z, "brick_slab[type=bottom]")
    b.set(C - 4, 6, BELL_Z, "brick_stairs[facing=east,half=bottom,shape=straight]")
    b.set(C + 4, 6, BELL_Z, "brick_stairs[facing=west,half=bottom,shape=straight]")

    # six stalls: two on the west, two on the east, two flanking the south steps
    w1, w2, e1, e2, s1, s2 = (stall(*s) for s in STALLS)
    stamp(b, w1, 1, 0, 6, turns=3)     # west side, front to the east: x 1..4, z 2..6
    stamp(b, w2, 1, 0, 14, turns=3)    # z 10..14
    stamp(b, e1, 19, 0, 2, turns=1)    # east side, front to the west: x 16..19, z 2..6
    stamp(b, e2, 19, 0, 10, turns=1)   # z 10..14
    stamp(b, s1, 7, 0, 18, turns=2)    # south side, front to the north: x 3..7, z 15..18
    stamp(b, s2, 17, 0, 18, turns=2)   # x 13..17

    # potted trees between the side stalls and in the north corners
    planter(b, 2, 8, "azalea")
    planter(b, 18, 8, "azalea")
    planter(b, 6, 2, "acacia")
    planter(b, 14, 2, "acacia")

    # benches facing the fountain
    bench_z(b, 6, 10, 12, "west")
    bench_z(b, 14, 10, 12, "east")

    # copper lanterns on posts at the corners and by the steps
    for x, z in ((1, 1), (19, 1), (1, 17), (19, 17), (9, 17), (11, 17)):
        lamp_post(b, x, z)

    return b
