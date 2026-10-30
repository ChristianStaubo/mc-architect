"""Tannery, Riverford: one storey of packed mud on sandstone, acacia frame, orange terracotta bands, flat roof
terrace with hide racks, a lean-to trough on the east and a water stair at the quay edge. --at 367,-72."""
from architect.build import Build
from architect.parts import clear_inside, door, floor, flower_box, straight_stairs, walls, window

W, D = 8, 6          # x 0..7, z 0..5
X2, Z2 = W - 1, D - 1
BASE, FILL, BAND, LOG = "cut_sandstone", "packed_mud", "orange_terracotta", "stripped_acacia_log"


def build():
    b = Build("tannery")
    floor(b, 0, 0, X2, Z2, 0, BASE)
    clear_inside(b, 0, 0, X2, Z2, 1, 7)
    floor(b, 1, 1, X2 - 1, Z2 - 1, 0, "smooth_sandstone")
    walls(b, 0, 0, X2, Z2, 1, 1, BASE)
    walls(b, 0, 0, X2, Z2, 2, 3, FILL)
    walls(b, 0, 0, X2, Z2, 4, 4, BAND)
    walls(b, 0, 0, X2, Z2, 5, 5, FILL)
    for x, z in ((0, 0), (X2, 0), (0, Z2), (X2, Z2), (3, 0), (3, Z2)):
        for y in range(1, 5):
            b.set(x, y, z, f"{LOG}[axis=y]")
    # roof terrace floor, parapet caps
    floor(b, 1, 1, X2 - 1, Z2 - 1, 4, "cut_sandstone")
    for x in range(0, X2 + 1):
        for z in (0, Z2):
            if (x + z) % 2 == 0:
                b.set(x, 5, z, "orange_terracotta")
    for z in range(0, Z2 + 1):
        for x in (0, X2):
            if (x + z) % 2 == 0:
                b.set(x, 5, z, "orange_terracotta")

    # partition between the back room (west) and the workshop (east)
    for z in range(1, Z2):
        for y in (1, 2, 3):
            b.set(3, y, z, FILL)
    door(b, 3, 1, 2, facing="west", wood="acacia")

    # north front: door, windows, banners, path
    door(b, 5, 1, 0, facing="north", wood="acacia")
    window(b, 1, 2, 0, "x", width=2, height=1)
    window(b, 4, 2, 0, "x", width=1, height=1)
    window(b, 6, 2, 0, "x", width=1, height=1)
    b.set(6, 1, -1, "acacia_slab[type=bottom]")
    b.set(4, 1, -1, "acacia_slab[type=bottom]")
    b.set(2, 3, -1, "brown_wall_banner[facing=north]")
    b.set(1, 3, -1, "orange_wall_banner[facing=north]")
    for z in (-1, -2):
        b.set(5, 0, z, "smooth_sandstone")
    b.set(4, 2, -1, "acacia_trapdoor[facing=north,half=bottom,open=true]")
    b.set(6, 2, -1, "acacia_trapdoor[facing=north,half=bottom,open=true]")
    b.set(4, 0, -1, "smooth_sandstone")
    b.set(6, 0, -1, "smooth_sandstone")
    b.set(7, 2, -1, "air")
    b.set(4, 3, -1, "air")
    # back, west and east windows
    window(b, 1, 2, Z2, "x", width=2, height=1)
    window(b, 0, 2, 3, "z", width=1, height=1)
    window(b, 4, 2, Z2, "x", width=1, height=1)
    window(b, 6, 2, Z2, "x", width=1, height=1)
    flower_box(b, 1, 2, Z2, "x", 2, "south")
    # east opening to the lean-to
    b.set(X2, 1, 1, "air")
    b.set(X2, 2, 1, "air")

    # workshop: cauldron (job block), crates, bolts of leather
    b.set(4, 1, 3, "cauldron")
    b.set(4, 1, 4, "chest[facing=east]")
    b.set(5, 1, 4, "hay_block[axis=y]")
    b.set(5, 1, 3, "brown_carpet")
    b.set(4, 1, 1, "brown_wool")
    b.set(4, 2, 1, "brown_wool")
    b.set(4, 3, 3, "lantern[hanging=true]")
    b.set(5, 3, 2, "lantern[hanging=true]")
    # back room: bed, chest, lantern
    b.set(1, 1, 3, "brown_bed[facing=north,part=head]")
    b.set(1, 1, 4, "brown_bed[facing=north,part=foot]")
    b.set(2, 1, 4, "chest[facing=north]")
    b.set(2, 2, 4, "lantern")
    b.set(1, 3, 1, "lantern[hanging=true]")
    b.set(2, 1, 1, "red_carpet")
    # stairs to the terrace
    straight_stairs(b, 6, 1, 4, "north", 3, "acacia_stairs")

    # terrace: hide racks, lanterns, pots
    for z in (2, 4):
        for x in (2, 5):
            b.set(x, 5, z, "acacia_fence[east=true,west=true]" if False else "acacia_fence")
            b.set(x, 6, z, "acacia_fence[east=true]" if x == 2 else "acacia_fence[west=true]")
        for x in (3, 4):
            b.set(x, 6, z, "acacia_fence[east=true,west=true]")
    b.set(3, 5, 2, "brown_wool")
    b.set(4, 5, 2, "orange_wool")
    b.set(3, 5, 4, "red_wool")
    b.set(4, 5, 4, "brown_wool")
    for x, z in ((0, 0), (X2, 0), (0, Z2), (X2, Z2)):
        b.set(x, 6, z, "lantern")
    b.set(1, 5, 1, "potted_dead_bush")
    b.set(6, 5, 1, "lantern")

    # lean-to with trough on the east
    for z in (2, 3, 4):
        b.set(9, 1, z, "stone_bricks")
    b.set(8, 1, 2, "stone_bricks")
    b.set(8, 1, 5, "stone_bricks")
    b.set(8, 1, 3, "water")
    b.set(8, 1, 4, "water")
    floor(b, 8, 1, 9, 5, 0, "smooth_sandstone")
    for z in (1, 5):
        for y in (1, 2):
            b.set(9, y, z, "acacia_fence")
    b.set(9, 2, 3, "acacia_fence")
    for x in (8, 9):
        for z in range(1, 6):
            b.set(x, 3, z, "acacia_slab[type=bottom]")
    b.set(8, 2, 1, "lantern[hanging=true]") if False else None

    # water stair down from the quay edge (NE corner)
    for x in (8, 9):
        b.set(x, -1, -2, "sandstone_stairs[facing=north,half=bottom]")
        b.set(x, -2, -1, "sandstone_stairs[facing=north,half=bottom]")
        b.set(x, -1, -1, "air")
        b.set(x, -1, 0, "air")
        b.set(x, -2, 0, "air")
        b.set(x, -3, 0, "water")
        b.set(x, -4, 0, "cut_sandstone")
    return b
