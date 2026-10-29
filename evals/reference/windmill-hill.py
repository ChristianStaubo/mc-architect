"""Stone tower windmill on the hilltop: a round fieldstone tower (radius 3) with a spruce log band at the
upper floor, a spruce cone cap and finial, and four big white sails on a dark-oak hub on the east side,
facing the view down the slope. Two floors inside (ladder up the north wall, central drive shaft through
both), door south onto a gravel path with lanterns, hay and barrels. Local (0,0) = world (-456, -192);
local y 0 = world 101 (the hilltop's ground). The slope is gentle, so the terrain is kept (--no-clear) and
only the tower's floor and path replace the grass; no foundation under the sails."""
from architect.build import Build
from architect.parts import cone_roof, door, round_tower, window

PLACE = ["--at", "-456,-192", "--y", "101", "--foundation", "none", "--no-clear"]

CX, CZ, R = 9, 8, 3
WALL_TOP = 11
FLOOR2 = 6
CAP = 12
HUB_Y = CAP + 1
SAIL_X = CX + R + 3            # the plane of the sails, two blocks out from the cap
ARM = 7
STONE = ["cobblestone", "stone_bricks", "mossy_cobblestone", "cobblestone", "andesite", "stone_bricks",
         "cracked_stone_bricks", "cobblestone"]


def d(x, z):
    return ((x - CX) ** 2 + (z - CZ) ** 2) ** 0.5


def connect(b, kinds=("spruce_fence",)):
    for (x, y, z), blk in list(b.blocks.items()):
        n = blk.split("[")[0]
        if n not in kinds:
            continue
        st = []
        for side, (dx, dz) in (("east", (1, 0)), ("north", (0, -1)), ("south", (0, 1)), ("west", (-1, 0))):
            o = b.blocks.get((x + dx, y, z + dz), "air").split("[")[0]
            ok = o == n or not (o == "air" or any(k in o for k in ("stairs", "slab", "lantern", "door", "hay")))
            st.append(f"{side}={'true' if ok else 'false'}")
        b.set(x, y, z, f"{n}[{','.join(st)},waterlogged=false]")


def sails(b):
    """Four arms in the plane x = SAIL_X, turning about the hub: a log spar, two blocks of sailcloth on
    one side (all on the same turning side, so it reads as a rotor) and a fence lattice edge."""
    for k in range(4):
        def put(u, v, blk):  # (u, v) in the arm's frame: v out along the spar, u across it
            for _ in range(k):
                u, v = v, -u
            b.set(SAIL_X, HUB_Y + v, CZ + u, blk)
        vertical = k % 2 == 0
        for v in range(1, ARM + 1):
            put(0, v, f"stripped_spruce_log[axis={'y' if vertical else 'z'}]")
        for v in range(2, ARM + 1):
            for u in (1, 2):
                put(u, v, "white_wool" if (v + u) % 5 else "light_gray_wool")
            put(3, v, "spruce_fence")
        put(1, ARM + 1, "spruce_fence")
        put(2, ARM + 1, "spruce_fence")
    b.set(SAIL_X, HUB_Y, CZ, "dark_oak_log[axis=x]")


