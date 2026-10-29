"""Weathered spruce boathouse: storage room on the shore, open roofed boat hall on posts over water, dock."""
from architect.build import Build
from architect.parts import clear_inside, door, floor, gable_roof, light, posts, walls, window

L, D, H = 22, 9, 4          # total length (x), depth (z), wall height
SPLIT = 14                  # x where the stone-based storage room starts
DOCK_X = 0


def build():
    b = Build("boathouse-shore")
    x2, z2 = L - 1, D - 1
    # stilts over water (x 2..SPLIT-1) down to the lake bed
    pts = [(x, z) for x in range(7, SPLIT, 3) for z in (0, z2)] + [(SPLIT - 1, 0), (SPLIT - 1, z2)]
    posts(b, pts, -1, -6, "stripped_spruce_log[axis=y]")
    # deck over water
    floor(b, 7, 0, SPLIT - 1, z2, 0, "spruce_planks")
    # open boat slip: centre planks removed so a boat can float in
    for x in range(8, SPLIT - 1):
        for z in (3, 4, 5):
            b.set(x, 0, z, "water")
    # storage room on the shore: stone base + spruce
    floor(b, SPLIT, 0, x2, z2, 0, "stone_bricks")
    clear_inside(b, SPLIT, 0, x2, z2, 1, H + 4)
    walls(b, SPLIT, 0, x2, z2, 1, H, "spruce_planks", corner="stripped_spruce_log[axis=y]")
    for x in range(SPLIT, x2 + 1):
        for z in (0, z2):
            b.set(x, 1, z, ["cobblestone", "mossy_cobblestone", "stone_bricks"][x % 3])
    for z in (1, z2 - 1):
        b.set(x2, 1, z, "cobblestone"); b.set(SPLIT, 1, z, "mossy_cobblestone")
    floor(b, SPLIT + 1, 1, x2 - 1, z2 - 1, 0, "spruce_planks")
    # beam band
    for x in range(SPLIT, x2 + 1):
        b.set(x, H, 0, "stripped_spruce_log[axis=x]")
        b.set(x, H, z2, "stripped_spruce_log[axis=x]")
    for z in range(1, z2):
        b.set(SPLIT, H, z, "stripped_spruce_log[axis=z]")
        b.set(x2, H, z, "stripped_spruce_log[axis=z]")
    # doors: land side (south, to path) and a hall door west into boat hall
    door(b, SPLIT + 4, 1, z2, facing="south", wood="spruce")
    door(b, SPLIT, 1, 6, facing="west", wood="spruce") if False else None
    # wall between hall and room open via a wide doorway
    for z in (3, 4, 5):
        for y in (1, 2):
            b.set(SPLIT, y, z, "air")
    window(b, SPLIT + 2, 2, 0, along="x", width=2)
    window(b, SPLIT + 6, 2, 0, along="x", width=2)
    window(b, x2, 2, 3, along="z", width=3)
    window(b, SPLIT + 7, 2, z2, along="x", width=1)
    # open hall: corner posts and roof beam supports
    for (x, z) in [(7, 0), (7, z2), (SPLIT - 1, 0), (SPLIT - 1, z2), (10, 0), (10, z2)]:
        for y in range(1, H + 1):
            b.set(x, y, z, "stripped_spruce_log[axis=y]")
    for x in range(7, SPLIT):
        b.set(x, H, 0, "stripped_spruce_log[axis=x]")
        b.set(x, H, z2, "stripped_spruce_log[axis=x]")
    # one roof over everything
    gable_roof(b, 6, 0, SPLIT, z2, H + 1, "spruce_stairs", "spruce_planks", ridge="x")
    gable_roof(b, SPLIT, 0, x2, z2, H + 1, "dark_oak_stairs", "stripped_spruce_log[axis=y]", ridge="z")
    # long dock out west, T-head at the end
    floor(b, 1, 3, 6, 5, 0, "spruce_planks")
    floor(b, 0, 1, 1, 7, 0, "spruce_planks")
    posts(b, [(0, 1), (0, 7), (1, 1), (1, 7), (3, 3), (3, 5), (5, 3), (5, 5), (6, 3), (6, 5)], -1, -6, "spruce_log[axis=y]")
    for (x, z) in [(0, 1), (0, 7), (3, 3), (3, 5)]:
        b.set(x, 1, z, "spruce_fence")
    b.set(0, 2, 1, "lantern[hanging=false]"); b.set(0, 2, 7, "lantern[hanging=false]")
    b.set(3, 2, 3, "lantern[hanging=false]")
    b.set(0, 1, 4, "barrel[facing=up]")
    b.set(2, 1, 5, "ladder[facing=east]") if False else None
    # fence rail along the open long sides of the hall
    for x in range(8, SPLIT - 1):
        if x != 10:
            b.set(x, 1, 0, "spruce_fence"); b.set(x, 1, z2, "spruce_fence")
    # lights
    light(b, 8, 3, 0, "lantern[hanging=true]"); light(b, 8, 3, z2, "lantern[hanging=true]")
    light(b, 12, 3, 0, "lantern[hanging=true]"); light(b, 12, 3, z2, "lantern[hanging=true]")
    light(b, SPLIT + 2, 3, 2, "lantern[hanging=true]"); light(b, SPLIT + 7, 3, 2, "lantern[hanging=true]")
    light(b, SPLIT + 4, 3, 6, "lantern[hanging=true]")
    for (x, z) in [(SPLIT + 2, 4), (SPLIT + 5, 3), (SPLIT + 5, 6), (SPLIT + 2, 7), (x2 - 1, 7)]:
        light(b, x, 1, z, 'lantern[hanging=false]')
    # storage furniture
    for z in (2, 3, 4):
        b.set(x2 - 1, 1, z, "barrel[facing=up]")
    b.set(x2 - 1, 1, 5, "chest[facing=west]")
    b.set(SPLIT + 1, 1, 7, "chest[facing=east]")
    b.set(SPLIT + 1, 1, 1, "crafting_table")
    # woodpile and flower boxes outside
    for z in (D, D + 1):
        b.set(SPLIT + 1, 1, z, 'spruce_log[axis=x]'); b.set(SPLIT + 2, 1, z, 'spruce_log[axis=x]')
    b.set(SPLIT + 6, 1, D, 'barrel[facing=up]'); b.set(SPLIT + 7, 1, D, 'barrel[facing=up]')
    b.set(SPLIT + 6, 2, D, 'lantern[hanging=false]')
    # path to the door
    for z in range(D, D + 3):
        b.set(SPLIT + 4, 0, z, "gravel")
    # chimney of stone through the roof, with a hearth inside
    for y in range(1, H + 5):
        b.set(x2 - 1, y, 1, "cobblestone" if y % 2 else "stone_bricks")
    b.set(x2 - 1, H + 5, 1, "campfire[lit=false]") if False else None
    # a rowing boat in the slip
    for x in range(9, 13):
        b.set(x, 0, 4, "oak_slab[type=bottom]")
    b.set(8, 0, 4, "oak_stairs[facing=east,half=bottom]") if False else None
    b.set(9, 1, 3, "oak_trapdoor[facing=south,half=bottom,open=false]")
    b.set(9, 1, 5, "oak_trapdoor[facing=north,half=bottom,open=false]")
    # stone stepping path from the door
    for z in range(D, D + 3):
        b.set(SPLIT + 4, 0, z, "cobblestone" if z % 2 else "stone_bricks")
    for x in (SPLIT + 3, SPLIT + 5):
        b.set(x, 0, D + 1, "mossy_cobblestone")
    # stone footing blocks at the water line under the hall
    for (x, z) in [(7, 0), (7, z2), (10, 0), (10, z2), (SPLIT - 1, 0), (SPLIT - 1, z2)]:
        b.set(x, -1, z, "mossy_cobblestone")
    return b
