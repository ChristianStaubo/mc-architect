"""The hall under the mountain: the high street ends at a rock face; a hidden 2x2 piston door
(redstone.piston_door_2x2, untouched) opens on a tunnel west into a vaulted great hall with a treasure
vault at the back, and a spiral stair climbs through the rock to a lookout balcony over the north lake.

Written in WORLD coordinates (the helpers convert): local (0,0,0) = world (300, 68, -190).
Preview: MC_RUN_ID=mountain:design ./mc.py place local/plans/mountain/hall.py --at 300,-190 --y 68 \
         --no-clear --foundation none --keep-trees --dry-run
`python3 local/plans/mountain/hall.py` prints the rock-cover check (every carved cell 3+ under ground)."""

import os
import random

from architect.build import Build
from architect.parts import spiral_stairs, stamp
from architect.redstone import piston_door_2x2

OX, OY, OZ = 300, 68, -190          # world position of the plan's local origin (the door's origin)
FLOOR = 67                          # floor block y everywhere below (walk at 68)

# hall (inside, world): nave + two aisles, two pillar rows
HX0, HX1 = 278, 290
HZ0, HZ1 = -196, -183
PILLAR_X = (280, 284, 288)
PILLAR_Z = (-193, -186)
NAVE_Z = range(-192, -186)          # -192..-187
AISLE_TOP = 73                      # top air y in the aisles (ceiling 74)
NAVE_TOP = {-192: 73, -187: 73, -191: 74, -188: 74, -190: 75, -189: 75}   # vault profile
# treasure vault behind the west wall
VX0, VX1, VZ0, VZ1, VTOP = 272, 276, -192, -187, 71
# hall -> shaft passage, spiral shaft, upper passage, balcony
PASS_X = (288, 289)
SHAFT = (284, -205, 287, -202)      # x1, z1, x2, z2 of the spiral ring
UP_FLOOR = 79                       # upper passage floor y (walk 80)
UP_Z = (-206, -205)
BAL_X0, BAL_X1, BAL_Z0, BAL_Z1, BAL_FLOOR = 301, 304, -208, -203, 80

