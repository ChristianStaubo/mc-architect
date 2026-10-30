"""Riverford smithy: mud-brick house with a hip roof and a loft, plus an open forge under an arch
with a flat terrace roof. Plot 12 x 10, door south."""

from architect.build import Build
from architect.parts import awning, chimney, clear_inside, door, floor, hip_roof, light, timber_frame, window

HX1, HZ1, HX2, HZ2 = 1, 1, 7, 6   # house footprint
H = 5                              # wall top
LOFT = 4                           # loft floor y
FX1, FX2 = 8, 11                   # forge pavilion x range (z HZ1..HZ2)
FRAME = "stripped_acacia_log"


def build():
    b = Build("smithy")
    # courtyard paving over the whole plot
    for x in range(12):
        for z in range(10):
            b.set(x, 0, z, "cut_sandstone" if (x + z) % 3 else "smooth_sandstone")
    # path to the door
    for z in range(7, 10):
        b.set(3, 0, z, "stone_bricks")
        b.set(4, 0, z, "stone_bricks")

    # ---- house
    clear_inside(b, HX1, HZ1, HX2, HZ2, 1, H + 6)
    timber_frame(b, HX1, HZ1, HX2, HZ2, 1, H, "mud_bricks", post=f"{FRAME}[axis=y]", beam=FRAME, every=3)
    for x in range(HX1, HX2 + 1):  # sandstone base band
        for z in (HZ1, HZ2):
            b.set(x, 1, z, "cut_sandstone")
    for z in range(HZ1, HZ2 + 1):
        for x in (HX1, HX2):
            b.set(x, 1, z, "cut_sandstone")
    floor(b, HX1 + 1, HZ1 + 1, HX2 - 1, HZ2 - 1, 0, "birch_planks")
    # terracotta band under the eaves
    for x in range(HX1 + 1, HX2):
        for z in (HZ1, HZ2):
            b.set(x, H - 1, z, "orange_terracotta" if x % 2 else "white_terracotta")
    for z in range(HZ1 + 1, HZ2):
        b.set(HX1, H - 1, z, "orange_terracotta" if z % 2 else "white_terracotta")

    door(b, 3, 1, HZ2, facing="south", wood="birch")
    window(b, 2, 2, HZ1, along="x", width=2, height=2)
    window(b, HX1, 2, 3, along="z", width=2, height=2)
    b.set(3, 4, HZ2, "mud_bricks")
    # terracotta arch over the door
    b.set(3, 3, HZ2, "red_terracotta")

    hip_roof(b, HX1, HZ1, HX2, HZ2, H, "brick_stairs", top="brick_slab[type=bottom]")
    # copper gutters under the eaves, copper weathervane
    for x in range(0, 9):
        b.set(x, H - 1, 0, "cut_copper_slab[type=top]")
        b.set(x, H - 1, HZ2 + 1, "cut_copper_slab[type=top]")
    for z in range(1, HZ2 + 1):
        b.set(0, H - 1, z, "cut_copper_slab[type=top]")
    b.set(4, H + 4, 3, "cut_copper")
    b.set(4, H + 5, 3, "lightning_rod[facing=up]")

    # loft with the bed, ladder in the south-east corner
    for x in range(HX1 + 1, HX2):
        for z in range(HZ1 + 1, HZ2):
            if (x, z) != (6, 5):
                b.set(x, LOFT, z, "birch_planks")
    for y in range(1, LOFT + 2):
        b.set(6, y, 5, "ladder[facing=north]")
    b.set(2, LOFT + 1, 2, "red_bed[facing=north,part=head]")
    b.set(2, LOFT + 1, 3, "red_bed[facing=north,part=foot]")
    b.set(5, LOFT + 1, 2, "copper_lantern[hanging=false]")
    b.set(4, LOFT + 1, 4, "lantern[hanging=false]")
    b.set(5, LOFT + 1, 3, "chest[facing=west]")

    # workshop
    b.set(2, 1, 2, "smithing_table")
    b.set(3, 1, 2, "chest[facing=south]")
    b.set(5, 1, 2, "red_carpet")
    b.set(2, 3, 4, "lantern[hanging=true]")
    b.set(5, 3, 4, "copper_lantern[hanging=true]")
    b.set(4, 1, 2, "decorated_pot")
    b.set(2, 1, 5, "flower_pot")

    # street wall: rack of copper pots and tools under an awning
    awning(b, 5, 7, HZ2, 3, "south", colors=("orange_wool", "white_wool"), depth=2)
    for x in (5, 6, 7):
        b.set(x, 2, HZ2, "copper_block" if x != 6 else "oxidized_copper")
    b.set(5, 1, HZ2 + 1, "birch_slab[type=top]")
    b.set(6, 1, HZ2 + 1, "birch_slab[type=top]")
    b.set(7, 1, HZ2 + 1, "birch_slab[type=top]")
    b.set(5, 2, HZ2 + 1, "decorated_pot")
    b.set(6, 2, HZ2 + 1, "flower_pot")
    b.set(7, 2, HZ2 + 1, "decorated_pot")
    b.set(1, 2, HZ2 + 1, "flower_pot")
    b.set(2, 1, HZ2 + 1, "potted_cactus")

    # lanterns by the door

    # ---- open forge pavilion
    for x in range(FX1, FX2 + 1):
        for z in range(HZ1, HZ2 + 1):
            b.set(x, 0, z, "stone_bricks" if (x + z) % 2 else "cracked_stone_bricks")
    clear_inside(b, FX1 - 1, HZ1 - 1, FX2 + 1, HZ2 + 1, 1, 6)
    # north wall (mud brick), columns at the corners, arch on the south
    for x in range(FX1, FX2 + 1):
        for y in (1, 2, 3):
            b.set(x, y, HZ1, "mud_bricks")
    for x, z in ((FX1, HZ2), (FX2, HZ2), (FX2, HZ1), (FX1, HZ1)):
        b.fill(x, 1, z, x, 3, z, f"{FRAME}[axis=y]")
    b.set(FX2, 1, 3, f"{FRAME}[axis=y]")
    b.fill(FX2, 2, 3, FX2, 3, 3, f"{FRAME}[axis=y]")
    b.set(FX1 + 1, 3, HZ2, "sandstone_stairs[facing=west,half=top]")
    b.set(FX1 + 2, 3, HZ2, "sandstone_stairs[facing=east,half=top]")
    # flat roof terrace
    for x in range(FX1, FX2 + 1):
        for z in range(HZ1, HZ2 + 1):
            b.set(x, 4, z, "cut_sandstone")
    for x in range(FX1 + 1, FX2 + 1):
        b.set(x, 5, HZ2, "cut_sandstone_slab[type=bottom]")
        b.set(x, 5, HZ1, "cut_sandstone_slab[type=bottom]")
    for z in range(HZ1, HZ2 + 1):
        b.set(FX2, 5, z, "cut_sandstone_slab[type=bottom]")
    b.set(FX2 - 1, 5, HZ2 - 1, "potted_fern")
    b.set(FX1 + 1, 5, HZ2 - 1, "potted_cactus")
    # forge: furnace under the chimney, anvil, lantern
    chimney(b, 10, HZ1, 1, 7, "bricks", smoke=True, cap="brick_slab[type=bottom]")
    b.set(10, 1, HZ1 + 1, "furnace[facing=south,lit=true]")
    b.set(9, 1, HZ1 + 1, "stone_brick_slab[type=bottom]")
    b.set(11, 1, HZ1 + 1, "stone_brick_slab[type=bottom]")
    b.set(10, 1, 4, "anvil[facing=east]")
    b.set(9, 1, 5, "chest[facing=south]")
    b.set(11, 1, 5, "decorated_pot")
    b.set(9, 3, 4, "copper_lantern[hanging=true]")
    b.set(10, 3, 3, "lantern[hanging=true]")
    b.set(9, 1, 3, "stone_brick_slab[type=top]")
    # trade sign and a hanging copper lantern pair by the door
    b.set(0, 1, 8, "flower_pot")
    b.set(11, 1, 8, "decorated_pot")
    b.set(0, 1, 5, "hay_block")
    b.set(0, 1, 4, "hay_block")
    return b
