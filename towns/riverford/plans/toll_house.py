"""Riverford toll house: 7x5 sandstone/mud-brick lodge beside the east gate, hatch on the east wall,
low brick-stair hip edge round a flat roof terrace. Door south onto the quay street.
Local 0,0 = north-west corner of the building; place with --at 353,-86."""

from architect.build import Build
from architect.parts import clear_inside, door, floor, light, posts, window

W, D = 7, 5  # footprint
X2, Z2 = W - 1, D - 1
LOG = "stripped_acacia_log"
FILL = "mud_bricks"
BASE = "cut_sandstone"
ROOF = "brick_stairs"
TRIM = "birch_planks"


def ring(b, x1, z1, x2, z2, y, stair):
    """One ring of roof stairs, tall side inward (the bridge's convention, as in hip_roof)."""
    for x in range(x1, x2 + 1):
        b.set(x, y, z1, f"{stair}[facing=south,half=bottom,shape=straight]")
        b.set(x, y, z2, f"{stair}[facing=north,half=bottom,shape=straight]")
    for z in range(z1 + 1, z2):
        b.set(x1, y, z, f"{stair}[facing=east,half=bottom,shape=straight]")
        b.set(x2, y, z, f"{stair}[facing=west,half=bottom,shape=straight]")
    for x, z, shape in ((x1, z1, "outer_left"), (x2, z1, "outer_right"), (x1, z2, "outer_right"), (x2, z2, "outer_left")):
        b.set(x, y, z, f"{stair}[facing={'south' if z == z1 else 'north'},half=bottom,shape={shape}]")


def crate(b, x, y, z):
    """A crate: planks body with a trapdoor lid."""
    b.set(x, y, z, "spruce_planks")
    b.set(x, y + 1, z, "spruce_trapdoor[facing=north,half=bottom,open=false]")


