"""Shaping the land in world coordinates: roads that follow it, terraces that seat a building on a slope,
bridges where a road meets water. Every function takes the ground as {(x, z): (top_y, top_block)}
(bridge.heightmap) and returns world cells {(x, y, z): block} for edits.place, so it can be undone."""

import random

from . import blocks

ROAD_MIX = [("dirt_path", 6), ("gravel", 2), ("coarse_dirt", 1), ("cobblestone", 1)]


def is_water(top):
    """A heightmap column (top_y, top_block) whose top is water."""
    return blocks.is_water(top[1])


def _pick(rng, mix):
    total = sum(w for _, w in mix)
    r = rng.uniform(0, total)
    for b, w in mix:
        r -= w
        if r <= 0:
            return b
    return mix[-1][0]


def polyline(points):
    """Every block along a list of (x, z) points, in order, one block per step (no diagonal jumps)."""
    out = []
    for (ax, az), (bx, bz) in zip(points, points[1:]):
        n = max(abs(bx - ax), abs(bz - az))
        for i in range(n):
            x, z = round(ax + (bx - ax) * i / n), round(az + (bz - az) * i / n)
            if out and abs(out[-1][0] - x) + abs(out[-1][1] - z) == 2:  # fill the corner of a diagonal step
                out.append((x, out[-1][1]))
            if not out or out[-1] != (x, z):
                out.append((x, z))
    out.append(tuple(points[-1]))
    return out


def road_profile(path, cols, max_step=1):
    """A height for every point on the path: the ground smoothed, then limited to `max_step` per block
    (forward and backward passes). Over water the road keeps a deck height (a bridge)."""
    raw = []
    for p in path:
        y, b = cols[p]
        raw.append(None if is_water((y, b)) else y + 1)  # walk height: standing on the ground block
    # bridge decks: the higher bank + 1, at least 3 above the water
    ys = list(raw)
    i = 0
    while i < len(ys):
        if ys[i] is None:
            j = i
            while j < len(ys) and ys[j] is None:
                j += 1
            banks = [v for v in (ys[i - 1] if i else None, ys[j] if j < len(ys) else None) if v is not None]
            wl = cols[path[i]][0]  # the water's surface block
            deck = max(max(banks) if banks else wl + 1, wl + 3)  # walk height on the deck
            for k in range(i, j):
                ys[k] = deck
            i = j
        else:
            i += 1
    # smooth (moving average over 5), then clamp the grade both ways
    sm = []
    for k in range(len(ys)):
        win = ys[max(0, k - 2):k + 3]
        sm.append(round(sum(win) / len(win)))
    for k in range(1, len(sm)):
        sm[k] = max(sm[k - 1] - max_step, min(sm[k - 1] + max_step, sm[k]))
    for k in range(len(sm) - 2, -1, -1):
        sm[k] = max(sm[k + 1] - max_step, min(sm[k + 1] + max_step, sm[k]))
    return sm, [r is None for r in raw]


DIRS = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}


def across(path, k):
    """The unit step across a path at point k (its width runs this way)."""
    px, pz = path[max(k - 1, 0)]
    nx, nz = path[min(k + 1, len(path) - 1)]
    return (1, 0) if abs(nz - pz) >= abs(nx - px) else (0, 1)