GX0, GZ0 = 273, -209
GROUND = '''
 97  96  95  94  94  94  94  94  94  94  93  93  93  93  93  93  92  92  91  91  90  90  89  87  87  86  85  84  83  81  79  77  77  76  75  74  73  72  69  67  66  65  64 62~ 62~
 96  95  94  93  93  93  93  93  93  93  93  93  93  93  93  93  92  92  92  91  91  90  89  88  87  86  91  84  83  81  79  78  77  77  76  75  74  72  69  67  66  64 62~ 62~ 62~
 96  94  94  93  93  93  93  93  93  93  93  93  93  93  92  92  92  91  91  90  89  88  87  87  86  86  85  84  82  81  79  78  77  77  76  75  74  73  69  66  64 62~ 62~ 62~ 62~
 95  94  93  93  93  93  93  93  93  93  93  93  92  92  92  92  91  90  89  88  87  87  86  86  85  85  84  83  82  80  79  78  77  77  76  80  75  73  69  64 62~ 62~ 62~ 62~ 62~
 95  94  93  93  93  93  93  93  93  92  92  92  92  92  91  91  90  89  88  87  86  86  85  85  84  84  83  83  81  80  79  78  77  77  77  76  75  74  68 62~ 62~ 62~ 62~ 62~ 62~
 95  94  93  93  93  93  93  93  92  92  92  92  91  91  90  90  89  87  86  85  85  85  84  83  83  83  82  82  81  79  79  78  78  77  77  76  75  74 62~ 62~ 62~ 62~ 62~ 62~ 62~
 94  94  93  93  92  92  92  92  92  92  91  91  90  90  89  88  92  86  86  85  84  84  83  82  82  81  80  80  79  78  78  77  77  77  76  75  74  73 62~ 62~ 62~ 62~ 62~ 62~ 62~
 94  93  93  92  92  92  92  92  92  91  91  96  89  88  87  87  91  89  85  84  83  83  82  81  80  79  79  78  78  77  77  77  76  76  75  74  73 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 94  93  93  92  92  92  92  92  91  91  90  89  88  87  91  86  91  89  84  83  82  81  80  79  78  78  77  77  77  77  76  76  76  75  74  72 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 94  93  92  92  92  92  91  91  91  90  89  88  87  86  85  91  93  83  83  82  81  80  78  78  77  77  76  76  76  76  76  75  75  73 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 95  93  93  92  92  91  91  91  90  89  88  87  90  90  89  84  83  83  82  81  80  79  78  77  77  76  76  76  75  75  74  74  72 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 95  94  93  92  92  91  90  90  89  87  87  86  85  85  84  83  83  82  81  79  79  78  77  77  76  76  75  75  74  73  72 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 96  94  93  92  91  91  90  88  87  86  86  85  85  84  84  83  82  81  80  78  78  77  76  76  76  75  75  74  73  72 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 97  95  93  92  91  90  89  87  86  86  85  85  84  83  83  82  81  80  78  77  77  76  76  75  75  75  74  73  72 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 98  95  93  92  91  90  89  87  86  86  85  85  84  84  83  82  81  80  79  77  77  76  76  75  75  75  74  74  72 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 98  96  94  92  92  91  89  87  86  86  85  85  84  84  83  83  82  81  79  78  77  76  76  75  75  75  74  74  72 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~
 99  97  94  93  92  91  89  87  86  86  85  85  84  84  83  83  82  81  80  78  77  77  76  75  75  75  74  74  72  64 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~ 62~  62  62  62  62  62
 99  97  94  93  92  91  89  87  86  86  85  85  84  84  84  83  82  82  81  79  78  77  76  75  75  75  74  74  72  65  64  64  64  64  63  63  63  63  63  63  63  63  63  63  62
 99  98  95  93  93  92  90  88  87  86  85  85  84  88  84  83  83  82  81  79  78  77  76  76  75  75  74  74  72  67  65  64  64  64  64  64  64  64  64  63  63  63  63  63  62
100  98  96  94  93  92  91  89  88  87  86  85  85  84  84  83  83  82  81  79  78  77  76  76  75  75  74  74  72  68  67  67  67  67  66  66  66  65  65  65  65  64  64  63  62
100  99  97  95  94  93  91  90  89  87  86  85  85  84  84  83  83  82  81  80  78  77  76  76  75  75  74  74  72  67  67  71  67  67  70  66  66  65  65  65  69  64  64  63  62
100  99  98  96  95  93  92  91  90  88  86  85  85  84  84  83  83  82  81  80  78  77  77  76  75  75  75  74  72  67  67  67  73  67  66  66  66  65  65  65  65  64  64  63  62
101 100  98  97  95  94  93  92  91  90  88  86  86  85  85  84  84  83  82  80  79  78  77  76  75  75  74  74  72  69  67  67  67  66  66  65  65  68  64  64  63  63  63  62  62
101 100  99  97  96  94  93  92  91  91  90  88  87  86  86  85  84  83  82  81  79  82  77  76  76  75  74  73  71  69  67  67  67  66  66  65  65  65  64  64  63  63  63  62  62
101 100  99  98  96  95  93  92  92  91  91  90  89  88  87  86  85  84  83  81  80  78  77  76  76  75  74  73  71  69  67  67  67  66  66  65  65  65  64  64  63  63  63  62  62
102 101 100  98  97  95  94  93  92  92  92  91  90  89  88  87  86  84  83  82  80  79  77  76  76  75  74  72  70  69  67  67  67  67  69  65  65  65  64  64  63  63  63  62  65
102 101 100  99  97  95  94  93  92  92  92  91  90  89  87  86  85  84  83  81  80  78  77  76  76  75  74  72  71  69  68  67  67  66  66  65  65  64  64  63  63  63  62  62  62
102 101 100  99  97  95  94  93  92  92  91  91  90  89  87  86  85  84  83  81  80  78  77  76  76  75  74  72  71  70  69  67  67  67  66  65  65  64  64  63  63  63  62  62  62
103 102 100  99  98  95  94  93  92  92  91  91  90  88  87  86  85  84  83  81  79  78  77  76  76  75  74  72  71  70  69  68  68  66  66  65  65  64  70  63  63  63  62  62  62
103 102 101  99  98  96  94  93  92  92  91  91  89  88  86  85  85  84  82  81  79  78  77  76  76  75  74  72  71  70  69  69  68  67  66  65  65  64  63  63  63  62  62  62  62
'''  # mc site, x 273..317 west->east, z -209..-180 north->south (top block y; ~ water)


