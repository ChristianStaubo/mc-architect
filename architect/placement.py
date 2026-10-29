"""Putting a plan on the land: block checks before placing, ground heights (as they were before our own
edits), foundations and clearing, whole-tree removal, and what to say when a build doesn't fit its plot.
The CLI (mc.py) only parses arguments and prints; this is the logic it calls."""

import difflib
import json
import statistics
from collections import Counter
from pathlib import Path

from . import audit, blocks, bridge, edits, render

ROOT = Path(__file__).resolve().parent.parent
BLOCKS = ROOT / "local" / "blocks.json"


def bounds(cells):
    """((min x, y, z), (max x, y, z)) of a cells dict (or any iterable of points)."""
    xs, ys, zs = zip(*cells)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def check_blocks(cells):
    """Refuse before placing (or previewing) if any block-data string won't parse on this server, with
    the closest real names. r2: 'chain' (it's iron_chain) and 'dark_oak_log[axis=x][axis=z]' only
    failed at place time."""
    names = sorted({b for b in cells.values() if not blocks.is_air(b)})
    bad = bridge.call("/validate", {"blocks": names})["invalid"]
    if not bad:
        return
    if not BLOCKS.exists():
        BLOCKS.parent.mkdir(parents=True, exist_ok=True)
        BLOCKS.write_text(json.dumps(bridge.call("/blocks")["blocks"]))
    known = json.loads(BLOCKS.read_text())
    lines = []
    for x in bad:
        base = blocks.name(x["block"])
        hint = ""
        if base not in known:
            close = difflib.get_close_matches(base, known, n=3, cutoff=0.6) or [k for k in known if base in k][:3]
            hint = f" (did you mean {', '.join(close)}?)" if close else ""
        lines.append(f"  {x['block']}: {x['error']}{hint}")
    raise SystemExit("refused: blocks this server can't place:\n" + "\n".join(lines))


def surface(cells):
    """{(x, z): (top_y, top_block)} of the highest block in each column that isn't air, a plant or a tree:
    the ground the way the server's heightmap sees it."""
    tops = {}
    for (x, y, z), b in cells.items():
        if not render.skipped(b) and not blocks.is_tree(b) and y > tops.get((x, z), (-10 ** 9,))[0]:
            tops[(x, z)] = (y, b)
    return tops


def original_ground(cols, task="", run=""):
    """Ground heights as they were before this task's (or run's) own live edits: re-previewing a plan
    over its own earlier build must not read that build as terrain (r2 tavern: y 122)."""
    for e in edits.listing():
        if not ((task and e.get("task") == task) or (run and e.get("run") == run)):
            continue
        tops = surface(edits.snapshot(e))
        for xz in cols:
            if xz in tops and e["min"][1] <= cols[xz][0] <= e["max"][1]:
                cols[xz] = tops[xz]
    return cols


def ground_cells(build, at, foundation="cobblestone", floor_y=None, clear=True, task="", run=""):
    """World cells for a build whose local (0, 0, 0) corner goes at X,Z on the ground: local y 0 sits one
    above the median ground height (or at floor_y); columns below the footprint are filled down to the
    terrain with `foundation` ("none": leave them, e.g. posts over water), and terrain inside the build's
    box (a hill) is cleared to air unless clear is False."""
    (lx0, ly0, lz0), (lx1, ly1, lz1) = build.bounds()
    x, z = at
    cols = original_ground(bridge.heightmap((x + lx0, z + lz0), (x + lx1, z + lz1)), task, run)
    foot = build.footprint()
    heights = [cols[(x + fx, z + fz)][0] for fx, fz in foot]
    y0 = floor_y if floor_y is not None else int(statistics.median(heights)) + 1
    lowest = {}
    for (bx, by, bz) in build.blocks:
        lowest[(bx, bz)] = min(by, lowest.get((bx, bz), by))
    cells = {}
    for (fx, fz) in foot:
        g = cols[(x + fx, z + fz)][0]
        if foundation != "none":
            for y in range(g + 1, y0 + ly0):  # foundation down to the ground
                cells[(x + fx, y, z + fz)] = foundation
        if clear:  # clear the hill inside the footprint, from the ground floor up (never below it:
            # posts and basements change only where the plan says; r1's boathouse got a flooded-out
            # air pocket under its floor when clearing started at its lowest post)
            # from the column's lowest planned block: under a windmill's sails, an eave or a bridge
            # deck the ground stays (windmill reference: holes in the grass under the sails)
            for y in range(y0 + max(lowest.get((fx, fz), ly0), 0), max(g, y0 + ly1) + 1):
                cells[(x + fx, y, z + fz)] = "air"
    for (bx, by, bz), blk in build.blocks.items():
        cells[(x + bx, y0 + by, z + bz)] = blk
    return cells, y0


