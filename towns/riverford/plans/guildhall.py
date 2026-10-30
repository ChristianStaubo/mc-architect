"""Riverford guildhall: the merchants' hall on the crown of the hill, the town's landmark.

Cut-sandstone ground floor with an arched loggia on the east front (door east, toward back street),
a terrace with a sandstone balustrade and steps in front of it; a mud-brick upper hall framed in
stripped acacia with terracotta bands and arched windows; a low brick hip roof with a flat roof
walk, and over the middle a square drum carrying a copper dome (unwaxed: it weathers) with a lantern
and finial. Inside: an entrance hall with the stair, the clerk's room (1 bed, 1 lectern), and upstairs
the guild hall with the long table under the open dome, trade-house banners and charts.

Local coords: x east (0..16), z south (0..14), y 0 = floor (world y 79). Plot x 266..282, z -54..-40.
"""

from architect.build import Build
from architect.parts import door, straight_stairs, window

# --- sizes ---------------------------------------------------------------------------------------
X0, X1 = 1, 13       # building west / east (east = loggia column line)
XM = 9               # east wall of the closed ground floor (loggia between XM and X1)
Z0, Z1 = 2, 12       # building north / south
TX = 16              # terrace edge (balustrade)
UP = 5               # upper floor level
TOP = 10             # top of the upper walls
CEIL = 11            # ceiling / eave beam level
DX0, DX1 = 4, 10     # drum footprint (square, 7 x 7), z the same
DRUM_TOP = 18
CX = CZ = 7          # centre of the dome
POSTS_X = (1, 5, 9, 13)    # frame posts on the north/south fronts
POSTS_Z = (2, 5, 9, 12)    # frame posts on the east/west fronts

# --- palette -------------------------------------------------------------------------------------
BASE = "cut_sandstone"
SMOOTH = "smooth_sandstone"
CHIS = "chiseled_sandstone"
FILL = "mud_bricks"
FRAME = "stripped_acacia_log"
COLUMN = "stripped_birch_log[axis=y]"
ROOF = "brick_stairs"
ROOF2 = "mud_brick_stairs"
FLOOR = "birch_planks"


def _h(*v):
    """A small deterministic hash for material mixing."""
    n = 0
    for a in v:
        n = (n * 73856093) ^ (a * 19349663 + 83492791)
    return n & 0xFFFF


def stair(name, facing, half="bottom", shape="straight"):
    return f"{name}[facing={facing},half={half},shape={shape}]"


def ring(b, x1, z1, x2, z2, y, name, half="bottom", inward=True, mix=None):
    """One ring of stairs around the box (a hip roof course or a cornice). inward: the tall back faces
    the middle (roof courses); else outward."""
    def pick(x, z):
        return mix if (mix and _h(x, y, z) % 5 == 0) else name
    def f(d):
        return d if inward else {"north": "south", "south": "north", "east": "west", "west": "east"}[d]
    for x in range(x1 + 1, x2):
        b.set(x, y, z1, stair(pick(x, z1), f("south"), half))
        b.set(x, y, z2, stair(pick(x, z2), f("north"), half))
    for z in range(z1 + 1, z2):
        b.set(x1, y, z, stair(pick(x1, z), f("east"), half))
        b.set(x2, y, z, stair(pick(x2, z), f("west"), half))
    shape = "outer_left" if inward else "outer_left"
    b.set(x1, y, z1, stair(name, f("south"), half, "outer_left" if inward else "outer_right"))
    b.set(x2, y, z1, stair(name, f("south"), half, "outer_right" if inward else "outer_left"))
    b.set(x1, y, z2, stair(name, f("north"), half, "outer_right" if inward else "outer_left"))
    b.set(x2, y, z2, stair(name, f("north"), half, "outer_left" if inward else "outer_right"))


