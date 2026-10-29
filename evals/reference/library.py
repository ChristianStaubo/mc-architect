"""Village library: a double-height stone hall with dark oak pilasters and tall windows, bookshelf bays
along every wall, reading tables and lecterns on the floor, a mezzanine gallery across the north end
reached by a central stair, a gabled entrance wing on the south and a deepslate roof with a small
lantern cupola."""

from architect.build import Build
from architect.parts import door, floor, gable_roof, hip_roof, window

PLACE = ["--at", "-46,362", "--y", "72"]

X2, Z2 = 16, 12        # hall x 0..16, z 0..12
TOP = 10               # wall top
MZ = 5                 # mezzanine slab level (stand at 6), covers z 1..4
WX1, WX2, WZ2 = 6, 10, 16   # entrance wing
STONE = "stone_bricks"
LOG = "dark_oak_log"
PLANK = "dark_oak_planks"
ROOF = "deepslate_tile_stairs"
HANG = "lantern[hanging=true]"
SHELF = "bookshelf"


def wall_box(b, x1, z1, x2, z2, y1, y2):
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            b.set(x, y, z1, STONE)
            b.set(x, y, z2, STONE)
        for z in range(z1, z2 + 1):
            b.set(x1, y, z, STONE)
            b.set(x2, y, z, STONE)


def bands(b, x1, z1, x2, z2, ys):
    """Dark oak beam rings at the given heights."""
    for y in ys:
        for x in range(x1 + 1, x2):
            b.set(x, y, z1, f"{LOG}[axis=x]")
            b.set(x, y, z2, f"{LOG}[axis=x]")
        for z in range(z1 + 1, z2):
            b.set(x1, y, z, f"{LOG}[axis=z]")
            b.set(x2, y, z, f"{LOG}[axis=z]")


def tall_window(b, x, z, along, out, y1=2, y2=8):
    window(b, x, y1, z, along=along, height=y2 - y1 + 1)
    ox, oz = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}[out]
    back = {"north": "south", "south": "north", "east": "west", "west": "east"}[out]
    b.set(x + ox, y1 - 1, z + oz, f"stone_brick_stairs[facing={back},half=top,shape=straight]")  # sill
    b.set(x + ox, y2 + 1, z + oz, f"stone_brick_slab[type=bottom]")                              # hood