def _grid():
    g = {}
    for dz, row in enumerate(GROUND.strip("\n").splitlines()):
        for dx, v in enumerate(row.split()):
            g[(GX0 + dx, GZ0 + dz)] = (int(v.rstrip("~")), v.endswith("~"))
    return g


def ground(x, z):
    return G[(x, z)][0]


def rnd(x, y, z, salt=0):
    return random.Random((x * 73856093) ^ (y * 19349663) ^ (z * 83492791) ^ salt).random()


def brick(x, y, z):
    r = rnd(x, y, z)
    return "mossy_stone_bricks" if r < 0.14 else "cracked_stone_bricks" if r < 0.24 else "stone_bricks"


def rockface(x, y, z):
    r = rnd(x, y, z, 7)
    return ("mossy_cobblestone" if r < 0.22 else "andesite" if r < 0.42 else "cobblestone" if r < 0.55
            else "moss_block" if r < 0.63 else "stone")


class W:
    """Set blocks by world coordinates."""

    def __init__(self, b):
        self.b = b

    def set(self, x, y, z, blk):
        self.b.set(x - OX, y - OY, z - OZ, blk)

    def get(self, x, y, z):
        return self.b.get(x - OX, y - OY, z - OZ)

    def fill(self, x1, y1, z1, x2, y2, z2, blk):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.set(x, y, z, blk(x, y, z) if callable(blk) else blk)

    def air(self, x1, y1, z1, x2, y2, z2):
        self.fill(x1, y1, z1, x2, y2, z2, "air")


def stair(facing, half="bottom", block="stone_brick_stairs"):
    return f"{block}[facing={facing},half={half},shape=straight]"


def wall_post(n=False, s=False, e=False, w=False, up=True):
    c = lambda v: "low" if v else "none"  # noqa: E731
    return f"stone_brick_wall[north={c(n)},south={c(s)},east={c(e)},west={c(w)},up={'true' if up else 'false'}]"


# ---------------------------------------------------------------- the door
def door(w):
    part, info = piston_door_2x2()
    stamp(w.b, part, 0, 0, 0)
    # the part fills its rock mass up to world y 73; on the cliff edge (x 300-301) that rises above the
    # grass: drop the plain filler there (never a mechanism cell) so the cliff top stays as it was
    for (lx, ly, lz), blk in list(w.b.blocks.items()):
        x, y, z = lx + OX, ly + OY, lz + OZ
        if x in (300, 301) and blk == "stone" and y >= ground(x, z) and (x, z) in G:
            del w.b.blocks[(lx, ly, lz)]
    # disguise the face around the niche: moss, andesite, cobble (all full solid blocks, so the wiring
    # behind sees the same conductors); the lever's own block stays stone
    for z in range(-197, -183):
        for y in range(64, 73):
            if w.get(301, y, z) == "stone" and (z, y) != (-194, 69):
                w.set(301, y, z, rockface(301, y, z))
    # vines inside the niche on its side walls (they stay when the door opens)
    for y in (68, 69):
        w.set(301, y, -190, "vine[north=true,south=false,east=false,west=false,up=false]")
        w.set(301, y, -189, "vine[south=true,north=false,east=false,west=false,up=false]")
    # vines hanging on the face above and beside the niche
    hang = [(-192, (69, 70, 71)), (-191, (68, 69, 70, 71)), (-190, (70, 71)), (-189, (70, 71)),
            (-188, (68, 69, 70, 71)), (-187, (70, 71)), (-186, (71,))]
    for z, ys in hang:
        for y in ys:
            if w.get(301, y, z) and w.get(301, y, z) != "air":
                w.set(302, y, z, "vine[west=true,north=false,south=false,east=false,up=false]")
    # tunnel lamps in small niches (plain rock of the part, far from the wiring at x >= 297)
    w.set(295, 68, -191, "lantern[hanging=false]")
    w.set(295, 68, -188, "lantern[hanging=false]")
    return info