def build():
    b = Build("windmill-hill")
    ring = [(x, z) for x in range(CX - R - 1, CX + R + 2) for z in range(CZ - R - 1, CZ + R + 2) if R - 0.5 <= d(x, z) < R + 0.5]
    inside = [(x, z) for x in range(CX - R, CX + R + 1) for z in range(CZ - R, CZ + R + 1) if d(x, z) < R - 0.5]
    skirt = [(x, z) for x in range(CX - R - 2, CX + R + 3) for z in range(CZ - R - 2, CZ + R + 3) if R + 0.5 <= d(x, z) < R + 1.5]

    # ---- tower: fieldstone walls, a spruce log band at the upper floor, a stone skirt at the foot
    round_tower(b, CX, CZ, 0, WALL_TOP, R, "cobblestone", inside="air")
    for (x, z) in ring:
        for y in range(0, WALL_TOP + 1):
            b.set(x, y, z, STONE[(x * 5 + y * 3 + z * 7) % len(STONE)])
        b.set(x, FLOOR2, z, "stripped_spruce_log[axis=y]")
        b.set(x, WALL_TOP, z, "spruce_planks")
    for (x, z) in skirt:
        f = ("east" if CX > x else "west") if abs(CX - x) >= abs(CZ - z) else ("south" if CZ > z else "north")
        b.set(x, 1, z, f"stone_brick_stairs[facing={f},half=bottom,shape=straight]")
        b.set(x, 0, z, "cobblestone")
    # floors
    for (x, z) in inside:
        b.set(x, 0, z, "spruce_planks")
        b.set(x, FLOOR2, z, "spruce_planks")
    # ---- cap: spruce cone with overhang and a finial
    cone_roof(b, CX, CZ, CAP, R, "spruce_stairs", top="spruce_planks")
    b.set(CX, CAP + R + 2, CZ, "spruce_fence")
    b.set(CX, CAP + R + 3, CZ, "lightning_rod")
    # central drive shaft from the ground floor up into the cap, axle out east to the hub
    b.fill(CX, 1, CZ, CX, CAP + R, CZ, "stripped_spruce_log[axis=y]")
    for x in range(CX + 1, SAIL_X):
        b.set(x, HUB_Y, CZ, "stripped_dark_oak_log[axis=x]")
    sails(b)

    # ---- door (south, toward the path down the hill) and windows
    door(b, CX, 1, CZ + R, facing="south", wood="spruce")
    b.set(CX, 3, CZ + R, "stripped_spruce_log[axis=x]")    # lintel
    b.set(CX, 0, CZ + R, "spruce_planks")
    for (x, z) in ((CX - 1, CZ + R + 1), (CX, CZ + R + 1), (CX + 1, CZ + R + 1)):
        b.set(x, 1, z, "air")                                   # no skirt step in front of the door
        b.set(x, 0, z, "gravel")
    window(b, CX + R, 2, CZ, along="z", height=2)
    window(b, CX - R, 2, CZ, along="z", height=2)
    window(b, CX - R, FLOOR2 + 2, CZ, along="z", height=2)
    window(b, CX + R, FLOOR2 + 2, CZ, along="z", height=2)
    window(b, CX, FLOOR2 + 2, CZ + R, along="x", height=2)

    # ---- inside: ladder up the north wall through a hatch, mill stores below, a loft above
    for y in range(1, FLOOR2 + 1):
        b.set(CX, y, CZ - 2, "ladder[facing=south]")
    b.set(CX - 2, 1, CZ - 1, "barrel[facing=up]")
    b.set(CX - 2, 1, CZ + 1, "hay_block[axis=y]")
    b.set(CX + 2, 1, CZ - 1, "barrel[facing=up]")
    b.set(CX + 2, 2, CZ - 1, "lantern[hanging=false]")
    b.set(CX - 2, 2, CZ - 1, "lantern[hanging=false]")
    b.set(CX + 1, 1, CZ, "grindstone[face=floor,facing=east]")
    b.set(CX + 2, 1, CZ + 1, "chest[facing=west]")
    b.set(CX - 2, FLOOR2 + 1, CZ, "barrel[facing=up]")
    b.set(CX - 2, FLOOR2 + 2, CZ, "lantern[hanging=false]")
    b.set(CX + 2, FLOOR2 + 1, CZ + 1, "lantern[hanging=false]")
    b.set(CX + 1, FLOOR2 + 1, CZ - 2, "hay_block[axis=y]")
    b.set(CX + 2, FLOOR2 + 1, CZ, "chest[facing=west]")

    # ---- outside: gravel path downhill, lantern posts at the door, hay and sacks by the wall
    for z in range(CZ + R + 2, 18):
        y = 0 if z < 17 else -1
        for x in (CX, CX + 1):
            b.set(x, y, z, "gravel" if (x + z) % 3 else "coarse_dirt")
    for x in (CX - 2, CX + 2):
        b.set(x, 1, CZ + R + 1, "spruce_fence")
        b.set(x, 2, CZ + R + 1, "lantern[hanging=false]")
    b.set(CX - 4, 1, CZ + 3, "hay_block[axis=y]")
    b.set(CX - 5, 1, CZ + 3, "hay_block[axis=x]")
    b.set(CX - 4, 1, CZ + 4, "barrel[facing=up]")
    connect(b)
    return b
