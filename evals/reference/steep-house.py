"""Hillside family house: a stone-brick lower storey (kitchen, dining, hearth) dug into the slope and
standing tall on the low south side with its own garden door; a dark-oak-framed spruce upper storey
entered at ground level from the high north side (hall, two bedrooms); a covered balcony on log
stilts off the bedrooms with a cross gable; dark oak roof, stone chimney, flower boxes, paths."""

from architect.build import Build
from architect.parts import (chimney, clear_inside, door, floor, flower_box, roofs, shutters,
                             straight_stairs, timber_frame, window)

# local (0,0) = world (-480,-128); local y 0 = world 105 (lower floor; people stand at y 1)
PLACE = ["--at", "-480,-128", "--y", "105", "--foundation", "none", "--no-clear"]

X1, Z1, X2, Z2 = 2, 6, 14, 14   # main block walls
UP = 4                          # upper floor slab (stand at 5), walls to 8, roof from 9
FRAME = "dark_oak_log"
FILL = "spruce_planks"
ROOF = "dark_oak_stairs"
HANG = "lantern[hanging=true]"
STAND = "lantern[hanging=false]"


def stone(x, y, z):
    h = (x * 7 + y * 13 + z * 29) % 10
    return ("mossy_stone_bricks" if h < 2 else "cracked_stone_bricks" if h == 2
            else "cobblestone" if h == 3 else "stone_bricks")


