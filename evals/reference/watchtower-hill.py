"""Stone watchtower on a snowy hill: flared base with door, 5x5 shaft with spiral stairs,
corbelled lookout platform with crenellations. 11x11 footprint, 21 tall, door south."""
from architect.build import Build
from architect.parts import clear_inside, door, floor, light, spiral_stairs, walls, window

S = 10          # base footprint 0..S
SH1, SH2 = 2, 8  # shaft walls
TOP = 18        # platform floor y
BASE_H = 4

def build():
    b = Build("watchtower")
    SB = ["stone_bricks"] * 5 + ["cracked_stone_bricks", "mossy_stone_bricks", "stone_bricks"]
    # base
    floor(b, 0, 0, S, S, 0, "cobblestone")
    clear_inside(b, 0, 0, S, S, 1, TOP + 3)
    walls(b, 0, 0, S, S, 1, BASE_H, "stone_bricks", corner="dark_oak_log[axis=y]")
    floor(b, 1, 1, S - 1, S - 1, 0, "spruce_planks")
    for i, x in enumerate(range(1, S)):  # texture
        if i % 3 == 1:
            b.set(x, 2, 0, "cracked_stone_bricks"); b.set(x, 3, S, "mossy_stone_bricks")
    for x in range(S + 1):
        for z in (0, S):
            b.set(x, BASE_H, z, "dark_oak_log[axis=x]")
    for z in range(1, S):
        for x in (0, S):
            b.set(x, BASE_H, z, "dark_oak_log[axis=z]")
    # base ceiling ring / ledge at y5, open over the shaft
    floor(b, 0, 0, S, S, BASE_H + 1, "stone_brick_slab[type=bottom]")
    floor(b, SH1, SH1, SH2, SH2, BASE_H + 1, "stone_bricks")
    # shaft
    walls(b, SH1, SH1, SH2, SH2, BASE_H + 1, TOP - 1, "stone_bricks", corner="dark_oak_log[axis=y]")
    for y in range(BASE_H + 2, TOP - 1):  # texture variation
        for x in range(SH1 + 1, SH2):
            for z in (SH1, SH2):
                if (x * 7 + y * 3 + z) % 5 == 0:
                    b.set(x, y, z, "mossy_stone_bricks" if (x + y) % 2 else "cracked_stone_bricks")
        for z in range(SH1 + 1, SH2):
            for x in (SH1, SH2):
                if (z * 7 + y * 3 + x) % 5 == 0:
                    b.set(x, y, z, "cracked_stone_bricks")
    for y in (9, 13):  # dark wood bands
        for i in range(SH1 + 1, SH2):
            for (x, z, ax) in ((i, SH1, "x"), (i, SH2, "x"), (SH1, i, "z"), (SH2, i, "z")):
                b.set(x, y, z, f"dark_oak_log[axis={ax}]")
    # corbel under platform
    for x in range(1, S):
        for z in range(1, S):
            if not (SH1 <= x <= SH2 and SH1 <= z <= SH2):
                b.set(x, TOP - 1, z, "stone_brick_slab[type=top]")
    # platform floor and parapet
    floor(b, 1, 1, S - 1, S - 1, TOP, "stone_bricks")
    floor(b, 3, 3, 7, 7, TOP, "air")  # filled below by stairs exit; re-floor except ring
    for x in range(4, 7):
        for z in range(4, 7):
            b.set(x, TOP, z, "stone_bricks")
    for x in range(1, S):
        for z in range(1, S):
            if x in (1, S - 1) or z in (1, S - 1):
                b.set(x, TOP + 1, z, "stone_bricks")
                if (x + z) % 2 == 0:
                    b.set(x, TOP + 2, z, "stone_bricks")
    for (x, z) in ((1, 1), (S - 1, 1), (1, S - 1), (S - 1, S - 1)):
        b.fill(x, TOP + 1, z, x, TOP + 3, z, "dark_oak_log[axis=y]")
        b.set(x, TOP + 4, z, "lantern[hanging=false]")
    # center column (torch post)
    b.fill(5, 1, 5, 5, TOP - 1, 5, "dark_oak_log[axis=y]")
    # stairs: ring of the 5x5 interior 3..7
    spiral_stairs(b, 3, 3, 7, 7, 1, TOP, "stone_brick_stairs", "dark_oak_planks")
    b.set(5, TOP, 5, "dark_oak_log[axis=y]")
    for (x, z, top) in ((4, 3, 2), (5, 3, 3), (6, 3, 4)):
        b.fill(x, 1, z, x, top - 1, z, "stone_bricks")
    # flagpole with banner on the platform centre
    b.fill(5, TOP + 1, 5, 5, TOP + 6, 5, "dark_oak_fence")
    b.set(5, TOP + 6, 5, "dark_oak_fence")
    for y in (TOP + 5, TOP + 6):
        for x in (6, 7):
            b.set(x, y, 5, "red_wool")
    # buttresses on the base ledge at the shaft corners
    for (x, z) in ((1, 1), (S - 1, 1), (1, S - 1), (S - 1, S - 1)):
        for y in (BASE_H + 2, BASE_H + 3):
            b.set(x, y, z, "stone_brick_wall")
    for x in range(3, 8, 2):
        b.set(x, BASE_H + 2, 1, "stone_brick_wall"); b.set(x, BASE_H + 2, S - 1, "stone_brick_wall")
    # hang torches on the center column
    for y, (dx, dz, f) in zip((2, 5, 8, 11, 14, 16), ((0, 1, "south"), (1, 0, "east"), (0, -1, "north"),
                                                      (-1, 0, "west"), (0, 1, "south"), (1, 0, "east"))):
        b.set(5 + dx, y, 5 + dz, f"wall_torch[facing={f}]")
    # door and windows
    door(b, 5, 1, S, facing="south", wood="dark_oak")
    light(b, 4, 2, S + 1, "lantern[hanging=false]")  # placeholder replaced below
    b.set(4, 2, S + 1, "air")
    b.set(3, 3, S + 1, "air")
    b.set(4, 1, S + 1, "lantern[hanging=false]")
    b.set(6, 1, S + 1, "lantern[hanging=false]")
    for x in (2, 8):
        window(b, x, 2, S, along="x", height=2)
        window(b, x, 2, 0, along="x", height=2)
    window(b, 0, 2, 5, along="z", height=2); window(b, S, 2, 5, along="z", height=2)
    for y in (7, 11, 15):
        for (x, z, al) in ((5, SH1, "x"), (5, SH2, "x"), (SH1, 5, "z"), (SH2, 5, "z")):
            if (x + y) % 2 or True:
                window(b, x, y, z, along=al, height=2)
    # parapet openings stay; outside: path and barrels
    for z in range(S + 1, S + 7):
        b.set(5, 0, z, "stone_bricks" if z % 2 else "gravel")
        b.set(4, 0, z, "gravel"); b.set(6, 0, z, "gravel")
    b.set(1, 1, S + 1, "barrel[facing=up]"); b.set(2, 1, S + 1, "barrel[facing=up]")
    b.set(8, 1, S + 1, "dark_oak_fence"); b.set(9, 1, S + 1, "dark_oak_fence")
    b.set(9, 2, S + 1, "lantern[hanging=false]")
    b.set(9, 1, S - 1, "chest[facing=north]") if False else None
    # inside base: chest and crafting
    b.set(1, 1, 1, "chest[facing=south]"); b.set(2, 1, 1, "barrel[facing=up]")
    b.set(9, 1, 1, "crafting_table")
    light(b, 1, 1, S - 1); light(b, S - 1, 1, S - 1); light(b, S - 1, 1, 2)
    # platform lights
    light(b, 3, TOP + 1, 3, "lantern[hanging=false]") if False else None
    return b
