"""Riverford traders' inn: sandstone-arch loggia on the quay, taproom + bar (brewing stand), kitchen
(smoker) in a back wing, two bedrooms upstairs, brick hip roof over the main block and a flat roof
terrace with awning and grape pergola on the wing. Door faces north (the quay street)."""

from architect.build import Build
from architect.parts import (awning, clear_inside, door, flower_box, floor, hip_roof, light, shutters,
                             straight_stairs, walls, window)

# main block x0..MX, z0..MZ ; wing x0..WX, z MZ..WZ
MX, MZ = 12, 7
WX, WZ = 6, 13
FLOOR2 = 4     # upper floor layer
TOP = 8        # top band layer / ceiling
ROOF_Y = 9

SAND = "cut_sandstone"
SMOOTH = "smooth_sandstone"
MUD = "mud_bricks"
FRAME = "stripped_acacia_log"
PLANK = "acacia_planks"
TOWN = "birch"


def band(b, x1, z1, x2, z2, y):
    """Terracotta band (orange/white) around a rectangle at layer y."""
    i = 0
    for x in range(x1, x2 + 1):
        for z in (z1, z2):
            b.set(x, y, z, "orange_terracotta" if i % 2 == 0 else "white_terracotta")
        i += 1
    for z in range(z1 + 1, z2):
        for x in (x1, x2):
            b.set(x, y, z, "orange_terracotta" if z % 2 == 0 else "white_terracotta")


def beam_ring(b, x1, z1, x2, z2, y):
    for x in range(x1, x2 + 1):
        b.set(x, y, z1, f"{FRAME}[axis=x]")
        b.set(x, y, z2, f"{FRAME}[axis=x]")
    for z in range(z1 + 1, z2):
        b.set(x1, y, z, f"{FRAME}[axis=z]")
        b.set(x2, y, z, f"{FRAME}[axis=z]")


def posts_y(b, pts, y1, y2):
    for x, z in pts:
        b.fill(x, y1, z, x, y2, z, f"{FRAME}[axis=y]")


def table(b, x, y, z):
    b.set(x, y, z, f"{TOWN}_fence")
    b.set(x, y + 1, z, f"{TOWN}_pressure_plate")


def chair(b, x, y, z, facing):
    b.set(x, y, z, f"{TOWN}_stairs[facing={facing},half=bottom,shape=straight]")