def ledge(w):
    """A fishing ledge at the water's edge under the lever: corbelled out of the cliff, barrels below
    the lever so it reads as a tap on a cask rack."""
    for z in range(-195, -190):
        for x in (302, 303):
            w.set(x, FLOOR, z, brick(x, FLOOR, z))
    for z in (-195, -194):
        w.set(302, 66, z, stair("west", "top"))
        w.set(303, 66, z, stair("west", "top"))
    w.fill(302, 65, -193, 302, 66, -193, brick)
    w.set(303, 66, -193, stair("west", "top"))
    w.fill(302, 66, -192, 303, 66, -192, brick)
    w.set(303, 65, -192, brick(303, 65, -192))
    w.set(303, 66, -191, brick(303, 66, -191))
    # a second course of corbels under the outer edge (no post: it would reach the lake bed at y 51)
    for z in (-195, -194, -193):
        w.set(302, 65, z, stair("west", "top"))
    # casks under and beside the lever, a lamp post on the corner
    w.set(302, 68, -195, "barrel[facing=up,open=false]")
    w.set(302, 68, -194, "barrel[facing=east,open=false]")
    w.set(302, 68, -193, "barrel[facing=up,open=false]")
    w.set(302, 69, -195, "barrel[facing=up,open=false]")
    w.set(303, 68, -195, "spruce_fence[north=false,south=false,east=false,west=false]")
    w.set(303, 69, -195, "lantern[hanging=false]")


# ---------------------------------------------------------------- shells (solid lining first)
def shells(w):
    w.fill(HX0 - 1, FLOOR, HZ0 - 1, HX1 + 1, 76, HZ1 + 1, brick)          # hall box
    w.fill(VX0 - 1, FLOOR, VZ0 - 1, VX1, VTOP + 1, VZ1 + 1, brick)        # vault box
    w.fill(291, FLOOR, -191, 293, 70, -188, brick)                        # tunnel to the part
    w.fill(287, FLOOR, -205, 290, 71, -197, brick)                        # passage to the shaft
    x1, z1, x2, z2 = SHAFT
    w.fill(x1 - 1, FLOOR, z1 - 1, x2 + 1, UP_FLOOR + 4, z2 + 1, brick)    # shaft box
    w.fill(288, UP_FLOOR - 1, UP_Z[0] - 1, 299, UP_FLOOR + 3, UP_Z[1] + 1, brick)  # upper passage


