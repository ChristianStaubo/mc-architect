"""Hunter's log cabin tucked into a gap in the grove: stacked dark-oak log walls on a mossy stone base,
spruce gable roof, a stone chimney with a hearth in the west gable (a big oak stands right behind it),
a covered porch on the downhill south side with steps and a path out east between the trunks.

The gap (world x 22..27, z 57..67) has no log in any column, so the cabin clears no tree: it is placed
with --no-clear and --keep-trees, and the plan sets the air it needs itself."""

from architect.build import Build
from architect.parts import chimney, door, gable_roof, window

# local (0, 0) = world (22, 57); local y 0 = world y 89 (the floor)
PLACE = ["--at", "22,57", "--y", "89", "--foundation", "none", "--no-clear", "--keep-trees"]

X1, X2 = 0, 5          # walls x 0..5
Z1, Z2 = 1, 7          # walls z 1..7
TOP = 4                # wall top course
LOG = "dark_oak_log"
CORNER = "stripped_dark_oak_log[axis=y]"
ROOF = "spruce_stairs"
GABLE = "spruce_planks"
STONE = ("mossy_cobblestone", "cobblestone", "mossy_cobblestone", "mossy_stone_bricks")


def stone(x, y, z):
    return STONE[(x * 7 + y * 3 + z * 5) % len(STONE)]


def build():
    b = Build("forest-cabin")

    # ---- foundation and floor: stone down into the slope (ground is 87..91 here) ----
    for x in range(X1, X2 + 1):
        for z in range(Z1, Z2 + 1):
            for y in range(-3, 0):
                b.set(x, y, z, stone(x, y, z))
            edge = x in (X1, X2) or z in (Z1, Z2)
            b.set(x, 0, z, stone(x, 0, z) if edge else "spruce_planks")

    # ---- log walls: horizontal logs, vertical stripped corner posts ----
    for y in range(1, TOP + 1):
        for x in range(X1 + 1, X2):
            b.set(x, y, Z1, f"{LOG}[axis=x]")
            b.set(x, y, Z2, f"{LOG}[axis=x]")
        for z in range(Z1 + 1, Z2):
            b.set(X1, y, z, f"{LOG}[axis=z]")
            b.set(X2, y, z, f"{LOG}[axis=z]")
    for x, z in ((X1, Z1), (X1, Z2), (X2, Z1), (X2, Z2)):
        b.fill(x, 1, z, x, TOP, z, CORNER)

    # ---- inside: clear whatever the hill or the canopy left ----
    b.fill(X1 + 1, 1, Z1 + 1, X2 - 1, 8, Z2 - 1, "air")

    # ---- roof (ridge along x, gables flush so no column reaches the trunks at x -1 and x 6) ----
    gable_roof(b, X1, Z1, X2, Z2, TOP, ROOF, GABLE, ridge="x", overhang=1, end_overhang=0)
    # tie beam across under the ridge for the lantern
    b.fill(X1 + 1, TOP, 4, X2 - 1, TOP, 4, f"{LOG}[axis=x]")
    # gable window
    window(b, X2, 6, 4, along="z")

    # ---- fireplace in the west gable: hearth in the wall, chimney stack above ----
    chimney(b, X1, 4, 2, 9, "mossy_cobblestone", smoke=False, cap="cobblestone_wall")
    for z in (3, 5):
        b.fill(X1, 1, z, X1, 3, z, stone(X1, 1, z))
    b.set(X1, 1, 4, "campfire[lit=true,signal_fire=false,facing=east]")
    b.set(X1 + 1, 0, 4, "cobblestone")
    b.set(X1 + 1, 0, 3, "cobblestone")
    b.set(X1 + 1, 0, 5, "cobblestone")
    b.set(X1, 2, 4, "mossy_cobblestone")

    # ---- door and windows ----
    door(b, 2, 1, Z2, facing="south", wood="spruce")
    window(b, 4, 1, Z2, along="x", height=2)
    window(b, X2, 1, 3, along="z", height=2)
    window(b, X2, 1, 5, along="z", height=2)
    window(b, 3, 2, Z1, along="x", height=2)

    # ---- interior ----
    b.set(4, 1, 5, "brown_bed[facing=south,part=foot]")
    b.set(4, 1, 6, "brown_bed[facing=south,part=head]")
    b.set(1, 1, 2, "barrel[facing=up]")
    b.set(2, 1, 2, "smoker[facing=south,lit=false]")
    b.set(4, 1, 2, "chest[facing=south]")
    b.set(4, 2, 2, "lantern[hanging=false]")
    b.set(1, 1, 6, "fletching_table")
    b.set(3, TOP - 1, 4, "lantern[hanging=true]")
    b.set(2, 1, 4, "brown_carpet")
    b.set(3, 1, 4, "brown_carpet")
    b.set(2, 1, 5, "brown_carpet")
    b.set(3, 1, 5, "brown_carpet")

    # ---- porch on the south side, under a lean-to that continues the roof slope ----
    PZ = Z2 + 2  # porch front row
    for x in range(X1, X2 + 1):
        for z in (Z2 + 1, PZ):
            b.fill(x, -3, z, x, -1, z, stone(x, -1, z))
            b.set(x, 0, z, "spruce_planks")
            b.fill(x, 1, z, x, 3, z, "air")
        b.set(x, 3, PZ, f"{ROOF}[facing=north,half=bottom,shape=straight]")
    for x in (X1, X2):
        b.fill(x, 1, PZ, x, 2, PZ, "spruce_fence")
    for x in (X1 + 1, X2 - 1):
        b.set(x, 1, PZ, "spruce_fence")
    for x in (2, 3):                        # steps down to the path
        b.set(x, -1, PZ + 1, "spruce_stairs[facing=north,half=bottom,shape=straight]")
        b.fill(x, 0, PZ + 1, x, 2, PZ + 1, "air")
    b.set(1, 3, Z2 + 1, "lantern[hanging=true]")
    b.set(4, 3, Z2 + 1, "lantern[hanging=true]")
    b.set(4, 1, Z2 + 1, "spruce_stairs[facing=north,half=bottom,shape=straight]")  # a seat by the door
    b.set(5, 1, Z2 + 1, "barrel[facing=up]")

    # ---- path: from the steps east along the open strip between the trunks ----
    ground = {x: (-2 if x + 22 <= 29 else -3) for x in range(2, 14)}
    for x in range(2, 14):
        z = PZ + 2
        b.set(x, ground[x], z, "dirt_path" if x % 3 else "coarse_dirt")
        b.set(x, ground[x] + 1, z, "air")

    # ---- woodpile against the east wall ----
    b.fill(X2 + 1, 0, 2, X2 + 1, 0, 3, "stripped_oak_log[axis=z]")
    b.set(X2 + 1, 1, 2, "stripped_oak_log[axis=z]")
    b.set(X2 + 1, -1, 2, "cobblestone")
    b.set(X2 + 1, -1, 3, "cobblestone")
    return b