def dome(b, cx, cz, y, radius, height, pick):
    """A dome (half ellipsoid) of the given base radius and height over (cx, cz), base at y: only the
    shell is set, the inside is left open (air) so it can be seen from below. Where a course steps in,
    the outer cell becomes a stair (tall side toward the middle) so the profile reads round, not stepped.
    pick(dx, k, dz, stair_facing_or_None) -> block."""
    def inside(dx, k, dz):
        return k >= 0 and (dx * dx + dz * dz) / (radius * radius) + (k / (height + 0.5)) ** 2 <= 1.0
    r = int(radius) + 1
    for k in range(0, height + 1):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if not inside(dx, k, dz):
                    continue
                shell = not (inside(dx + 1, k, dz) and inside(dx - 1, k, dz) and inside(dx, k, dz + 1)
                             and inside(dx, k, dz - 1) and inside(dx, k + 1, dz))
                if not shell:
                    b.set(cx + dx, y + k, cz + dz, "air")
                    continue
                face = None
                if not inside(dx, k + 1, dz) and (dx or dz):
                    if abs(dx) >= abs(dz):
                        face = "west" if dx > 0 else "east"
                    else:
                        face = "north" if dz > 0 else "south"
                    # only where the cell inward of it (toward the middle) is still dome above: a real step
                    ix = dx - (1 if dx > 0 else -1 if dx < 0 else 0) if abs(dx) >= abs(dz) else dx
                    iz = dz - (1 if dz > 0 else -1 if dz < 0 else 0) if abs(dz) > abs(dx) else dz
                    if not inside(ix, k + 1, iz):
                        face = None
                b.set(cx + dx, y + k, cz + dz, pick(dx, k, dz, face))


def copper(dx, k, dz, face=None):
    """Unwaxed copper, already part-weathered (it keeps going green): ribs in cut copper, panels a mix."""
    rib = dx == 0 or dz == 0 or abs(dx) == abs(dz)
    n = _h(dx, k, dz) % 10
    tone = "weathered_" if n < 4 else ("oxidized_" if n < 7 else "exposed_")
    if rib:
        tone = "weathered_" if k % 2 else "exposed_"
    if face:
        return f"{tone}cut_copper_stairs[facing={face},half=bottom,shape=straight]"
    return f"{tone}cut_copper" if rib else f"{tone}copper"


def arch_window(b, x, y, z, along, width, height):
    """Glass `height` tall, then an arched head: upside-down stairs at the ends, glass in the middle."""
    window(b, x, y, z, along, width, height)
    if width >= 3:
        if along == "x":
            b.set(x, y + height, z, stair(SMOOTH + "_stairs", "west", "top"))
            b.set(x + width - 1, y + height, z, stair(SMOOTH + "_stairs", "east", "top"))
            window(b, x + 1, y + height, z, "x", width - 2, 1)
        else:
            b.set(x, y + height, z, stair(SMOOTH + "_stairs", "north", "top"))
            b.set(x, y + height, z + width - 1, stair(SMOOTH + "_stairs", "south", "top"))
            window(b, x, y + height, z + 1, "z", 1, width - 2)


def wall_banner(b, x, y, z, color, facing):
    b.set(x, y, z, f"{color}_wall_banner[facing={facing}]")


