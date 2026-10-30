"""Shared by gate_tower_w.py and gate_tower_e.py (Riverford's north gate): one tower, built in the west
tower's orientation (door on the east side) and mirrored for the east tower through a view of the Build.

Plot is 7 x 9 (local x 0..6, z 0..8). Tower 6 x 7: x 1..6, z 2..8, interior x 2..5, z 3..7.
Floors (layer y): 0 ground, 4, 8; roof terrace layer 12, parapet 13, merlons 14. Standing level = layer + 1.
Stairs: flight 1 on x=2 (ground to 2nd floor), flight 2 on x=5 (to 3rd), flight 3 on x=2 (to the roof).
The arch walk (gate_arch.py) joins the 2nd floor through the doorway at (6, 5..6, 4).
"""

import re

from architect.build import Build
from architect.parts import awning, door, floor, hip_roof, light, straight_stairs, walls, window, clear_inside

W = 7
TX1, TX2, TZ1, TZ2 = 1, 6, 2, 8
IX1, IX2, IZ1, IZ2 = 2, 5, 3, 7
F1, F2, F3, ROOF = 0, 4, 8, 12

CORNER = "stripped_acacia_log[axis=y]"
FILL = "mud_bricks"
BASE = "cut_sandstone"
STAIR = "birch_stairs"
FLOORING = "birch_planks"


def _mirror_block(block):
    if "[" not in block:
        return block
    name, rest = block.split("[", 1)
    rest = re.sub(r"\b(east|west)\b", lambda m: "\0" + ("west" if m.group(1) == "east" else "east"), rest)
    rest = rest.replace("\0", "")
    rest = re.sub(r"(?<=[=_])(left|right)\b", lambda m: "\1" + ("right" if m.group(1) == "left" else "left"), rest)
    return name + "[" + rest.replace("\1", "")


class View:
    """A Build seen through an optional east-west mirror, so the parts work unchanged."""

    def __init__(self, b, mirror):
        self.b, self.mirror = b, mirror

    def _x(self, x):
        return W - 1 - x if self.mirror else x

    def set(self, x, y, z, block):
        self.b.set(self._x(x), y, z, _mirror_block(block) if self.mirror else block)

    def get(self, x, y, z):
        return self.b.get(self._x(x), y, z)

    def fill(self, x1, y1, z1, x2, y2, z2, block):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.set(x, y, z, block)

    def sign(self, x, y, z, block, lines, side="front"):
        self.b.sign(self._x(x), y, z, _mirror_block(block) if self.mirror else block, lines, side)


def ring(b, y, block_x, block_z, x1=TX1, x2=TX2, z1=TZ1, z2=TZ2):
    """A beam ring at layer y: logs along x on the north/south walls, along z on the east/west walls."""
    for x in range(x1, x2 + 1):
        b.set(x, y, z1, block_x)
        b.set(x, y, z2, block_x)
    for z in range(z1, z2 + 1):
        b.set(x1, y, z, block_z)
        b.set(x2, y, z, block_z)


