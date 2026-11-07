"""The Kingsway Express: an underground boat line on blue ice from Kingsreach to Riverford, stopping under
each Kingsway waystation. All by code (no agents): it's a line, a cross-section and a station pattern.

  python scripts/express.py plan            # stations, legs, the depth it must run at; writes local/express.json
  python scripts/express.py place [--only leg-1,st-kingsreach]   # place what isn't placed yet (undoable edits)

Cross-section (looking along a leg): shell | 2-wide ice lane | divider | 2-wide ice lane | shell, 2 blocks
of air over the ice, a ceiling with a light every 8 blocks. (A boat is about 1.4 blocks wide: a 1-wide lane
doesn't take one.) Stations: a hall where the lanes run between platforms, a
bubble column up (soul sand) and one down (magma) to a hut on the surface, and a ladder shaft as backup."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from architect import bridge, edits, terrain  # noqa: E402
from architect import town as towns  # noqa: E402
from architect.placement import water_depths  # noqa: E402

PLAN = ROOT / "local" / "express.json"
VERSION = "w2"   # edit tasks are express:<id>:<VERSION>; w2 = 2-wide lanes (w1's 1-wide lanes took no boat)
SHELL, DIVIDER, CEIL = "deepslate_bricks", "deepslate_brick_wall", "deepslate_tiles"
LIGHT = "sea_lantern"
ENDS = {"kingsreach": (-2468, 250), "riverford": (272, -58)}   # near each town's end of the Kingsway


def taken_cells():
    """Every road and plot cell (with a margin) of the towns the stations go beside."""
    out = set()
    for t in ("kingsway", "kingsreach", "riverford"):
        lay = towns.layout(t)
        for r in lay.get("roads", []):
            out |= {(x + dx, z + dz) for x, z in towns.road_cells(r) for dx in (-2, 0, 2) for dz in (-2, 0, 2)}
        for p in lay.get("plots", []):
            (x0, z0), (x1, z1) = p["min"], p["max"]
            out |= {(x, z) for x in range(x0 - 3, x1 + 4) for z in range(z0 - 3, z1 + 4)}
    return out


def find_spot(near, taken, size=9, reach=40):
    """A dry, nearly flat size x size spot free of roads and plots, nearest to `near`: (x, z) of its middle."""
    cx, cz = near
    cols = bridge.heightmap((cx - reach - size, cz - reach - size), (cx + reach + size, cz + reach + size))
    h = size // 2
    best = None
    for dx in range(-reach, reach + 1, 2):
        for dz in range(-reach, reach + 1, 2):
            x, z = cx + dx, cz + dz
            cells = [(x + i, z + j) for i in range(-h, h + 1) for j in range(-h, h + 1)]
            if any(c in taken for c in cells):
                continue
            why, floor = terrain.site_check(cols, cells, 3)
            d = dx * dx + dz * dz
            if not why and (best is None or d < best[0]):
                best = (d, (x, z), floor - 1)
    if not best:
        raise SystemExit(f"no free spot near {near}")
    return best[1], best[2]


def legs(stations):
    """Axis-aligned legs between consecutive stations, one corner each. The line runs straight through
    every station (a leg leaves along the axis the last one arrived on, the same way), so the hall, its
    platforms and shafts sit beside the track, never across it. The first leg's order is the free choice:
    the one with no U-turn at any station wins."""
    def build(x_first0):
        out, arrive, uturns = [], None, 0
        for a, b in zip(stations, stations[1:]):
            (ax, az), (bx, bz) = a["at"], b["at"]
            x_first = x_first0 if arrive is None else arrive[0] == "x"
            corner = (bx, az) if x_first else (ax, bz)
            pts = [(ax, az), corner, (bx, bz)]
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
            d0 = terrain.unit((ax, az), pts[1])
            if arrive and (d0[0] or d0[1]) and d0 != arrive[1]:
                uturns += 1
            d1 = terrain.unit(pts[-2], (bx, bz))
            arrive = ("x" if d1[0] else "z", d1)
            out.append({"id": f"leg-{len(out) + 1}", "from": a["id"], "to": b["id"], "points": [list(p) for p in pts]})
        return uturns, out
    return min((build(True), build(False)), key=lambda r: r[0])[1]


def depth_needed(lgs):
    """The lowest water bed (or ground) the line passes under, sampled every 8 blocks: the tunnel runs
    well below it."""
    low = 10 ** 9
    for leg in lgs:
        for a, b in zip(leg["points"], leg["points"][1:]):
            low = min(low, _lowest(terrain.polyline([tuple(a), tuple(b)])[::8]))
    return low


def _lowest(path):
    """The lowest bed (or ground) under a straight run of sample points, 64 at a time."""
    low = 10 ** 9
    for i in range(0, len(path), 64):
        chunk = path[i:i + 64]
        xs, zs = [p[0] for p in chunk], [p[1] for p in chunk]
        cols = bridge.heightmap((min(xs), min(zs)), (max(xs), max(zs)))
        dep = water_depths([(x, z, cols[(x, z)][0]) for x, z in chunk if terrain.is_water(cols[(x, z)])])
        for x, z in chunk:
            low = min(low, cols[(x, z)][0] - dep.get((x, z), 0))
    return low


def plan():
    taken = taken_cells()
    kw = towns.town("kingsway")
    targets = [("kingsreach", "Kingsreach", ENDS["kingsreach"])] + \
              [(d["id"], d["name"], tuple(d["at"])) for d in kw["districts"] if d.get("plots")] + \
              [("riverford", "Riverford", ENDS["riverford"])]
    stations = []
    for sid, name, near in targets:
        at, g = find_spot(near, taken)
        stations.append({"id": f"st-{sid}", "name": name, "at": list(at), "ground": g})
        print(f"station {name}: {at}, ground y {g}")
    lgs = legs(stations)
    low = depth_needed(lgs)
    y = min(30, low - 8)
    total = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for l in lgs for a, b in zip(l["points"], l["points"][1:]))
    print(f"{len(lgs)} legs, {total} blocks of tunnel; lowest bed or ground passed under: y {low}; ice at y {y}")
    PLAN.write_text(json.dumps({"ice_y": y, "stations": stations, "legs": lgs}, indent=1))


# ---- geometry ----

def band(path, r):
    """Cells within Chebyshev distance r of the path."""
    return {(x + dx, z + dz) for x, z in path for dx in range(-r, r + 1) for dz in range(-r, r + 1)}


LANE = (1, 2)   # a lane's offsets from the centre line (each side): 2 wide
OFFSETS = (*LANE, *(-o for o in LANE))


def lane_paths(pts):
    """The lanes' lines (offsets OFFSETS): the centre polyline moved sideways along the left normal of the
    segments meeting at each point (summed at a corner, so the lines join)."""
    steps = [terrain.unit(a, b) for a, b in zip(pts, pts[1:])]
    normals = []
    for i in range(len(pts)):
        meet = steps[max(i - 1, 0):i + 1]
        normals.append((sum(-dz for dx, dz in meet), sum(dx for dx, dz in meet)))
    return [terrain.polyline([(p[0] + s * n[0], p[1] + s * n[1]) for p, n in zip(pts, normals)]) for s in OFFSETS]


def tunnel_cells(pts, y):
    path = terrain.polyline([tuple(p) for p in pts])
    cells = {}
    for x, z in band(path, 3):      # the shell: floor, walls, ceiling
        cells[(x, y - 1, z)] = SHELL
        for h in range(3):
            cells[(x, y + h, z)] = SHELL
        cells[(x, y + 3, z)] = CEIL
    for x, z in band(path, 2):      # the bore
        for h in range(3):
            cells[(x, y + h, z)] = "air"
    for s, lane in zip(OFFSETS, lane_paths(pts)):
        for k, (x, z) in enumerate(lane):
            cells[(x, y, z)] = "blue_ice"
            if k % 8 == 4 and abs(s) == LANE[0]:  # one light over each lane
                cells[(x, y + 3, z)] = LIGHT
    for x, z in path:               # the divider between the lanes
        for h in range(3):
            cells[(x, y + h, z)] = DIVIDER if h < 2 else SHELL
    return cells


def station_cells(st, y, lgs):
    """The hall (platforms either side of the lanes, a way across the divider), the shafts up to a hut."""
    sx, sz = st["at"]
    g = st["ground"]
    mine = [l for l in lgs if st["id"] in (l["from"], l["to"])]
    # which way the line runs through the station: from its first leg's first step
    l0 = mine[0]
    p0, p1 = (l0["points"][0], l0["points"][1]) if l0["from"] == st["id"] else (l0["points"][-1], l0["points"][-2])
    along = terrain.unit(p0, p1)
    across = (-along[1] * st.get("side", 1), along[0] * st.get("side", 1))  # side: which side the shafts and hut go
    at = lambda a, c: (sx + along[0] * a + across[0] * c, sz + along[1] * a + across[1] * c)  # noqa: E731
    cells = {}
    L, W = 7, 7
    for a in range(-L, L + 1):
        for c in range(-W, W + 1):
            x, z = at(a, c)
            edge = abs(a) == L or abs(c) == W
            cells[(x, y - 1, z)] = "polished_deepslate"
            for h in range(4):
                cells[(x, y + h, z)] = "deepslate_tiles" if edge else "air"
            cells[(x, y + 4, z)] = "deepslate_tiles"
            if abs(a) == L and abs(c) <= 2:  # the track runs on through the hall's end walls
                for h in range(3):
                    cells[(x, y + h, z)] = "air"
                cells[(x, y + 3, z)] = CEIL
            if abs(c) >= 3 and not edge:
                cells[(x, y, z)] = "polished_deepslate" if (a + c) % 2 else "deepslate_tiles"  # platforms
            if abs(c) in (1, 2):
                cells[(x, y, z)] = "blue_ice"
            if c == 0 and abs(a) < L:
                cells[(x, y, z)] = DIVIDER if abs(a) > 1 else "polished_deepslate"  # a gap to cross over
                cells[(x, y + 1, z)] = DIVIDER if abs(a) > 1 else "air"
            if (a % 4 == 0) and edge and abs(c) == W:
                cells[(x, y + 2, z)] = LIGHT
        for c in (-W + 1, W - 1):
            x, z = at(a, c)
            if a % 4 == 0:
                cells[(x, y + 4, z)] = LIGHT
    # boats: a chest on each platform, and signs
    for c in (-W + 1, W - 1):
        x, z = at(-L + 1, c)
        cells[(x, y + 1, z)] = "barrel[facing=up]"
    # the shafts, on the +across platform's far side: up (soul sand), down (magma), ladder
    shafts = {"up": at(2, W + 2), "down": at(-2, W + 2), "ladder": at(0, W + 2)}
    top = g + 1   # walk level on the surface
    for kind, (x, z) in shafts.items():
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for yy in range(y - 1, top + 3):
                    cells.setdefault((x + i, yy, z + j), "glass" if kind != "ladder" else "deepslate_bricks")
        for yy in range(y + 1, top + 1):  # bubble columns as blocks: placing skips the updates that make them
            cells[(x, yy, z)] = {"up": "bubble_column[drag=false]", "down": "bubble_column[drag=true]", "ladder": "air"}[kind]
        cells[(x, y, z)] = {"up": "soul_sand", "down": "magma_block", "ladder": "polished_deepslate"}[kind]
        for yy in (top + 1, top + 2):
            cells[(x, yy, z)] = "air"
    # ladders on the shaft's wall away from the hall
    lx, lz = shafts["ladder"]
    back = terrain.DIRS[(-across[0], -across[1])]   # facing back toward the hall
    for yy in range(y + 1, top + 1):
        cells[(lx + across[0], yy, lz + across[1])] = "deepslate_bricks"
        cells[(lx, yy, lz)] = f"ladder[facing={back}]"
    # a corridor from the platform to the shafts, doors holding the water in
    for a in range(-3, 4):
        for c in (W, W + 1):
            x, z = at(a, c)
            cells[(x, y - 1, z)] = "polished_deepslate"
            cells[(x, y, z)] = "polished_deepslate"
            for h in (1, 2):
                cells[(x, y + h, z)] = "air"
            cells[(x, y + 3, z)] = "deepslate_tiles"
    # each shaft opens toward the hall at the bottom and into the hut at the top: open doors hold the
    # columns' water, the ladder shaft is just open
    for base in (y + 1, top):
        for kind, (x, z) in shafts.items():
            wx, wz = x - across[0], z - across[1]   # the shaft's wall on the hall side
            if kind == "ladder":
                cells[(wx, base, wz)] = cells[(wx, base + 1, wz)] = "air"
            else:
                cells[(wx, base, wz)] = f"spruce_door[facing={back},half=lower,open=true,hinge=left]"
                cells[(wx, base + 1, wz)] = f"spruce_door[facing={back},half=upper,open=true,hinge=left]"
    # the hut on the surface: a 9 x 5 stone room over the three shafts, doors to them, a sign and lamp
    for a in range(-4, 5):
        for c in (W + 1, W + 2, W + 3):
            x, z = at(a, c)
            cells.setdefault((x, top - 1, z), "polished_andesite")
    for a in range(-4, 5):
        for c in range(W - 1, W + 6):
            x, z = at(a, c)
            edge = abs(a) == 4 or c in (W - 1, W + 5)
            cells.setdefault((x, top - 1, z), "stone_bricks" if edge else "polished_andesite")  # a floor under all of it
            for h in range(2, 6):  # a footing down into the ground, around the shafts
                cells.setdefault((x, top - h, z), "stone_bricks")
            if edge:
                for h in range(4):
                    cells[(x, top + h, z)] = "stone_bricks" if h < 3 else "stone_brick_slab[type=bottom]"
            else:
                cells[(x, top + 3, z)] = "stone_brick_slab[type=bottom]"
                for h in range(0, 3):
                    cells.setdefault((x, top + h, z), "air")
    # the hut's door, on the side away from the shafts
    x, z = at(0, W - 1)
    cells[(x, top, z)] = f"oak_door[facing={back},half=lower,hinge=left]"
    cells[(x, top + 1, z)] = f"oak_door[facing={back},half=upper,hinge=left]"
    x, z = at(1, W - 2)
    cells[(x, top, z)] = "lantern[hanging=false]"
    x, z = at(-1, W - 2)
    cells[(x, top, z)] = "lantern[hanging=false]"
    return cells, at, shafts, across


def place(only=None):
    p = json.loads(PLAN.read_text())
    y = p["ice_y"]
    done = {e.get("task") for e in edits.listing()}
    for leg in p["legs"]:
        task = f"express:{leg['id']}:{VERSION}"
        if task in done or (only and leg["id"] not in only):
            continue
        cells = tunnel_cells(leg["points"], y)
        e = edits.place(cells, label=f"express-{leg['id']}", run="express", task=task)
        print(f"{leg['id']} ({leg['from']} -> {leg['to']}): {e['changed']} blocks changed", flush=True)
    for st in p["stations"]:
        task = f"express:{st['id']}:{VERSION}"
        if task in done or (only and st["id"] not in only):
            continue
        cells, at, shafts, across = station_cells(st, y, p["legs"])
        e = edits.place(cells, label=f"express-{st['id']}", run="express", task=task)
        print(f"{st['id']} ({st['name']}): {e['changed']} blocks changed; hut over {shafts['up']}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["plan", "place"])
    ap.add_argument("--only", help="comma-separated leg/station ids")
    a = ap.parse_args()
    plan() if a.action == "plan" else place(a.only.split(",") if a.only else None)
