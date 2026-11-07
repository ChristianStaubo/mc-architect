"""Long roads between towns: the highway's look (terrain.road with a wider, paved surface) and its
bridges, which a bridge kit (kits/README.md) builds to fit each real crossing.

A crossing is two bank points on one axis (route.py makes them so). The deck runs at least 6 above the
water; where a bank is lower, the bridge grows a ramp onto the land (1 up per block), so the kit always
meets the ground at both ends."""

from . import blocks
from . import bridge as server
from . import parts, terrain
from .build import load
from .kits import walk_y
from .placement import water_depths

HIGHWAY_MIX = [("stone_bricks", 5), ("andesite", 3), ("cracked_stone_bricks", 1), ("polished_andesite", 2),
               ("cobblestone", 1)]
TURNS = {(1, 0): 0, (0, 1): 1, (-1, 0): 2, (0, -1): 3}  # stamp's clockwise quarter turns from local +x
MIN_RISE = 6


def crossing(br):
    """What a kit needs to know about a real crossing: direction, water level, depth, bank heights,
    and so the rise and ramps. br: {"a": [x, z], "b": [x, z], "width": 7}."""
    (ax, az), (bx, bz) = br["a"], br["b"]
    if ax != bx and az != bz:
        raise ValueError(f"bridge {br['id']}: banks {br['a']} and {br['b']} aren't on one axis")
    d = terrain.unit((ax, az), (bx, bz))
    n = abs(bx - ax) + abs(bz - az)
    w = br.get("width", 7)
    cols = server.heightmap((min(ax, bx), min(az, bz)), (max(ax, bx), max(az, bz)))  # the line, bank to bank
    line = [(ax + d[0] * i, az + d[1] * i) for i in range(n + 1)]
    wet = [p for p in line if blocks.is_water(cols[p][1])]
    if not wet:
        raise ValueError(f"bridge {br['id']}: no water between the banks")
    water_y = max(cols[p][0] for p in wet)
    depths = water_depths([(x, z, cols[(x, z)][0]) for x, z in wet])
    ya, yb = cols[tuple(br["a"])][0] + 1, cols[tuple(br["b"])][0] + 1  # walk heights on the banks
    rise = max(ya, yb, water_y + MIN_RISE) - water_y
    ramp_a, ramp_b = rise - (ya - water_y), rise - (yb - water_y)
    start = (ax - d[0] * ramp_a, az - d[1] * ramp_a)
    return {"dir": d, "start": start, "length": n + 1 + ramp_a + ramp_b, "width": w, "water_y": water_y,
            "rise": rise, "depth": max(depths.values()), "ramp_a": ramp_a, "ramp_b": ramp_b}


def bridge_cells(br, kit, seed=1):
    """World cells for the bridge `br` built by `kit`, and the crossing it was fitted to."""
    c = crossing(br)
    b = load(kit, {"length": c["length"], "width": c["width"], "rise": c["rise"], "depth": c["depth"],
                   "ramp_a": c["ramp_a"], "ramp_b": c["ramp_b"], "seed": seed})
    turned = type(b)(b.name)
    parts.stamp(turned, b, 0, 0, 0, TURNS[c["dir"]])
    # local z runs across, centred on the road: shift so the middle of the width is on the line
    mid = c["width"] // 2
    off = {0: (0, -mid), 1: (mid, 0), 2: (0, mid), 3: (-mid, 0)}[TURNS[c["dir"]]]
    sx, sz = c["start"]
    cells = {(sx + x + off[0], c["water_y"] + y, sz + z + off[1]): v for (x, y, z), v in turned.blocks.items()}
    # headroom along the way across: terrain on the ramps must not block it
    for i in range(c["length"]):
        y = walk_y(i, c["length"], c["rise"], c["ramp_a"], c["ramp_b"])
        for k in range(-mid, mid + 1):
            px = sx + c["dir"][0] * i + (k if c["dir"][1] else 0)
            pz = sz + c["dir"][1] * i + (k if c["dir"][0] else 0)
            for h in range(3):
                cells.setdefault((px, c["water_y"] + y + h, pz), "air")
    return cells, c