def tower(mirror):
    east = mirror
    raw = Build("gate_tower_e" if east else "gate_tower_w")
    b = View(raw, mirror)

    # --- plinth, floors, walls
    floor(b, TX1, TZ1, TX2, TZ2, F1, BASE)
    floor(b, IX1, IZ1, IX2, IZ2, F1, "smooth_sandstone")
    clear_inside(b, IX1, IZ1, IX2, IZ2, 1, ROOF + 3)
    walls(b, TX1, TZ1, TX2, TZ2, 1, ROOF - 1, FILL, corner=CORNER)
    ring(b, 1, BASE, BASE)                       # sandstone base band (the plinth's second course)
    # sandstone plinth is a bit chunkier on the river side: a skirt of stairs would clash; keep it clean
    for f in (F2, F3):
        floor(b, IX1, IZ1, IX2, IZ2, f, FLOORING)
        ring(b, f, "stripped_acacia_log[axis=x]", "stripped_acacia_log[axis=z]")
    # terracotta band under the roof edge, and the cornice
    for i, (x, z) in enumerate([(x, TZ1) for x in range(TX1 + 1, TX2)] + [(TX2, z) for z in range(TZ1, TZ2 + 1)] +
                               [(x, TZ2) for x in range(TX2 - 1, TX1, -1)] + [(TX1, z) for z in range(TZ2, TZ1 - 1, -1)]):
        b.set(x, ROOF - 1, z, "orange_terracotta" if i % 2 == 0 else "white_terracotta")
    ring(b, ROOF, "stripped_acacia_log[axis=x]", "stripped_acacia_log[axis=z]")
    for x in (TX1, TX2):
        for z in (TZ1, TZ2):
            b.set(x, ROOF, z, CORNER)

    # --- acacia floor beams poking out (river side at the 3rd floor, west face at both floors)
    for x in (2, 4, 6):
        b.set(x, F3, 1, "stripped_acacia_log[axis=z]")
    for z in (3, 5, 7):
        for f in (F2, F3):
            b.set(0, f, z, "stripped_acacia_log[axis=x]")

    # --- roof terrace: floor, crenellated parapet
    floor(b, IX1, IZ1, IX2, IZ2, ROOF, "smooth_sandstone")
    perimeter = [(x, TZ1) for x in range(TX1, TX2 + 1)] + [(TX2, z) for z in range(TZ1 + 1, TZ2 + 1)] + \
                [(x, TZ2) for x in range(TX2 - 1, TX1 - 1, -1)] + [(TX1, z) for z in range(TZ2 - 1, TZ1, -1)]
    for i, (x, z) in enumerate(perimeter):
        b.set(x, ROOF + 1, z, FILL)
        if i % 2 == 0:
            b.set(x, ROOF + 2, z, FILL)
    # --- stairs inside (flight 1 and 3 on x=2, flight 2 on x=5), holes cut by the headroom
    straight_stairs(b, 2, F1 + 1, IZ2, "north", 4, STAIR, support=FILL)
    straight_stairs(b, 5, F2 + 1, IZ2, "north", 4, STAIR)
    straight_stairs(b, 2, F3 + 1, IZ2, "north", 4, STAIR, support=FILL)

    # --- door (east, onto the gate passage), doorway to the arch walk
    b.fill(TX2, 1, 6, TX2, 3, 6, FILL)
    door(b, TX2, 1, 6, "east", "birch")
    b.set(TX2, 3, 6, "stripped_acacia_log[axis=x]")
    b.fill(TX2, F2 + 1, 4, TX2, F2 + 2, 4, "air")
    b.set(TX2, F2 + 3, 4, "stripped_acacia_log[axis=x]")

    # --- windows: river side (north) and west/south faces
    window(b, 3, F2 + 2, TZ1, "x", width=2, height=2)
    for x in (2, 5):
        window(b, x, F3 + 2, TZ1, "x", width=1, height=2)
    window(b, 4, F2 + 2, TZ2, "x", width=2, height=2)
    window(b, 4, F3 + 2, TZ2, "x", width=2, height=2)
    window(b, TX1, F2 + 2, 4, "z", width=2, height=2)
    window(b, TX1, F3 + 2, 4, "z", width=2, height=2)
    window(b, TX1, 2, 5, "z", width=1, height=2)        # ground floor slit
    window(b, 4, 2, TZ2, "x", width=1, height=2)
    window(b, TX2, F3 + 2, 4, "z", width=2, height=2)   # looks over the passage
    # window trim: acacia lintels/sills
    for (x, z, along, wd) in ((3, TZ1, "x", 2), (4, TZ2, "x", 2)):
        for i in range(wd):
            xx = x + i
            b.set(xx, F2 + 1, z, "stripped_acacia_log[axis=x]")
            b.set(xx, F2 + 4, z, "stripped_acacia_log[axis=x]")
    for z in (4, 5):
        b.set(TX1, F2 + 1, z, "stripped_acacia_log[axis=z]")
        b.set(TX1, F2 + 4, z, "stripped_acacia_log[axis=z]")

    # --- vines on the west face (they hang from the beams)
    for z in (4, 6):
        for y in range(2, F3):
            if b.get(0, y, z) is None:
                b.set(0, y, z, "vine[east=true]")

    # --- the river face: terrace in the shallows
    floor(b, 2, 0, 6, 1, F1, BASE)
    floor(b, 1, 1, 1, 1, F1, BASE)
    if not east:
        # bench + the orange/white awning over it
        for x in (3, 4, 5):
            b.set(x, 1, 1, "birch_stairs[facing=south,half=bottom,shape=straight]")
        for x in (2, 6):
            b.fill(x, 1, 1, x, 3, 1, "stripped_acacia_log[axis=y]")
            b.fill(x, 1, 0, x, 2, 0, "acacia_fence")
        awning(b, 2, 6, TZ1, 4, "north", ("orange_wool", "white_wool"), depth=2)
    else:
        # the banner side: planters, and Riverford's banner hangs on the river face
        for x in (3, 4, 5):
            b.set(x, 1, 1, "flower_pot")
        for x in (2, 6):
            b.set(x, 1, 1, "potted_azalea_bush")
        b.set(3, 6 + 4, 1, "orange_wall_banner[facing=north]")
        b.set(4, 6 + 4, 1, "orange_wall_banner[facing=north]")
    # --- lanterns inside (hung from the floor above)
    for f in (F1, F2, F3):
        light(b, 4, f + 3, 5, "lantern[hanging=true]")
    light(b, 3, F1 + 3, 3, "lantern[hanging=true]")
    # --- roof terrace dressing: pots, lanterns on the merlons
    for (x, z) in ((3, 3), (5, 3), (5, 7)):
        b.set(x, ROOF + 1, z, "flower_pot")
    for (x, z) in ((TX1, TZ1), (TX2, TZ1), (TX1, TZ2), (TX2, TZ2)):
        b.set(x, ROOF + 3, z, "lantern[hanging=false]")

    # --- furnishing
    if not east:
        # ground: the guard room
        b.set(3, 1, 3, "chest[facing=south]")
        b.set(4, 1, 3, "chest[facing=south]")
        b.set(5, 1, 3, "hay_block[axis=y]")
        b.fill(3, 1, 6, 5, 1, 6, "red_carpet")
        # 2nd floor: the warden's workroom
        b.set(3, F2 + 1, 7, "fletching_table")
        b.set(4, F2 + 1, 7, "chest[facing=north]")
        b.set(3, F2 + 1, 3, "hay_block[axis=y]")
        b.set(4, F2 + 1, 3, "flower_pot")
        # 3rd floor: the warden's bed
        b.set(4, F3 + 1, 5, "red_bed[facing=north,part=head]")
        b.set(4, F3 + 1, 6, "red_bed[facing=north,part=foot]")
        b.set(3, F3 + 1, 7, "chest[facing=north]")
        b.set(3, F3 + 1, 3, "flower_pot")
    else:
        # ground: guard room
        b.set(3, 1, 3, "chest[facing=south]")
        b.set(4, 1, 3, "crafting_table")
        b.set(5, 1, 3, "hay_block[axis=y]")
        b.fill(3, 1, 6, 5, 1, 6, "red_carpet")
        # 2nd floor: guardroom landing at the arch walk, benches
        b.set(3, F2 + 1, 7, "birch_stairs[facing=east,half=bottom,shape=straight]")
        b.set(4, F2 + 1, 7, "chest[facing=north]")
        b.set(3, F2 + 1, 3, "hay_block[axis=y]")
        b.set(4, F2 + 1, 3, "flower_pot")
        # 3rd floor: store
        b.set(4, F3 + 1, 5, "hay_block[axis=y]")
        b.set(4, F3 + 1, 6, "hay_block[axis=y]")
        b.set(3, F3 + 1, 7, "chest[facing=north]")
        b.set(3, F3 + 1, 3, "flower_pot")
        # copper-domed lookout kiosk on the terrace
        for (x, z) in ((3, 5), (5, 5), (3, 7), (5, 7)):
            b.fill(x, ROOF + 1, z, x, ROOF + 3, z, "stripped_acacia_log[axis=y]")
        hip_roof(b, 3, 5, 5, 7, ROOF + 4, "waxed_cut_copper_stairs", top="waxed_copper_block", overhang=1)
        b.fill(3, ROOF + 4, 5, 5, ROOF + 4, 7, "waxed_cut_copper")
        b.set(4, ROOF + 5, 6, "waxed_copper_block")
        b.set(4, ROOF + 7, 6, "lightning_rod[facing=up]")
        light(b, 4, ROOF + 3, 6, "lantern[hanging=true]")
    return raw
