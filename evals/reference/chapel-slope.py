"""Hillside chapel: a pale calcite nave (ridge east-west) with stone-brick pilasters, buttresses and tall
2x4 windows, a lower raised chancel at the west end with the altar under a stained window, and a square
bell tower on the east front holding the door, a belfry with a hanging bell and a steep slate spire.
The floor sits at the slope's middle level (y 79): the north hill is cut only inside the walls and
regraded under the eave, the low south-west corner gets a deliberate stone plinth. A path runs south
from the tower door past a few gravestones."""

from architect.build import Build
from architect.parts import door, gable_roof, window

PLACE = ["--at", "-376,440", "--y", "79"]

PALE = "calcite"
TRIM = "stone_bricks"
ROOF = "deepslate_tile_stairs"
WOOD = "dark_oak"
HANG = "lantern[hanging=true]"
STAND = "lantern[hanging=false]"

# original ground (world y) of the plot, rows z 440..459, cols x -376..-357; local y = world - 79
GROUND = """
83 83 83 83 83 83 83 82 82 82 82 82 82 81 80 79 79 79 78 78
82 82 82 82 82 82 82 82 82 82 82 81 81 81 80 79 79 79 78 78
81 81 81 81 81 82 82 82 82 82 81 81 81 80 79 79 79 79 78 78
79 80 80 80 81 81 81 82 82 81 81 81 80 80 79 79 79 79 78 78
79 79 79 79 80 80 81 81 82 81 81 80 80 79 79 79 79 79 78 77
79 79 79 79 79 80 80 81 81 81 80 80 79 79 79 79 79 79 78 78
79 79 79 79 79 79 79 80 80 80 80 80 79 79 79 79 79 79 78 78
79 79 79 79 79 79 79 79 80 79 79 79 79 79 79 79 79 79 78 78
79 79 79 79 79 79 79 79 79 79 79 79 79 79 79 79 79 79 78 78
79 79 79 79 78 79 79 79 79 79 79 79 79 79 79 79 79 79 78 78
79 79 78 78 78 78 78 79 79 79 79 79 79 79 79 79 79 79 79 78
79 78 78 78 78 78 78 78 79 79 79 79 79 79 79 79 79 79 79 78
79 78 78 78 77 78 78 78 78 79 79 79 79 79 79 79 79 79 79 78
78 78 78 78 77 77 78 78 78 79 79 79 79 79 79 79 79 79 79 78
78 78 78 77 77 77 78 78 78 78 79 79 79 79 79 79 79 79 79 78
78 78 77 77 77 77 77 78 78 78 79 79 79 79 79 79 79 79 78 78
78 78 77 77 77 77 77 78 78 78 79 79 79 79 79 79 79 79 78 78
77 77 77 77 76 77 77 77 78 78 78 79 79 79 79 79 79 78 78 78
77 77 77 76 76 76 77 77 77 78 78 78 78 78 78 78 78 78 78 77
76 76 76 76 76 76 76 77 77 77 77 78 78 78 78 78 78 78 77 77
"""
G = [[int(v) - 79 for v in row.split()] for row in GROUND.strip().splitlines()]


def g(x, z):
    """Local y of the original ground's top block at local (x, z)."""
    return G[z][x]


# nave x 5..14, z 6..14; chancel x 1..5, z 7..13; tower x 14..18, z 8..12
NX1, NX2, NZ1, NZ2, NTOP = 5, 14, 6, 14, 6
CX1, CZ1, CZ2, CTOP = 1, 7, 13, 5
TX1, TX2, TZ1, TZ2, TTOP = 14, 18, 8, 12, 16


def stone(x, y, z):
    h = (x * 7 + y * 13 + z * 29) % 11
    return "mossy_stone_bricks" if h == 0 else "cracked_stone_bricks" if h == 1 else TRIM


def pale(x, y, z):
    h = (x * 5 + y * 11 + z * 17) % 9
    return "polished_diorite" if h == 0 else PALE


def box(b, x1, z1, x2, z2, y1, y2):
    """Pale walls with a stone-brick plinth course at y1 and stone quoins at the corners."""
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                if x in (x1, x2) or z in (z1, z2):
                    corner = x in (x1, x2) and z in (z1, z2)
                    b.set(x, y, z, stone(x, y, z) if (y == y1 or corner) else pale(x, y, z))
    for x in range(x1 + 1, x2):
        for z in range(z1 + 1, z2):
            b.fill(x, y1 + 1, z, x, y2, z, "air")


def plinth(b, x1, z1, x2, z2):
    """Stone footing under the walls down past the ground, dirt under the floor: no cobble cliff."""
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            edge = x in (x1, x2) or z in (z1, z2)
            for y in range(-4, 0):
                b.set(x, y, z, stone(x, y, z) if edge else "dirt")