def build():
    b = Build("toll_house")
    # --- shell
    floor(b, 0, 0, X2, Z2, 0, BASE)
    clear_inside(b, 0, 0, X2, Z2, 1, 7)
    floor(b, 1, 1, X2 - 1, Z2 - 1, 0, "birch_planks")
    for x in range(W):
        for z in range(D):
            if x in (0, X2) or z in (0, Z2):
                b.set(x, 1, z, BASE)
                b.set(x, 2, z, FILL)
                b.set(x, 3, z, FILL)
    # frame posts: corners and the middle of the long walls
    for x, z in ((0, 0), (X2, 0), (0, Z2), (X2, Z2), (3, 0), (3, Z2)):
        b.fill(x, 1, z, x, 3, z, f"{LOG}[axis=y]")
    # beam band under the roof deck
    for x in range(W):
        for z in (0, Z2):
            b.set(x, 3, z, f"{TRIM}")
    for z in range(1, Z2):
        for x in (0, X2):
            b.set(x, 3, z, f"{TRIM}")
    for x, z in ((0, 0), (X2, 0), (0, Z2), (X2, Z2), (3, 0), (3, Z2)):
        b.set(x, 3, z, f"{LOG}[axis=y]")

    # --- openings
    door(b, 5, 1, Z2, facing="south", wood="acacia")
    window(b, 1, 2, 0, along="x")
    window(b, 5, 2, 0, along="x")
    window(b, 2, 2, Z2, along="x")  # hidden behind the board? no: board is outside z=Z2+1; window stays
    window(b, 0, 2, 2, along="z")
    window(b, X2, 2, 2, along="z")  # the toll hatch, east wall

    # --- roof: eave ring, inner ring, flat terrace deck
    b.fill(0, 4, 0, X2, 4, Z2, BASE)  # ceiling / deck
    ring(b, -1, -1, X2 + 1, Z2 + 1, 4, ROOF)
    ring(b, 0, 0, X2, Z2, 5, "mud_brick_stairs")
    b.fill(1, 5, 1, X2 - 1, 5, Z2 - 1, "smooth_sandstone_slab[type=bottom]")
    # copper-ish accents on the eaves
    for x in range(0, W, 2):
        b.set(x, 3, -1, "cut_copper_slab[type=top]") if False else None
    # roof access: ladder in the back-right corner of the main room up to the terrace
    for y in range(1, 6):
        b.set(5, y, 1, "ladder[facing=south]")
    b.set(5, 5, 1, "ladder[facing=south]")
    # terrace dressing
    b.set(1, 6, 1, "potted_fern")
    b.set(X2 - 1, 6, Z2 - 1, "potted_azure_bluet")
    b.set(1, 6, Z2 - 1, "potted_red_tulip")
    b.set(3, 6, 2, "acacia_fence")
    b.set(3, 7, 2, "lantern[hanging=false]")

    # --- interior: back room (bed + cartography table) west, office east
    for z in (1, 3):
        b.set(3, 1, z, FILL)
        b.set(3, 2, z, FILL)
        b.set(3, 3, z, FILL)
    b.set(1, 1, 1, "red_bed[facing=south,part=foot]")
    b.set(1, 1, 2, "red_bed[facing=south,part=head]")
    b.set(2, 1, 1, "cartography_table")
    b.set(2, 1, 3, "chest[facing=north]")
    b.set(1, 1, 3, "bookshelf")
    b.set(1, 2, 3, "bookshelf")
    b.set(4, 1, 1, "bookshelf")
    b.set(4, 2, 1, "bookshelf")
    b.set(4, 1, 3, "chest[facing=north]")
    b.set(5, 1, 3, "red_carpet")
    b.set(4, 1, 2, "red_carpet")
    b.set(2, 1, 2, "red_carpet")
    light(b, 1, 3, 1, "lantern[hanging=true]")
    light(b, 4, 3, 2, "lantern[hanging=true]")
    light(b, 2, 3, 3, "lantern[hanging=true]")
    # ledger desk by the hatch
    b.set(5, 1, 2, "acacia_stairs[facing=east,half=bottom]")

    # --- the hatch (east wall, x=6): counter of sandstone slabs, trapdoor shutters, striped awning
    for z in (1, 2, 3):
        b.set(7, 1, z, "cut_sandstone_slab[type=top]")
    b.set(7, 2, 1, "acacia_trapdoor[facing=west,half=bottom,open=true]")
    b.set(7, 2, 3, "acacia_trapdoor[facing=west,half=bottom,open=true]")
    b.set(7, 3, 1, "orange_wool")
    b.set(7, 3, 2, "white_wool")
    b.set(7, 3, 3, "orange_wool")
    b.set(7, 4, 0, "acacia_fence")  # awning fits under the eave stairs
    b.set(7, 2, 2, "lantern[hanging=false]")

    # --- south front: board of trader banners, sign, lanterns by the door
    for x in (0, 1, 2):
        b.set(x, 2, Z2 + 1, "spruce_planks")
        b.set(x, 3, Z2 + 1, "spruce_planks")
    banners = ("cyan", "red", "yellow")  # lakeside first
    for x, c in zip((0, 1, 2), banners):
        for y in (2, 3):
            pass
        b.set(x, 2, Z2 + 2, f"{c}_wall_banner[facing=south]")
        b.set(x, 3, Z2 + 2, f"{c}_wall_banner[facing=south]") if False else None
    b.sign(1, 1, Z2 + 1, "oak_wall_sign[facing=south]", ["Trader's board", "Lakeside", "first", ""])
    b.set(4, 3, Z2 + 1, "lantern[hanging=false]") if False else None
    b.set(4, 3, Z2 + 1, "acacia_fence")
    b.set(4, 2, Z2 + 1, "acacia_fence")
    b.set(4, 1, Z2 + 1, "acacia_fence")
    b.set(4, 4, Z2 + 1, "lantern[hanging=false]") if False else None
    b.set(6, 3, Z2 + 1, "acacia_fence")
    b.set(6, 2, Z2 + 1, "acacia_fence")
    b.set(6, 1, Z2 + 1, "acacia_fence")
    b.set(4, 4, Z2 + 1, "lantern[hanging=false]")
    b.set(6, 4, Z2 + 1, "lantern[hanging=false]")
    # window box under the south window
    b.set(2, 1, Z2 + 1, "dirt")
    b.set(2, 2, Z2 + 1, "potted_red_tulip")

    # --- quay side: path, cart, crates and sacks
    b.fill(5, 0, Z2 + 1, 5, 0, Z2 + 2, "sandstone")
    b.fill(3, 0, Z2 + 1, 3, 0, Z2 + 2, "dirt_path")
    # hand cart
    for x in (3, 4):
        b.set(x, 1, Z2 + 2, "spruce_slab[type=top]")
    b.set(3, 1, Z2 + 1, "spruce_slab[type=top]")
    b.set(4, 1, Z2 + 1, "spruce_slab[type=top]")
    b.set(3, 2, Z2 + 1, "white_wool")
    b.set(4, 2, Z2 + 1, "spruce_trapdoor[facing=south,half=bottom,open=true]")
    b.set(2, 1, Z2 + 2, "spruce_trapdoor[facing=west,half=bottom,open=true]")
    b.set(5, 1, Z2 + 2, "spruce_trapdoor[facing=east,half=bottom,open=true]") if False else None
    b.set(3, 1, Z2 + 3, "spruce_fence") if False else None
    # crates and sacks
    crate(b, 7, 1, Z2 + 1)
    crate(b, 7, 1, Z2 + 2)
    b.set(7, 3, Z2 + 1, "spruce_planks")
    b.set(7, 4, Z2 + 1, "spruce_trapdoor[facing=north,half=bottom,open=false]")
    b.set(6, 1, Z2 + 2, "white_wool")
    b.set(6, 2, Z2 + 2, "light_gray_wool")
    b.set(7, 1, Z2 + 3, "white_wool") if False else None

    # --- weighing beam on the west side
    for y in range(1, 5):
        b.set(-1, y, 3, "acacia_fence")
    for z in (2, 3, 4):
        b.set(-1, 4, z, "acacia_fence")
    for z in (2, 4):
        b.set(-1, 3, z, "iron_chain[axis=y]")
        b.set(-1, 2, z, "heavy_weighted_pressure_plate")
    b.set(-1, 1, 2, "white_wool")
    b.set(-1, 0, 5, "dirt_path")
    return b
