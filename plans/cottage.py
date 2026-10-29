"""A small timber-frame cottage: stone foundation, log frame, plank walls, glass windows, gable roof,
a lit interior. 9 x 7 footprint, door facing south."""

from architect.build import Build
from architect.parts import clear_inside, door, floor, gable_roof, light, walls, window

W, D, H = 9, 7, 4  # footprint and wall height (blocks)


def build():
    b = Build("cottage")
    x2, z2 = W - 1, D - 1
    floor(b, 0, 0, x2, z2, 0, "cobblestone")
    clear_inside(b, 0, 0, x2, z2, 1, H + 3)
    walls(b, 0, 0, x2, z2, 1, H, "spruce_planks", corner="oak_log[axis=y]")
    floor(b, 1, 1, x2 - 1, z2 - 1, 0, "oak_planks")
    # a log band under the eaves
    for x in range(x2 + 1):
        b.set(x, H, 0, "oak_log[axis=x]")
        b.set(x, H, z2, "oak_log[axis=x]")
    for z in range(1, z2):
        b.set(0, H, z, "oak_log[axis=z]")
        b.set(x2, H, z, "oak_log[axis=z]")

    door(b, W // 2, 1, z2, facing="south", wood="spruce")
    for x in (2, x2 - 2):
        window(b, x, 2, z2, along="x")
        window(b, x - 1, 2, 0, along="x", width=3)
    window(b, 0, 2, D // 2 - 1, along="z", width=3)
    window(b, x2, 2, D // 2 - 1, along="z", width=3)

    gable_roof(b, 0, 0, x2, z2, H + 1, "dark_oak_stairs", "spruce_planks", ridge="x")

    # inside: light (no mob spawns), a bed, a table, storage
    light(b, 2, 1, 1)
    light(b, x2 - 2, 1, 1)
    b.set(1, 1, 2, "red_bed[facing=north,part=head]")
    b.set(1, 1, 3, "red_bed[facing=north,part=foot]")
    b.set(x2 - 1, 1, 2, "crafting_table")
    b.set(x2 - 1, 1, 3, "chest[facing=west]")
    b.set(x2 - 1, 1, 4, "barrel[facing=up]")
    return b