# ---------------------------------------------------------------- the great hall
def hall(w):
    for x in range(HX0, HX1 + 1):
        for z in range(HZ0, HZ1 + 1):
            top = NAVE_TOP.get(z, AISLE_TOP)
            w.air(x, FLOOR + 1, z, x, top, z)
            # floor: polished andesite nave, stone brick aisles
            w.set(x, FLOOR, z, "polished_andesite" if z in NAVE_Z else brick(x, FLOOR, z))
        # the vault's lower courses: upside-down stairs where the nave steps up
        w.set(x, 74, -192, stair("north", "top"))
        w.set(x, 74, -187, stair("south", "top"))
        w.set(x, 75, -191, stair("north", "top"))
        w.set(x, 75, -188, stair("south", "top"))
    # pillar rows: pillars, and arches between them (rounded with upside-down stairs at y 72)
    for z in PILLAR_Z:
        w.set(HX0 - 1, FLOOR, z, "chiseled_stone_bricks")
        for x in range(HX0, HX1 + 1):
            if x in PILLAR_X:
                w.fill(x, FLOOR, z, x, 73, z, "stone_bricks")
                w.set(x, FLOOR + 1, z, "chiseled_stone_bricks")
                w.set(x, 73, z, "chiseled_stone_bricks")
                w.set(x, FLOOR, z, "chiseled_stone_bricks")
            else:
                w.set(x, 73, z, brick(x, 73, z))
                left = x - 1 in PILLAR_X or x - 1 < HX0
                right = x + 1 in PILLAR_X or x + 1 > HX1
                if left:
                    w.set(x, 72, z, stair("west", "top"))
                elif right:
                    w.set(x, 72, z, stair("east", "top"))
    # dark oak beams: across the aisles at every pillar, a tie beam across the nave
    for x in PILLAR_X:
        for z in list(range(HZ0, PILLAR_Z[0])) + list(range(PILLAR_Z[1] + 1, HZ1 + 1)):
            w.set(x, 73, z, "dark_oak_log[axis=z]")
        for z in range(-191, -187):
            w.set(x, 74, z, "dark_oak_log[axis=z]")
        # lanterns: on chains under the tie beam over the table, under the aisle beams
        for z in (-190, -189):
            w.set(x, 73, z, "lantern[hanging=true]")
        w.set(x, 72, -195, "lantern[hanging=true]")
        w.set(x, 72, -184, "lantern[hanging=true]")
    # between the beams, lanterns on chains from the crown of the vault
    for x in (279, 282, 286, 289):
        w.set(x, 75, -190, "iron_chain[axis=y]")
        w.set(x, 74, -190, "lantern[hanging=true]")
        w.set(x, 75, -189, "iron_chain[axis=y]")
        w.set(x, 74, -189, "lantern[hanging=true]")
    # the long table, chairs, candles
    for x in range(281, 288):
        for z in (-190, -189):
            w.set(x, 68, z, "dark_oak_slab[type=top]")
    for x in (281, 283, 285, 287):
        w.set(x, 68, -191, stair("north", block="spruce_stairs"))
        w.set(x, 68, -188, stair("south", block="spruce_stairs"))
    for x, z in ((282, -190), (284, -189), (286, -190)):
        w.set(x, 69, z, "candle[candles=3,lit=true]")
    w.set(284, 69, -190, "candle[candles=4,lit=true]")
    w.set(280, 68, -190, stair("west", block="dark_oak_stairs"))   # the head of the table
    w.set(280, 68, -189, stair("west", block="dark_oak_stairs"))
    # banners: red on the pillars facing the nave, black on the walls in the bays
    for x in PILLAR_X:
        w.set(x, 72, -192, "red_wall_banner[facing=south]")
        w.set(x, 72, -187, "red_wall_banner[facing=north]")
    for x in (282, 286):
        w.set(x, 72, HZ0, "black_wall_banner[facing=south]")
    w.set(282, 72, HZ1, "black_wall_banner[facing=north]")
    # the hearth in the south wall, bay x 285-287
    w.fill(284, FLOOR, HZ1 + 2, 288, 71, HZ1 + 2, "stone_bricks")
    w.fill(285, 68, HZ1 + 1, 287, 69, HZ1 + 1, "air")
    w.fill(285, FLOOR, HZ1 + 1, 287, FLOOR, HZ1 + 1, "polished_blackstone_bricks")
    w.fill(285, 68, HZ1 + 2, 287, 69, HZ1 + 2, "polished_blackstone_bricks")
    for x in (285, 286, 287):
        w.set(x, 68, HZ1 + 1, "campfire[lit=true,facing=north,signal_fire=false,waterlogged=false]")
    for x in range(285, 288):
        w.set(x, FLOOR, HZ1, "polished_blackstone_bricks")                 # hearthstone
        w.set(x, 70, HZ1, stair("south", "top"))                           # mantel
    w.fill(285, 71, HZ1, 287, AISLE_TOP, HZ1, "stone_bricks")              # chimney breast
    w.set(286, 71, HZ1, "chiseled_stone_bricks")
    # pilasters on the long walls opposite the pillars (the aisle beams land on them)
    for x in PILLAR_X:
        for z in (HZ0, HZ1):
            if (x, z) == (288, HZ0):
                continue                      # the passage to the stair leaves the north wall here
            w.fill(x, 69, z, x, 72, z, "stone_bricks")
            w.set(x, 68, z, "chiseled_stone_bricks")
            w.set(x, 72, z, "chiseled_stone_bricks")
    # a red runner from the tunnel mouth to the foot of the table, and into the vault
    for x in (288, 289, 290):
        for z in (-190, -189):
            w.set(x, 68, z, "red_carpet")
    # aisle furniture: map table, lectern, casks, books
    w.set(285, 68, HZ0, "cartography_table")
    w.set(286, 68, HZ0, "lectern[facing=south,has_book=false,powered=false]")
    w.set(287, 68, HZ0, "bookshelf")
    w.set(281, 68, HZ0, "bookshelf")
    w.set(281, 69, HZ0, "bookshelf")
    for x, y, z in ((278, 68, HZ0), (279, 68, HZ0), (278, 69, HZ0), (278, 68, HZ0 + 1),
                    (278, 68, HZ1), (279, 68, HZ1), (278, 69, HZ1)):
        w.set(x, y, z, "barrel[facing=up,open=false]")
    w.set(282, 68, HZ1, "smithing_table")
    w.set(283, 68, HZ1, "anvil[facing=east]")
    # tunnel mouth in the east wall: a chiseled frame
    for z in (-191, -188):
        w.fill(291, 68, z, 291, 70, z, "chiseled_stone_bricks")
    w.set(291, 70, -190, "chiseled_stone_bricks")
    w.set(291, 70, -189, "chiseled_stone_bricks")