def build():
    b = Build("steep-house")

    # ---------- lower storey: stone, dug into the hill ----------
    for y in range(0, UP):
        for x in range(X1, X2 + 1):
            for z in (Z1, Z2):
                b.set(x, y, z, stone(x, y, z))
        for z in range(Z1, Z2 + 1):
            for x in (X1, X2):
                b.set(x, y, z, stone(x, y, z))
    for (x, z) in ((X1, Z1), (X2, Z1), (X1, Z2), (X2, Z2), (6, Z2), (10, Z2)):
        b.fill(x, 0, z, x, UP - 1, z, "polished_andesite")      # quoins / pilasters
    for x in range(X1 - 1, X2 + 2):                             # plinth on the low south side
        b.set(x, 0, Z2 + 1, "stone_brick_stairs[facing=north,half=bottom]")
    b.set(X1 - 1, 0, Z2 + 1, stone(X1 - 1, 0, Z2 + 1))
    b.set(X2 + 1, 0, Z2 + 1, stone(X2 + 1, 0, Z2 + 1))
    clear_inside(b, X1 + 1, Z1 + 1, X2 - 1, Z2 - 1, 1, UP - 1)
    floor(b, X1 + 1, Z1 + 1, 7, Z2 - 1, 0, "polished_andesite")  # kitchen
    floor(b, 8, Z1 + 1, X2 - 1, Z2 - 1, 0, "spruce_planks")       # living / dining

    # ---------- upper storey: timber frame ----------
    timber_frame(b, X1, Z1, X2, Z2, UP, 8, FILL, post=f"{FRAME}[axis=y]", beam=FRAME, every=4)
    clear_inside(b, X1 + 1, Z1 + 1, X2 - 1, Z2 - 1, UP + 1, 8)
    floor(b, X1 + 1, Z1 + 1, X2 - 1, Z2 - 1, UP, "spruce_planks")
    for x in range(X1, X2 + 1):                                  # plate under the eaves
        b.set(x, 9, Z1, FILL)
        b.set(x, 9, Z2, FILL)
    floor(b, X1 + 1, Z1 + 1, X2 - 1, Z2 - 1, 8, "spruce_planks")  # ceiling / loft floor
    for x in (5, 8, 11):                                         # ceiling beams
        for z in range(Z1 + 1, Z2):
            b.set(x, 8, z, f"{FRAME}[axis=z]")
    # partitions: hall z 7..9, bedrooms z 11..13 split at x 8
    b.fill(X1 + 1, UP + 1, 10, X2 - 1, 7, 10, FILL)
    b.fill(8, UP + 1, 11, 8, 7, Z2 - 1, FILL)
    door(b, 4, UP + 1, 10, facing="north", wood="spruce")
    door(b, 12, UP + 1, 10, facing="north", wood="spruce")

    # stairs between the floors, along z 8, rising east to the hall
    straight_stairs(b, 10, 1, 8, "east", 3, "spruce_stairs", support="spruce_planks")
    b.set(9, UP + 1, 8, "spruce_fence")

    # ---------- balcony on stilts (south), with a cross gable ----------
    floor(b, 5, 15, 11, 17, UP, "spruce_planks")
    for (x, z) in ((5, 17), (8, 17), (11, 17), (5, 15), (11, 15)):
        b.fill(x, -1, z, x, UP - 1, z, f"{FRAME}[axis=y]")
        b.set(x, -2, z, "cobblestone")
    for x in range(6, 11):
        b.set(x, UP - 1, 17, f"{FRAME}[axis=x]")
    for (x, z) in ((5, 17), (11, 17)):
        b.fill(x, UP + 1, z, x, 8, z, f"{FRAME}[axis=y]")
    for x in range(6, 11):
        b.set(x, 8, 17, f"{FRAME}[axis=x]")
        b.set(x, UP + 1, 17, "spruce_fence")
    for z in (15, 16):
        b.set(5, UP + 1, z, "spruce_fence")
        b.set(11, UP + 1, z, "spruce_fence")
    door(b, 7, UP + 1, Z2, facing="south", wood="spruce")
    door(b, 9, UP + 1, Z2, facing="south", wood="spruce")

    # ---------- roofs ----------
    roofs(b,
          dict(x1=X1, z1=Z1, x2=X2, z2=Z2, y=9, stair=ROOF, gable=FILL, ridge="x"),
          dict(x1=5, z1=Z2, x2=11, z2=17, y=9, stair=ROOF, gable=FILL, ridge="z"))
    b.set(8, 10, 17, "glass_pane[east=false,west=false,north=false,south=false]")
    chimney(b, X2 + 1, 10, 0, 15, block="cobblestone")

    # ---------- doors and windows ----------
    door(b, 5, UP + 1, Z1, facing="north", wood="dark_oak")      # entrance, high side
    door(b, 4, 1, Z2, facing="south", wood="spruce")             # garden door, low side
    window(b, 8, 2, Z2, along="x", width=2, height=2)
    window(b, 12, 2, Z2, along="x", width=1, height=2)
    window(b, X2, 2, 12, along="z", width=1, height=2)
    window(b, X1, 2, 12, along="z", width=1, height=2)
    window(b, 8, 6, Z1, along="x", width=2, height=2)
    window(b, 12, 6, Z1, along="x", width=1, height=2)
    window(b, 3, 6, Z2, along="x", width=2, height=2)
    window(b, 12, 6, Z2, along="x", width=2, height=2)
    for z in (8, 12):
        window(b, X1, 6, z, along="z", width=1, height=2)
        window(b, X2, 6, z, along="z", width=1, height=2)
    shutters(b, 8, 6, Z1, "x", 2, 2, "north")
    shutters(b, X1, 6, 12, "z", 1, 2, "west")
    shutters(b, X2, 6, 8, "z", 1, 2, "east")
    flower_box(b, X2, 6, 12, "z", 1, "east")
    flower_box(b, 12, 6, Z1, "x", 1, "north")

    # ---------- entrance stoop and porch hood (north) ----------
    for x in range(3, 8):
        for z in (4, 5):
            b.set(x, UP, z, "stone_bricks" if (x + z) % 3 else "mossy_stone_bricks")
            for y in range(UP + 1, UP + 3):
                b.set(x, y, z, "air")
    for x in (3, 7):
        b.fill(x, UP + 1, 4, x, UP + 2, 4, "spruce_fence")
    for x in range(3, 8):
        for z in (4, 5):
            b.set(x, UP + 3, z, "dark_oak_slab[type=bottom]")
    b.set(4, UP + 2, 5, HANG)
    b.set(6, UP + 2, 5, HANG)
    b.set(5, UP, 3, "dirt_path")                                 # path up the hill
    for z in range(0, 3):
        b.set(5, UP + 1, z, "dirt_path")

    # ---------- lower interior: kitchen, dining, hearth ----------
    b.set(3, 1, 7, "smoker[facing=south]")
    b.set(4, 1, 7, "furnace[facing=south]")
    b.set(5, 1, 7, "crafting_table")
    b.set(6, 1, 7, "barrel[facing=up]")
    b.set(3, 1, 8, "barrel[facing=east]")
    b.set(3, 1, 9, "water_cauldron[level=3]")
    b.set(3, 1, 10, "chest[facing=east]")
    for z in (11, 12):                                           # dining table
        b.set(6, 1, z, "spruce_fence")
        b.set(6, 2, z, "spruce_pressure_plate")
        b.set(5, 1, z, "spruce_stairs[facing=east,half=bottom]")
        b.set(7, 1, z, "spruce_stairs[facing=west,half=bottom]")
    # hearth on the east wall, chimney outside
    b.set(13, 1, 10, "campfire[lit=true,facing=west]")
    b.set(13, 1, 9, "stone_bricks")
    b.set(13, 1, 11, "stone_bricks")
    b.fill(13, 2, 9, 13, 3, 11, "stone_bricks")
    b.set(X2, 1, 10, "cobblestone")
    for (x, z, f) in ((11, 11, "east"), (11, 13, "east")):     # armchairs by the fire
        b.set(x, 1, z, f"spruce_stairs[facing={f},half=bottom]")
    b.set(11, 1, 12, "red_carpet")
    b.set(12, 1, 12, "red_carpet")
    b.set(9, 1, 13, "bookshelf")
    b.set(10, 1, 13, "bookshelf")
    for (x, z) in ((4, 9), (6, 11), (11, 12), (8, 10)):
        b.set(x, 3, z, HANG)

    # ---------- upper interior ----------
    for (x, z) in ((5, 8), (11, 9), (5, 12), (11, 12)):
        b.set(x, 7, z, HANG)
    b.set(3, UP + 1, 13, "red_bed[facing=north,part=foot]")      # bedroom A (parents)
    b.set(3, UP + 1, 12, "red_bed[facing=north,part=head]")
    b.set(4, UP + 1, 13, "red_bed[facing=north,part=foot]")
    b.set(4, UP + 1, 12, "red_bed[facing=north,part=head]")
    b.set(3, UP + 1, 11, "chest[facing=south]")
    b.set(6, UP + 1, 11, "barrel[facing=up]")
    b.set(13, UP + 1, 13, "blue_bed[facing=north,part=foot]")    # bedroom B (children)
    b.set(13, UP + 1, 12, "blue_bed[facing=north,part=head]")
    b.set(11, UP + 1, 13, "light_blue_bed[facing=north,part=foot]")
    b.set(11, UP + 1, 12, "light_blue_bed[facing=north,part=head]")
    b.set(9, UP + 1, 11, "chest[facing=south]")
    b.set(3, UP + 1, 7, "bookshelf")
    b.set(3, UP + 1, 8, "bookshelf")
    b.set(7, UP + 1, 7, "potted_fern")
    b.set(13, UP + 1, 9, "barrel[facing=up]")

    # loft in the roof: ladder up through a hatch in the hall corner
    b.fill(13, UP + 1, 7, 13, 8, 7, "ladder[facing=west]")
    b.set(8, 9, 10, STAND)
    b.set(4, 9, 9, "chest[facing=east]")
    b.set(4, 9, 11, "barrel[facing=up]")
    b.set(12, 9, 11, "white_wool")

    # ---------- balcony furniture, lights ----------
    b.set(6, UP + 2, 17, STAND)
    b.set(10, UP + 2, 17, STAND)
    b.set(10, UP + 1, 16, "spruce_stairs[facing=west,half=bottom]")
    b.set(6, UP + 1, 16, "potted_azure_bluet")

    # ---------- garden side (south) ----------
    for z in range(15, 20):
        b.set(4, -1 if z > 16 else 0, z, "gravel" if z % 2 else "coarse_dirt")
    b.set(2, 1, 15, "barrel[facing=up]")
    b.set(2, 2, 15, STAND)
    b.fill(13, 1, 15, 13, 1, 16, "spruce_log[axis=z]")           # woodpile
    b.set(13, 2, 15, "spruce_log[axis=z]")
    return b
