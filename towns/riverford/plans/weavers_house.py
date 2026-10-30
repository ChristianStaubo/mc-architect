"""Weaver's house, Riverford: mud brick on sandstone, white terracotta bands, birch frame, wide arch workshop
with striped awning, hip roof in brick, east balcony over a wool line. Plan origin: --at 355,-72."""
from architect.build import Build
from architect.parts import (awning, clear_inside, door, floor, flower_box, hip_roof, light, straight_stairs, walls,
                             window)

W, D = 8, 6          # x 0..7, z 0..5
X2, Z2 = W - 1, D - 1
BASE, FILL, BAND, LOG = "cut_sandstone", "mud_bricks", "white_terracotta", "stripped_birch_log"
WOOLS = ["orange_wool", "white_wool", "red_wool", "white_wool"]


def build():
    b = Build("weavers_house")
    floor(b, 0, 0, X2, Z2, 0, BASE)
    clear_inside(b, 0, 0, X2, Z2, 1, 9)
    floor(b, 1, 1, X2 - 1, Z2 - 1, 0, "smooth_sandstone")
    # walls: sandstone base course, mud brick, band at floor level and under the eaves
    walls(b, 0, 0, X2, Z2, 1, 1, BASE)
    walls(b, 0, 0, X2, Z2, 2, 3, FILL)
    walls(b, 0, 0, X2, Z2, 4, 4, BAND)
    walls(b, 0, 0, X2, Z2, 5, 7, FILL)
    walls(b, 0, 0, X2, Z2, 8, 8, BAND)
    for x, z in ((0, 0), (X2, 0), (0, Z2), (X2, Z2)):
        for y in range(1, 8):
            b.set(x, y, z, f"{LOG}[axis=y]")
    for z in (3,):
        for y in range(1, 8):
            b.set(0, y, z, f"{LOG}[axis=y]")
            b.set(X2, y, z, f"{LOG}[axis=y]")
    for y in range(1, 8):
        b.set(4, y, Z2, f"{LOG}[axis=y]")
        b.set(2, y, 0, f"{LOG}[axis=y]") if y < 4 else None
    # upper floor and ceiling
    floor(b, 1, 1, X2 - 1, Z2 - 1, 4, "birch_planks")

    # ground floor north: door at x1, wide arch x3..6 with lintel
    door(b, 1, 1, 0, facing="north", wood="birch")
    for x in range(3, 7):
        for y in (1, 2, 3):
            b.set(x, y, 0, "air")
        b.set(x, 3, 0, f"{LOG}[axis=x]")
    awning(b, 3, 6, 0, 4, "north", colors=("orange_wool", "white_wool"), depth=2)
    # front dressing
    for x in (0, 2):
        pass
    b.set(0, 1, -1, "birch_fence")
    b.set(0, 2, -1, "lantern")
    b.set(2, 1, -1, "potted_red_tulip")
    for x in range(1, 7):
        if x in (1,):
            continue
    for x in (3, 4, 5, 6):
        b.set(x, 0, -1, "smooth_sandstone")
        b.set(x, 0, -2, "smooth_sandstone")
    b.set(1, 0, -1, "smooth_sandstone")
    b.set(1, 0, -2, "smooth_sandstone")
    # upper north windows + flower boxes
    window(b, 1, 5, 0, "x", width=2, height=2)
    window(b, 4, 5, 0, "x", width=3, height=2)
    flower_box(b, 4, 4, 0, "x", 3, "north") if False else None
    # south and west windows
    window(b, 2, 2, Z2, "x", width=2, height=2)
    window(b, 5, 2, Z2, "x", width=1, height=2)
    window(b, 2, 5, Z2, "x", width=2, height=2)
    window(b, 5, 5, Z2, "x", width=2, height=2)
    window(b, 0, 5, 1, "z", width=2, height=2)
    window(b, X2, 2, 1, "z", width=1, height=2)
    window(b, X2, 2, 4, "z", width=1, height=2)
    flower_box(b, 2, 2, Z2, "x", 2, "south")
    flower_box(b, 5, 5, Z2, "x", 2, "south")

    # orange terracotta pattern on the upper walls (only where the wall is plain mud brick)
    for (x, y, z), blk in list(b.blocks.items()):
        if y == 6 and blk == FILL and (x + z) % 2 == 0:
            b.set(x, y, z, "orange_terracotta")
    for x in (2, 5):
        for y in (2, 3):
            b.set(x, y, -1, "air")
    # vines up the south-west corner
    for y in (2, 3, 4):
        b.set(-1, y, 5, "vine[east=true]")
    # roof: brick hip, copper cap
    hip_roof(b, 0, 0, X2, Z2, 8, "brick_stairs", top="cut_copper", overhang=1)

    # ground floor interior: loom workshop, wool bolts, chest
    b.set(2, 1, 4, "loom[facing=north]")
    b.set(1, 1, 4, "chest[facing=east]")
    for i, z in enumerate((2, 3)):
        b.set(1, 1, z, WOOLS[i])
    b.set(1, 2, 2, "red_wool")
    b.set(1, 2, 3, "orange_wool")
    b.set(4, 1, 1, "white_wool")
    b.set(4, 2, 1, "orange_wool")
    b.set(3, 1, 3, "red_carpet")
    b.set(4, 1, 3, "orange_carpet")
    b.set(3, 3, 2, "lantern[hanging=true]")
    b.set(5, 3, 2, "lantern[hanging=true]")
    b.set(2, 3, 3, "lantern[hanging=true]")
    # stairs up along the east wall
    straight_stairs(b, 6, 1, 4, "west", 4, "birch_stairs")

    # upper room: bed, chest, table, banner, rug
    b.set(1, 5, 1, "white_bed[facing=north,part=head]")
    b.set(1, 5, 2, "white_bed[facing=north,part=foot]")
    b.set(1, 5, 4, "chest[facing=east]")
    b.set(1, 6, 4, "lantern")
    b.set(4, 5, 2, "birch_fence")
    b.set(4, 6, 2, "lantern")
    b.set(3, 5, 2, "birch_stairs[facing=east,half=bottom]")
    b.set(5, 5, 2, "birch_stairs[facing=west,half=bottom]")
    b.set(4, 5, 3, "red_carpet")
    b.set(3, 5, 3, "orange_carpet")
    b.set(5, 5, 3, "orange_carpet")
    b.set(6, 5, 1, "birch_fence")
    b.set(6, 6, 1, "lantern")
    b.set(6, 5, 2, "birch_fence")
    b.set(6, 6, 2, "lantern")

    # balcony on the east side, door from the upper room
    b.set(X2, 5, 3, "air")
    b.set(X2, 6, 3, "air")
    door(b, X2, 5, 3, facing="east", wood="birch")
    for x in (8, 9):
        for z in (2, 3, 4):
            b.set(x, 4, z, "birch_planks")
    for z in (2, 4):
        for y in (1, 2, 3):
            b.set(9, y, z, f"{LOG}[axis=y]")
    for z in (2, 3, 4):
        b.set(9, 5, z, "birch_fence")
    b.set(8, 5, 2, "birch_fence")
    b.set(8, 5, 4, "birch_fence")
    b.set(9, 6, 2, "lantern")
    b.set(9, 6, 4, "lantern")
    b.set(8, 5, 3, "potted_azure_bluet")
    # clothesline: poles at x10, lines at y4, dyed wool hanging
    for z in (1, 5):
        for y in range(1, 5):
            b.set(10, y, z, "birch_fence")
    for z in (1, 5):
        for x in (8, 9):
            b.set(x, 4, z, "birch_fence[east=true,west=true]")
        b.set(10, 4, z, "birch_fence")
    for z in (2, 3, 4):
        b.set(10, 4, z, "birch_fence[north=true,south=true]")
    cols = ["orange_wool", "white_wool", "red_wool", "light_blue_wool", "yellow_wool", "white_wool"]
    i = 0
    for (x, z) in ((8, 1), (9, 1), (10, 2), (10, 3), (10, 4), (9, 5), (8, 5)):
        for y in (3, 2):
            b.set(x, y, z, cols[i % len(cols)])
        i += 1
    # lanterns
    return b