def build():
    b = Build("library")

    # ---------- hall shell ----------
    floor(b, -1, -1, X2 + 1, Z2 + 1, 0, "polished_andesite")    # plinth step all round
    wall_box(b, 0, 0, X2, Z2, 1, TOP)
    b.fill(1, 1, 1, X2 - 1, TOP + 8, Z2 - 1, "air")
    floor(b, 1, 1, X2 - 1, Z2 - 1, 0, "spruce_planks")
    for x in range(1, X2):                                        # dark oak border inlay
        b.set(x, 0, 1, PLANK)
        b.set(x, 0, Z2 - 1, PLANK)
    bands(b, 0, 0, X2, Z2, (MZ, TOP))
    for x in (0, 4, 8, 12, 16):                                   # pilasters
        for z in (0, Z2):
            b.fill(x, 1, z, x, TOP, z, f"{LOG}[axis=y]")
    for z in (4, 8):
        for x in (0, X2):
            b.fill(x, 1, z, x, TOP, z, f"{LOG}[axis=y]")
    for x, z in ((0, 0), (X2, 0), (0, Z2), (X2, Z2)):             # stone corner buttresses
        for dx, dz in ((-1 if x == 0 else 1, 0), (0, -1 if z == 0 else 1)):
            b.fill(x + dx, 1, z + dz, x + dx, 3, z + dz, STONE)
            b.set(x + dx, 4, z + dz, f"stone_brick_stairs[facing={'east' if dx < 0 else 'west' if dx > 0 else 'south' if dz < 0 else 'north'},half=bottom,shape=straight]")

    # ---------- entrance wing (south) ----------
    floor(b, WX1, Z2, WX2, WZ2, 0, "polished_andesite")
    wall_box(b, WX1, Z2 + 1, WX2, WZ2, 1, 4)
    for z in (Z2 + 1, WZ2):
        for x in (WX1, WX2):
            b.fill(x, 1, z, x, 4, z, f"{LOG}[axis=y]")
    for x in range(WX1 + 1, WX2):
        b.set(x, 4, WZ2, f"{LOG}[axis=x]")
    for z in range(Z2 + 2, WZ2):
        b.set(WX1, 4, z, f"{LOG}[axis=z]")
        b.set(WX2, 4, z, f"{LOG}[axis=z]")
    b.fill(WX1 + 1, 1, Z2, WX2 - 1, 4, WZ2 - 1, "air")
    b.fill(WX1 + 1, 0, Z2, WX2 - 1, 0, WZ2 - 1, "spruce_planks")
    b.set(WX1 + 1, 4, Z2, f"stone_brick_stairs[facing=east,half=top,shape=straight]")   # arch
    b.set(WX2 - 1, 4, Z2, f"stone_brick_stairs[facing=west,half=top,shape=straight]")
    b.set(8, 4, Z2, STONE)
    wing = Build("wing")
    gable_roof(wing, WX1, Z2, WX2, WZ2, 5, ROOF, PLANK, ridge="z")
    for (x, y, z), blk in wing.blocks.items():
        if z > Z2:
            b.set(x, y, z, blk)
    door(b, 8, 1, WZ2, facing="south", wood="dark_oak")
    window(b, 8, 6, WZ2, along="x", height=1)                     # gable light
    for x in (WX1, WX2):
        window(b, x, 2, Z2 + 3, along="z", height=2)

    # ---------- main roof + cupola ----------
    gable_roof(b, 0, 0, X2, Z2, TOP + 1, ROOF, STONE, ridge="x")
    for x in (0, X2):                                             # round-ish gable windows
        window(b, x, 13, 6, along="z", height=2)
        window(b, x, 14, 5, along="z", width=3, height=1)
    b.fill(7, 18, 5, 9, 18, 7, "deepslate_tiles")
    for x, z in ((7, 5), (9, 5), (7, 7), (9, 7)):
        b.fill(x, 19, z, x, 20, z, f"{LOG}[axis=y]")
    b.set(8, 19, 6, "lantern[hanging=false]")
    hip_roof(b, 7, 5, 9, 7, 21, ROOF, top="deepslate_tile_slab[type=bottom]", overhang=1)

    # ---------- windows ----------
    for x in (2, 14):
        tall_window(b, x, Z2, "x", "south")
    for x in (0, X2):
        out = "west" if x == 0 else "east"
        for z in (6, 10):
            tall_window(b, x, z, "z", out)
        tall_window(b, x, 2, "z", out, 2, 3)
        tall_window(b, x, 2, "z", out, 7, 8)
    for x in (2, 6, 10, 14):
        tall_window(b, x, 0, "x", "north", 2, 3)
        tall_window(b, x, 0, "x", "north", 7, 8)

    # ---------- mezzanine (north) ----------
    floor(b, 1, 1, X2 - 1, 4, MZ, PLANK)
    for x in range(1, X2):
        if x not in (7, 8, 9):
            b.set(x, MZ + 1, 4, "dark_oak_fence")
        b.set(x, MZ, 4, f"{LOG}[axis=x]")                         # edge beam
    for x in (4, 12):                                             # columns under the edge
        b.fill(x, 1, 4, x, MZ - 1, 4, f"{LOG}[axis=y]")
    # central stair, 3 wide, rising north onto the mezzanine
    for i in range(4):
        z, y = 8 - i, 1 + i
        for x in (7, 8, 9):
            b.set(x, y, z, f"dark_oak_stairs[facing=north,half=bottom,shape=straight]")
            b.fill(x, 1, z, x, y - 1, z, PLANK) if y > 1 else None
    for i in range(4):
        z, y = 8 - i, 2 + i
        for x in (6, 10):
            b.set(x, y, z, "dark_oak_fence")                      # banisters
    b.set(6, 1, 8, "dark_oak_fence")
    b.set(10, 1, 8, "dark_oak_fence")
    b.set(6, 2, 8, "lantern[hanging=false]")
    b.set(10, 2, 8, "lantern[hanging=false]")

    # ---------- bookshelves ----------
    def shelves(cells, y1, y2):
        for x, z in cells:
            b.fill(x, y1, z, x, y2, z, SHELF)
    # ground floor: bays along the side walls between windows
    side = [(1, z) for z in (1, 3, 5, 7, 8, 9, 11)] + [(X2 - 1, z) for z in (1, 3, 5, 7, 8, 9, 11)]
    shelves(side, 1, 3)
    shelves([(x, 1) for x in (1, 3, 4, 5, 7, 8, 9, 11, 12, 13, 15)], 1, 3)       # under the mezzanine
    shelves([(x, Z2 - 1) for x in (1, 3, 4, 5, 11, 12, 13, 15)], 1, 3)            # south wall
    # free-standing double stacks under the mezzanine
    shelves([(x, 3) for x in (2, 3, 13, 14)], 1, 3)
    # mezzanine level
    shelves([(x, 1) for x in (1, 3, 4, 5, 7, 8, 9, 11, 12, 13, 15)], MZ + 1, MZ + 3)
    shelves([(1, 3), (X2 - 1, 3)], MZ + 1, MZ + 3)
    b.fill(1, MZ + 4, 1, X2 - 1, TOP + 2, 1, PLANK)              # cornice: shelves meet the roof
    for x in (1, 15):
        b.set(x, 4, 7, "chiseled_bookshelf[facing=east]" if x == 1 else "chiseled_bookshelf[facing=west]")

    # ---------- reading tables, lecterns, light ----------
    for tx in (3, 13):
        for tz in (6, 7, 8, 9):
            b.set(tx, 1, tz, f"{PLANK}")
        b.set(tx, 2, 6, "lantern[hanging=false]")
        b.set(tx, 2, 9, "lantern[hanging=false]")
        b.set(tx, 2, 7, "white_carpet")
        for tz in (7, 8):
            b.set(tx - 1, 1, tz, "spruce_stairs[facing=west,half=bottom,shape=straight]")
            b.set(tx + 1, 1, tz, "spruce_stairs[facing=east,half=bottom,shape=straight]")
    b.set(8, 1, 10, "lectern[facing=south]")
    b.set(7, 1, 15, "lectern[facing=east]")
    b.set(9, 1, 15, "barrel[facing=up]")
    b.set(9, 2, 15, "lantern[hanging=false]")
    b.set(7, 1, 13, "potted_fern")
    b.set(9, 1, 13, "potted_fern")
    b.set(7, 6, 2, "lectern[facing=south]")
    b.set(10, 6, 2, f"{PLANK}")
    b.set(10, 7, 2, "lantern[hanging=false]")
    b.set(11, 6, 2, "spruce_stairs[facing=east,half=bottom,shape=straight]")
    b.set(3, 6, 2, "lantern[hanging=false]")
    b.set(13, 6, 2, "lantern[hanging=false]")
    for x in (2, 6, 10, 14):                                      # under the mezzanine
        b.set(x, 4, 2, HANG)
    for x, z in ((1, 10), (X2 - 1, 10), (1, 6), (X2 - 1, 6)):
        b.set(x, 1, z, "lantern[hanging=false]")
    for x in (5, 11):                                             # chandeliers from the roof
        b.fill(x, 12, 7, x, 16, 7, "iron_chain[axis=y]")
        b.set(x, 11, 7, HANG)
    b.set(8, 3, 15, HANG)

    # ---------- weathering ----------
    for (x, y, z), blk in list(b.blocks.items()):
        if blk == STONE:
            h = (x * 7 + y * 13 + z * 29) % 11
            if h in (0, 1):
                b.set(x, y, z, "mossy_stone_bricks")
            elif h in (2, 3):
                b.set(x, y, z, "cracked_stone_bricks")

    # ---------- outside: path, lamps, planters ----------
    for z in range(WZ2 + 1, WZ2 + 4):
        for x in (7, 8, 9):
            b.set(x, 0, z, "gravel" if (x + z) % 3 == 0 else "dirt_path")
    for x in (6, 10):
        b.set(x, 1, WZ2 + 2, "stone_brick_wall")
        b.set(x, 2, WZ2 + 2, "dark_oak_fence")
        b.set(x, 3, WZ2 + 2, "lantern[hanging=false]")
    for x in (1, 3, 13, 15):
        b.set(x, 1, Z2 + 1, "azalea" if x in (1, 15) else "potted_poppy")
    return b
