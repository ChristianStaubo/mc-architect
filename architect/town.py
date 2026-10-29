"""Towns: a layout (roads, plots, landmarks) written by the planner, checked against the terrain and
drawn as a map before anything is built.

towns/<name>/town.json    the brief: area, what the town should have, style
towns/<name>/layout.json  the planner's layout:
  {"palette": {...},
   "roads": [{"id": "main", "points": [[x, z], ...], "width": 3}],
   "plots": [{"id": "market", "district": "market", "type": "market square", "min": [x, z], "max": [x, z],
              "floor_y": 66, "door": "south", "brief": "...", "landmark": false}]}
"""

import json
import statistics
from pathlib import Path

from . import render, terrain

ROOT = Path(__file__).resolve().parent.parent
TOWNS = ROOT / "towns"
WATER_TYPES = ("boathouse", "pier", "dock", "harbour", "harbor", "lighthouse", "bridge", "fishing")
DISTRICT_COLORS = [(230, 60, 50), (190, 80, 220), (250, 140, 30), (250, 215, 60), (250, 250, 250),
                   (80, 200, 230), (120, 210, 80), (240, 120, 170), (160, 160, 160)]


def town(name):
    p = TOWNS / name / "town.json"
    if not p.exists():
        raise SystemExit(f"no town {name} (towns/{name}/town.json)")
    return json.loads(p.read_text())


def layout(name):
    p = TOWNS / name / "layout.json"
    if not p.exists():
        raise SystemExit(f"no layout yet for {name}: the planner writes towns/{name}/layout.json")
    return json.loads(p.read_text())


def plot(name, pid):
    for p in layout(name)["plots"]:
        if p["id"] == pid:
            return p
    raise SystemExit(f"no plot {pid} in {name}")


def road_cells(r):
    """The (x, z) cells a road covers (its width), the same way terrain.road lays it."""
    half = r.get("width", 3) // 2
    path = terrain.polyline([tuple(p) for p in r["points"]])
    out = set()
    for k, (x, z) in enumerate(path):
        ux, uz = terrain.across(path, k)
        out |= {(x + ux * w, z + uz * w) for w in range(-half, half + 1)}
    return out


def door_point(p):
    """Where the plot's door side meets the outside: the middle of that side, one block out."""
    (x0, z0), (x1, z1) = p["min"], p["max"]
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    d = p.get("door", "south")
    return {"north": (cx, z0 - 1), "south": (cx, z1 + 1), "west": (x0 - 1, cz), "east": (x1 + 1, cz)}[d]


def check(name, cols):
    """Problems with a layout, as {level, what, msg}: fail = must fix before building, warn = look at it."""
    t, lay = town(name), layout(name)
    (ax0, az0), (ax1, az1) = t["area"]["min"], t["area"]["max"]
    out = []

    def add(level, what, msg):
        out.append({"level": level, "what": what, "msg": msg})

    roads = {r["id"]: road_cells(r) for r in lay.get("roads", [])}
    all_road = set().union(*roads.values()) if roads else set()
    plots = lay.get("plots", [])
    ids = [p["id"] for p in plots]
    for d in {i for i in ids if ids.count(i) > 1}:
        add("fail", d, "duplicate plot id")

    for r in lay.get("roads", []):
        cells = roads[r["id"]]
        if any(not (ax0 <= x <= ax1 and az0 <= z <= az1) for x, z in cells):
            add("fail", r["id"], "road leaves the town area")
        path = terrain.polyline([tuple(p) for p in r["points"]])
        if any(p not in cols for p in path):
            continue
        ys, wet = terrain.road_profile(path, cols, max_step=99)
        steep, run = 0, 0
        for k in range(2, len(path)):
            if not wet[k] and abs(ys[k] - ys[k - 2]) >= 2:  # more than 1 up per 2 along
                run += 1
                steep = max(steep, run)
            else:
                run = 0
        if steep >= 6:
            add("warn", r["id"], f"{steep} blocks in a row steeper than 1 in 2: switchbacks or a stair street?")
        spans = sum(1 for k in range(1, len(wet)) if wet[k] and not wet[k - 1])
        if spans:
            add("info", r["id"], f"crosses water {spans}x: built as a bridge")
    # roads join up
    if len(roads) > 1:
        ids_r = list(roads)
        seen, todo = {ids_r[0]}, [ids_r[0]]
        while todo:
            a = todo.pop()
            for b in ids_r:
                if b not in seen and any((x + dx, z + dz) in roads[b] for x, z in roads[a]
                                         for dx in (-1, 0, 1) for dz in (-1, 0, 1)):
                    seen.add(b)
                    todo.append(b)
        for b in ids_r:
            if b not in seen:
                add("fail", b, "road doesn't connect to the rest of the network")

    for i, p in enumerate(plots):
        (x0, z0), (x1, z1) = p["min"], p["max"]
        if x1 < x0 or z1 < z0:
            add("fail", p["id"], "max must be >= min")
            continue
        if not (ax0 <= x0 and x1 <= ax1 and az0 <= z0 and z1 <= az1):
            add("fail", p["id"], "plot outside the town area")
            continue
        area = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
        for q in plots[i + 1:]:
            (qx0, qz0), (qx1, qz1) = q["min"], q["max"]
            if x0 - 1 <= qx1 and qx0 <= x1 + 1 and z0 - 1 <= qz1 and qz0 <= z1 + 1:
                add("fail", p["id"], f"overlaps or touches plot {q['id']} (leave a 1-block gap)")
        if area & all_road:
            add("fail", p["id"], f"a road runs through it ({len(area & all_road)} blocks)")
        wet = sum(1 for c in area if c in cols and terrain.is_water(cols[c])) / len(area)
        is_water_type = any(k in p.get("type", "") for k in WATER_TYPES)
        if wet > 0.3 and not is_water_type:
            add("fail", p["id"], f"{wet:.0%} water under a {p.get('type')}: move it, or make it a water build")
        if is_water_type and wet == 0:
            add("warn", p["id"], f"a {p.get('type')} with no water in its plot")
        land = [cols[c][0] for c in area if c in cols and not terrain.is_water(cols[c])]
        if land and "floor_y" in p:
            pad = p["floor_y"] - 1
            cut, fill = max(0, max(land) - pad), max(0, pad - min(land))
            if cut > 8 or fill > 8:
                add("warn", p["id"], f"earthworks: cut {cut}, fill {fill} at floor_y {p['floor_y']} "
                                     f"(ground {min(land)}..{max(land)}): split levels or move it")
        elif "floor_y" not in p:
            add("fail", p["id"], "no floor_y")
        dp = door_point(p)
        dist = min((abs(dp[0] - x) + abs(dp[1] - z) for x, z in all_road), default=999)
        if dist > 4 and not p.get("no_road"):
            add("fail", p["id"], f"its {p.get('door', 'south')} door is {dist} blocks from a road (max 4)")
    return out


