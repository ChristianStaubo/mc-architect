"""Riverford's town wall, built along the planner's line (layout.json "wall") and following the ground
column by column: a cut-sandstone footing, mud-brick courses and sandstone-slab coping (3 high, too high
for villagers to leave), a pillar with a copper lantern every 8 blocks, a low quay parapet along the river
bank, fence gates closing the gaps between the riverfront buildings, and a small south gate.

World coordinates (local = world): place with
./mc.py place towns/riverford/plans/wall.py --at 0,0 --y 0 --no-clear --foundation none
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from architect import blocks, bridge, terrain  # noqa: E402
from architect.build import Build  # noqa: E402

PLACE = ["--at", "0,0", "--y", "0", "--no-clear", "--foundation", "none"]
LAYOUT = json.loads((ROOT / "towns" / "riverford" / "layout.json").read_text())
SOUTH_GATE = range(339, 342)          # three fence gates on the z -46 run, in line with the trade road
RIVER_GAPS = [(range(327, 331), -88), (range(350, 351), -88), (range(361, 362), -88), (range(377, 378), -87)]


def ground(points):
    """{(x, z): (top solid y, is water, river bed y)} along the points."""
    xs, zs = [p[0] for p in points], [p[1] for p in points]
    lo, hi = (min(xs), min(zs)), (max(xs), max(zs))
    hm = bridge.heightmap(lo, hi)
    out = {}
    for (x, z) in points:
        y, top = hm[(x, z)]
        bed = y
        if blocks.is_water(top):
            col = bridge.region((x, y - 12, z), (x, y, z))
            bed = max((yy for (_, yy, _), b in col.items() if not blocks.is_water(b) and not blocks.is_air(b)), default=y - 12)
        out[(x, z)] = (y, blocks.is_water(top), bed)
    return out


def wall(b, points, height=3, pillars=8, gate=None):
    g = ground(points)
    for i, (x, z) in enumerate(points):
        y, wet, bed = g[(x, z)]
        for yy in range(bed + 1, y + 1):            # under water: footing up from the river bed
            b.set(x, yy, z, "cut_sandstone")
        if gate and gate(x, z):
            b.set(x, y + 1, z, "acacia_fence_gate[facing=south]")
            b.fill(x, y + 2, z, x, y + 3, z, "air")
            b.set(x, y + 4, z, "mud_brick_slab[type=top]")  # the lintel over the gateway
            continue
        b.set(x, y + 1, z, "cut_sandstone")
        b.fill(x, y + 2, z, x, y + height, z, "mud_bricks")
        if i % pillars == 0:
            b.set(x, y + height + 1, z, "chiseled_sandstone")
            b.set(x, y + height + 2, z, "copper_lantern")
        else:
            b.set(x, y + height + 1, z, "sandstone_slab[type=bottom]")


def parapet(b, points):
    """The quay side: low enough to look over, too high for a villager to step."""
    g = ground(points)
    for (x, z) in points:
        y, wet, bed = g[(x, z)]
        for yy in range(bed + 1, y + 1):
            b.set(x, yy, z, "cut_sandstone")
        b.set(x, y + 1, z, "cut_sandstone")
        b.set(x, y + 2, z, "mud_brick_wall")


def build():
    b = Build("riverford_wall")
    w = LAYOUT["wall"]
    wall(b, terrain.polyline(w["points"]), gate=lambda x, z: z == -46 and x in SOUTH_GATE)
    parapet(b, terrain.polyline(w["river_side"]))
    gaps = [(x, z) for xs, z in RIVER_GAPS for x in xs]
    g = ground(gaps)
    for (x, z) in gaps:  # between the riverfront buildings: fence gates down to the water stairs
        y = g[(x, z)][0]
        b.set(x, y + 1, z, "acacia_fence_gate[facing=north]")
    return b
