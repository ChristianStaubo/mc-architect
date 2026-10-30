"""Riverford mason's house and yard: a cut/chiseled sandstone house with a flat roof terrace and a
terracotta panel over the door, walled work yard with a stonecutter under a lean-to, a crane, stacked
stone and a half-carved column on trestles. Plot 10 x 10, door south."""

from architect.build import Build
from architect.parts import clear_inside, door, floor, window

HX1, HZ1, HX2, HZ2 = 0, 4, 5, 9   # house footprint (south end of the plot)
FRAME = "stripped_acacia_log"


def build():
    b = Build("masons_yard")
    # paving: sandstone and gravel yard
    for x in range(10):
        for z in range(10):
            b.set(x, 0, z, ("smooth_sandstone", "cut_sandstone", "gravel")[(x * 3 + z * 5) % 3])
    for z in range(4, 10):
        b.set(7, 0, z, "stone_bricks")

    # ---- house
    clear_inside(b, HX1, HZ1, HX2, HZ2, 1, 8)
    for x in range(HX1, HX2 + 1):
        for z in range(HZ1, HZ2 + 1):
            edge = x in (HX1, HX2) or z in (HZ1, HZ2)
            if edge:
                b.set(x, 1, z, "cut_sandstone")
                b.set(x, 2, z, "cut_sandstone")
                b.set(x, 3, z, "chiseled_sandstone" if (x + z) % 2 else "cut_sandstone")
                b.set(x, 4, z, "cut_sandstone")
                b.set(x, 5, z, "cut_sandstone")
    for x, z in ((HX1, HZ1), (HX2, HZ1), (HX1, HZ2), (HX2, HZ2)):
        b.fill(x, 1, z, x, 5, z, "chiseled_sandstone")
    floor(b, 1, HZ1 + 1, HX2 - 1, HZ2 - 1, 1, "smooth_sandstone")
    b.set(3, 1, HZ2, "smooth_sandstone")
    # flat roof terrace with a parapet
    for x in range(HX1, HX2 + 1):
        for z in range(HZ1, HZ2 + 1):
            b.set(x, 6, z, "smooth_sandstone")
    for x in range(HX1, HX2 + 1):
        for z in range(HZ1, HZ2 + 1):
            if x in (HX1, HX2) or z in (HZ1, HZ2):
                if not (x == HX2 and z == 5):
                    b.set(x, 7, z, "cut_sandstone_slab[type=bottom]")

    door(b, 3, 2, HZ2, facing="south", wood="acacia")
    # terracotta pattern panel over the door
    pattern = [["orange_terracotta", "white_terracotta", "red_terracotta"],
               ["red_terracotta", "orange_terracotta", "white_terracotta"]]
    for dz, row in enumerate(pattern):
        for dx, blk in enumerate(row):
            b.set(2 + dx, 5 - dz, HZ2, blk)
    # lanterns by the door and a flower pot
    window(b, 1, 3, HZ2, along="x", width=1, height=2)
    window(b, HX1, 3, 6, along="z", width=2, height=2)
    window(b, 2, 3, HZ1, along="x", width=2, height=2)
    # roof access: ladder on the yard side
    for y in range(1, 7):
        b.set(HX2 + 1, y, 5, "ladder[facing=east]")
    b.set(HX2, 7, 5, "air")

    # interior
    b.set(1, 2, HZ1 + 1, "red_bed[facing=north,part=head]")
    b.set(1, 2, HZ1 + 2, "red_bed[facing=north,part=foot]")
    b.set(4, 2, HZ1 + 1, "chest[facing=west]")
    b.set(4, 2, 7, "crafting_table")
    b.set(3, 2, 5, "decorated_pot")
    b.set(3, 5, 6, "lantern[hanging=true]")
    b.set(1, 5, 8, "lantern[hanging=true]")
    b.set(2, 2, 6, "red_carpet")
    b.set(2, 2, 7, "red_carpet")
    # roof terrace furniture
    b.set(1, 7, 8, "potted_fern")
    b.set(3, 7, 7, "lantern[hanging=false]")
    b.set(4, 7, 5, "potted_cactus")

    # ---- work yard wall (x 6..9 east of the house, z 0..3 north of it)
    def wall(x, z):
        b.set(x, 1, z, "cut_sandstone")
        b.set(x, 2, z, "cut_sandstone")
        b.set(x, 3, z, "cut_sandstone_slab[type=bottom]")

    def pilaster(x, z):
        b.fill(x, 1, z, x, 3, z, "chiseled_sandstone")
        b.set(x, 4, z, "cut_sandstone_slab[type=bottom]")

    for x in range(0, 10):
        wall(x, 0)
    for z in range(0, 10):
        wall(9, z)
    for z in range(1, HZ1):
        wall(0, z)
    for x in range(HX2 + 1, 10):
        if x not in (7, 8):
            wall(x, 9)
    for x, z in ((0, 0), (9, 0), (9, 3), (9, 6), (9, 9), (0, 3), (3, 0), (6, 0), (6, 9)):
        pilaster(x, z)
    b.set(7, 1, 9, "acacia_fence_gate[facing=south,open=false]")
    b.set(8, 1, 9, "acacia_fence_gate[facing=south,open=false]")
    b.set(7, 4, 9, "copper_lantern[hanging=false]")
    b.set(7, 3, 9, "air")

    # lean-to over the stonecutter (x 6..8, z 1..3)
    lx = (6, 8)
    for x in lx:
        b.fill(x, 1, 3, x, 3, 3, f"{FRAME}[axis=y]")
        b.fill(x, 1, 2, x, 4, 2, f"{FRAME}[axis=y]")
        b.fill(x, 1, 1, x, 5, 1, f"{FRAME}[axis=y]")
    for x in range(6, 9):
        b.set(x, 3, 3, f"{FRAME}[axis=x]")
        b.set(x, 4, 2, f"{FRAME}[axis=x]")
        b.set(x, 5, 1, f"{FRAME}[axis=x]")
        b.set(x, 4, 3, "acacia_stairs[facing=north,half=bottom,shape=straight]")
        b.set(x, 5, 2, "acacia_stairs[facing=north,half=bottom,shape=straight]")
        b.set(x, 6, 1, "acacia_stairs[facing=north,half=bottom,shape=straight]")
    b.set(7, 1, 2, "stonecutter[facing=south]")
    b.set(7, 3, 2, "lantern[hanging=true]")
    b.set(8, 1, 2, "sandstone_slab[type=bottom]")

    # crane at the north-west: fence post, boom, chain with a hanging block
    for y in range(1, 7):
        b.set(4, y, 2, "acacia_fence[north=false,south=false,east=false,west=false]")
    for x in (1, 2, 3, 4):
        b.set(x, 7, 2, f"{FRAME}[axis=x]")
    b.set(4, 6, 2, f"{FRAME}[axis=y]")
    b.set(3, 6, 2, "acacia_stairs[facing=east,half=top,shape=straight]")
    for y in (4, 5, 6):
        b.set(1, y, 2, "iron_chain[axis=y]")
    b.set(1, 3, 2, "chiseled_sandstone")
    b.set(1, 1, 2, "cut_sandstone")
    b.set(1, 2, 2, "cut_sandstone")

    # stacks of stone and terracotta
    for x, z, blk, h in ((2, 1, "sandstone", 3), (3, 1, "cut_sandstone", 2), (5, 1, "orange_terracotta", 2),
                         (5, 2, "red_terracotta", 1), (2, 3, "smooth_sandstone", 1), (3, 3, "white_terracotta", 2)):
        b.fill(x, 1, z, x, h, z, blk)

    # half-carved column lying on trestles: carved (chiseled) half, rough half
    for z in (5, 8):
        b.set(8, 1, z, "acacia_fence[north=false,south=false,east=false,west=false]")
    b.set(8, 2, 5, "chiseled_sandstone")
    b.set(8, 2, 6, "chiseled_sandstone")
    b.set(8, 2, 7, "sandstone")
    b.set(8, 2, 8, "sandstone")
    b.set(7, 1, 7, "sandstone_slab[type=bottom]")
    b.set(6, 1, 8, "flower_pot")
    # offcuts by the gate
    b.fill(6, 1, 7, 6, 2, 7, "cut_sandstone")
    b.set(6, 1, 6, "terracotta")
    b.set(9 - 1, 1, 3, "orange_terracotta")
    return b