DIGITS = ["111101101101111", "010110010010111", "111001111100111", "111001111001111", "101101111001001",
          "111100111001111", "111100111101111", "111001001001001", "111101111101111", "111101111001111"]


def _text(px, w, h, x, y, s, rgb, scale=2):
    for i, ch in enumerate(s):
        if not ch.isdigit():
            continue
        g = DIGITS[int(ch)]
        for r in range(5):
            for c in range(3):
                if g[r * 3 + c] == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            X, Y = x + (i * 4 + c) * scale + dx, y + r * scale + dy
                            if 0 <= X < w and 0 <= Y < h:
                                px[(Y * w + X) * 3:(Y * w + X) * 3 + 3] = bytes(rgb)


def draw(name, cols, path, scale=5):
    """The layout on the terrain: roads brown (bridges darker), plots outlined in their district colour
    with their number, door marked. North up. Returns the plot numbering."""
    t, lay = town(name), layout(name)
    (ax0, az0), (ax1, az1) = t["area"]["min"], t["area"]["max"]
    sub = {(x, z): cols[(x, z)] for x in range(ax0, ax1 + 1) for z in range(az0, az1 + 1) if (x, z) in cols}
    w, h, px = render.top_down(sub, scale=scale)

    def put(x, z, rgb, inset=0):
        for dx in range(inset, scale - inset):
            for dz in range(inset, scale - inset):
                X, Y = (x - ax0) * scale + dx, (z - az0) * scale + dz
                if 0 <= X < w and 0 <= Y < h:
                    px[(Y * w + X) * 3:(Y * w + X) * 3 + 3] = bytes(rgb)

    for r in lay.get("roads", []):
        for x, z in road_cells(r):
            wet = (x, z) in cols and terrain.is_water(cols[(x, z)])
            put(x, z, (95, 60, 30) if wet else (150, 105, 60))
    districts = sorted({p.get("district", "") for p in lay.get("plots", [])})
    numbering = {}
    for n, p in enumerate(lay.get("plots", []), 1):
        numbering[n] = p["id"]
        rgb = DISTRICT_COLORS[districts.index(p.get("district", "")) % len(DISTRICT_COLORS)]
        (x0, z0), (x1, z1) = p["min"], p["max"]
        for x in range(x0, x1 + 1):
            put(x, z0, rgb)
            put(x, z1, rgb)
        for z in range(z0, z1 + 1):
            put(x0, z, rgb)
            put(x1, z, rgb)
        dx, dz = door_point(p)
        put(dx, dz, (20, 20, 20), inset=1)
        _text(px, w, h, (x0 + 1) * scale - ax0 * scale + 2, (z0 + 1) * scale - az0 * scale + 2, str(n),
              (20, 20, 20), scale=max(2, scale // 2))
    render.write_png(path, w, h, px)
    return numbering


def site_report(name, cols, step=8):
    """Text the planner reads: the area's height grid (every `step` blocks, ~ = water), the slope classes
    and the water level."""
    t = town(name)
    (ax0, az0), (ax1, az1) = t["area"]["min"], t["area"]["max"]
    area = {k: v for k, v in cols.items() if ax0 <= k[0] <= ax1 and az0 <= k[1] <= az1}
    sl = terrain.slope_map(area)
    n = len(sl)
    classes = {"gentle (0-1)": sum(v <= 1 for v in sl.values()), "steep (2-3)": sum(2 <= v <= 3 for v in sl.values()),
               "cliff (4+)": sum(v >= 4 for v in sl.values())}
    water = [v[0] for v in area.values() if terrain.is_water(v)]
    lines = [f"town {name}: x {ax0}..{ax1}, z {az0}..{az1}",
             f"water level y {statistics.mode(water) if water else '-'}; water {len(water) / n:.0%} of the area",
             "slopes: " + ", ".join(f"{k} {v / n:.0%}" for k, v in classes.items()),
             f"ground y every {step} blocks (rows z north->south, columns x west->east, ~ water, ^ cliff):",
             "       " + "".join(f"{x:>6}" for x in range(ax0, ax1 + 1, step))]
    for z in range(az0, az1 + 1, step):
        row = []
        for x in range(ax0, ax1 + 1, step):
            y, b = cols[(x, z)]
            mark = "~" if terrain.is_water((y, b)) else ("^" if sl.get((x, z), 0) >= 4 else " ")
            row.append(f"{y:>5}{mark}")
        lines.append(f"{z:>6} " + "".join(row))
    return "\n".join(lines)
