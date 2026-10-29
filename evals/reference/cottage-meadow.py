"""L-shaped timber and stone cottage on a meadow: main hall (ridge x) plus south wing (cross gable),
chimney, flower boxes, garden fence, path."""
from architect.build import Build
from architect.parts import clear_inside, door, floor, gable_roof, light, timber_frame, window

MW, MD = 13, 7      # main hall x 0..12, z 0..6
WW, WD = 7, 6       # wing x 0..6, z 6..11 (shares z=6 wall line)
H = 4
LOG = "oak_log[axis=y]"
FILL = "birch_planks"
BASE = "cobblestone"


def build():
    b = Build("cottage-meadow")
    mx, mz = MW - 1, MD - 1
    wx, wz = WW - 1, MD - 1 + WD - 1   # wing x2, z2 = 6, 11
    # floors and stone base
    floor(b, 0, 0, mx, mz, 0, BASE)
    floor(b, 0, mz, wx, wz, 0, BASE)
    clear_inside(b, 0, 0, mx, mz, 1, H + 4)
    clear_inside(b, 0, mz, wx, wz, 1, H + 4)
    # walls: stone course at y1, timber frame above
    timber_frame(b, 0, 0, mx, mz, 1, H, FILL, LOG, "dark_oak_log", every=4)
    timber_frame(b, 0, mz, wx, wz, 1, H, FILL, LOG, "dark_oak_log", every=3)
    for x in range(0, mx + 1):
        for z in (0, mz):
            if z == mz and x <= wx:
                continue
            if x % 4 != 0:
                b.set(x, 1, z, "stone_bricks" if x % 3 else "mossy_cobblestone")
    for z in range(1, mz):
        for x in (0, mx):
            b.set(x, 1, z, "stone_bricks" if z % 2 else "mossy_cobblestone")
    for x in range(1, wx):
        b.set(x, 1, wz, "stone_bricks" if x % 2 else "mossy_cobblestone")
    for z in range(mz + 1, wz):
        b.set(0, 1, z, "stone_bricks"); b.set(wx, 1, z, "stone_bricks")
    # open the wing to the hall
    for x in range(1, wx):
        for y in range(1, H):
            b.set(x, y, mz, "air")
    # interior floor
    floor(b, 1, 1, mx - 1, mz - 1, 0, "spruce_planks")
    floor(b, 1, mz, wx - 1, wz - 1, 0, "spruce_planks")
    # door on wing south, porch
    door(b, 3, 1, wz, facing="south", wood="spruce")
    b.set(2, 2, wz + 1, "lantern[hanging=false]") if False else None
    for x in (2, 4):
        b.set(x, 1, wz + 1, "oak_fence"); 
    b.set(1, 1, wz + 1, "oak_fence"); b.set(5, 1, wz + 1, "oak_fence")
    for x in (1, 5):
        for y in (2, 3):
            b.set(x, y, wz + 1, "oak_fence")
    for x in range(1, 6):
        b.set(x, 4, wz + 1, "dark_oak_slab[type=bottom]")
    b.set(3, 3, wz + 1, "lantern[hanging=true]")
    floor(b, 1, wz + 1, 5, wz + 1, 0, "cobblestone")
    # windows
    window(b, 2, 2, 0, along="x", width=2, height=2)
    window(b, 7, 2, 0, along="x", width=2, height=2)
    window(b, mx, 2, 2, along="z", width=2, height=2)
    window(b, 0, 2, 2, along="z", width=2, height=2)
    window(b, 0, 2, 8, along="z", width=2, height=2)
    window(b, wx, 2, 8, along="z", width=2, height=2)
    window(b, 5, 2, wz, along="x", width=1, height=2)
    window(b, 1, 2, wz, along="x", width=1, height=2)
    for x in (2, 7):
        b.set(x, 1, -1, "flowering_azalea_leaves") if False else None
    # roofs
    gable_roof(b, 0, 0, mx, mz, H + 1, "spruce_stairs", FILL, ridge="x", overhang=1)
    gable_roof(b, 0, mz, wx, wz, H + 1, "spruce_stairs", FILL, ridge="z", overhang=1)
    # chimney on east end of hall (2 wide, stepped base)
    for y in range(0, H + 6):
        for z in (3, 4):
            b.set(mx + 1, y, z, "stone_bricks" if y > 1 else "cobblestone")
    for z in (2, 3, 4, 5):
        b.set(mx + 1, 1, z, "cobblestone")
    for z in (3, 4):
        b.set(mx + 1, H + 6, z, "stone_brick_wall")
    b.set(mx + 1, 2, 2, "cobblestone") ; b.set(mx + 1, 2, 5, "cobblestone")
    # planter boxes under the front windows, woodpile, lamp post, gable windows
    for x in (2, 3, 7, 8):
        b.set(x, 1, -1, "spruce_planks"); b.set(x, 2, -1, "poppy" if x % 2 else "azure_bluet")
    for x in (1, 5):
        b.set(x, 1, wz + 1, "oak_fence")
    for z in (-1,):
        for x in (10, 11):
            b.set(x, 1, z, "oak_log[axis=z]"); b.set(x, 2, z, "oak_log[axis=z]") if x == 10 else None
    b.set(1, 0, wz + 3, "cobblestone"); b.set(5, 0, wz + 3, "cobblestone")
    b.set(1, 1, wz + 3, "oak_fence"); b.set(1, 2, wz + 3, "oak_fence"); b.set(1, 3, wz + 3, "lantern[hanging=false]")
    b.set(5, 1, wz + 3, "oak_fence"); b.set(5, 2, wz + 3, "lantern[hanging=false]")
    for x in (3, 4):
        b.set(x, 0, wz + 6, "dirt_path")
    # interior
    light(b, 3, 1, 1); light(b, 9, 1, 1); light(b, 3, 1, 8); light(b, 9, 1, 5)
    b.set(1, 1, 1, "red_bed[facing=east,part=foot]")
    b.set(2, 1, 1, "red_bed[facing=east,part=head]")
    b.set(11, 1, 1, "crafting_table")
    b.set(11, 1, 2, "furnace[facing=west]")
    b.set(11, 1, 3, "chest[facing=west]")
    b.set(11, 1, 4, "barrel[facing=up]")
    b.set(11, 1, 5, "bookshelf")
    b.set(6, 1, 5, "oak_fence"); b.set(6, 2, 5, "oak_pressure_plate")
    # garden and path
    for x in range(8, 13):
        b.set(x, 0, wz + 1, "farmland") if False else None
    for z in range(wz + 1, wz + 6):
        floor(b, 3, z, 3, z, 0, "dirt_path")
    for x in range(7, 12):
        b.set(x, 1, mz + 1, "oak_fence")
    for x in (8, 10):
        b.set(x, 1, mz + 2, "poppy")
    b.set(9, 1, mz + 2, "blue_orchid")
    for z in (8, 9):
        b.set(12, 0, z, "cobblestone")
    b.set(12, 1, 8, "hay_block"); b.set(12, 1, 9, "barrel[facing=up]")
    return b
