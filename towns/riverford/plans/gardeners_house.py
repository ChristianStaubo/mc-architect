"""Riverford gardeners' farmhouse: packed-mud walls, acacia frame, roof terrace with a pergola, and a
two-terrace kitchen garden behind (wheat, beetroot, carrots, potatoes, water channel, melons, scarecrow)."""
from architect.build import Build
from architect.parts import (clear_inside, door, floor, light, timber_frame, window, straight_stairs,
                             awning, flower_box)

FRAME = "stripped_acacia_log"
FILL = "mud_bricks"
BASE = "cut_sandstone"
X1, X2, Z1, Z2 = 1, 7, 1, 5
ROOF_Y = 4
GX1, GX2 = 9, 13          # garden columns
WALL_X = 14
WALL_Z = 9
CH = 12                   # water channel column


def wall(b, x, y, z, **c):
    s = dict(north=False, south=False, east=False, west=False)
    s.update(c)
    props = ",".join(f"{k}={'low' if v else 'none'}" for k, v in s.items())
    b.set(x, y, z, f"mud_brick_wall[up=true,{props}]")


def build():
    b = Build("gardeners_house")
    # --- house ---
    floor(b, X1, Z1, X2, Z2, 0, BASE)
    clear_inside(b, X1, Z1, X2, Z2, 1, 9)
    floor(b, X1 + 1, Z1 + 1, X2 - 1, Z2 - 1, 0, "birch_planks")
    timber_frame(b, X1, Z1, X2, Z2, 1, 3, FILL, post=f"{FRAME}[axis=y]", beam=FRAME, every=3)
    for x in range(X1, X2 + 1):
        for z in (Z1, Z2):
            if "log" not in (b.get(x, 1, z) or ""):
                b.set(x, 1, z, BASE)
    for z in range(Z1, Z2 + 1):
        for x in (X1, X2):
            if "log" not in (b.get(x, 1, z) or ""):
                b.set(x, 1, z, BASE)
    # roof terrace deck, eaves, parapet
    floor(b, X1, Z1, X2, Z2, ROOF_Y, "birch_planks")
    for x in range(X1, X2 + 1):
        b.set(x, ROOF_Y, Z1, f"{FRAME}[axis=x]")
        b.set(x, ROOF_Y, Z2, f"{FRAME}[axis=x]")
    for x in range(0, X2 + 2):
        b.set(x, ROOF_Y, 0, "brick_slab[type=bottom]")
        b.set(x, ROOF_Y, Z2 + 1, "brick_slab[type=bottom]")
    for z in range(0, Z2 + 2):
        b.set(0, ROOF_Y, z, "brick_slab[type=bottom]")
    for x in range(X1, X2 + 1):
        for z in (Z1, Z2):
            b.set(x, ROOF_Y + 1, z, "cut_sandstone_slab[type=bottom]")
    for z in range(Z1, Z2 + 1):
        b.set(X1, ROOF_Y + 1, z, "cut_sandstone_slab[type=bottom]")
        if z != 2:
            b.set(X2, ROOF_Y + 1, z, "cut_sandstone_slab[type=bottom]")
    # pergola: posts, beams, leaves
    for x in (X1, 4, X2):
        for z in (Z1, Z2):
            b.fill(x, ROOF_Y + 1, z, x, ROOF_Y + 3, z, f"{FRAME}[axis=y]")
    for z in range(Z1, Z2 + 1):
        for x in (X1, 4, X2):
            b.set(x, ROOF_Y + 4, z, f"{FRAME}[axis=z]")
    for x in range(X1, X2 + 1):
        for z in (Z1, 3, Z2):
            if x not in (X1, 4, X2) or z == 3:
                b.set(x, ROOF_Y + 4, z, f"{FRAME}[axis=x]") if x not in (X1, 4, X2) else None
    for x, z in ((2, 3), (3, 3), (5, 3), (6, 3), (3, 2), (5, 4), (2, 5), (6, 1)):
        b.set(x, ROOF_Y + 5, z, "oak_leaves[persistent=true]")
    b.set(1, ROOF_Y + 3, 3, "oak_leaves[persistent=true]")
    b.set(7, ROOF_Y + 3, 4, "oak_leaves[persistent=true]")
    b.set(4, ROOF_Y + 1, 3, "potted_azalea_bush")
    b.set(2, ROOF_Y + 1, 4, "hay_block")
    b.set(6, ROOF_Y + 1, 4, "birch_slab[type=bottom]")
    light(b, 6, ROOF_Y + 3, 2, "lantern[hanging=true]") if False else None
    light(b, 2, ROOF_Y + 3, 3, "lantern[hanging=true]") if False else None
    b.set(3, ROOF_Y + 1, 1, "lantern[hanging=false]")
    # door, windows
    door(b, 3, 1, Z1, facing="north", wood="acacia")
    window(b, 5, 2, Z1, along="x", width=2, height=2)
    window(b, 2, 2, Z2, along="x", width=2, height=2)
    window(b, 5, 2, Z2, along="x", width=2, height=2)
    window(b, X1, 2, 2, along="z", width=2, height=2)
    window(b, X2, 2, 2, along="z", width=2, height=2)
    flower_box(b, 5, 1, Z1 - 1, along="x", width=2, out="north") if False else None
    # steps and path
    b.set(3, 0, 0, "sandstone_stairs[facing=south,half=bottom,shape=straight]")
    for x in range(2, 5):
        b.set(x, -1, 0, "dirt_path")
    b.set(2, 1, 0, "potted_poppy")
    b.set(2, 0, 0, BASE)
    b.set(5, 0, 0, BASE)
    b.set(5, 1, 0, "potted_cornflower")
    # outside stair to the roof terrace (east side)
    straight_stairs(b, 8, 1, 5, "north", 4, "sandstone_stairs", support=BASE)
    # interior
    light(b, 3, 3, 3, "lantern[hanging=true]")
    light(b, 5, 3, 3, "lantern[hanging=true]")
    for x in (5, 6):
        b.set(x, 1, 3, "red_bed[facing=south,part=foot]")
        b.set(x, 1, 4, "red_bed[facing=south,part=head]")
    b.set(2, 1, 2, "chest[facing=east]")
    b.set(2, 1, 4, "hay_block")
    b.set(2, 1, 3, "potted_fern")
    # --- kitchen garden ---
    # terrace A (ground level y-1, z1..4) and terrace B (y0, z6..8), sandstone retaining edges
    b.fill(8, -1, 0, WALL_X, -1, WALL_Z, "dirt")
    b.fill(GX1, 0, 0, WALL_X - 1, 5, WALL_Z - 1, "air")
    b.fill(GX1, -1, 0, GX2 + 1, -1, 0, "dirt_path")
    b.fill(GX1, 0, 6, GX2 + 1, 0, 8, "dirt")
    b.fill(GX1, 0, 5, GX2 + 1, 0, 5, BASE)
    b.fill(GX1, -1, 5, GX2 + 1, -1, 5, BASE)
    for z in range(1, 5):
        b.set(9, -1, z, "dirt_path")
        for x in range(10, 15):
            b.set(x, -1, z, "farmland[moisture=7]")
        b.set(CH, -1, z, "water")
    for z in (6, 7):
        for x in range(10, 15):
            b.set(x, 0, z, "farmland[moisture=7]")
        b.set(CH, 0, z, "water")
    for x in range(10, 15):
        if x == CH:
            continue
    # crops (y above farmland)
    crops = {10: "wheat[age=7]", 11: "beetroots[age=3]", 13: "carrots[age=7]", 14: "potatoes[age=7]"}
    for z in range(1, 5):
        for x, c in crops.items():
            b.set(x, 0, z, c)
    for z in (6, 7):
        for x, c in {10: "wheat[age=7]", 11: "carrots[age=7]", 13: "potatoes[age=7]", 14: "beetroots[age=3]"}.items():
            b.set(x, 1, z, c)
    # composters at the garden edge, one each
    b.set(9, 0, 2, "composter[level=3]")
    b.set(9, 0, 4, "composter[level=5]")
    # steps between terraces
    b.set(9, 0, 5, "sandstone_stairs[facing=south,half=bottom,shape=straight]")
    for z in (6, 7, 8):
        b.set(9, 0, z, "dirt_path")
    # melon and pumpkin patch along the back wall
    for x in range(10, 15):
        b.set(x, 0, 8, "grass_block")
        b.set(x, 1, 8, "melon" if x % 2 == 0 else "pumpkin")
    # scarecrow in a straw hat
    b.set(11, 0, 6, "dirt")
    b.set(11, 1, 6, "air")
    b.set(11, 2, 6, "acacia_fence[north=false,south=false,east=true,west=true]")
    b.set(10, 2, 6, "acacia_fence[north=false,south=false,east=true,west=false]")
    b.set(12, 2, 6, "water") if False else None
    b.set(11, 3, 6, "hay_block")
    b.set(11, 4, 6, "carved_pumpkin[facing=south]")
    b.set(11, 5, 6, "bamboo_slab[type=bottom]")
    b.set(11, 1, 6, "acacia_fence[north=false,south=false,east=false,west=false]")
    # town wall at the back and east edge, low wall around the garden
    for x in range(GX1, WALL_X + 1):
        for y in (0, 1, 2):
            wall(b, x, y if x != WALL_X else y, WALL_Z, east=x < WALL_X, west=x > GX1)
    for z in range(0, WALL_Z):
        wall(b, WALL_X, 0, z, north=z > 0, south=True)
        wall(b, WALL_X, 1, z, north=z > 0, south=True)
    # lamp posts
    b.set(9, 0, 8, "acacia_fence[north=false,south=false,east=false,west=false]")
    b.set(9, 1, 8, "lantern[hanging=false]")
    # sign
    return b
