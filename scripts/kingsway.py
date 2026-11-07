"""Lay out the Kingsway: the highway from Kingsreach to Riverford (route.py over local/survey/kingsway.json),
its bridges, and waystation hamlets along it, as towns/kingsway/{town.json,layout.json}. All by code:
agents write the kits that build it (kits/kingsway_*.py), not the layout.

  python scripts/kingsway.py [--hamlets 4]"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from architect import bridge, route, terrain  # noqa: E402
from architect import town as towns  # noqa: E402

START, GOAL = (-2470, 234), (280, -47)   # Kingsreach's harbour avenue, Riverford's back street
PIECE = 60                               # highway blocks per road piece (one heightmap read each)
WIDTH = 5
# a hamlet: (kind, frontage along the road, depth back from it)
HAMLET = [("inn", 15, 12), ("stable", 12, 9), ("smithy", 11, 9), ("watchtower", 7, 7), ("house", 10, 9),
          ("house", 9, 10), ("house", 11, 9), ("shrine", 7, 7), ("house", 10, 10)]
NAMES = ["Harrowford Stage", "Saltmere Crossing", "Greywater Rest", "Highfold Stage", "Thornbury Rest"]


def pieces(path_pts, start_id):
    """Road pieces of about PIECE blocks along a run of waypoints (no water crossing inside)."""
    out, cur, n = [], [path_pts[0]], 0
    for a, b in zip(path_pts, path_pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        while n + seg > PIECE:  # cut this leg where the piece is full
            t = (PIECE - n) / seg
            cut = (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t))
            cur.append(cut)
            out.append(cur)
            cur, a, n = [cut], cut, 0
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
        cur.append(b)
        n += seg
    if len(cur) > 1:
        out.append(cur)
    return [{"id": f"hw-{start_id + i:03d}", "points": [list(p) for p in pc], "width": WIDTH, "style": "highway"}
            for i, pc in enumerate(pc for pc in out if pc[0] != pc[-1])]


def hamlet(name, hid, path, k, taken):
    """Plots on both sides of the highway around path[k], doors to the road."""
    cx, cz = path[k]
    cols = bridge.heightmap((cx - 60, cz - 60), (cx + 60, cz + 60))
    plots = []
    slots = [(o, s) for o in (0, -14, 14, -28, 28, -42, 42) for s in (1, -1)]
    kinds = list(HAMLET)
    for o, side in slots:
        if not kinds or not (0 <= k + o < len(path)):
            continue
        for kind, front, depth in kinds:
            p = _fit(path, k + o, side, kind, front, depth, cols, taken)
            if p:
                break
        else:
            continue
        kinds.remove((kind, front, depth))
        p.update({"id": f"{hid}_{kind}_{len(plots) + 1}", "district": hid,
                  "brief": f"{kind} at {name}, a waystation on the Kingsway"})
        plots.append(p)
    return plots


WHY = {}


def _fit(path, i, side, kind, front, depth, cols, taken):
    """A plot for `kind` beside the road at path[i] on `side`, stepped back from the road until it's
    clear of it (diagonal stretches), or None (and why, counted in WHY)."""
    px, pz = path[i]
    ux, _ = terrain.across(path, i)
    why = "road or plot"
    for back in range(0, 13, 2):
        near = WIDTH // 2 + 3 + back
        if ux:  # the road runs north-south here: plots east/west of it
            x0 = px + near if side > 0 else px - near - depth + 1
            (x0, z0), (x1, z1) = (x0, pz - front // 2), (x0 + depth - 1, pz - front // 2 + front - 1)
            door = "west" if side > 0 else "east"
        else:
            z0 = pz + near if side > 0 else pz - near - depth + 1
            (x0, z0), (x1, z1) = (px - front // 2, z0), (px - front // 2 + front - 1, z0 + depth - 1)
            door = "north" if side > 0 else "south"
        ring = {(x, z) for x in range(x0 - 2, x1 + 3) for z in range(z0 - 2, z1 + 3)}
        if ring & taken:
            continue
        cells = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
        why, floor = terrain.site_check(cols, cells, 8)
        if why:
            break
        taken |= set(cells)
        return {"type": kind, "kind": kind, "kit": "waystation", "min": [x0, z0], "max": [x1, z1],
                "floor_y": floor, "door": door, "landmark": kind == "inn"}
    WHY[why] = WHY.get(why, 0) + 1
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hamlets", type=int, default=4)
    a = ap.parse_args()
    s = route.survey("kingsway")
    pts, crossings = route.waypoints(s, route.plan(s, START, GOAL))
    roads, bridges, run = [], [], [pts[0]]
    banks = {tuple(c[0]): c for c in crossings}
    for p in pts[1:]:
        run.append(p)
        if tuple(p) in banks:  # a crossing starts here: close the run, add the bridge, the next run starts across
            c = banks[tuple(p)]
            roads += pieces(run, len(roads) + 1)
            bridges.append({"id": f"br-{len(bridges) + 1}", "a": list(c[0]), "b": list(c[1]), "width": WIDTH + 2,
                            "seed": len(bridges) + 1})
            run = []
    roads += pieces(run, len(roads) + 1)
    path = terrain.polyline([tuple(q) for r in roads for q in r["points"]])
    taken = set()
    for r in roads:
        taken |= towns.road_cells(r)
    plots, districts = [], []
    for i in range(a.hamlets):
        k = int(len(path) * (i + 1) / (a.hamlets + 1))
        for shift in (0, 40, -40, 80, -80, 120, -120):  # nudge along the road to firmer, drier ground
            trial = set(taken)  # a nudge that's given up mustn't leave its plots reserved
            got = hamlet(NAMES[i], f"h{i + 1}", path, k + shift, trial) if 0 <= k + shift < len(path) else []
            if len(got) >= 6:
                break
        taken |= {(x, z) for q in got for x in range(q["min"][0], q["max"][0] + 1) for z in range(q["min"][1], q["max"][1] + 1)}
        plots += got
        districts.append({"id": f"h{i + 1}", "name": NAMES[i], "at": list(path[k + shift]), "plots": len(got)})
        print(f"{NAMES[i]}: {len(got)} plots at {path[k + shift]}")
    d = ROOT / "towns" / "kingsway"
    d.mkdir(exist_ok=True)
    (d / "town.json").write_text(json.dumps({
        "name": "kingsway", "area": {"min": [s["x0"], s["z0"]], "max": [s["x0"] + (s["w"] - 1) * s["step"],
                                                                       s["z0"] + (s["h"] - 1) * s["step"]]},
        "brief": "The Kingsway: a paved royal highway from Kingsreach's harbour avenue to Riverford, about 3 km, "
                 "with stone bridges over the inlet and the river, and waystation hamlets a day's ride apart: an "
                 "inn, stables, a smithy, a watchtower, a roadside shrine and a few houses for the people who "
                 "keep the road.",
        "style": "royal road style shared by every waystation: grey stone brick and cobblestone bases, spruce and "
                 "dark oak timber frames, whitewashed (white terracotta or calcite) upper walls, steep dark roofs "
                 "(deepslate tiles or dark oak), lanterns on posts, banners in the crown's blue and gold, hay, "
                 "carts and barrels about the yards",
        "kits": {"bridge": "kits/kingsway_bridge.py", "waystation": "kits/kingsway_waystation.py"},
        "districts": districts}, indent=1))
    (d / "layout.json").write_text(json.dumps({"roads": roads, "bridges": bridges, "plots": plots}, indent=1))
    L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for r in roads for a, b in zip(r["points"], r["points"][1:]))
    print("plots refused:", WHY)
    print(f"{len(roads)} road pieces ({L:.0f} blocks), {len(bridges)} bridges, {len(plots)} plots")


if __name__ == "__main__":
    main()
