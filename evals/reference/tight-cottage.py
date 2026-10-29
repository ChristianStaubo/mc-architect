"""Tiny timber cottage on a 9 x 11 plot: a 7 x 8 room under a steep spruce gable roof that runs out over a
recessed front porch, a stone chimney through the roof, shutters and flower boxes under the eaves.
Everything, eaves included, stays inside x 0..8, z 0..10."""
from architect.build import Build
from architect.parts import chimney, door, floor, gable_roof, light, shutters, window

X1, X2, Z1, Z2 = 1, 7, 1, 8      # the room's walls
H = 4                            # wall height (y 1..4), roof from y 5
POST = "dark_oak_log[axis=y]"
FILL = "birch_planks"
ROOF = "spruce_stairs"
BASE = ["cobblestone", "mossy_cobblestone", "stone_bricks"]

PLACE = ["--at", "-472,-48", "--y", "96"]


def build():
    b = Build("tight-cottage")
    # stone floor slab + interior floor
    floor(b, X1, Z1, X2, Z2, 0, "cobblestone")
    floor(b, X1 + 1, Z1 + 1, X2 - 1, Z2 - 1, 0, "spruce_planks")
    b.fill(X1 + 1, 1, Z1 + 1, X2 - 1, H + 5, Z2 - 1, "air")
    # walls: a stone course at y1, birch panels above, dark oak frame posts and a beam band at the top
    for y in range(1, H + 1):
        for x in range(X1, X2 + 1):
            for z in (Z1, Z2):
                b.set(x, y, z, FILL)
        for z in range(Z1, Z2 + 1):
            for x in (X1, X2):
                b.set(x, y, z, FILL)
    for i, x in enumerate(range(X1, X2 + 1)):
        b.set(x, 1, Z1, BASE[i % 3]); b.set(x, 1, Z2, BASE[(i + 1) % 3])
    for i, z in enumerate(range(Z1, Z2 + 1)):
        b.set(X1, 1, z, BASE[(i + 2) % 3]); b.set(X2, 1, z, BASE[i % 3])
    for x in range(X1 + 1, X2):
        b.set(x, H, Z1, "dark_oak_log[axis=x]"); b.set(x, H, Z2, "dark_oak_log[axis=x]")
    for z in range(Z1 + 1, Z2):
        b.set(X1, H, z, "dark_oak_log[axis=z]"); b.set(X2, H, z, "dark_oak_log[axis=z]")
    posts = [(X1, Z1), (X2, Z1), (X1, Z2), (X2, Z2), (4, Z1), (X1, 4), (X2, 4), (2, Z2), (6, Z2)]
    for x, z in posts:
        b.fill(x, 1, z, x, H, z, POST)
    # roof: ridge north-south, eaves at x 0 and 8, gable ends at z 1 and z 9 (the porch gable), eaves to z 0..10
    gable_roof(b, X1, Z1, X2, Z2 + 1, H + 1, ROOF, FILL, ridge="z", overhang=1, end_overhang=1)
    # dark oak trim on the gable ends' bottom row, a round window in the north gable
    for x in range(X1, X2 + 1):
        b.set(x, H + 1, Z1, "dark_oak_log[axis=x]"); b.set(x, H + 1, Z2 + 1, "dark_oak_log[axis=x]")
    window(b, 4, H + 2, Z1, along="x", width=1, height=1)
    window(b, 4, H + 2, Z2 + 1, along="x", width=1, height=1)
    # front porch under the roof: posts, planks, a railing, a step down to the path
    floor(b, X1, Z2 + 1, X2, Z2 + 1, 0, "spruce_planks")
    for x in (X1, X2):
        b.fill(x, 1, Z2 + 1, x, H, Z2 + 1, POST)
    for x in (2, 6):
        b.set(x, 1, Z2 + 1, "spruce_fence")
    b.set(3, 1, Z2 + 1, "potted_red_tulip")
    b.set(5, 1, Z2 + 1, "spruce_stairs[facing=west,half=bottom,shape=straight]")   # a porch seat
    light(b, 4, H, Z2 + 1, "lantern[hanging=true]")
    b.set(4, 0, Z2 + 2, "spruce_stairs[facing=north,half=bottom,shape=straight]")
    for x in (3, 5):
        b.set(x, -1, Z2 + 2, "coarse_dirt")
    door(b, 4, 1, Z2, facing="south", wood="spruce")
    # windows: two-wide with shutters and flower boxes on the long sides, small ones front and back
    window(b, X1, 2, 2, along="z", width=2, height=2)
    window(b, X1, 2, 6, along="z", width=1, height=2)
    window(b, X2, 2, 5, along="z", width=2, height=2)
    window(b, 2, 2, Z1, along="x", width=2, height=2)
    window(b, 6, 2, Z1, along="x", width=1, height=2)
    window(b, 3, 2, Z2, along="x", width=1, height=2)
    window(b, 5, 2, Z2, along="x", width=1, height=2)
    shutters(b, X1, 2, 2, along="z", width=2, height=2, out="west")
    shutters(b, X2, 2, 5, along="z", width=2, height=2, out="east")
    for z, fl in ((2, "poppy"), (3, "azure_bluet")):
        b.set(X1 - 1, 1, z, "moss_block"); b.set(X1 - 1, 2, z, fl)
    for z, fl in ((5, "cornflower"), (6, "dandelion")):
        b.set(X2 + 1, 1, z, "moss_block"); b.set(X2 + 1, 2, z, fl)
    # chimney: a furnace hearth in the north-east corner, stack up through the roof
    b.set(6, 1, 2, "furnace[facing=west,lit=false]")
    chimney(b, 6, 2, 2, 8, block="stone_bricks", smoke=True)
    # interior: bed under the west window, nightstand, storage and a work corner on the east wall
    b.set(2, 1, 2, "red_bed[facing=north,part=head]")
    b.set(2, 1, 3, "red_bed[facing=north,part=foot]")
    b.set(3, 1, 2, "barrel[facing=up]")
    light(b, 3, 2, 2, "lantern[hanging=false]")
    b.set(6, 1, 3, "crafting_table")
    b.set(6, 1, 4, "chest[facing=west,type=single]")
    b.set(6, 1, 7, "barrel[facing=up]")
    b.set(6, 2, 7, "barrel[facing=west]")
    b.set(5, 1, 7, "chest[facing=north,type=single]")
    b.set(2, 1, 7, "bookshelf")
    b.set(2, 2, 7, "potted_cornflower")
    # small table and stool by the west window
    b.set(2, 1, 5, "spruce_fence"); b.set(2, 2, 5, "spruce_pressure_plate")
    b.set(3, 1, 5, "spruce_stairs[facing=west,half=bottom,shape=straight]")
    # lights: hanging lanterns from the beams
    b.fill(X1 + 1, H + 1, 4, X2 - 1, H + 1, 4, "dark_oak_log[axis=x]")  # tie beam across the room
    light(b, 4, H, 4, "lantern[hanging=true]")
    light(b, 5, 1, 6, "lantern[hanging=false]")
    return b