def ring(b, a1, c1, a2, c2, y, stair):
    if a1 == a2 or c1 == c2:
        b.fill(a1, y, c1, a2, y, c2, "deepslate_tiles")
        return
    for x in range(a1, a2 + 1):
        b.set(x, y, c1, f"{stair}[facing=south,half=bottom,shape=straight]")
        b.set(x, y, c2, f"{stair}[facing=north,half=bottom,shape=straight]")
    for z in range(c1 + 1, c2):
        b.set(a1, y, z, f"{stair}[facing=east,half=bottom,shape=straight]")
        b.set(a2, y, z, f"{stair}[facing=west,half=bottom,shape=straight]")
    for x, z, shape in ((a1, c1, "outer_left"), (a2, c1, "outer_right"), (a1, c2, "outer_right"), (a2, c2, "outer_left")):
        b.set(x, y, z, f"{stair}[facing={'south' if z == c1 else 'north'},half=bottom,shape={shape}]")


def build():
    b = Build("chapel-slope")

    # ---------- footings ----------
    plinth(b, NX1, NZ1, NX2, NZ2)
    plinth(b, CX1, CZ1, NX1, CZ2)
    plinth(b, TX1, TZ1, TX2, TZ2)

    # ---------- chancel (west, lower roof) ----------
    box(b, CX1, CZ1, NX1, CZ2, 0, CTOP)
    gable_roof(b, CX1, CZ1, NX1, CZ2, CTOP + 1, ROOF, PALE, ridge="x")
    for (x, y, z) in list(b.blocks):           # keep the chancel roof out of the nave
        if x > NX1 and y > 0:
            del b.blocks[(x, y, z)]

    # ---------- nave ----------
    box(b, NX1, NZ1, NX2, NZ2, 0, NTOP)
    for x in (8, 11):                          # pilasters
        for z in (NZ1, NZ2):
            b.fill(x, 0, z, x, NTOP, z, TRIM)
    for x in range(NX1, NX2 + 1):              # cornice
        for z in (NZ1, NZ2):
            b.set(x, NTOP, z, stone(x, NTOP, z))
    for x in (8, 11):                          # buttresses
        for z, out, f in ((NZ1 - 1, -1, "south"), (NZ2 + 1, 1, "north")):
            b.fill(x, min(g(x, z), 0) - 2, z, x, 2, z, TRIM)
            b.set(x, 3, z, f"stone_brick_stairs[facing={f},half=bottom]")
    nave_roof = gable_roof(b, NX1, NZ1, NX2, NZ2, NTOP + 1, ROOF, PALE, ridge="x")
    # tall windows, two per bay, both long walls
    for x in (6, 9, 12):
        for z in (NZ1, NZ2):
            window(b, x, 2, z, along="x", width=2, height=4)
    # small window in the west gable above the chancel roof
    window(b, NX1, 10, 10, along="z", width=1, height=2, pane="white_stained_glass_pane")
    # arch from nave into chancel
    b.fill(NX1, 1, 8, NX1, 4, 12, "air")
    b.set(NX1, 4, 8, "stone_brick_stairs[facing=south,half=top]")
    b.set(NX1, 4, 12, "stone_brick_stairs[facing=north,half=top]")

    # ---------- tower (east front) ----------
    box(b, TX1, TZ1, TX2, TZ2, 0, TTOP)
    for y in (6, 11, TTOP):                    # string courses
        for x in range(TX1, TX2 + 1):
            for z in range(TZ1, TZ2 + 1):
                if x in (TX1, TX2) or z in (TZ1, TZ2):
                    b.set(x, y, z, stone(x, y, z))
    b.fill(TX1, 1, 9, TX1, 3, 11, "air")       # opening into the nave
    b.fill(TX1, 4, 9, TX1, 4, 11, TRIM)
    door(b, 16, 1, TZ2, facing="south", wood=WOOD)
    b.set(16, 3, TZ2, "chiseled_stone_bricks")
    window(b, 16, 7, TZ2, along="x", height=3)
    window(b, TX2, 7, 10, along="z", height=3)
    window(b, 16, 7, TZ1, along="x", height=3)
    # belfry: plank floor at y 11 with a ladder hatch, open arches, the bell on a beam
    b.fill(15, 11, 9, 17, 11, 11, "spruce_planks")
    for y in range(1, 12):
        b.set(17, y, 9, "ladder[facing=south]")
    b.set(17, 12, 9, "air")
    for y in range(12, 15):
        b.set(16, y, TZ1, "air")
        b.set(16, y, TZ2, "air")
        b.set(TX2, y, 10, "air")
    b.fill(15, 15, 10, 17, 15, 10, f"{WOOD}_log[axis=x]")
    b.set(16, 14, 10, "bell[attachment=ceiling,facing=north]")
    b.set(15, 12, 11, STAND)
    # steep slate spire
    for k, h in enumerate((3, 2, 1)):
        y = TTOP + 1 + 2 * k
        ring(b, 16 - h, 10 - h, 16 + h, 10 + h, y, ROOF)
        if h > 1:
            hh = h - 1
            for x in range(16 - hh, 16 + hh + 1):
                for z in range(10 - hh, 10 + hh + 1):
                    if x in (16 - hh, 16 + hh) or z in (10 - hh, 10 + hh):
                        b.set(x, y + 1, z, "deepslate_tiles")
    b.set(16, TTOP + 6, 10, "deepslate_tiles")
    b.set(16, TTOP + 7, 10, "deepslate_tile_wall")
    b.set(16, TTOP + 8, 10, "lightning_rod")

    # ---------- floors ----------
    b.fill(NX1 + 1, 0, NZ1 + 1, NX2 - 1, 0, NZ2 - 1, "polished_andesite")
    b.fill(CX1 + 1, 0, CZ1 + 1, NX1, 0, CZ2 - 1, "polished_andesite")
    b.fill(TX1 + 1, 0, TZ1 + 1, TX2 - 1, 0, TZ2 - 1, "polished_andesite")
    b.fill(TX1, 0, 9, TX1, 0, 11, "polished_andesite")
    for x in range(NX1, TX1 + 1):              # red aisle from tower to chancel
        b.set(x, 1, 10, "red_carpet")
    for z in range(9, 12):
        b.set(15, 1, z, "red_carpet")

    # ---------- pews facing the altar (west) ----------
    for x in (7, 9, 11):
        for z in (8, 9, 11, 12):
            b.set(x, 1, z, "spruce_stairs[facing=east,half=bottom]")

    # ---------- chancel: raised dais, altar, candles ----------
    b.fill(2, 1, 8, 3, 1, 12, "smooth_stone")
    for z in range(8, 13):
        b.set(4, 1, z, "stone_brick_stairs[facing=west,half=bottom]")
    b.fill(2, 2, 9, 2, 2, 11, "chiseled_quartz_block")
    b.set(2, 3, 9, "candle[candles=3,lit=true]")
    b.set(2, 3, 10, "white_candle[candles=1,lit=true]")
    b.set(2, 3, 11, "candle[candles=3,lit=true]")
    window(b, CX1, 3, 10, along="z", height=3, pane="yellow_stained_glass_pane")
    window(b, CX1, 3, 8, along="z", height=2, pane="white_stained_glass_pane")
    window(b, CX1, 3, 12, along="z", height=2, pane="white_stained_glass_pane")
    for z in (CZ1, CZ2):
        window(b, 3, 2, z, along="x", height=3)
    b.set(2, 2, 8, STAND)
    b.set(2, 2, 12, STAND)

    # ---------- nave lighting: tie beams with hanging lanterns ----------
    for x in (8, 11):
        b.fill(x, NTOP + 1, NZ1, x, NTOP + 1, NZ2, f"{WOOD}_log[axis=z]")
        for z in (8, 12):
            b.set(x, NTOP, z, HANG)
    b.set(13, 1, 7, STAND)
    b.set(13, 1, 13, STAND)
    b.set(6, 1, 7, "potted_white_tulip")
    b.set(6, 1, 13, "potted_white_tulip")
    b.set(15, 1, 9, STAND)
    b.set(17, 1, 11, "barrel[facing=up]")
    b.set(17, 2, 11, STAND)

    # ---------- regrade under the north eave where the hill was cut ----------
    for x in range(CX1 - 1, TX2 + 2):
        for z in range(0, 20):
            if (x, 1, z) in b.blocks or (x, 0, z) in b.blocks:
                continue
            top = g(x, z)
            if top >= 0 and any((x, y, z) in b.blocks for y in range(1, 30)):
                for y in range(0, top + 1):
                    b.set(x, y, z, "grass_block" if y == top else "dirt")

    # ---------- path south from the door ----------
    for z in range(TZ2 + 1, 20):
        top = g(16, z)
        for x in (15, 16, 17):
            gy = min(top, g(x, z))
            b.set(x, gy, z, "dirt_path" if x == 16 else ("gravel" if (x + z) % 2 else "coarse_dirt"))
    b.set(16, 0, 18, "stone_brick_stairs[facing=north,half=bottom]") if g(16, 18) < 0 else None
    for z in (TZ2 + 2, TZ2 + 5):               # lamp posts
        for x in (14, 18):
            gy = g(x, z)
            b.set(x, gy + 1, z, "stone_brick_wall")
            b.set(x, gy + 2, z, f"{WOOD}_fence")
            b.set(x, gy + 3, z, STAND)

    # ---------- small churchyard south-west ----------
    for x, z in ((3, 17), (6, 17), (9, 17), (4, 19), (7, 19), (10, 19)):
        gy = g(x, z)
        b.set(x, gy + 1, z, "mossy_stone_brick_wall" if (x + z) % 2 else "stone_brick_wall")
    for x, z in ((2, 16), (5, 18), (8, 16), (11, 18)):
        b.set(x, g(x, z) + 1, z, "poppy" if x % 2 else "oxeye_daisy")
    return b
