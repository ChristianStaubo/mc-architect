"""Riverford river warehouse: 13x7, two storeys. Smooth sandstone ground floor with three arches onto the
quay street (south), mud-brick upper floor, low brick hip roof with copper gutters, a loading platform and
hoist beam over the water on the north side, striped awning on posts along the quay front.
Local 0,0 = north-west corner; place with --at 364,-88."""

from architect.build import Build
from architect.parts import awning, clear_inside, door, dock, floor, hip_roof, light, straight_stairs, window

W, D = 13, 7
X2, Z2 = W - 1, D - 1
LOG = "stripped_acacia_log"
SAND = "smooth_sandstone"
BASE = "cut_sandstone"
MUD = "mud_bricks"
DECK_Y = 5  # upper floor level


def crate(b, x, y, z):
    """Crate: planks body with a trapdoor lid."""
    b.set(x, y, z, "spruce_planks")
    b.set(x, y + 1, z, "spruce_trapdoor[facing=north,half=bottom,open=false]")


def sack(b, x, y, z, colour="white_wool"):
    b.set(x, y, z, colour)


def hay(b, x, y, z, axis="x"):
    b.set(x, y, z, f"hay_block[axis={axis}]")


def build():
    b = Build("warehouse")
    floor(b, 0, 0, X2, Z2, 0, BASE)
    clear_inside(b, 0, 0, X2, Z2, 1, 9)
    floor(b, 1, 1, X2 - 1, Z2 - 1, 0, "acacia_planks")

    # --- walls: sandstone ground floor, beam band, mud-brick upper floor
    for x in range(W):
        for z in range(D):
            if x in (0, X2) or z in (0, Z2):
                b.set(x, 1, z, BASE)
                for y in (2, 3, 4):
                    b.set(x, y, z, SAND)
                b.set(x, 5, z, f"{LOG}[axis={'x' if z in (0, Z2) else 'z'}]")
                for y in (6, 7, 8):
                    b.set(x, y, z, MUD)
    # corner posts and pillars between arches
    for x in (0, 4, 8, 12):
        for z in (0, Z2):
            b.fill(x, 1, z, x, 4, z, f"{LOG}[axis=y]")
    for x, z in ((0, 0), (X2, 0), (0, Z2), (X2, Z2), (6, 0), (6, Z2)):
        b.fill(x, 6, z, x, 8, z, f"{LOG}[axis=y]")
    for z in (3,):
        for x in (0, X2):
            b.fill(x, 6, z, x, 8, z, f"{LOG}[axis=y]")
    # upper floor deck (stairs cut through it later)
    floor(b, 1, 1, X2 - 1, Z2 - 1, DECK_Y, "acacia_planks")

    # --- three arches on the quay (south). centre arch is glazed with the door.
    for a in (1, 5, 9):
        for x in range(a, a + 3):
            for y in (1, 2, 3):
                b.set(x, y, Z2, "air")
        b.set(a, 3, Z2, "smooth_sandstone_stairs[facing=west,half=top]")
        b.set(a + 2, 3, Z2, "smooth_sandstone_stairs[facing=east,half=top]")
    door(b, 6, 1, Z2, facing="south", wood="acacia")
    for y in (1, 2):
        b.set(5, y, Z2, "glass_pane")
        b.set(7, y, Z2, "glass_pane")
    b.set(6, 3, Z2, "glass_pane")
    # wide loading opening onto the platform (north), upper hoist door
    for x in (5, 6, 7):
        for y in (1, 2, 3):
            b.set(x, y, 0, "air")
    b.set(5, 3, 0, "smooth_sandstone_stairs[facing=west,half=top]")
    b.set(7, 3, 0, "smooth_sandstone_stairs[facing=east,half=top]")
    for y in (6, 7):
        b.set(6, y, 0, "air")
    # hoist hatch: open opening with a ledge and rails (no door: the outside is a drop)
    for x in (5, 6, 7):
        b.set(x, 5, -1, "acacia_slab[type=top]")
    b.set(5, 6, -1, "acacia_fence")
    b.set(7, 6, -1, "acacia_fence")
    b.set(5, 6, 0, "acacia_trapdoor[facing=south,half=bottom,open=true]")
    b.set(7, 6, 0, "acacia_trapdoor[facing=south,half=bottom,open=true]")
    # ceiling, with the space under the hip roof filled solid (no sealed attic)
    for x in range(1, X2):
        for z in range(1, Z2):
            k = min(x + 1, X2 + 1 - x, z + 1, Z2 + 1 - z)
            b.fill(x, 9, z, x, 9 + k - 1, z, "acacia_planks")

    # --- small upper windows
    for x in (2, 4, 8, 10):
        window(b, x, 7, Z2, along="x")
    for x in (2, 10):
        window(b, x, 7, 0, along="x")
    window(b, 0, 7, 2, along="z")
    window(b, 0, 7, 4, along="z")
    window(b, X2, 7, 3, along="z")
    # lower side windows
    window(b, 0, 2, 3, along="z", height=2)

    # --- roof with copper gutters
    hip_roof(b, 0, 0, X2, Z2, 9, "brick_stairs", top="brick_slab[type=bottom]", overhang=1)
    for x in range(-1, W + 1):
        for z in (-1, D):
            b.set(x, 8, z, "cut_copper_slab[type=top]")
    for z in range(0, D):
        for x in (-1, W):
            b.set(x, 8, z, "cut_copper_slab[type=top]")

    # --- stairs to the upper floor, along the north wall at the east end
    straight_stairs(b, 11, 1, 1, "west", 4, "acacia_stairs")

    # --- ground floor goods
    for z in range(1, 6):
        b.set(1, 1, z, "chest[facing=east]") if z in (1, 2, 4, 5) else None
    b.set(1, 2, 1, "chest[facing=east]") if False else None
    for x, z in ((2, 1), (3, 1), (2, 2), (3, 2)):
        crate(b, x, 1, z)
    crate(b, 2, 3, 1)
    crate(b, 3, 3, 1) if False else None
    crate(b, 2, 3, 2)
    for z in (4, 5):
        for x in (9, 10):
            hay(b, x, 1, z)
    hay(b, 9, 2, 5)
    hay(b, 10, 2, 5)
    hay(b, 9, 2, 4)
    for x, z, c in ((7, 4, "white_wool"), (8, 4, "light_gray_wool"), (7, 5, "white_wool"), (8, 5, "white_wool"), (7, 3, "light_gray_wool")):
        sack(b, x, 1, z, c)
    sack(b, 8, 2, 4, "white_wool")
    # scale
    b.fill(4, 1, 3, 4, 3, 3, "acacia_fence")
    b.set(3, 3, 3, "acacia_fence")
    b.set(5, 3, 3, "acacia_fence")
    b.set(3, 2, 3, "iron_chain[axis=y]")
    b.set(5, 2, 3, "iron_chain[axis=y]")
    b.set(3, 1, 3, "heavy_weighted_pressure_plate")
    b.set(5, 1, 3, "heavy_weighted_pressure_plate")
    # chest row under the awning bay and the centre aisle stays clear
    b.set(11, 1, 5, "chest[facing=west]")
    b.set(11, 1, 4, "chest[facing=west]")
    for x, z in ((3, 4), (7, 2), (9, 2), (5, 5)):
        light(b, x, 4, z, "lantern[hanging=true]")
    light(b, 6, 4, 3, "lantern[hanging=true]")

    # --- upper floor: hay loft, chests, sacks
    for z in (1, 2, 3):
        for x in (1, 2):
            hay(b, x, 6, z, axis="z")
    hay(b, 1, 7, 1, axis="z")
    hay(b, 2, 7, 1, axis="z")
    for x in (3, 4, 5):
        b.set(x, 6, 1, "chest[facing=south]")
    for x, z, c in ((9, 5, "white_wool"), (10, 5, "light_gray_wool"), (10, 4, "white_wool"), (9, 4, "white_wool")):
        sack(b, x, 6, z, c)
    sack(b, 10, 7, 5, "white_wool")
    for x, z in ((4, 4), (5, 4), (4, 5)):
        crate(b, x, 6, z)
    crate(b, 4, 8, 4) if False else None
    for x, z in ((3, 3), (8, 4)):
        light(b, x, 8, z, "lantern[hanging=true]")
    light(b, 6, 8, 2, "lantern[hanging=true]")
    light(b, 6, 8, 5, "lantern[hanging=true]")
    light(b, 10, 8, 2, "lantern[hanging=true]")
    light(b, 2, 8, 5, "lantern[hanging=true]")

    # --- north: loading platform over the water and hoist beam
    dock(b, 3, -2, 9, -1, 0, -5, wood="acacia", boats=0)
    for x in (5, 6, 7):
        b.set(x, 1, -1, "air")
    for z in (-1, -2):
        b.set(6, 8, z, f"{LOG}[axis=z]")
    b.set(6, 7, -1, "acacia_fence")
    b.set(6, 7, -2, "iron_chain[axis=y]")
    b.set(6, 6, -2, "iron_chain[axis=y]")
    b.set(6, 5, -2, "iron_chain[axis=y]")
    b.set(6, 4, -2, "lantern[hanging=true]")
    crate(b, 4, 1, -1)
    crate(b, 8, 1, -1)
    crate(b, 8, 1, -2)
    sack(b, 3, 1, -1)

    # --- south: awning on posts with goods under it
    awning(b, 1, 11, Z2, 4, "south", colors=("orange_wool", "white_wool"), depth=2)
    for x in (1, 4, 8, 11):
        b.fill(x, 1, Z2 + 2, x, 2, Z2 + 2, "acacia_fence")
    for x in (1, 4, 8, 11):
        b.set(x, 3, Z2 + 2, "orange_wool" if x % 2 else "white_wool") if False else None
    b.fill(1, 0, Z2 + 1, 11, 0, Z2 + 1, "sandstone")
    crate(b, 2, 1, Z2 + 1)
    crate(b, 3, 1, Z2 + 1)
    crate(b, 2, 3, Z2 + 1) if False else None
    sack(b, 10, 1, Z2 + 1)
    sack(b, 11, 1, Z2 + 1, "light_gray_wool")
    hay(b, 9, 1, Z2 + 1)
    b.set(9, 2, Z2 + 1, "hay_block[axis=x]")
    b.set(7, 1, Z2 + 1, "chest[facing=south]")
    b.set(5, 1, Z2 + 1, "chest[facing=south]")
    for x in (4, 8):
        b.set(x, 3, Z2 + 1, "lantern[hanging=false]") if False else None
    b.set(0, 1, Z2 + 1, "acacia_fence")
    b.set(0, 2, Z2 + 1, "lantern[hanging=false]")
    b.set(X2, 1, Z2 + 1, "acacia_fence")
    b.set(X2, 2, Z2 + 1, "lantern[hanging=false]")
    return b