def vault(w):
    w.air(VX0, FLOOR + 1, VZ0, VX1, VTOP, VZ1)
    w.fill(VX0, FLOOR, VZ0, VX1, FLOOR, VZ1, "polished_andesite")
    # archway from the nave, iron-barred windows either side
    w.air(277, 68, -190, 277, 70, -189)
    for z in (-191, -188):
        w.fill(277, 68, z, 277, 71, z, "chiseled_stone_bricks")
    w.fill(277, 71, -190, 277, 71, -189, "chiseled_stone_bricks")
    for z in (-192, -187):
        w.set(277, 69, z, "iron_bars[north=true,south=true,east=false,west=false]")
        w.set(277, 70, z, "iron_bars[north=true,south=true,east=false,west=false]")
    for z in (-190, -189):
        w.set(278, 73, z, "red_wall_banner[facing=east]")       # over the arch, on the end wall
    # the hoard: a gold dais at the back, chests and casks along the sides
    w.fill(VX0, 68, -190, VX0, 68, -189, "gold_block")
    w.set(VX0, 69, -190, "gold_block")
    w.set(VX0, 69, -189, "lantern[hanging=false]")
    w.set(VX0, 70, -190, "lantern[hanging=false]")
    w.set(VX0, 68, -191, "emerald_block")
    w.set(VX0, 68, -188, "diamond_block")
    for x in (273, 275):
        w.set(x, 68, VZ0, "chest[facing=south,type=single,waterlogged=false]")
        w.set(x, 68, VZ1, "chest[facing=north,type=single,waterlogged=false]")
    for x in (274, 276):
        w.set(x, 68, VZ0, "barrel[facing=up,open=false]")
        w.set(x, 68, VZ1, "barrel[facing=up,open=false]")
        w.set(x, 69, VZ0, "candle[candles=2,lit=true]")
        w.set(x, 69, VZ1, "candle[candles=2,lit=true]")
    w.set(VX0, 68, VZ0, "gold_block")
    w.set(VX0, 68, VZ1, "gold_block")
    for x in (273, 275):
        w.set(x, VTOP, -190, "lantern[hanging=true]")
        w.set(x, VTOP, -189, "lantern[hanging=true]")