def road(points, cols, width=3, seed=1, surface=ROAD_MIX, lamp_every=14, bridge_wood="spruce",
         support="stone_bricks", step="stone_brick_stairs"):
    """A road along `points` (x, z) on the ground. The surface follows the land at a walkable grade, a
    stair on the higher block wherever it rises one (tall side uphill), 3 blocks cleared above, an
    embankment of `support` where it runs above the ground, and a bridge (plank deck, fence rails, log
    posts down to the bed, lanterns) over water. Lamp posts every `lamp_every` blocks, alternating sides.
    Returns (world cells, [((x, z), walk_y), ...])."""
    rng = random.Random(seed)
    path = polyline(points)
    ys, wet = road_profile(path, cols)
    half = width // 2
    cells = {}

    lamp_side = 1
    for k, ((x, z), y) in enumerate(zip(path, ys)):
        ux, uz = across(path, k)
        for w in range(-half, half + 1):
            cx, cz = x + ux * w, z + uz * w
            g = cols.get((cx, cz), (y - 1, "stone"))[0]
            if wet[k]:
                cells[(cx, y - 1, cz)] = f"{bridge_wood}_planks"
            else:
                cells[(cx, y - 1, cz)] = _pick(rng, surface)
                for yy in range(g + 1, y - 1):  # embankment where the road runs above the ground
                    cells[(cx, yy, cz)] = support
            for h in range(3):  # headroom
                cells[(cx, y + h, cz)] = "air"
        if wet[k]:
            for side in (-half - 1, half + 1):
                rx, rz = x + ux * side, z + uz * side
                cells[(rx, y - 1, rz)] = f"{bridge_wood}_planks"
                cells[(rx, y, rz)] = f"{bridge_wood}_fence"
                if k % 4 == 0:  # posts down into the bed
                    bed = cols.get((rx, rz), (y - 6, ""))[0]
                    for yy in range(bed - 3, y - 1):
                        cells[(rx, yy, rz)] = f"{bridge_wood}_log[axis=y]"
                    if k % 8 == 0:
                        cells[(rx, y + 1, rz)] = "lantern[hanging=false]"
        elif lamp_every and k % lamp_every == lamp_every // 2:
            lx, lz = x + ux * (half + 1) * lamp_side, z + uz * (half + 1) * lamp_side
            g = cols.get((lx, lz), (y - 1, ""))[0]
            if abs(g + 1 - y) <= 1 and (lx, g + 1, lz) not in cells:
                cells[(lx, g + 1, lz)] = f"{bridge_wood}_fence"
                cells[(lx, g + 2, lz)] = f"{bridge_wood}_fence"
                cells[(lx, g + 3, lz)] = "lantern[hanging=false]"
                lamp_side = -lamp_side
    # steps: where the walk height changes by one between neighbours, the higher block's surface becomes
    # a stair facing uphill (its tall side away from the lower block)
    for k in range(1, len(path)):
        if wet[k] or wet[k - 1] or ys[k] == ys[k - 1]:
            continue
        hi, lo = (k, k - 1) if ys[k] > ys[k - 1] else (k - 1, k)
        d = (path[hi][0] - path[lo][0], path[hi][1] - path[lo][1])
        if d not in DIRS:
            continue
        ux, uz = across(path, hi)
        for w in range(-half, half + 1):
            cx, cz = path[hi][0] + ux * w, path[hi][1] + uz * w
            cells[(cx, ys[hi] - 1, cz)] = f"{step}[facing={DIRS[d]},half=bottom,shape=straight]"
            if cells.get((cx, ys[hi] - 2, cz), "air") == "air":
                cells[(cx, ys[hi] - 2, cz)] = support
    return cells, list(zip(path, ys))


def terrace(x1, z1, x2, z2, floor_y, cols, top="grass_block", fill="dirt", wall="stone_bricks",
            cap="stone_brick_slab[type=bottom]", margin=1):
    """Seat a level pad (x1..x2, z1..z2, plus `margin`) at floor_y - 1 so a plan's y 0 sits on it.
    Higher ground is cut away (and a retaining wall faces the cut where it's 2+ blocks high); lower
    ground is filled, with a retaining wall on the pad's edge where the drop is 2+ blocks, capped with
    a slab lip. Water is left as it is. Returns world cells."""
    cells = {}
    lo_x, hi_x, lo_z, hi_z = x1 - margin, x2 + margin, z1 - margin, z2 + margin
    pad_y = floor_y - 1
    for x in range(lo_x, hi_x + 1):
        for z in range(lo_z, hi_z + 1):
            g = cols.get((x, z))
            if not g or is_water(g):  # water stays water (a boathouse stands over it on posts)
                continue
            gy = g[0]
            edge = x in (lo_x, hi_x) or z in (lo_z, hi_z)
            if gy > pad_y:  # cut
                for y in range(pad_y + 1, gy + 1):
                    cells[(x, y, z)] = "air"
                cells[(x, pad_y, z)] = top
            else:  # fill
                for y in range(gy + 1, pad_y):
                    cells[(x, y, z)] = wall if edge and pad_y - gy >= 2 else fill
                cells[(x, pad_y, z)] = top
                if edge and pad_y - gy >= 2:
                    cells[(x, pad_y, z)] = wall
                    cells[(x, pad_y + 1, z)] = cap
    # retaining walls against the cut: the first ring outside the pad, where it stands 2+ above the pad
    for x in range(lo_x - 1, hi_x + 2):
        for z in range(lo_z - 1, hi_z + 2):
            if lo_x <= x <= hi_x and lo_z <= z <= hi_z:
                continue
            g = cols.get((x, z))
            if g and g[0] - pad_y >= 2:
                for y in range(pad_y + 1, g[0] + 1):
                    cells[(x, y, z)] = wall
    return cells


def slope_map(cols):
    """{(x, z): steepness} = the biggest height difference to a neighbour: 0-1 gentle, 2-3 steep, 4+ cliff."""
    out = {}
    for (x, z), (y, _) in cols.items():
        d = 0
        for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if (nx, nz) in cols:
                d = max(d, abs(cols[(nx, nz)][0] - y))
        out[(x, z)] = d
    return out
