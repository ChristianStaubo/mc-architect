"""A row of five timber shopfronts stepping down the slope along a street (fronts face south), sharing
party walls: a tall narrow yellow bakery with a front gable, a low blue tailor's with its eaves to the
street and a dormer, a white two-storey apothecary with a jettied upper floor, a squat orange
greengrocer's under a striped awning, and a cyan smithy under a hipped slate roof."""

from architect.build import Build
from architect.parts import (awning, door, flower_box, gable_roof, hip_roof, shutters, window)

PLACE = ["--at", "1,-23", "--y", "112"]

Z2 = 7          # front wall (street side, south); back wall z = 0
FRAME = "spruce_log"


def shell(b, x1, x2, fy, top, fill, beams=(), frame=FRAME):
    """Walls x1..x2 / z 0..Z2 from fy+1 to top with log posts at the corners, beam bands, a floor."""
    b.fill(x1, fy, 0, x2, fy, Z2, "spruce_planks")
    for y in range(fy + 1, top + 1):
        for x in range(x1, x2 + 1):
            b.set(x, y, 0, fill)
            b.set(x, y, Z2, fill)
        for z in range(0, Z2 + 1):
            b.set(x1, y, z, fill)
            b.set(x2, y, z, fill)
    b.fill(x1 + 1, fy + 1, 1, x2 - 1, top + 6, Z2 - 1, "air")
    for x in (x1, x2):
        for z in (0, Z2):
            b.fill(x, fy + 1, z, x, top, z, f"{frame}[axis=y]")
        b.fill(x, fy + 1, 4, x, top, 4, f"{frame}[axis=y]")
    for y in beams + (top,):
        for x in range(x1 + 1, x2):
            b.set(x, y, 0, f"{frame}[axis=x]")
            b.set(x, y, Z2, f"{frame}[axis=x]")
    b.fill(x1, fy, Z2, x2, fy, Z2, "stone_bricks")                 # sill course
    b.fill(x1, fy, 0, x2, fy, 0, "stone_bricks")


def upper_floor(b, x1, x2, y, ladder_x):
    b.fill(x1 + 1, y, 1, x2 - 1, y, Z2 - 1, "spruce_planks")
    b.set(ladder_x, y, 1, "air")
    for yy in range(y - 4, y + 1):
        if not b.blocks.get((ladder_x, yy - 1, 1), "").startswith("spruce_planks") or yy > y - 4:
            pass
    return y


def ladder(b, x, y1, y2):
    for y in range(y1, y2 + 1):
        b.set(x, y, 1, "ladder[facing=south]")