def build():
    b = Build("inn")

    # ---------- floors ----------
    floor(b, 0, 0, MX, MZ, 0, SAND)
    floor(b, 0, MZ, WX, WZ, 0, SAND)
    floor(b, 0, 0, MX, 1, 0, SMOOTH)                      # loggia floor
    floor(b, 1, 3, MX - 1, 6, 0, f"{TOWN}_planks")         # taproom
    floor(b, 1, 8, WX - 1, WZ - 1, 0, "smooth_red_sandstone")  # kitchen
    # air for both storeys
    b.fill(0, 1, 0, MX, TOP, MZ, "air")
    b.fill(0, 1, MZ, WX, 12, WZ, "air")

    # ---------- ground storey: main block ----------
    # back wall of the loggia / front wall of the taproom (z2) and sides, mud brick on a sandstone base
    walls(b, 0, 2, MX, MZ, 1, 3, MUD)
    for x in range(0, MX + 1):
        for z in (2, MZ):
            b.set(x, 1, z, SAND)
    for z in range(2, MZ + 1):
        for x in (0, MX):
            b.set(x, 1, z, SAND)
    # loggia end walls
    for z in (0, 1):
        for x in (0, MX):
            b.fill(x, 1, z, x, 3, z, SAND)
    # loggia columns and arches
    for cx in (0, 4, 8, 12):
        b.set(cx, 1, 0, SAND)
        b.set(cx, 2, 0, SMOOTH)
        b.set(cx, 3, 0, "chiseled_sandstone")
    for gx in (1, 5, 9):
        b.set(gx, 3, 0, f"sandstone_stairs[facing=west,half=top,shape=straight]")
        b.set(gx + 1, 3, 0, SAND)
        b.set(gx + 2, 3, 0, f"sandstone_stairs[facing=east,half=top,shape=straight]")
    b.set(6, 3, 0, "waxed_oxidized_cut_copper")   # copper keystone over the door
    # arch back-fill: inner sandstone lintel line along z1 on y3 so the loggia ceiling is solid
    for x in range(0, MX + 1):
        b.set(x, 3, 1, SAND)
    # step up from the quay street
    for gx in (1, 5, 9):
        for x in range(gx, gx + 3):
            b.set(x, 0, -1, "sandstone_stairs[facing=south,half=bottom,shape=straight]")

    # doors and windows
    door(b, 6, 1, 2, "north", TOWN)
    door(b, 0, 1, 4, "west", "acacia")
    door(b, MX, 1, 4, "east", "acacia")
    window(b, 2, 2, 2, "x", 1, 2)
    window(b, 10, 2, 2, "x", 1, 2)
    window(b, 0, 2, 6, "z", 1, 2)
    window(b, MX, 2, 6, "z", 1, 2)
    window(b, 0, 2, 2, "z", 1, 1) if False else None

    # inner partition taproom / kitchen has a door at x5
    door(b, 5, 1, MZ, "south", "acacia")

    # floor between storeys (upper floor layer) and beam band
    floor(b, 0, 0, MX, MZ, FLOOR2, PLANK)
    floor(b, 0, MZ, WX, WZ, FLOOR2, PLANK)
    beam_ring(b, 0, 0, MX, MZ, FLOOR2)
    beam_ring(b, 0, MZ, WX, WZ, FLOOR2)

    # ---------- ground storey: wing (kitchen) on its sandstone terrace ----------
    walls(b, 0, MZ, WX, WZ, 1, 3, MUD)
    for z in range(MZ, WZ + 1):
        for x in (0, WX):
            b.fill(x, 1, z, x, 2, z, SAND)
    for x in range(0, WX + 1):
        b.fill(x, 1, WZ, x, 2, WZ, SAND)
    window(b, 0, 2, 10, "z", 2, 2)
    window(b, WX, 2, 10, "z", 2, 2)
    window(b, 2, 3, WZ, "x", 2, 1)
    # re-set main/wing shared wall door
    door(b, 5, 1, MZ, "south", "acacia")

    # ---------- upper storey: main ----------
    walls(b, 0, 0, MX, MZ, 5, TOP, MUD)
    posts_y(b, [(x, z) for x in (0, 4, 8, 12) for z in (0, MZ)] + [(0, 4), (MX, 4)], 5, 7)
    beam_ring(b, 0, 0, MX, MZ, FLOOR2)
    band(b, 0, 0, MX, MZ, TOP)
    # windows (front)
    for x in (2, 6, 10):
        window(b, x, 6, 0, "x", 1, 2)
        shutters(b, x, 6, 0, "x", 1, 2, "north", wood=TOWN)
        flower_box(b, x, 6, 0, "x", 1, "north", front=f"{TOWN}_trapdoor")
    # rear and side windows
    for x in (9, 11):
        window(b, x, 6, MZ, "x", 1, 2)
    for z in (2, 5):
        window(b, MX, 6, z, "z", 1, 2)
    window(b, 0, 6, 2, "z", 1, 2)
    window(b, 0, 6, 6, "z", 1, 2)
    # ceiling inside
    floor(b, 1, 1, MX - 1, MZ - 1, TOP, PLANK)

    # ---------- upper storey: wing ----------
    walls(b, 0, MZ, WX, WZ, 5, TOP, MUD)
    posts_y(b, [(0, WZ), (WX, WZ), (WX, MZ), (0, MZ), (3, WZ)], 5, 7)
    beam_ring(b, 0, MZ, WX, WZ, FLOOR2)
    band(b, 0, MZ, WX, WZ, TOP)
    window(b, 0, 6, 10, "z", 1, 2)
    window(b, WX, 6, 10, "z", 1, 2)
    window(b, 1, 6, WZ, "x", 1, 2)
    window(b, 5, 6, WZ, "x", 1, 2)

    # ---------- stairs: taproom -> upper hall ----------
    # fill before the stairs so the stairwell is cut through the floor
    straight_stairs(b, 1, 1, 6, "east", 4, f"{TOWN}_stairs", support=PLANK)
    # rails at the hole on the upper floor
    for x in (1, 2, 3):
        b.set(x, 5, 5, f"{TOWN}_fence[east={'true' if x < 3 else 'false'},west={'true' if x > 1 else 'false'},north=false,south=false]")
    b.set(0, 5, 5, "air") if False else None

    # ---------- upper partitions ----------
    # partition between hall and innkeeper's room
    for z in range(1, MZ):
        for y in (5, 6, 7):
            b.set(7, y, z, MUD)
        b.set(7, 5, z, f"{FRAME}[axis=y]") if False else None
    for z in range(1, MZ):
        b.set(7, TOP, z, MUD)
    door(b, 7, 5, 3, "east", "acacia")
    # attic hatch with a ladder on the partition, so the roof space is a reachable (lit) loft
    b.set(6, TOP, 5, "air")
    for y in range(5, TOP + 1):
        b.set(6, y, 5, "ladder[facing=west]")
    for x, z in ((2, 2), (4, 5), (6, 2), (9, 2), (9, 5), (11, 3), (1, 5), (3, 3), (5, 5), (10, 5)):
        b.set(x, TOP + 1, z, "lantern[hanging=false]")
    # partition main/wing: door (5,5,MZ)
    door(b, 5, 5, MZ, "south", "acacia")

    # ---------- terrace ----------
    floor(b, 1, 8, WX - 1, WZ - 1, TOP, SMOOTH)
    # hole for the terrace stairs cut later; parapet
    beam_ring(b, 0, MZ, WX, WZ, TOP)
    band(b, 0, MZ, WX, WZ, TOP)
    # high wall behind the terrace (rear gable of the main block)
    for x in range(0, WX + 1):
        for y in range(9, 13):
            b.set(x, y, MZ, MUD)
        b.set(x, 10, MZ, "orange_terracotta" if x % 2 == 0 else "white_terracotta")
    # parapet: low sandstone slabs, pillars at the corners
    for z in range(MZ + 1, WZ + 1):
        for x in (0, WX):
            b.set(x, 9, z, "cut_sandstone_slab[type=bottom]")
    for x in range(1, WX):
        b.set(x, 9, WZ, "cut_sandstone_slab[type=bottom]")
    for x, z in ((0, WZ), (WX, WZ)):
        b.fill(x, 9, z, x, 10, z, SAND)
        b.set(x, 11, z, "lantern[hanging=false]")
    # terrace stairs on the east side, going north up through the roof
    straight_stairs(b, 5, 5, 12, "north", 4, f"{TOWN}_stairs", support=None)
    for z in (9, 10, 11, 12):
        b.set(4, 9, z, f"{TOWN}_fence[north={'true' if z > 9 else 'false'},south={'true' if z < 12 else 'false'},east=false,west=false]")
    # the awning off the high wall, orange and white
    awning(b, 1, 3, MZ, 12, "south", colors=("orange_wool", "white_wool"), depth=2)
    # grape pergola
    for px, pz in ((1, 10), (3, 10), (1, 12), (3, 12)):
        posts_y(b, [(px, pz)], 9, 11)
    for x in range(1, 4):
        b.set(x, 12, 10, f"{FRAME}[axis=x]") if False else None
    for z in (10, 12):
        for x in range(1, 4):
            b.set(x, 12, z, f"stripped_birch_log[axis=x]")
    for x in (1, 3):
        b.set(x, 12, 11, f"stripped_birch_log[axis=z]")
    for x, z in ((1, 11), (3, 11), (2, 10), (2, 12), (1, 10), (3, 10), (1, 12), (3, 12)):
        b.set(x, 11, z, "vine[up=true]") if (x, z) not in ((1, 10), (3, 10), (1, 12), (3, 12)) else None
    for x in (1, 2, 3):
        b.set(x, 9, 11, "grass_block") if False else None
    # potted plants
    for x, z, pot in ((1, 8, "potted_fern"), (2, 8, "potted_red_tulip"), (3, 8, "potted_dandelion"),
                      (5, 9, "air"), (1, 13, "potted_cactus"), (5, 13, "potted_fern")):
        if pot != "air":
            b.set(x, 9, z, pot)
    light(b, 3, 9, 11, "lantern[hanging=false]") if False else None
    b.set(2, 11, 11, "lantern[hanging=true]")
    b.set(2, 11, 11, "air") if False else None

    # ---------- main roof: brick hip, wing side left open for the terrace ----------
    roof = Build("roof")
    hip_roof(roof, 0, 0, MX, MZ, ROOF_Y, "brick_stairs", top="brick_slab[type=bottom]", overhang=1)
    for (x, y, z), blk in roof.blocks.items():
        if x <= WX and z >= MZ:
            continue
        if y == ROOF_Y + 1:
            blk = blk.replace("brick_stairs", "mud_brick_stairs")
        b.set(x, y, z, blk)

    # ---------- interiors ----------
    # loggia: tables under the arches, pots by the door
    for tx in (2, 10):
        table(b, tx, 1, 1)
        chair(b, tx - 1, 1, 1, "west")
        chair(b, tx + 1, 1, 1, "east")
    b.set(5, 1, 1, "potted_fern")
    b.set(7, 1, 1, "potted_red_tulip")
    for gx in (1, 9):
        b.set(gx + 1, 2, 0, "lantern[hanging=true]")
    # hanging boat sign on a copper bracket
    b.set(6, 3, -1, "waxed_oxidized_cut_copper")
    b.sign(6, 2, -1, f"{TOWN}_hanging_sign[attached=false,rotation=8]", ["~ The ~", "Boat", "Inn"])

    # taproom: bar along z5, brewing stand behind it, tables in front
    for x in range(7, 11):
        b.set(x, 1, 5, f"{TOWN}_planks")
        b.set(x, 2, 5, f"{TOWN}_pressure_plate")
    b.set(7, 1, 6, "chest[facing=north]")
    b.set(8, 1, 6, "potted_azure_bluet")
    b.set(10, 1, 6, "brewing_stand")
    b.set(10, 2, 6, "lantern[hanging=false]") if False else None
    for x in (8, 10):
        b.set(x, 1, 4, f"stripped_{TOWN}_log[axis=y]")
    table(b, 4, 1, 3)
    chair(b, 3, 1, 3, "west")
    chair(b, 5, 1, 3, "east")
    table(b, 2, 1, 4) if False else None
    for x, z in ((3, 3), (9, 3)):
        b.set(x, 3, z + 1, "lantern[hanging=true]")
    b.set(9, 3, 5, "lantern[hanging=true]")
    b.set(5, 3, 5, "lantern[hanging=true]")
    b.set(1, 3, 3, "lantern[hanging=true]")
    b.set(11, 3, 3, "lantern[hanging=true]")
    # kitchen
    b.set(3, 1, 12, "smoker[facing=north,lit=false]")
    b.set(1, 1, 12, "chest[facing=east]")
    b.set(2, 1, 12, "crafting_table")
    for z in (9, 10, 11):
        b.set(5, 1, z, f"{TOWN}_planks")
    b.set(5, 2, 9, "potted_fern")
    b.set(1, 1, 8, "hay_block[axis=y]")
    b.set(1, 1, 9, "white_wool")
    b.set(1, 1, 10, "orange_wool")
    b.set(3, 3, 10, "lantern[hanging=true]")
    b.set(3, 3, 8, "lantern[hanging=true]")
    # kitchen table
    table(b, 3, 1, 10)
    # upper hall: table, chest, lamps
    table(b, 4, 5, 2)
    chair(b, 3, 5, 2, "west")
    chair(b, 5, 5, 2, "east")
    b.set(1, 5, 1, "chest[facing=south]")
    b.set(2, 5, 1, "potted_fern")
    b.set(3, 7, 3, "lantern[hanging=true]")
    b.set(5, 7, 4, "lantern[hanging=true]")
    # innkeeper's room (east): bed along x, head at the east wall
    b.set(11, 5, 4, "red_bed[facing=east,part=head]")
    b.set(10, 5, 4, "red_bed[facing=east,part=foot]")
    b.set(11, 5, 2, "chest[facing=south]") if False else None
    b.set(9, 5, 1, "chest[facing=south]")
    b.set(11, 5, 1, "potted_dandelion")
    b.set(9, 7, 3, "lantern[hanging=true]")
    # cook's room (wing): bed head against the west wall's south end
    b.set(1, 5, 12, "orange_bed[facing=north,part=head]") if False else None
    b.set(1, 5, 11, "orange_bed[facing=south,part=head]")
    b.set(1, 5, 10, "orange_bed[facing=south,part=foot]")
    b.set(3, 5, 9, "chest[facing=south]") if False else None
    b.set(2, 5, 12, "chest[facing=north]")
    b.set(3, 7, 10, "lantern[hanging=true]")
    b.set(3, 5, 12, "potted_fern")

    # ---------- outside details ----------
    b.set(-1, 0, 4, "sandstone_stairs[facing=east,half=bottom,shape=straight]")
    b.set(MX + 1, 0, 4, "sandstone_stairs[facing=west,half=bottom,shape=straight]")
    for x in (-1, MX + 1):
        for z in (3, 5):
            b.fill(x, 0, z, x, 1, z, f"{TOWN}_fence")
            b.set(x, 2, z, "lantern[hanging=false]")
    b.set(-1, 0, 6, "potted_fern")
    b.set(MX + 1, 0, 6, "potted_red_tulip")
    return b
