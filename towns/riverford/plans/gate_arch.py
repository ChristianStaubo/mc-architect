"""Riverford north gate arch: joins gate_tower_w (x 331..337) and gate_tower_e (x 343..349) over the trade
road (x 339..341). Place: --at 338,-85 --y 63 --no-clear --foundation none --keep-trees.
Local x 0..4 = world 338..342, local z 0..2 = world -85..-83, y 0 = 63 (road surface is y 62).
Two piers (x 0 and 4), a lintel at y 4 whose top is the arch walk (standing y 5, level with both towers'
2nd floors, doorways at world z -84 = local z 1), a stepped soffit, a row of fence gates across the road at
ground level, a lantern in the soffit and copper lanterns on brackets over each tower door."""

from architect.build import Build

FILL, BASE = "mud_bricks", "cut_sandstone"


def build():
    b = Build("gate_arch")
    # piers: three deep, sandstone course then mud brick to y 3
    for x in (0, 4):
        b.fill(x, 0, 0, x, 1, 2, BASE)
        b.fill(x, 2, 0, x, 3, 2, FILL)
    # lintel: the deck at y 4 (the walk is the middle row z 1); orange/white terracotta band on both faces
    b.fill(0, 4, 1, 4, 4, 1, FILL)
    for x in range(5):
        for z in (0, 2):
            b.set(x, 4, z, "orange_terracotta" if x % 2 == 0 else "white_terracotta")
    # stepped soffit: upside-down stairs at the springing (x 1 and 3, y 3)
    for z in range(3):
        b.set(1, 3, z, "mud_brick_stairs[facing=west,half=top,shape=straight]")
        b.set(3, 3, z, "mud_brick_stairs[facing=east,half=top,shape=straight]")
    # rail on both sides of the walk
    for x in range(5):
        for z in (0, 2):
            b.set(x, 5, z, "acacia_fence[east=true,west=true,north=false,south=false]")
    # beam stubs poking out under the deck on both faces
    for x in (0, 2, 4):
        b.set(x, 4, -1, "stripped_acacia_log[axis=z]")
        b.set(x, 4, 3, "stripped_acacia_log[axis=z]")
    # fence gates across the road at ground level (never doors): closed, in the middle row
    for x in (1, 2, 3):
        b.set(x, 0, 1, "acacia_fence_gate[facing=north,open=false,in_wall=false]")
    b.set(2, 3, 1, "lantern[hanging=true]")
    # door steps (sandstone slab) and a copper lantern on a bracket over each tower door (world z -82)
    for x in (0, 4):
        b.set(x, 0, 3, "cut_sandstone_slab[type=bottom]")
        b.set(x, 4, 3, "acacia_fence")
        b.set(x, 3, 3, "waxed_copper_lantern[hanging=true]")
    return b