def whole_trees(world, seeds, allowed=lambda p: True):
    """Every tree block (log, leaf, vine...) connected to the seeds, plus the snow lying on them, where
    `allowed`. r2: clearing only the blocks touching a build left snow-capped leaves floating."""
    tree = audit.flood(world, seeds, blocks.is_tree)
    tree |= {(x, y + 1, z) for (x, y, z) in tree if blocks.name(world.get((x, y + 1, z), "air")) == "snow"}
    return {p for p in tree if allowed(p)}


def clear_trees(cells, inside=None, margin=2, reach=7):
    """Trees that touch the build (its box plus `margin`) go whole, up to `reach` blocks beyond, but
    only `inside` the plot when one is given ((min x, z), (max x, z))."""
    (x0, y0, z0), (x1, y1, z1) = bounds(cells)
    lo, hi = (x0 - margin, y0, z0 - margin), (x1 + margin, y1 + 8, z1 + margin)
    world = bridge.region((lo[0] - reach, lo[1], lo[2] - reach), (hi[0] + reach, hi[1] + reach, hi[2] + reach))
    near = lambda p: all(lo[i] <= p[i] <= hi[i] for i in range(3))  # noqa: E731
    seeds = [p for p, b in world.items() if p not in cells and blocks.is_tree(b) and near(p)]
    ok = lambda p: p not in cells and (not inside or (inside[0][0] <= p[0] <= inside[1][0] and  # noqa: E731
                                                       inside[0][1] <= p[2] <= inside[1][1]))
    out = dict(cells)
    out.update({p: "air" for p in whole_trees(world, seeds, ok)})
    return out


def overflow(build, at, plot):
    """Say exactly what sticks out of the plot ((min x, z), (max x, z)): which sides, by how much, and
    which blocks (in local coordinates, so the plan can be fixed). The inn's builder had to guess."""
    (px0, pz0), (px1, pz1) = plot
    out = {}
    for (x, y, z), b in build.blocks.items():
        wx, wz = at[0] + x, at[1] + z
        for side, bad in (("west", wx < px0), ("east", wx > px1), ("north", wz < pz0), ("south", wz > pz1)):
            if bad:
                out.setdefault(side, []).append(((x, y, z), blocks.name(b)))
    (lx0, _, lz0), (lx1, _, lz1) = build.bounds()
    lines = [f"refused: the build doesn't fit the plot (x {px0}..{px1}, z {pz0}..{pz1}); placed at --at {at[0]},{at[1]} "
             f"it covers x {at[0] + lx0}..{at[0] + lx1}, z {at[1] + lz0}..{at[1] + lz1}."]
    for side, cells in out.items():
        far = {"west": px0 - min(at[0] + c[0] for c, _ in cells), "east": max(at[0] + c[0] for c, _ in cells) - px1,
               "north": pz0 - min(at[1] + c[2] for c, _ in cells), "south": max(at[1] + c[2] for c, _ in cells) - pz1}[side]
        kinds = Counter(n for _, n in cells).most_common(4)
        lines.append(f"  {side}: {far} block(s) too far, {len(cells)} blocks: "
                     + ", ".join(f"{k} {v}" for k, v in kinds) + f" (local e.g. {sorted(c for c, _ in cells)[:3]})")
    lines.append("  fix: trim those (often a roof overhang: gable_roof end_overhang=0, or overhang=0), or move with --at")
    return "\n".join(lines)


def water_depths(points):
    """{(x, z): blocks of water below the surface} for [(x, z, surface_y), ...], in one region read
    (one request per column was ~80 round trips for a watery site)."""
    if not points:
        return {}
    xs, zs, ys = [p[0] for p in points], [p[1] for p in points], [p[2] for p in points]
    col = bridge.region((min(xs), min(ys) - 30, min(zs)), (max(xs), max(ys), max(zs)))
    out = {}
    for x, z, top in points:
        d = 0
        while d <= 30 and blocks.is_water(col.get((x, top - d, z), "air")):
            d += 1
        out[(x, z)] = d
    return out