# ---------------------------------------------------------------- tunnels, shaft, lookout
def tunnels(w):
    # entrance: the part's tunnel ends at x 294; dressed stone from x 293 to the hall
    w.air(291, 68, -190, 293, 69, -189)
    w.set(292, 68, -191, "lantern[hanging=false]")
    # hall (north aisle) -> shaft: a 3-high passage north at x 288-289
    w.air(288, 68, -204, 289, 70, HZ0 - 1)
    w.set(288, 70, -200, "lantern[hanging=true]")
    w.set(289, 70, -203, "lantern[hanging=true]")
    # upper passage east to the balcony (walk 80)
    w.air(288, UP_FLOOR + 1, UP_Z[0], 298, UP_FLOOR + 2, UP_Z[1])
    for x in (290, 293, 296):
        w.set(x, UP_FLOOR + 3, UP_Z[(x // 3) % 2], "shroomlight")
    # last step up to the balcony door
    for z in UP_Z:
        w.set(299, UP_FLOOR + 1, z, stair("east"))
        w.air(299, UP_FLOOR + 2, z, 299, UP_FLOOR + 3, z)
        w.set(299, UP_FLOOR + 4, z, "stone_bricks")
        w.set(299, UP_FLOOR + 1 - 1, z, "stone_bricks")


def shaft(w):
    x1, z1, x2, z2 = SHAFT
    # the spiral: one lap of 12 steps from the hall floor (walk 68) to the upper passage (walk 80);
    # start=4 puts the first step at the passage's end (x 287, z -204), the top landing at (287, -205)
    spiral_stairs(w.b, x1 - OX, z1 - OZ, x2 - OX, z2 - OZ, 0, UP_FLOOR + 1 - OY,
                  "stone_brick_stairs", "polished_andesite", start=4)
    # the newel is solid rock-brick; shroomlights in it light the stair
    for y, (x, z) in ((70, (286, -203)), (73, (285, -203)), (76, (285, -204)), (79, (286, -204))):
        w.set(x, y, z, "shroomlight")


def balcony(w):
    x0, x1, z0, z1, fy = BAL_X0, BAL_X1, BAL_Z0, BAL_Z1, BAL_FLOOR
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            g = ground(x, z)
            for y in range(g + 1, fy):                       # a one-course base down to the slope
                w.set(x, y, z, brick(x, y, z))
            w.set(x, fy, z, "polished_andesite" if x0 < x < x1 and z0 < z < z1 else brick(x, fy, z))
            w.air(x, fy + 1, z, x, max(g, fy + 3), z)
    # corbels under the outer edge where it stands proud of the slope
    for z in range(z0, z1 + 1):
        if ground(x1 + 1, z) < fy - 1:
            w.set(x1 + 1, fy - 1, z, stair("west", "top"))
    # parapet: a wall along the outer edge and the low ends of the sides; where the slope is higher the
    # side is a stone-brick retaining wall up to the grass
    for z in range(z0, z1 + 1):
        end = z in (z0, z1)
        w.set(x1, fy + 1, z, wall_post(n=z > z0, s=z < z1, w=end, up=end))
    for z in (z0, z1):
        for x in range(x0, x1):
            g = ground(x, z)
            if g >= fy + 1:
                w.fill(x, fy + 1, z, x, g, z, brick)
            else:
                w.set(x, fy + 1, z, wall_post(e=True, w=True, up=False))
    w.set(x1, fy + 2, z0, "lantern[hanging=false]")
    w.set(x1, fy + 2, z1, "lantern[hanging=false]")
    # the back wall: a retaining wall up to the slope, never above it except the door's lintel
    for z in range(z0, z1 + 1):
        g = ground(x0 - 1, z)
        top = max(g, fy + 3) if z in UP_Z else (g if g > fy else fy + 1)
        w.fill(x0 - 1, fy, z, x0 - 1, top, z, brick)
    for z in UP_Z:
        w.air(x0 - 1, fy + 1, z, x0 - 1, fy + 2, z)
        w.set(x0 - 1, fy + 3, z, "chiseled_stone_bricks")
    # a stone hood over the door and the benches, corbelled out of the slope
    for z in range(z0 + 1, z1):
        if ground(x0 - 1, z) >= fy + 3:
            w.set(x0, fy + 3, z, stair("west", "top"))
    # benches against the back wall, looking east over the lake; a lantern hung from the hood
    w.set(x0, fy + 1, z0 + 1, stair("west", block="spruce_stairs"))
    w.set(x0, fy + 1, z1 - 1, stair("west", block="spruce_stairs"))
    w.set(x0 + 1, fy + 1, z0 + 1, "barrel[facing=up,open=false]")
    w.set(x0 + 1, fy + 2, z0 + 1, "lantern[hanging=false]")


def build():
    b = Build("mountain-hall")
    w = W(b)
    if os.environ.get("MOUNTAIN_BASELINE"):  # the same box with nothing in it: the terrain's own audit
        w.set(271, 64, -208, "stone")
        w.set(304, 84, -181, "air")
        return b
    door(w)
    shells(w)
    hall(w)
    vault(w)
    tunnels(w)
    shaft(w)
    balcony(w)
    ledge(w)
    return b


def cover_report(b):
    """Carved (air) cells with fewer than 3 blocks of ground above them, outside the door face and the
    balcony (the two places meant to break the surface)."""
    bad = []
    for (lx, ly, lz), blk in b.blocks.items():
        if blk != "air":
            continue
        x, y, z = lx + OX, ly + OY, lz + OZ
        if (x, z) not in G or y > ground(x, z):
            continue
        if x >= 299 and z <= -202:          # balcony and its door
            continue
        if x >= 300 and -192 <= z <= -187:  # the door face niche
            continue
        if ground(x, z) - y < 3:
            bad.append((x, y, z, ground(x, z) - y))
    return bad


G = _grid()

if __name__ == "__main__":
    bb = build()
    (a, c) = bb.bounds()
    print("local bounds", a, c, "world", (a[0] + OX, a[1] + OY, a[2] + OZ), (c[0] + OX, c[1] + OY, c[2] + OZ))
    bad = cover_report(bb)
    print(f"cover: {len(bad)} carved cells with < 3 blocks above", sorted(bad)[:30])
    print("blocks", len(bb.blocks))
    # the audit on a model world (solid rock under the surface grid, air above, water as air): shows the
    # build's own fails in full, without the natural caves inside the box the real preview also counts
    from architect import audit
    own = {(lx + OX, ly + OY, lz + OZ): blk for (lx, ly, lz), blk in bb.blocks.items()}
    xs, ys, zs = zip(*own)
    box = ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
    cells = {}
    for x in range(box[0][0] - 2, box[1][0] + 3):
        for z in range(box[0][2] - 2, box[1][2] + 3):
            g = ground(x, z) if (x, z) in G else 90
            for y in range(box[0][1] - 3, box[1][1] + 3):
                cells[(x, y, z)] = "air" if y > g else "stone"
    cells.update(own)
    r = audit.audit(cells, box)
    print(f"model audit: {r['fails']} fail, {r['warns']} warn")
    import sys
    full = len(sys.argv) > 1
    for c in r["checks"]:
        print(" ", c["level"], c["check"], c["msg"], c["at"])
    # walk test on the model: from the road end, can a player reach each room, and how many full-block
    # jumps (a step up onto something that is not a stair or slab) are on the best route?
    import heapq
    def stand(p):
        return audit.standable(cells, p)
    def soft(p):
        u = cells.get((p[0], p[1] - 1, p[2]), "")
        return "stairs" in u or "slab" in u
    start = (303, 68, -189)
    best, q = {start: 0}, [(0, start)]
    while q:
        cst, p = heapq.heappop(q)
        if cst > best.get(p, 1e9):
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1, -2):
                n = (p[0] + dx, p[1] + dy, p[2] + dz)
                if n in cells and stand(n) and (dy <= 0 or soft(n) or audit.passable(cells.get((p[0], p[1] + 2, p[2])))):
                    c2 = cst + 1 + (100 if dy == 1 and not soft(n) and not soft(p) else 0)
                    if c2 < best.get(n, 1e9):
                        best[n] = c2
                        heapq.heappush(q, (c2, n))
                    break
    for label, goal in (("hall", (284, 68, -192)), ("vault", (273, 68, -190)), ("hearth", (286, 68, -184)),
                        ("passage top", (293, 80, -205)), ("balcony", (302, 81, -205)),
                        ("ledge/lever", (303, 68, -194))):
        c = best.get(goal)
        print(f"walk {label:<12}", "UNREACHABLE" if c is None else f"{c % 100} steps, {c // 100} full-block jumps")
    if full:  # design pictures from the plan alone (no server): floor plans and cutaway x-rays
        from architect import render
        out = sys.argv[1]
        near = {p: b for p, b in cells.items()}
        plans = [render.plan({p: b for p, b in near.items() if 270 <= p[0] <= 306 and -210 <= p[2] <= -180},
                             y, scale=8) for y in (68, 69, 72, 75, 80, 82)]
        render.sheet(plans, f"{out}/plans.png", columns=3)
        cuts = []
        hallonly = {p: b for p, b in own.items() if p[0] <= 291 and p[2] >= -197}
        for cut, view in ((72, "se"), (72, "nw")):
            cuts.append(render.iso({p: b for p, b in hallonly.items() if p[1] <= cut}, tile=9, view=view))
        filler = ("stone", "stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks")
        skel = {p: b for p, b in own.items() if b not in filler and not b.startswith("redstone")
                and not (p[0] <= 291 and p[2] >= -197 and p[1] >= 73)}
        for view in ("se", "ne"):
            cuts.append(render.iso(skel, tile=7, view=view))
        render.sheet(cuts, f"{out}/cutaway.png", columns=2)
        print("wrote", f"{out}/plans.png", f"{out}/cutaway.png")