def build():
    b = Build("guildhall")

    # ---------------------------------------------------------------- platform, terrace, paving
    for x in range(0, TX + 1):
        for z in range(1, 14):
            b.set(x, 0, z, SMOOTH if (x + z) % 2 else BASE)
    # a terracotta runner from the steps to the door
    for x in range(XM + 1, TX + 1):
        b.set(x, 0, 7, "orange_terracotta")
    # loggia floor: orange / white checker
    for x in range(XM + 1, X1):
        for z in range(Z0 + 1, Z1):
            b.set(x, 0, z, "orange_terracotta" if (x + z) % 2 else "white_terracotta")

    # ---------------------------------------------------------------- ground floor (closed part)
    for y in range(1, UP):
        for x in range(X0, XM + 1):
            for z in (Z0, Z1):
                b.set(x, y, z, BASE if _h(x, y, z) % 6 else SMOOTH)
        for z in range(Z0, Z1 + 1):
            for x in (X0, XM):
                b.set(x, y, z, BASE if _h(x, y, z) % 6 else SMOOTH)
    # inside air and floors
    b.fill(X0 + 1, 1, Z0 + 1, XM - 1, UP - 1, Z1 - 1, "air")
    b.fill(X0 + 1, 0, Z0 + 1, XM - 1, 0, Z1 - 1, SMOOTH)
    # a glazed terracotta medallion in the entrance hall
    for (x, z, f) in ((6, 5, "north"), (7, 5, "east"), (7, 6, "south"), (6, 6, "west")):
        b.set(x, 0, z, f"orange_glazed_terracotta[facing={f}]")
    # pilasters (protruding piers) on the north and south fronts, corner piers on the west
    for x in (X0, 5, XM):
        for z in (Z0 - 1, Z1 + 1):
            for y in range(1, UP):
                b.set(x, y, z, CHIS if y == UP - 1 else BASE)
    for z in (5, 9):
        for y in range(1, UP):
            b.set(X0 - 1, y, z, CHIS if y == UP - 1 else BASE)
    for z in (Z0 - 1, Z0, Z1, Z1 + 1):
        for y in range(1, UP):
            b.set(X0 - 1, y, z, CHIS if y == UP - 1 else BASE)
    # ground-floor windows (1 wide, 2 tall) with sills
    for x in (3, 7):
        for z, out in ((Z0, "north"), (Z1, "south")):
            window(b, x, 2, z, "x", 1, 2)
            oz = -1 if out == "north" else 1
            b.set(x, 1, z + oz, stair(SMOOTH + "_stairs", "south" if out == "north" else "north", "top"))
    window(b, X0, 2, 3, "z", 2, 2)
    window(b, X0, 2, 7, "z", 1, 2)
    window(b, X0, 2, 10, "z", 2, 2)
    window(b, XM, 2, 3, "z", 2, 2)
    window(b, XM, 2, 10, "z", 2, 2)
    door(b, XM, 1, 7, "east", "birch")
    b.set(XM, 3, 7, CHIS)
    b.sign(XM + 1, 3, 7, "birch_wall_sign[facing=east]", ["", "Guildhall", "of Riverford", ""])

    # ---------------------------------------------------------------- loggia
    for z in POSTS_Z:
        b.set(X1, 1, z, SMOOTH)
        b.set(X1, 2, z, COLUMN)
        b.set(X1, 3, z, COLUMN)
        b.set(X1, 4, z, CHIS)
    # east arches: (z3..4) (z6..8) (z10..11); upside-down stairs at the springing
    for za, zb in ((3, 4), (6, 8), (10, 11)):
        b.set(X1, 4, za, stair(SMOOTH + "_stairs", "north", "top"))
        b.set(X1, 4, zb, stair(SMOOTH + "_stairs", "south", "top"))
        for z in range(za, zb + 1):
            for y in range(1, 4):
                b.set(X1, y, z, "air")
        if zb - za == 2:
            b.set(X1, 4, za + 1, "air")
    # end arches north and south (x10..12)
    for z in (Z0, Z1):
        b.set(XM + 1, 4, z, stair(SMOOTH + "_stairs", "west", "top"))
        b.set(X1 - 1, 4, z, stair(SMOOTH + "_stairs", "east", "top"))
        for x in range(XM + 1, X1):
            for y in range(1, 4):
                b.set(x, y, z, "air")
        b.set(XM + 2, 4, z, "air")
    # pilasters on the loggia corners to match the fronts
    for z in (Z0 - 1, Z1 + 1):
        for y in range(1, UP):
            b.set(X1, y, z, CHIS if y == UP - 1 else BASE)
    # loggia benches, lanterns, plants
    for z in (3, 4, 10, 11):
        b.set(XM + 1, 1, z, stair("birch_stairs", "west"))
    b.set(11, 4, 4, "copper_lantern[hanging=true]")
    b.set(11, 4, 10, "copper_lantern[hanging=true]")
    b.set(11, 4, 7, "copper_lantern[hanging=true]")
    for z in (5, 9):
        b.set(XM + 1, 1, z, "potted_azalea_bush")

    # ---------------------------------------------------------------- upper floor
    b.fill(X0, UP, Z0, X1, UP, Z1, FLOOR)
    for x in range(X0, X1 + 1):
        b.set(x, UP, Z0, "orange_terracotta")
        b.set(x, UP, Z1, "orange_terracotta")
    for z in range(Z0, Z1 + 1):
        b.set(X0, UP, z, "orange_terracotta")
        b.set(X1, UP, z, "orange_terracotta")
    # walls: mud brick in an acacia frame, a red/white terracotta frieze under the eave
    for y in range(UP + 1, TOP + 1):
        for x in range(X0, X1 + 1):
            for z in (Z0, Z1):
                if y == TOP:
                    blk = "red_terracotta" if x % 2 else "white_terracotta"
                elif y == UP + 1:
                    blk = "orange_terracotta" if x % 2 else "white_terracotta"
                else:
                    blk = FILL if _h(x, y, z) % 7 else "packed_mud"
                b.set(x, y, z, blk)
        for z in range(Z0, Z1 + 1):
            for x in (X0, X1):
                if y == TOP:
                    blk = "red_terracotta" if z % 2 else "white_terracotta"
                elif y == UP + 1:
                    blk = "orange_terracotta" if z % 2 else "white_terracotta"
                else:
                    blk = FILL if _h(x, y, z) % 7 else "packed_mud"
                b.set(x, y, z, blk)
        for x in POSTS_X:
            for z in (Z0, Z1):
                b.set(x, y, z, f"{FRAME}[axis=y]")
        for z in POSTS_Z:
            for x in (X0, X1):
                b.set(x, y, z, f"{FRAME}[axis=y]")
    b.fill(X0 + 1, UP + 1, Z0 + 1, X1 - 1, TOP, Z1 - 1, "air")
    # arched windows: 3-wide bays on the long fronts, the middle bays on the short fronts
    for z in (Z0, Z1):
        arch_window(b, 6, UP + 2, z, "x", 3, 2)
        for x in (3, 11):
            window(b, x, UP + 2, z, "x", 1, 2)
            b.set(x, UP + 4, z, CHIS)
    arch_window(b, X1, UP + 2, 6, "z", 3, 2)
    for za in (3, 10):
        window(b, X1, UP + 2, za, "z", 2, 2)
        window(b, X0, UP + 2, za, "z", 2, 2)
    # sills under the upper windows, flower boxes on the long fronts
    for xa, w in ((3, 1), (6, 3), (11, 1)):
        for z, oz, f in ((Z0, -1, "south"), (Z1, 1, "north")):
            for x in range(xa, xa + w):
                b.set(x, UP + 1, z + oz, stair(SMOOTH + "_stairs", f, "top"))
    for za in (6, 7, 8):
        b.set(X1 + 1, UP + 1, za, stair(SMOOTH + "_stairs", "west", "top"))
    flowers = ("potted_red_tulip", "potted_orange_tulip", "potted_azure_bluet")
    for i, xa in enumerate((3, 11)):
        for z, oz in ((Z0, -1), (Z1, 1)):
            b.set(xa, UP + 2, z + oz, flowers[(i + z) % 3])
    # a string course of sandstone slabs at the upper floor line
    for x in range(X0, X1 + 1):
        for z in (Z0 - 1, Z1 + 1):
            if b.get(x, UP, z) is None:
                b.set(x, UP, z, f"{SMOOTH}_slab[type=bottom]")
    for z in range(Z0 - 1, Z1 + 2):
        for x in (X0 - 1, X1 + 1):
            if b.get(x, UP, z) is None:
                b.set(x, UP, z, f"{SMOOTH}_slab[type=bottom]")
    # trade-house banners hung outside on the east front
    for z, c in ((5, "orange"), (9, "red")):
        wall_banner(b, X1 + 1, TOP - 1, z, c, "east")

    # ---------------------------------------------------------------- ceiling, roof
    b.fill(X0 + 1, CEIL, Z0 + 1, X1 - 1, CEIL, Z1 - 1, FLOOR)
    for z in range(Z0 + 1, Z1):
        if z in (4, 10):
            for x in range(X0 + 1, X1):
                b.set(x, CEIL, z, f"{FRAME}[axis=x]")
    for x in range(X0, X1 + 1):
        b.set(x, CEIL, Z0, f"{FRAME}[axis=x]")
        b.set(x, CEIL, Z1, f"{FRAME}[axis=x]")
    for z in range(Z0, Z1 + 1):
        b.set(X0, CEIL, z, f"{FRAME}[axis=z]")
        b.set(X1, CEIL, z, f"{FRAME}[axis=z]")
    ring(b, X0 - 1, Z0 - 1, X1 + 1, Z1 + 1, CEIL, ROOF, mix=ROOF2)
    ring(b, X0, Z0, X1, Z1, CEIL + 1, ROOF, mix=ROOF2)
    b.fill(X0 + 1, CEIL + 1, Z0 + 1, X1 - 1, CEIL + 1, Z1 - 1, FILL)
    ring(b, X0 + 1, Z0 + 1, X1 - 1, Z1 - 1, CEIL + 2, ROOF, mix=ROOF2)
    b.fill(X0 + 2, CEIL + 2, Z0 + 2, X1 - 2, CEIL + 2, Z1 - 2, SMOOTH)
    # corner pinnacles with copper lanterns on the roof
    for x in (X0, X1):
        for z in (Z0, Z1):
            b.set(x, CEIL + 1, z, CHIS)
            b.set(x, CEIL + 2, z, f"{SMOOTH}_slab[type=bottom]")
            b.set(x, CEIL + 2, z, CHIS)
            b.set(x, CEIL + 3, z, "copper_lantern[hanging=false]")
    # a balcony over the loggia, off the hall's east door
    door(b, X1, UP + 1, 7, "east", "birch")
    for z in (6, 7, 8):
        b.set(X1 + 1, UP, z, SMOOTH)
        b.set(X1 + 1, UP - 1, z, stair(SMOOTH + "_stairs", "west", "top"))
        b.set(X1 + 2, UP, z, f"{SMOOTH}_slab[type=top]")
        b.set(X1 + 2, UP + 1, z, "sandstone_wall[north=low,south=low,east=none,west=none,up=false,waterlogged=false]")
    for z in (5, 9):
        b.set(X1 + 1, UP + 1, z, "sandstone_wall[north=none,south=none,east=low,west=none,up=true,waterlogged=false]")
        b.set(X1 + 2, UP + 1, z, CHIS)
        b.set(X1 + 2, UP, z, f"{SMOOTH}_slab[type=top]")
    b.set(X1 + 2, UP + 2, 5, "potted_red_tulip")
    b.set(X1 + 2, UP + 2, 9, "potted_orange_tulip")
    # copper downspouts at the corners
    for (x, z) in ((X0 - 1, Z0 - 1), (X0 - 1, Z1 + 1), (X1, Z0 - 1), (X1, Z1 + 1)):
        for y in range(UP + 1, CEIL):
            b.set(x, y, z, "lightning_rod[facing=up]")

    # ---------------------------------------------------------------- drum
    for y in range(CEIL + 1, DRUM_TOP + 1):
        for x in range(DX0, DX1 + 1):
            for z in (DX0, DX1):
                b.set(x, y, z, FILL)
        for z in range(DX0, DX1 + 1):
            for x in (DX0, DX1):
                b.set(x, y, z, FILL)
    for y in range(CEIL + 1, DRUM_TOP + 1):
        for x in range(DX0, DX1 + 1):
            for z in range(DX0, DX1 + 1):
                if x in (DX0, DX1) or z in (DX0, DX1):
                    if y == CEIL + 1:
                        b.set(x, y, z, BASE)
                    elif y == DRUM_TOP:
                        b.set(x, y, z, "orange_terracotta" if (x + z) % 2 else "white_terracotta")
                    if (x in (DX0, DX1) and z in (DX0, DX1)) and CEIL + 1 < y < DRUM_TOP:
                        b.set(x, y, z, f"{FRAME}[axis=y]")
                else:
                    b.set(x, y, z, "air")
    # drum windows, one arched opening per side
    arch_window(b, 6, CEIL + 2, DX0, "x", 3, 2)
    arch_window(b, 6, CEIL + 2, DX1, "x", 3, 2)
    arch_window(b, DX0, CEIL + 2, 6, "z", 3, 2)
    arch_window(b, DX1, CEIL + 2, 6, "z", 3, 2)
    # the opening in the hall ceiling, up into the drum and dome
    b.fill(DX0 + 1, CEIL, DX0 + 1, DX1 - 1, CEIL + 1, DX1 - 1, "air")
    # cornice
    ring(b, DX0 - 1, DX0 - 1, DX1 + 1, DX1 + 1, DRUM_TOP, SMOOTH + "_stairs", half="top", inward=True)
    # corner pinnacles on the drum
    for x in (DX0, DX1):
        for z in (DX0, DX1):
            b.set(x, DRUM_TOP + 1, z, CHIS)
            b.set(x, DRUM_TOP + 2, z, "copper_lantern[hanging=false]")

    # ---------------------------------------------------------------- dome, lantern, finial
    DH = 5
    dome(b, CX, CZ, DRUM_TOP + 1, 3.6, DH, copper)
    apex = DRUM_TOP + 1 + DH
    b.set(CX, apex + 1, CZ, "cut_copper_slab[type=bottom]")
    b.set(CX, apex + 1, CZ, "copper_block")
    b.set(CX, apex + 2, CZ, "copper_lantern[hanging=false]")
    b.set(CX, apex + 3, CZ, "lightning_rod[facing=up]")
    # a hanging lantern inside the dome, on a chain over the table
    top_air = max(y for (x, y, z), blk in b.blocks.items() if (x, z) == (CX, CZ) and blk == "air" and y < apex)
    for y in range(CEIL + 2, top_air + 1):
        b.set(CX, y, CZ, "iron_chain[axis=y]")
    b.set(CX, CEIL + 1, CZ, "copper_lantern[hanging=true]")

    # ---------------------------------------------------------------- terrace and balustrade
    def balustrade(x, z, axis):
        conn = "north=low,south=low,east=none,west=none" if axis == "z" else "north=none,south=none,east=low,west=low"
        b.set(x, 1, z, f"sandstone_wall[{conn},up=false,waterlogged=false]")
    for z in range(1, 14):
        if z in (1, 5, 9, 13):
            b.set(TX, 1, z, CHIS)
        elif z not in (6, 7, 8):
            balustrade(TX, z, "z")
    for x in (14, 15):
        balustrade(x, 1, "x")
        balustrade(x, 13, "x")
    b.set(TX, 2, 1, "potted_red_tulip")
    b.set(TX, 2, 13, "potted_orange_tulip")
    b.set(TX, 2, 5, "copper_lantern[hanging=false]")
    b.set(TX, 2, 9, "copper_lantern[hanging=false]")
    for z in (6, 7, 8):
        b.set(TX, 0, z, stair("sandstone_stairs", "west"))

    # vines climbing the west wall beside the window
    for z in (6, 8):
        for y in range(2, 5):
            b.set(X0 - 1, y, z, "vine[east=true,north=false,south=false,west=false,up=false]")
    # potted plants along the north and south walks
    for x in (2, 4, 6, 8):
        b.set(x, 1, Z0 - 1, "potted_fern" if x % 4 else "potted_red_tulip") if x not in (3, 7) else None
    for x in (2, 4, 6, 8):
        b.set(x, 1, Z1 + 1, "potted_dandelion" if x % 4 else "potted_azalea_bush")

    # ---------------------------------------------------------------- inside: ground floor
    # stair up along the north wall, from the entrance west to the upper hall
    straight_stairs(b, 8, 1, 3, "west", 4, "birch_stairs", width=2)
    for x in (5, 6, 7):
        b.set(x, UP + 1, 5, "birch_fence[east=true,west=true]" if x != 5 else "birch_fence[east=true,west=false]")
    b.set(8, UP + 1, 5, "birch_fence[west=true,north=true]")
    b.set(8, UP + 1, 4, "birch_fence[north=true,south=true]")
    b.set(8, UP + 1, 3, "birch_fence[south=true]")
    # partition: entrance hall (north) / clerk's room (south)
    for x in range(X0 + 1, XM):
        for y in range(1, UP):
            b.set(x, y, 8, f"{FRAME}[axis=y]" if x in (2, 8) else "birch_planks")
    door(b, 6, 1, 8, "north", "birch")
    # entrance hall: chests of the trade houses, plants, lanterns, banners
    b.set(2, 1, 5, "chest[facing=east]")
    b.set(2, 1, 6, "chest[facing=east]")
    b.set(2, 1, 7, "potted_fern")
    b.set(4, 1, 3, "potted_azalea_bush")
    b.set(3, 4, 6, "lantern[hanging=true]")
    b.set(8, 4, 6, "lantern[hanging=true]")
    wall_banner(b, 2, 3, 6, "orange", "east")
    # clerk's room: 1 bed, the lectern, the guild's records
    b.set(2, 1, 11, "orange_bed[facing=south,part=head]")
    b.set(2, 1, 10, "orange_bed[facing=south,part=foot]")
    b.set(3, 1, 11, "chest[facing=north]")
    for x in (3, 4, 5):
        for y in (1, 2, 3):
            b.set(x, y, 9, "bookshelf")
    b.set(4, 1, 10, "lectern[facing=north]")
    b.set(7, 1, 11, "birch_stairs[facing=south,half=bottom,shape=straight]")
    b.set(8, 1, 11, "birch_planks")
    b.set(8, 2, 11, "candle[candles=3,lit=true]")
    b.set(8, 1, 10, "chest[facing=west]")
    b.set(5, 4, 10, "lantern[hanging=true]")
    b.set(2, 1, 9, "potted_cactus")

    # ---------------------------------------------------------------- inside: the guild hall
    y = UP + 1
    for x in range(4, 11):
        b.set(x, y, 7, "acacia_planks" if x in (4, 10) else "acacia_slab[type=top]")
        b.set(x, y + 1, 7, "white_carpet" if x % 2 else ("candle[candles=4,lit=true]" if x in (4, 10) else "orange_carpet"))
    for x in range(5, 10):
        b.set(x, y, 6, stair("birch_stairs", "north"))
        b.set(x, y, 8, stair("birch_stairs", "south"))
    b.set(3, y, 7, stair("acacia_stairs", "west"))
    b.set(11, y, 7, stair("acacia_stairs", "east"))
    # a dais at the west end: bookshelves, trade-house banners
    for z in range(5, 10):
        for yy in (y, y + 1):
            b.set(2, yy, z, "bookshelf")
    for z, c in ((6, "orange"), (7, "red"), (8, "yellow")):
        b.set(1, y + 2, z, FILL)
        b.set(1, y + 3, z, FILL)
        wall_banner(b, 2, y + 3, z, c, "east")
    # banners on the posts along both long walls
    for x, c1, c2 in ((5, "cyan", "lime"), (9, "blue", "magenta")):
        wall_banner(b, x, y + 3, Z0 + 1, c1, "south")
        wall_banner(b, x, y + 3, Z1 - 1, c2, "north")
    # charts: white and light-blue carpets laid on chests along the walls (map tables are job blocks)
    for x in (11, 12):
        b.set(x, y, Z1 - 1, "chest[facing=north]")
    b.set(12, y, Z0 + 1, "chest[facing=south]")
    b.set(11, y, Z0 + 1, "chest[facing=south]")
    for (x, z) in ((2, 3), (2, 11), (12, 6), (12, 8)):
        b.set(x, y, z, "potted_fern")
    # lanterns hung from the ceiling
    for (x, z) in ((3, 4), (11, 4), (3, 10), (11, 10), (7, 4)):
        if b.get(x, CEIL, z) and b.get(x, CEIL, z) != "air":
            b.set(x, TOP, z, "lantern[hanging=true]")
    return b
