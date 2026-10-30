"""Riverford boat shed: a brick-roofed shed on acacia piles over the river, a slip with a boat inside,
a loft with the boatwright's bed, a quay with a half-built hull on a cradle. Local 0..12 = the plot."""

from architect.build import Build
from architect.parts import awning, door, hip_roof, light, posts, straight_stairs, window

X1, X2, Z1, Z2 = 2, 10, 1, 10      # shed walls
BED = -11
FRAME = "stripped_acacia_log"
FILL, PANEL, BASE = "mud_bricks", "birch_planks", "cut_sandstone"
DECK = "acacia_planks"
SLIP = (5, 7)                      # slip water x range (inside z 2..5)


def build():
    b = Build("boat_shed")

    # piles under the shed and the quay
    pts = [(x, z) for x in (2, 4, 6, 8, 10) for z in (1, 5, 10)] + [(2, 7), (10, 7), (3, 3), (9, 3)]
    posts(b, pts, -1, BED, "stripped_acacia_log[axis=y]")
    posts(b, [(x, 11) for x in (0, 3, 6, 9, 12)], -1, -5, "acacia_log[axis=y]")

    # deck, quay
    b.fill(X1, 0, Z1, X2, 0, Z2, DECK)
    b.fill(0, 0, 11, 12, 0, 12, "smooth_sandstone")
    b.fill(0, 0, 10, 1, 0, 10, "smooth_sandstone")
    b.fill(11, 0, 10, 12, 0, 10, "smooth_sandstone")
    b.fill(SLIP[0], 0, 2, SLIP[1], 0, 5, "air")          # the slip (water below)
    b.fill(0, -1, 0, 0, -1, 0, "air")

    # walls: base band, mud brick with birch panels, frame posts
    for y in range(1, 6):
        for x in range(X1, X2 + 1):
            for z in (Z1, Z2):
                b.set(x, y, z, BASE if y == 1 else (PANEL if (x - X1) % 4 in (2, 3) and y < 5 else FILL))
        for z in range(Z1, Z2 + 1):
            for x in (X1, X2):
                b.set(x, y, z, BASE if y == 1 else (PANEL if (z - Z1) % 4 in (2, 3) and y < 5 else FILL))
    for x, z in [(x, z) for x in (2, 6, 10) for z in (1, 5, 10)] + [(2, 10), (10, 1)]:
        if x in (X1, X2) or z in (Z1, Z2):
            for y in range(1, 6):
                b.set(x, y, z, FRAME)
    for x in range(X1, X2 + 1):                       # eaves belt
        for z in (Z1, Z2):
            b.set(x, 5, z, f"{FRAME}[axis=x]")
    for z in range(Z1, Z2 + 1):
        for x in (X1, X2):
            b.set(x, 5, z, f"{FRAME}[axis=z]")
    for c in ((X1, Z1), (X1, Z2), (X2, Z1), (X2, Z2)):
        b.set(c[0], 5, c[1], FRAME + "[axis=y]")
    b.fill(X1 + 1, 1, Z1 + 1, X2 - 1, 4, Z2 - 1, "air")

    # south door + windows
    door(b, 6, 1, Z2, "south", "birch")
    b.set(6, 3, Z2, "birch_trapdoor[facing=south,half=top,open=false]")
    window(b, 3, 2, Z2, "x", 2, 2)
    window(b, 8, 2, Z2, "x", 2, 2)
    for x in (X1, X2):
        window(b, x, 2, 7, "z", 2, 2)
        window(b, x, 5, 3, "z", 2, 1)                 # loft windows (in the belt)
        for z in (7, 8):
            pass
    # water gate: sill walkway, fence gates, high open lintel
    b.fill(SLIP[0] - 1, 1, Z1, SLIP[1] + 1, 3, Z1, "air")
    b.fill(SLIP[0] - 1, 0, Z1, SLIP[1] + 1, 0, Z1, DECK)
    for x in range(SLIP[0], SLIP[1] + 1):
        b.set(x, 1, Z1, "acacia_fence_gate[facing=north,open=false,in_wall=false]")
        b.set(x, 4, Z1, f"{FRAME}[axis=x]")
    for x in (SLIP[0] - 1, SLIP[1] + 1):
        b.fill(x, 1, Z1, x, 3, Z1, FRAME + "[axis=y]")
    # slip walkways edge: fence rails keep people out of the water
    for z in range(2, 6):
        b.set(SLIP[0] - 1, 1, z, "acacia_fence[east=false,west=false,north=true,south=true]" if 2 < z < 5 else "acacia_fence")
        b.set(SLIP[1] + 1, 1, z, "acacia_fence")
    # (rails above are single-height; walkway cells x=4 and x=8 become rails, x=3 and x=9 stay open)

    # loft: floor over the slip, rail on the south edge, stairs up the east side
    b.fill(3, 4, 2, 8, 4, 6, DECK)
    b.fill(9, 4, 2, 9, 4, 5, DECK)
    straight_stairs(b, 9, 1, 9, "north", 4, "acacia_stairs", support=None)
    for x in range(3, 9):
        b.set(x, 5, 6, "acacia_fence")
    b.set(9, 5, 6, "air")
    # restore loft floor that stairs headroom may have cut
    b.fill(3, 4, 2, 8, 4, 6, DECK)
    b.fill(9, 4, 2, 9, 4, 5, DECK)
    b.set(9, 4, 6, "acacia_stairs[facing=north,half=bottom,shape=straight]")

    # interior
    b.set(3, 5, 3, "red_bed[facing=north,part=head]")
    b.set(3, 5, 4, "red_bed[facing=north,part=foot]")
    b.set(4, 5, 2, "chest[facing=south]")
    b.set(8, 5, 3, "hay_block[axis=y]")
    light(b, 8, 5, 4)
    light(b, 5, 5, 2, "lantern[hanging=false]")
    b.set(3, 1, 2, "barrel[facing=up]")                # fisherman's job block, by the slip
    light(b, 3, 2, 2)
    b.set(9, 1, 2, "acacia_trapdoor[facing=south,half=top,open=false]")
    b.set(9, 1, 3, "chest[facing=west]")
    light(b, 9, 2, 3)
    # south room: nets, crates, rope, lamps
    b.set(3, 1, 9, "hay_block[axis=x]")
    b.set(4, 1, 9, "white_wool")
    b.set(3, 1, 8, "acacia_trapdoor[facing=east,half=bottom,open=false]")
    light(b, 3, 2, 9)
    b.set(8, 1, 9, "acacia_fence")
    light(b, 8, 2, 9)
    b.set(5, 1, 6, "acacia_fence")
    light(b, 5, 2, 6)
    b.set(9, 1, 8, "chest[facing=west]")
    b.set(7, 3, 6, "lantern[hanging=true]")
    b.set(7, 4, 7, "chain[axis=y]") if False else None
    b.entity(6, -1, 3, "spruce_boat")
    # slip floats: oar rack on the walkway wall
    for z in (6, 7):
        pass

    # roof: wide low hip in brick stairs with a copper ridge
    hip_roof(b, X1, Z1, X2, Z2, 5, "brick_stairs", top="waxed_cut_copper_slab", overhang=1)

    # exterior: awning over the door, lanterns, plants
    awning(b, 5, 7, Z2, 4, "south", ("orange_wool", "white_wool"), depth=2)
    for x in (4, 8):
        b.set(x, 1, 11, "acacia_fence")
        b.set(x, 2, 11, "lantern[hanging=false]")
    for x in (3, 9):
        b.set(x, 1, 11, "flower_pot") if False else None
    b.set(5, 1, 11, "potted_fern")
    b.set(7, 1, 11, "potted_poppy")
    b.set(2, 3, 11, "orange_terracotta") if False else None

    # the cradle with a half-built hull on the quay (west of the door)
    for x in (0, 2, 4):
        b.set(x, 1, 11, "stripped_spruce_log[axis=z]")
        b.set(x, 1, 12, "stripped_spruce_log[axis=z]")
    for x in range(0, 6):
        b.set(x, 2, 11, "spruce_planks")                # planked side
        b.set(x, 2, 12, "stripped_spruce_log[axis=x]")  # keel/strake
    for x in (0, 2, 4):
        b.set(x, 3, 12, "spruce_fence")                 # bare ribs
        b.set(x, 4, 12, "spruce_fence")
    for x in range(0, 3):
        b.set(x, 3, 11, "spruce_planks")                # half-planked
    b.set(5, 1, 12, "spruce_slab[type=bottom]")
    # oars leaning on the east end
    for z in (11, 12):
        for k in range(1, 4):
            b.set(11, k, z, "acacia_fence")
        b.set(11, 4, z, "spruce_trapdoor[facing=east,half=bottom,open=true]")
    b.set(10, 1, 11, "white_wool")
    b.set(12, 1, 10, "hay_block[axis=y]")
    b.sign(9, 2, 11, "oak_wall_sign[facing=south]", ["BOAT", "SHED"]) if False else None
    for p in ((3, -6, 4), (6, -6, 6), (7, -4, 7)):   # air pockets in the river bed under the deck
        b.set(*p, "water")
    return b