def build():
    b = Build("stall-row")

    # ---------- E: smithy, x 19..23, floor 0, two storeys, hipped deepslate roof (built first: lowest ground)
    shell(b, 19, 23, 0, 9, "cyan_terracotta", beams=(5,), frame="dark_oak_log")
    b.fill(20, 5, 1, 22, 5, 6, "spruce_planks")
    b.set(22, 5, 1, "air")
    ladder(b, 22, 1, 5)
    door(b, 20, 1, Z2, "south", "dark_oak")
    window(b, 22, 2, Z2, "x", height=2)
    window(b, 21, 7, Z2, "x", width=2, height=2)
    window(b, 23, 2, 2, "z", width=2, height=2)
    window(b, 23, 7, 2, "z", width=2, height=2)
    hip_roof(b, 19, 0, 23, Z2, 10, "deepslate_tile_stairs")
    b.fill(23, 1, 0, 23, 13, 0, "cobblestone")                     # forge chimney up the back corner
    b.set(23, 14, 0, "campfire[lit=true,signal_fire=false,facing=north]")
    b.set(20, 1, 1, "blast_furnace[facing=south,lit=true]")
    b.set(21, 1, 1, "anvil[facing=east]")
    b.set(22, 1, 3, "grindstone[face=floor,facing=west]")
    b.set(20, 1, 4, "smithing_table")
    b.set(20, 3, 3, "lantern[hanging=true]") if False else None
    b.set(21, 4, 4, "lantern[hanging=true]")
    b.set(22, 1, 6, "barrel[facing=up]")
    b.set(21, 6, 2, "red_bed[facing=north,part=head]")
    b.set(21, 6, 3, "red_bed[facing=north,part=foot]")
    b.set(20, 6, 5, "lantern[hanging=false]")
    b.set(20, 6, 1, "chest[facing=south]")
    b.set(19, 3, Z2 + 1, "dark_oak_wall_sign[facing=south]") if False else None
    b.set(22, 4, Z2 + 1, "spruce_wall_sign[facing=south]")

    # ---------- D: greengrocer, x 14..19, floor 0, single storey, eaves to the street, awning
    shell(b, 14, 19, 0, 4, "orange_terracotta")
    gable_roof(b, 14, 0, 19, Z2, 5, "mangrove_stairs", "orange_terracotta", ridge="x", end_overhang=0)
    door(b, 18, 1, Z2, "south", "spruce")
    window(b, 15, 1, Z2, "x", width=2, height=2)                   # open display window
    awning(b, 14, 19, Z2, 4, "south", colors=("lime_wool", "white_wool"), depth=2)
    for x, crop in ((15, "pumpkin"), (16, "melon")):
        b.set(x, 1, Z2 + 1, crop)
    b.set(17, 1, Z2 + 1, "composter[level=8]")
    for x in (15, 16):
        b.set(x, 1, 5, "barrel[facing=up]")
        b.set(x, 1, 2, "hay_block")
    b.set(17, 1, 2, "composter[level=4]")
    b.set(18, 1, 2, "pumpkin")
    b.set(16, 2, 5, "lantern[hanging=false]")
    b.set(17, 4, 3, "lantern[hanging=true]")
    b.set(18, 4, 5, "lantern[hanging=true]")

    # ---------- C: apothecary, x 10..14, floor 1, two storeys with a jettied upper floor, front gable
    shell(b, 10, 14, 1, 5, "white_terracotta", frame="dark_oak_log")
    # jetty: the upper storey sits one block further out over the street, on brackets
    b.fill(10, 6, 0, 14, 10, Z2 + 1, "air")
    for y in range(6, 11):
        for x in range(10, 15):
            b.set(x, y, 0, "white_terracotta")
            b.set(x, y, Z2 + 1, "white_terracotta")
        for z in range(0, Z2 + 2):
            b.set(10, y, z, "white_terracotta")
            b.set(14, y, z, "white_terracotta")
    for x in (10, 14):
        for z in (0, Z2 + 1):
            b.fill(x, 6, z, x, 10, z, "dark_oak_log[axis=y]")
    for x in range(11, 14):
        b.set(x, 6, Z2 + 1, "dark_oak_log[axis=x]")
        b.set(x, 10, Z2 + 1, "dark_oak_log[axis=x]")
    b.fill(11, 6, 1, 13, 6, Z2, "spruce_planks")
    b.set(13, 6, 1, "air")
    ladder(b, 13, 2, 6)
    for x in (10, 12, 14):
        b.set(x, 5, Z2 + 1, "dark_oak_stairs[facing=north,half=top,shape=straight]")   # brackets
    door(b, 12, 2, Z2, "south", "dark_oak")
    window(b, 11, 3, Z2, "x", height=1)
    window(b, 13, 3, Z2, "x", height=1)
    window(b, 11, 7, Z2 + 1, "x", width=3, height=2)
    shutters(b, 11, 7, Z2 + 1, "x", 3, 2, "south", wood="dark_oak")
    flower_box(b, 11, 7, Z2 + 1, "x", 3, "south") if False else None
    gable_roof(b, 10, 0, 14, Z2 + 1, 11, "spruce_stairs", "white_terracotta", ridge="z")
    window(b, 12, 12, Z2 + 1, "x", height=2)
    b.set(11, 2, 1, "brewing_stand")
    b.set(12, 2, 1, "cauldron")
    b.set(11, 2, 3, "spruce_planks")
    b.set(13, 2, 3, "spruce_planks")
    b.set(11, 3, 3, "potted_red_mushroom")
    b.set(13, 3, 3, "lantern[hanging=false]")
    b.set(11, 3, 1, "lantern[hanging=false]") if False else None
    b.set(11, 5, 5, "lantern[hanging=true]")
    b.set(11, 7, 2, "white_bed[facing=north,part=head]")
    b.set(11, 7, 3, "white_bed[facing=north,part=foot]")
    b.set(12, 7, 6, "lantern[hanging=false]")
    b.set(12, 7, 1, "bookshelf")
    b.set(12, 8, 1, "potted_allium")
    b.set(11, 4, Z2 + 1, "dark_oak_wall_sign[facing=south]") if False else None

    # ---------- B: tailor, x 4..10, floor 1, single storey, eaves to the street, dormer
    shell(b, 4, 10, 1, 5, "light_blue_terracotta")
    gable_roof(b, 4, 0, 10, Z2, 6, "brick_stairs", "light_blue_terracotta", ridge="x", end_overhang=0)
    for x in range(4, 11):                                          # C's taller wall wins the party line
        for y in range(6, 11):
            if (x, y, 0) in b.blocks and x == 10:
                pass
    door(b, 5, 2, Z2, "south", "spruce")
    window(b, 7, 3, Z2, "x", width=3, height=2)
    flower_box(b, 7, 3, Z2, "x", 3, "south")
    for x, c in ((6, "light_blue_wool"), (7, "white_wool"), (8, "pink_wool"), (9, "yellow_wool")):
        b.set(x, 2, 1, c)
    b.set(7, 2, 3, "loom[facing=south]")
    b.set(9, 2, 3, "cartography_table") if False else None
    b.set(9, 2, 4, "armor_stand") if False else None
    b.set(5, 2, 1, "chest[facing=south]")
    b.set(9, 2, 5, "barrel[facing=up]")
    b.set(9, 3, 5, "lantern[hanging=false]")
    b.set(6, 5, 3, "lantern[hanging=true]")
    # dormer on the street slope
    for x in (6, 8):
        b.fill(x, 6, 4, x, 8, 7, "light_blue_terracotta")
    b.fill(7, 6, 4, 7, 9, 6, "air")
    b.fill(6, 6, 7, 8, 7, 7, "light_blue_terracotta")
    window(b, 7, 6, Z2, "x", height=2)
    gable_roof(b, 6, 4, 8, Z2, 8, "brick_stairs", "light_blue_terracotta", ridge="z", end_overhang=1)
    b.fill(7, 8, 4, 7, 9, 5, "air")

    # ---------- A: bakery, x 0..4, floor 2, tall and narrow, two storeys, front gable
    shell(b, 0, 4, 2, 11, "yellow_terracotta", beams=(7,))
    b.fill(1, 7, 1, 3, 7, 6, "spruce_planks")
    b.set(3, 7, 1, "air")
    ladder(b, 3, 3, 7)
    door(b, 2, 3, Z2, "south", "oak")
    window(b, 1, 4, Z2, "x", height=2)
    window(b, 3, 4, Z2, "x", height=2)
    window(b, 2, 8, Z2, "x", height=2)
    shutters(b, 2, 8, Z2, "x", 1, 2, "south", wood="spruce")
    window(b, 0, 4, 3, "z", width=2, height=2)
    window(b, 0, 9, 3, "z", width=2, height=2)
    gable_roof(b, 0, 0, 4, Z2, 12, "dark_oak_stairs", "yellow_terracotta", ridge="z")
    window(b, 2, 13, Z2, "x", height=1)
    b.fill(1, 3, 1, 1, 3, 2, "smoker[facing=east,lit=true]")
    b.set(1, 3, 2, "furnace[facing=east,lit=true]")
    b.set(1, 3, 4, "spruce_planks")
    b.set(1, 4, 4, "cake")
    b.set(1, 3, 5, "barrel[facing=up]")
    b.set(1, 4, 5, "lantern[hanging=false]")
    b.set(2, 6, 3, "lantern[hanging=true]")
    b.set(1, 8, 2, "yellow_bed[facing=north,part=head]")
    b.set(1, 8, 3, "yellow_bed[facing=north,part=foot]")
    b.set(2, 8, 6, "lantern[hanging=false]")
    b.set(3, 8, 3, "chest[facing=west]") if False else None
    b.set(1, 6, Z2 + 1, "oak_wall_sign[facing=south]")

    # ---------- the street: pavement stepping down the slope, kerb, lamp posts
    for x in range(-1, 25):
        fy = 2 if x <= 4 else 1 if x <= 13 else 0
        for z in (Z2 + 1, Z2 + 2, Z2 + 3):
            if (x, fy + 1, z) in b.blocks and b.blocks[(x, fy + 1, z)] not in ("air",):
                pass
            if (x, fy, z) not in b.blocks or z > Z2 + 1 or b.blocks[(x, fy, z)] == "air":
                h = (x * 5 + z * 3) % 7
                b.set(x, fy, z, "cobblestone" if h < 2 else "andesite" if h < 4 else "stone_bricks")
    for x, fy in ((4, 2), (13, 1)):                                 # steps down the slope
        for z in (Z2 + 2, Z2 + 3):
            b.set(x + 1, fy, z, "stone_brick_stairs[facing=west,half=bottom,shape=straight]")
    for x, fy in ((-1, 2), (9, 1), (24, 0)):
        b.set(x, fy + 1, Z2 + 3, "spruce_fence")
        b.set(x, fy + 2, Z2 + 3, "spruce_fence")
        b.set(x, fy + 3, Z2 + 3, "lantern[hanging=false]")
    return b
