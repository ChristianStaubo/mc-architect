"""Covered oak bridge on stone piers: an 11-block timber gallery over the river (oak frame, plank
skirting and fence balustrade, dark oak gable roof, hanging lanterns), stone-brick abutments with
stair flights climbing three steps up the high west bank and stepping three down to the low east
meadow, parapet walls with lanterns at both portals."""

from architect.build import Build
from architect.parts import gable_roof

# local (0,0) = world (296,-491); local y 0 = world 70 (deck planks; people stand at y 1)
PLACE = ["--at", "296,-491", "--y", "70", "--foundation", "none", "--no-clear"]

X1, X2 = 8, 18          # covered deck (world x 304..314)
Z1, Z2 = 5, 9           # side frames (world z -486..-482); walk lanes z 6..8
PIERS = (11, 15)
BED = -28               # well below the river bed
POST = "stripped_oak_log[axis=y]"
LOG = "oak_log"
STONE = "stone_bricks"
ROOF = "dark_oak_stairs"
HANG = "lantern[hanging=true]"
STAND = "lantern[hanging=false]"


def stone(x, y, z):
    h = (x * 7 + y * 13 + z * 29) % 9
    return "mossy_stone_bricks" if h in (0, 1) else "cracked_stone_bricks" if h == 2 else STONE


def column(b, x, z, top, bottom):
    for y in range(bottom, top + 1):
        b.set(x, y, z, stone(x, y, z))


def build():
    b = Build("river-bridge")

    # ---------- piers and abutments ----------
    for px in PIERS:
        for z in range(Z1, Z2 + 1):
            column(b, px, z, -1, BED)
        for z, f in ((Z1 - 1, "south"), (Z2 + 1, "north")):  # cutwaters up- and downstream
            for y in range(BED, -7):
                b.set(px, y, z, stone(px, y, z))
            b.set(px, -7, z, f"stone_brick_stairs[facing={f},half=bottom]")
        for dx, f in ((-1, "east"), (1, "west")):              # stone corbels under the stringers
            for z in (Z1, 7, Z2):
                b.set(px + dx, -1, z, f"stone_brick_stairs[facing={f},half=top]")
    for z in range(Z1, Z2 + 1):                                # west abutment, in the river edge
        column(b, 7, z, 0, BED)

    # ---------- deck ----------
    for x in range(X1, X2 + 1):
        for z in range(Z1, Z2 + 1):
            b.set(x, 0, z, "oak_planks" if Z1 < z < Z2 else f"stripped_oak_log[axis=x]")
        for z in (Z1, 7, Z2):
            if x not in PIERS:
                b.set(x, -1, z, f"{LOG}[axis=x]")          # stringers

    # ---------- timber gallery ----------
    for x in range(X1, X2 + 1):
        for z in (Z1, Z2):
            if x in (X1, 11, 15, X2):
                b.fill(x, 1, z, x, 3, z, POST)
            else:
                b.set(x, 1, z, "oak_planks")                   # skirting
                b.set(x, 2, z, "oak_fence")                    # balustrade
            b.set(x, 4, z, f"{LOG}[axis=x]")                   # top beam
            b.set(x, 5, z, "oak_planks")                       # plate under the eaves
    for x in (X1, 11, 15, X2):                                 # tie beams across
        for z in range(Z1 + 1, Z2):
            b.set(x, 4, z, f"{LOG}[axis=z]")
    gable_roof(b, X1, Z1, X2, Z2, 5, ROOF, "oak_planks", ridge="x")
    for x in (X1 - 1, X2 + 1):                                 # dark trim on the gable ends
        b.set(x, 7, 7, "dark_oak_planks")
    for x in (X1, X2):
        b.set(x, 6, 7, "stripped_dark_oak_log[axis=x]")
    for x in (11, 15):
        b.set(x, 3, 7, HANG)
    b.set(13, 3, 6, HANG)
    for x in (9, 17):
        b.set(x, 3, 8, HANG)

    # ---------- west approach: three steps up to the high bank ----------
    for z in range(6, 9):
        b.set(7, 1, z, "stone_brick_stairs[facing=west,half=bottom]")
        b.set(6, 2, z, "stone_brick_stairs[facing=west,half=bottom]")
        column(b, 6, z, 1, -5)
        b.set(5, 3, z, "polished_andesite")                    # landing on the hilltop
        column(b, 5, z, 2, 1)
    for z in (Z1, Z2):
        b.set(7, 1, z, stone(7, 1, z))
        b.set(7, 2, z, "stone_brick_wall")
        column(b, 6, z, 2, -5)
        b.set(6, 3, z, "stone_brick_wall")
        b.set(6, 4, z, STAND)

    # ---------- east approach: three steps down to the meadow ----------
    for z in range(6, 9):
        b.set(19, -1, z, "stone_brick_stairs[facing=west,half=bottom]")
        column(b, 19, z, -2, -6)
        b.set(20, -2, z, "stone_brick_stairs[facing=west,half=bottom]")
        column(b, 20, z, -3, -6)
        b.set(21, -3, z, "stone_brick_stairs[facing=west,half=bottom]")
    for z in (Z1, Z2):
        column(b, 19, z, -1, -6)
        b.set(19, 0, z, "stone_brick_wall")
        b.set(19, 1, z, STAND)
        column(b, 20, z, -2, -6)
        b.set(20, -1, z, "stone_brick_wall")
        b.set(21, -3, z, stone(21, -3, z))
    for x, y in ((22, -4), (23, -4), (24, -5), (25, -5)):     # path on into the meadow
        b.set(x, y, 7, "gravel" if x % 2 else "coarse_dirt")
    return b
