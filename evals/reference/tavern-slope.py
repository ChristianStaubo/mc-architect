"""Timber-frame tavern dug into a hillside: stone-brick ground floor (bar room), plaster upper floor
(three guest rooms off a corridor), a gabled entrance wing on the low south side, chimney on the hill end."""

from architect.build import Build
from architect.parts import (clear_inside, door, floor, gable_roof, light, straight_stairs,
                             timber_frame, window)

W, D = 18, 10          # main block footprint (x 0..17, z 0..9)
WX1, WX2, WZ2 = 11, 17, 14  # entrance wing: x 11..17, z 9..14
Y_UP = 4               # upper floor slab level; storey top beam at 8
FRAME = "dark_oak_log"
BASE = "stone_bricks"
PLASTER = "birch_planks"
ROOF = "dark_oak_stairs"
GABLE = "spruce_planks"
HANG = "lantern[hanging=true]"


def build():
    b = Build("tavern-slope")
    x2, z2 = W - 1, D - 1

    # ---------- ground floor shell ----------
    floor(b, 0, 0, x2, z2, 0, "cobblestone")
    floor(b, WX1, z2, WX2, WZ2, 0, "cobblestone")
    timber_frame(b, 0, 0, x2, z2, 0, Y_UP, BASE, post=f"{FRAME}[axis=y]", beam=FRAME, every=4)
    timber_frame(b, WX1, z2, WX2, WZ2, 0, Y_UP, BASE, post=f"{FRAME}[axis=y]", beam=FRAME, every=6)
    clear_inside(b, 1, 1, x2 - 1, z2 - 1, 1, 3)
    clear_inside(b, WX1 + 1, z2 + 1, WX2 - 1, WZ2 - 1, 1, 3)
    b.fill(13, 1, z2, 15, 3, z2, "air")              # opening between wing and bar room
    b.fill(13, 0, z2, 15, 0, z2, "spruce_planks")
    floor(b, 1, 1, x2 - 1, z2 - 1, 0, "spruce_planks")
    floor(b, WX1 + 1, z2 + 1, WX2 - 1, WZ2 - 1, 0, "spruce_planks")

    # ---------- wing roof first (main upper walls overwrite what pokes in) ----------
    gable_roof(b, WX1, z2, WX2, WZ2, Y_UP + 1, ROOF, GABLE, ridge="z")

    # ---------- upper storey ----------
    timber_frame(b, 0, 0, x2, z2, Y_UP, 8, PLASTER, post=f"{FRAME}[axis=y]", beam=FRAME, every=4)
    clear_inside(b, 1, 1, x2 - 1, z2 - 1, Y_UP + 1, 8)
    floor(b, 1, 1, x2 - 1, z2 - 1, Y_UP, "spruce_planks")
    for x in (4, 8, 12):                               # open ceiling beams
        for z in range(1, z2):
            b.set(x, 8, z, f"{FRAME}[axis=z]")

    # partitions: corridor z1..3, rooms z5..8
    for x in range(1, x2):
        b.fill(x, 5, 4, x, 7, 4, "spruce_planks")
    for x in (6, 12):
        b.fill(x, 5, 5, x, 7, 8, "spruce_planks")
    for dx in (3, 9, 14):
        door(b, dx, 5, 4, facing="south", wood="spruce")

    # stairs against the north wall, rising east
    straight_stairs(b, 2, 1, 1, "east", 4, "oak_stairs", support="spruce_planks")
    for x in (2, 3, 4):
        b.set(x, 5, 2, "oak_fence")

    # main roof
    gable_roof(b, 0, 0, x2, z2, 9, ROOF, GABLE, ridge="x")

    # dormers on the south slope
    for c in (3, 9):
        for x in (c - 1, c + 1):
            b.fill(x, 9, 7, x, 11, 10, "birch_planks")
        b.fill(c, 9, 7, c, 12, 9, "air")
        b.fill(c - 1, 9, 10, c + 1, 10, 10, "birch_planks")
        b.set(c, 10, 10, "glass_pane")
        b.set(c, 9, 10, "glass_pane")
        gable_roof(b, c - 1, 7, c + 1, 10, 11, ROOF, GABLE, ridge="z")
        b.set(c, 11, 10, "glass_pane")

    # ---------- weathering: mossy / cracked variation on stone ----------
    for (x, y, z), blk in list(b.blocks.items()):
        if blk == BASE:
            h = (x * 7 + y * 13 + z * 29) % 9
            if h in (0, 1):
                b.set(x, y, z, "mossy_stone_bricks")
            elif h in (2, 3):
                b.set(x, y, z, "cracked_stone_bricks")

    # ---------- windows ----------
    for x in (2, 6, 10):
        window(b, x, 2, z2, along="x", height=2)       # south, ground
    for x in (6, 10):
        window(b, x, 2, 0, along="x", height=2)        # north, ground
    for z in (2, 6):
        window(b, x2, 2, z, along="z", height=2)       # east, ground
    for z in (11, 12):
        window(b, WX1, 2, z, along="z", height=2)
        window(b, WX2, 2, z, along="z", height=2)
    for x in (2, 6, 10, 14):
        window(b, x, 6, 0, along="x", height=2)        # corridor north
    for x in (2, 9):
        window(b, x, 6, z2, along="x", height=2)       # rooms south
    window(b, 0, 6, 7, along="z", height=2)
    window(b, x2, 6, 7, along="z", height=2)
    window(b, 0, 6, 2, along="z", height=2)
    window(b, x2, 6, 2, along="z", height=2)

    # ---------- entrance ----------
    door(b, 14, 1, WZ2, facing="south", wood="dark_oak")
    b.set(14, 3, WZ2 + 1, "oak_wall_sign[facing=south]")
    b.set(13, 3, WZ2 + 1, "red_wall_banner[facing=south]")
    b.set(15, 3, WZ2 + 1, "red_wall_banner[facing=south]")
    for x in (12, 16):
        b.set(x, 1, WZ2 + 1, "dark_oak_fence")
        b.set(x, 2, WZ2 + 1, "dark_oak_fence")
        b.set(x, 3, WZ2 + 1, "lantern[hanging=false]")
    # front terrace (z 15..16) with steps stepping down the slope to the south
    for x in range(WX1 - 1, WX2 + 2):
        for z in (WZ2 + 1, WZ2 + 2):
            b.fill(x, -3, z, x, -1, z, "cobblestone")
            b.set(x, 0, z, "stone_bricks" if (x + z) % 3 else "mossy_stone_bricks")
    for z in (WZ2 + 1, WZ2 + 2):
        for x in (WX1 - 1, WX2 + 1):
            b.set(x, 1, z, "cobblestone_wall")
    for i, z in enumerate(range(WZ2 + 3, WZ2 + 6)):
        for x in (13, 14, 15):
            b.fill(x, -3, z, x, -i - 1, z, "cobblestone")
            b.set(x, -i - 1, z, "stone_brick_stairs[facing=south,half=bottom]")
        b.set(12, -i - 1, z, "cobblestone_wall")
        b.set(16, -i - 1, z, "cobblestone_wall")
    for z in range(WZ2 + 6, WZ2 + 9):                  # path south at ground level
        b.set(14, -3, z, "dirt_path")
        b.set(13 if z % 2 else 15, -3, z, "gravel")
    for x in (12, 16):
        b.set(x, 2, WZ2 + 2, "dark_oak_fence")
        b.set(x, 3, WZ2 + 2, "lantern[hanging=false]")
        b.set(x, 1, WZ2 + 2, "dark_oak_fence")
    # outdoors: flower boxes, barrels, woodpile
    for x in (2, 6, 10):
        b.set(x, 0, z2 + 1, "cobblestone")
        b.set(x, 1, z2 + 1, "potted_poppy" if x != 6 else "potted_azure_bluet")
    b.set(8, 1, z2 + 1, "barrel[facing=up]")
    b.set(9, 1, z2 + 1, "barrel[facing=up]")
    b.fill(x2 + 1, 1, 1, x2 + 1, 1, 4, "oak_log[axis=z]")
    b.fill(x2 + 1, 2, 2, x2 + 1, 2, 3, "oak_log[axis=z]")

    # chimney on the hill (west) end
    b.fill(0, 1, 6, 0, 16, 6, "stone_bricks")
    b.fill(0, 1, 5, 0, 3, 5, "cobblestone")
    b.fill(0, 1, 7, 0, 3, 7, "cobblestone")
    b.set(0, 17, 6, "stone_brick_slab[type=bottom]")

    # ---------- ground floor interior ----------
    b.fill(1, 1, 5, 1, 2, 5, "stone_bricks")           # fireplace
    b.fill(1, 1, 7, 1, 2, 7, "stone_bricks")
    b.fill(1, 3, 5, 1, 3, 7, "stone_bricks")
    b.set(1, 1, 6, "campfire[lit=true]")
    for x in range(8, 15):                             # bar counter
        b.set(x, 1, 3, "dark_oak_planks")
        b.set(x, 2, 3, "spruce_slab[type=bottom]")
    for x in range(9, 16):
        b.set(x, 1, 1, "barrel[facing=south]")
    b.set(15, 1, 2, "chest[facing=west]")
    b.set(8, 1, 1, "brewing_stand")
    b.set(11, 2, 3, "lantern[hanging=false]")
    for (tx, tz) in ((4, 5), (4, 8), (9, 6), (7, 8)):  # tables
        b.set(tx, 1, tz, "oak_fence")
        b.set(tx, 2, tz, "oak_pressure_plate")
    for (sx, sz, f) in ((3, 5, "west"), (5, 5, "east"), (3, 8, "west"), (5, 8, "east"),
                        (8, 6, "west"), (10, 6, "east"), (9, 7, "south")):
        b.set(sx, 1, sz, f"oak_stairs[facing={f},half=bottom]")
    for (lx, lz) in ((3, 3), (9, 5), (13, 6), (6, 8), (13, 2), (4, 6)):
        b.set(lx, 3, lz, HANG)
    b.set(12, 1, 11, "barrel[facing=up]")
    b.set(16, 1, 11, "barrel[facing=up]")
    b.set(12, 2, 11, "lantern[hanging=false]")
    b.set(16, 2, 11, "lantern[hanging=false]")
    b.set(12, 1, 13, "dark_oak_fence")
    b.set(12, 2, 13, "lantern[hanging=false]")
    b.set(16, 1, 13, "dark_oak_fence")
    b.set(16, 2, 13, "lantern[hanging=false]")

    # ---------- upstairs furnishing ----------
    for hx, hz, ch in ((1, 5, (5, 8)), (11, 5, (7, 8)), (16, 5, (13, 8))):
        b.set(hx, 5, hz, "red_bed[facing=north,part=head]")
        b.set(hx, 5, hz + 1, "red_bed[facing=north,part=foot]")
        b.set(ch[0], 5, ch[1], "chest[facing=north]")
    for (lx, lz) in ((4, 2), (8, 2), (12, 2), (4, 7), (8, 7)):
        b.set(lx, 7, lz, HANG)
    light(b, 15, 5, 8, "lantern[hanging=false]")
    return b
