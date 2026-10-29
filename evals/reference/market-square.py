"""Colourful village market: paved square, central well, four striped-awning stalls, lanterns."""
from architect.build import Build

N = 24
C = 11.5  # centre

STALLS = [  # side, colours, goods
    ("N", "red_wool", "white_wool", "barrel[facing=up]"),
    ("S", "blue_wool", "white_wool", "hay_block"),
    ("W", "yellow_wool", "orange_wool", "composter"),
    ("E", "lime_wool", "white_wool", "barrel[facing=up]"),
]
GOODS_ON_COUNTER = ["melon", "pumpkin", "hay_block", "red_wool"]


def tf(side, u, v):
    """stall-local (u across 0..5, v depth 0=back..3=front) -> world local x,z"""
    if side == "N":
        return 9 + u, 1 + v
    if side == "S":
        return 14 - u, 22 - v
    if side == "W":
        return 1 + v, 14 - u
    return 22 - v, 9 + u


def build():
    b = Build("market-square")
    import random
    rnd = random.Random(5)
    # paving, varied
    for x in range(N):
        for z in range(N):
            edge = x in (0, N - 1) or z in (0, N - 1)
            blk = "polished_andesite" if edge else rnd.choice(
                ["stone_bricks", "cracked_stone_bricks", "bricks", "cobblestone", "mossy_stone_bricks", "stone_bricks"])
            b.set(x, 0, z, blk)
    # inner decorative ring around the well and cross paths
    for x in range(N):
        for z in range(N):
            if abs(x - C) < 1.6 or abs(z - C) < 1.6:
                b.set(x, 0, z, rnd.choice(["terracotta", "smooth_stone", "bricks", "stone_bricks"]))
    for x in range(8, 16):
        for z in range(8, 16):
            b.set(x, 0, z, "white_terracotta" if (x + z) % 2 else "orange_terracotta")
    # clear air above
    for x in range(N):
        for z in range(N):
            for y in range(1, 8):
                b.set(x, y, z, "air")
    # well 4x4 at 10..13
    for x in range(10, 14):
        for z in range(10, 14):
            inner = 11 <= x <= 12 and 11 <= z <= 12
            if inner:
                b.set(x, 0, z, "stone_bricks")
                b.set(x, 1, z, "water")
            else:
                b.set(x, 1, z, "mossy_stone_brick_wall" if (x in (10, 13) and z in (10, 13)) is False else "stone_brick_wall")
    for x, z in [(10, 10), (13, 10), (10, 13), (13, 13)]:
        for y in (1, 2, 3):
            b.set(x, y, z, "oak_log[axis=y]" if y > 1 else "stone_brick_wall")
        b.set(x, 4, z, "oak_log[axis=y]")
    for x in range(9, 15):
        for z in range(9, 15):
            if 10 <= x <= 13 and 10 <= z <= 13 or (x in (9, 14) or z in (9, 14)):
                edge = not (10 <= x <= 13 and 10 <= z <= 13)
                if edge and (x in (9, 14)) and (z in (9, 14)):
                    continue
                if edge or not (11 <= x <= 12 and 11 <= z <= 12):
                    b.set(x, 5, z, "spruce_slab[type=bottom]" if edge else "dark_oak_planks")
    # hanging bucket and lantern
    b.set(11, 4, 10, "iron_chain[axis=y]")
    b.set(11, 3, 10, "lantern[hanging=true]")
    b.set(12, 4, 13, "iron_chain[axis=y]")
    b.set(12, 3, 13, "lantern[hanging=true]")
    # stalls
    for side, c1, c2, goods in STALLS:
        for u in range(6):
            for v in range(4):
                x, z = tf(side, u, v)
                b.set(x, 0, z, "oak_planks" if (u + v) % 3 else "spruce_planks")
        # posts at corners
        for (u, v) in [(0, 0), (5, 0), (0, 3), (5, 3)]:
            x, z = tf(side, u, v)
            for y in (1, 2, 3):
                b.set(x, y, z, "oak_fence")
        # back shelf: barrels / goods
        for u in range(1, 5):
            x, z = tf(side, u, 0)
            b.set(x, 1, z, goods if u % 2 else "barrel[facing=up]")
            b.set(x, 2, z, "oak_slab[type=bottom]")
            xx, zz = tf(side, u, 1)
            b.set(xx, 1, zz, ["melon", "pumpkin", "hay_block", "bookshelf"][(u + len(side)) % 4] if False else "air")
        # side walls half (trapdoor-less): low fence rail
        for v in (1, 2):
            for u in (0, 5):
                x, z = tf(side, u, v)
                b.set(x, 1, z, "oak_fence")
        # counter at front
        for u in range(1, 5):
            x, z = tf(side, u, 3)
            b.set(x, 1, z, "oak_planks" if u % 2 else "spruce_planks")
            b.set(x, 2, z, ["melon", "pumpkin", "hay_block", "red_wool"][u - 1]
                  if False else ["melon", "pumpkin", "hay_block", "jack_o_lantern"][u - 1])
        # awning: stepped pitch, high at the back, low at the front, plus a hanging valance
        for u in range(6):
            col = c1 if u % 2 == 0 else c2
            for v in range(4):
                x, z = tf(side, u, v)
                b.set(x, 5 if v < 2 else 4, z, col)
            for yy in (4,):
                for v in (0, 1):
                    for uu in (0, 5):
                        pass
            x, z = tf(side, u, 4)
            b.set(x, 4, z, col.replace("_wool", "_carpet"))
        for (u, v) in [(0, 0), (5, 0), (0, 1), (5, 1)]:
            x, z = tf(side, u, v)
            b.set(x, 4, z, "oak_fence")
        # lantern under the awning
        x, z = tf(side, 2, 2)
        b.set(x, 3, z, "lantern[hanging=true]")
        x, z = tf(side, 3, 2)
        b.set(x, 3, z, "lantern[hanging=true]")
        # a sign-ish: flower pots front
        x, z = tf(side, 0, 4)
        b.set(x, 1, z, "barrel[facing=up]")
        b.set(x, 2, z, "potted_poppy")
        x, z = tf(side, 5, 4)
        b.set(x, 1, z, "barrel[facing=up]")
        b.set(x, 2, z, "potted_cornflower")
    # corner lamp posts
    for x, z in [(1, 1), (22, 1), (1, 22), (22, 22), (6, 6), (17, 6), (6, 17), (17, 17)]:
        b.set(x, 0, z, "stone_bricks")
        for y in (1, 2, 3):
            b.set(x, y, z, "oak_fence")
        b.set(x, 4, z, "lantern[hanging=false]")
    # crates and flowers in corners
    for x, z in [(3, 3), (20, 3), (3, 20), (20, 20)]:
        b.set(x, 1, z, "barrel[facing=up]")
        b.set(x + (1 if x < 12 else -1), 1, z, "hay_block")
        b.set(x, 2, z, "flowering_azalea" if False else "potted_red_tulip")
    for x, z in [(7, 12), (7, 11), (16, 12), (16, 11), (11, 7), (12, 7), (11, 16), (12, 16)]:
        b.set(x, 0, z, "grass_block")
        b.set(x, 1, z, ["poppy", "cornflower", "oxeye_daisy", "azure_bluet"][(x + z) % 4])
    return b
