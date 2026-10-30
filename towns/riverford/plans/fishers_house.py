"""Riverford fishers' house: mud-brick, acacia frame, sandstone base, brick hip roof, loggia, net terrace."""
from architect.build import Build
from architect.parts import (clear_inside, door, floor, hip_roof, light, timber_frame, window,
                             straight_stairs, shutters, flower_box)

FRAME = "stripped_acacia_log"
FILL = "mud_bricks"
BASE = "cut_sandstone"
ROOF = "brick_stairs"
X1, X2, Z1, Z2 = 2, 11, 3, 8     # ground storey
UX2 = 8                          # upper storey stops here; x9..11 is the terrace
FL2 = 4                          # upper floor level


def build():
    b = Build("fishers_house")
    # ground storey
    floor(b, X1, Z1, X2, Z2, 0, BASE)
    clear_inside(b, X1, Z1, X2, Z2, 1, 10)
    floor(b, X1 + 1, Z1 + 1, X2 - 1, Z2 - 1, 0, "birch_planks")
    timber_frame(b, X1, Z1, X2, Z2, 1, 3, FILL, post=f"{FRAME}[axis=y]", beam=FRAME, every=3)
    # sandstone base band on the wall foot
    for x in range(X1, X2 + 1):
        for z in (Z1, Z2):
            if "log" not in (b.get(x, 1, z) or ""):
                b.set(x, 1, z, BASE)
    for z in range(Z1, Z2 + 1):
        for x in (X1, X2):
            if "log" not in (b.get(x, 1, z) or ""):
                b.set(x, 1, z, BASE)
    # upper floor + terrace deck
    floor(b, X1, Z1, X2, Z2, FL2, "birch_planks")
    for x in range(X1, X2 + 1):
        b.set(x, FL2, Z1, f"{FRAME}[axis=x]")
        b.set(x, FL2, Z2, f"{FRAME}[axis=x]")
    # upper storey
    clear_inside(b, X1, Z1, UX2, Z2, FL2 + 1, FL2 + 3)
    timber_frame(b, X1, Z1, UX2, Z2, FL2 + 1, FL2 + 3, FILL, post=f"{FRAME}[axis=y]", beam=FRAME, every=3)
    # interior stairs (west wall), cut through the upper floor
    straight_stairs(b, 3, 1, 7, "north", 3, "birch_stairs")
    for z in (5, 6, 7):
        b.set(3, 0, z, "birch_planks")
    # doors and windows
    door(b, 6, 1, Z1, facing="north", wood="birch")
    window(b, 3, 2, Z1, along="x", width=2, height=2)
    window(b, 9, 2, Z1, along="x", width=2, height=2)
    window(b, 4, 2, Z2, along="x", width=2, height=2)
    window(b, 8, 2, Z2, along="x", width=2, height=2)
    window(b, X1, 2, 4, along="z", width=2, height=2)
    window(b, X2, 2, 4, along="z", width=2, height=2)
    window(b, 4, FL2 + 2, Z1, along="x", width=2, height=2)
    window(b, 4, FL2 + 2, Z2, along="x", width=2, height=2)
    window(b, X1, FL2 + 2, 5, along="z", width=2, height=2)
    # door from the upper room to the terrace
    door(b, UX2, FL2 + 1, 6, facing="east", wood="birch")
    for z in (4, 7):
        window(b, UX2, FL2 + 2, z, along="z", width=1, height=1)
    # terracotta band under the roof
    for x in range(X1, UX2 + 1):
        for z in (Z1, Z2):
            if "log" not in (b.get(x, FL2 + 3, z) or ""):
                b.set(x, FL2 + 3, z, "orange_terracotta")
    # low hip roof over the upper storey
    hip_roof(b, X1, Z1, UX2, Z2, FL2 + 4, ROOF, top="brick_slab", overhang=1)
    # terrace parapet, nets, smoking rack
    for x in range(9, X2 + 1):
        b.set(x, FL2 + 1, Z1, BASE)
        b.set(x, FL2 + 1, Z2, BASE)
    for z in range(Z1, Z2 + 1):
        b.set(X2, FL2 + 1, z, BASE)
    for z in (4, 7):
        b.set(10, FL2 + 1, z, "acacia_fence[north=false,south=false,east=false,west=false]")
        b.set(10, FL2 + 2, z, "acacia_fence[north=false,south=false,east=false,west=false]")
    for z in (5, 6):
        b.set(10, FL2 + 2, z, "iron_chain[axis=z]")
        b.set(10, FL2 + 1, z, "dried_kelp_block")
    b.set(9, FL2 + 1, 7, "campfire[lit=true,facing=south]")
    b.set(9, FL2 + 2, 7, "acacia_fence[north=false,south=false,east=false,west=false]")
    b.set(11, FL2 + 2, 6, "lantern[hanging=false]")
    # loggia in front: sandstone floor, acacia columns, slab roof, barrel, lanterns
    floor(b, 2, 1, 11, 2, 0, BASE)
    for x in (2, 5, 8, 11):
        b.fill(x, 1, 1, x, 3, 1, f"{FRAME}[axis=y]")
    for x in range(2, 12):
        b.set(x, 3, 1, f"{FRAME}[axis=x]")
    b.fill(2, FL2, 1, 11, FL2, 2, "cut_sandstone_slab[type=bottom]")
    b.set(3, 1, 2, "barrel[facing=up]")
    b.set(4, 1, 2, "potted_cactus")
    b.set(10, 1, 2, "potted_fern")
    b.set(7, 3, 2, "lantern[hanging=true]")
    b.set(10, 3, 2, "lantern[hanging=true]")
    b.set(4, 3, 2, "lantern[hanging=true]")
    # steps up from the street and the path
    for x in (5, 6, 7, 8):
        b.set(x, 0, 0, "sandstone_stairs[facing=south,half=bottom,shape=straight]")
    for x in range(5, 9):
        b.set(x, -1, 0, "dirt_path")
    # inside, ground floor: barrel by the door, chest, table, lamp
    b.set(4, 1, 4, "barrel[facing=up]")
    b.set(10, 1, 4, "chest[facing=west]")
    b.set(10, 1, 7, "hay_block")
    b.set(8, 1, 6, "birch_fence")
    b.set(8, 2, 6, "birch_pressure_plate")
    b.set(7, 1, 7, "white_wool")
    light(b, 6, 3, 5, "lantern[hanging=true]")
    light(b, 9, 3, 6, "lantern[hanging=true]")
    # upstairs: two beds, chest, light
    for x in (6, 7):
        b.set(x, FL2 + 1, 4, "red_bed[facing=south,part=foot]")
        b.set(x, FL2 + 1, 5, "red_bed[facing=south,part=head]")
    b.set(4, FL2 + 1, 7, "chest[facing=east]")
    light(b, 4, FL2 + 2, 7, "lantern[hanging=false]")
    return b
