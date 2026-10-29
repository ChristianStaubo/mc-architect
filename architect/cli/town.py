"""Towns: the site, the layout check, roads, terraces, briefs, the whole-town sheet."""

import json

from .. import blocks, bridge, edits, journal, render, terrain
from .. import town as towns
from ..placement import original_ground, whole_trees
from .common import out_path, ROOT


def town_terrain(name, refresh=False):
    """The town area's ground before we built anything (cached in local/towns/NAME/terrain.json), so
    checks and maps don't read our own buildings as terrain."""
    p = ROOT / "local" / "towns" / name / "terrain.json"
    if refresh or not p.exists():
        t = towns.town(name)
        (x0, z0), (x1, z1) = t["area"]["min"], t["area"]["max"]
        cols = bridge.heightmap((x0 - 8, z0 - 8), (x1 + 8, z1 + 8))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({f"{x},{z}": [y, b] for (x, z), (y, b) in cols.items()}))
    return {tuple(map(int, k.split(","))): (v[0], v[1]) for k, v in json.loads(p.read_text()).items()}


def cmd_town(a):
    name = a.name
    if a.action == "site":
        cols = town_terrain(name, refresh=a.refresh)
        print(towns.site_report(name, cols))
        t = towns.town(name)
        (x0, z0), (x1, z1) = t["area"]["min"], t["area"]["max"]
        sub = {k: v for k, v in cols.items() if x0 <= k[0] <= x1 and z0 <= k[1] <= z1}
        path = out_path(f"town-{name}-terrain")
        render.top_down(sub, path, scale=5)
        sl = terrain.slope_map(sub)
        shade = {k: (v[0], "grass_block" if sl[k] <= 1 else "gold_block" if sl[k] <= 3 else "red_wool")
                 for k, v in sub.items()}
        for k, v in sub.items():
            if terrain.is_water(v):
                shade[k] = v
        path2 = out_path(f"town-{name}-slopes")
        render.top_down(shade, path2, scale=5)
        print(f"map: {path}\nslopes (green gentle, yellow steep, red cliff, blue water): {path2}")
    elif a.action == "show":
        cols = town_terrain(name)
        issues = towns.check(name, cols)
        path = out_path(f"town-{name}-layout")
        numbering = towns.draw(name, cols, path)
        lay = towns.layout(name)
        print(f"{len(lay.get('roads', []))} roads, {len(lay.get('plots', []))} plots")
        for n, pid in numbering.items():
            p = towns.plot(name, pid)
            print(f"  {n:>2} {pid:<16} {p.get('district', ''):<12} {p.get('type', ''):<18} "
                  f"x {p['min'][0]}..{p['max'][0]} z {p['min'][1]}..{p['max'][1]} floor y {p.get('floor_y')} door {p.get('door')}")
        for i in issues:
            print(f"  {i['level'].upper():<4} {i['what']:<16} {i['msg']}")
        fails = sum(i["level"] == "fail" for i in issues)
        print(f"{fails} fail, {sum(i['level'] == 'warn' for i in issues)} warn. map (north up): {path}")
        return 2 if fails else 0
    elif a.action == "road":
        r = next((r for r in towns.layout(name)["roads"] if r["id"] == a.id), None)
        if not r:
            raise SystemExit(f"no road {a.id}")
        xs = [p[0] for p in r["points"]]
        zs = [p[1] for p in r["points"]]
        cols = original_ground(bridge.heightmap((min(xs) - 6, min(zs) - 6), (max(xs) + 6, max(zs) + 6)),
                               task=f"town:{name}:road:{a.id}")
        cells, prof = terrain.road([tuple(p) for p in r["points"]], cols, width=r.get("width", 3))
        if a.dry_run:
            print(f"road {a.id}: {len(prof)} blocks long, walk y {prof[0][1]}..{prof[-1][1]}, {len(cells)} cells; nothing placed")
            return
        e = edits.place(cells, label=f"road-{a.id}", run=journal.run_id(), task=f"town:{name}:road:{a.id}")
        print(f"placed road {a.id} as {e['id']}: {e['changed']} blocks changed")
    elif a.action == "terrace":
        p = towns.plot(name, a.id)
        (x0, z0), (x1, z1) = p["min"], p["max"]
        cols = original_ground(bridge.heightmap((x0 - 3, z0 - 3), (x1 + 3, z1 + 3)), task=f"town:{name}:{a.id}:terrace")
        cells = terrain.terrace(x0, z0, x1, z1, p["floor_y"], cols, margin=0)
        if a.dry_run:
            print(f"terrace {a.id}: {len(cells)} cells; nothing placed")
            return
        # its own tag: the building's place reads the terraced ground, not the ground before the terrace
        e = edits.place(cells, label=f"terrace-{a.id}", run=journal.run_id(), task=f"town:{name}:{a.id}:terrace")
        print(f"terraced {a.id} as {e['id']}: {e['changed']} blocks changed")
    elif a.action == "brief":
        p = towns.plot(name, a.id)
        t = towns.town(name)
        lay = towns.layout(name)
        print("\n".join([
            f"TOWN {name}, PLOT {p['id']} ({p.get('district')}): {p.get('type')}",
            f"Brief: {p.get('brief', '')}",
            f"Town style: {lay.get('palette', {}).get('notes') or t.get('style')}",
            f"Palette: {json.dumps({k: v for k, v in lay.get('palette', {}).items() if k != 'notes'})}",
            f"Plot: x {p['min'][0]}..{p['max'][0]}, z {p['min'][1]}..{p['max'][1]}; the ground is terraced to floor y {p['floor_y']}.",
            f"Door: on the {p.get('door', 'south')} side, facing the road.",
            f"Place with: ./mc.py place PLAN --plot {name}/{p['id']} (y 0 of your plan = floor y {p['floor_y']}).",
        ]))
    elif a.action == "shots":
        lay = towns.layout(name)
        pts = [tuple(p) for r in lay["roads"] for p in r["points"]] + \
              [tuple(p[k]) for p in lay["plots"] for k in ("min", "max")]
        xs, zs = [p[0] for p in pts], [p[1] for p in pts]
        lo_xz, hi_xz = (min(xs) - 6, min(zs) - 6), (max(xs) + 6, max(zs) + 6)
        floors = [p["floor_y"] for p in lay["plots"]]
        cols = bridge.heightmap(lo_xz, hi_xz)
        cells = bridge.region((lo_xz[0], min(floors) - 10, lo_xz[1]), (hi_xz[0], max(floors) + 30, hi_xz[1]))
        cells = {p: b for p, b in cells.items() if p[1] >= cols[(p[0], p[2])][0] - 3 or p[1] >= min(floors) - 2}
        imgs = [render.iso(cells, tile=a.tile, view=v) for v in ("se", "sw", "nw", "ne")]
        imgs.append(render.top_down(cols, scale=4))
        path = out_path(f"town-{name}-shots")
        render.sheet(imgs, path, columns=2)
        print(f"{path}\nlayout: views from the SE, SW, NW, NE corners (2 per row), then top-down (north up); "
              f"area x {lo_xz[0]}..{hi_xz[0]}, z {lo_xz[1]}..{hi_xz[1]}")
    elif a.action == "tidy":
        # Trees within `reach` of a plot or road go whole (no half-trees, no floating leaves), but the
        # flood never enters a plot (buildings' log frames live there), the road corridor, or water
        # (bridge posts). Every lakeside builder lost views to trees on neighbouring land.
        lay = towns.layout(name)
        reach = 4
        plots = [((p["min"][0], p["min"][1]), (p["max"][0], p["max"][1])) for p in lay["plots"]]
        in_plots = {(x, z) for p0, p1 in plots for x in range(p0[0], p1[0] + 1) for z in range(p0[1], p1[1] + 1)}
        road = set()
        for r in lay["roads"]:
            road |= towns.road_cells({**r, "width": r.get("width", 3) + 2})
        near = set()
        for (p0, p1) in plots:
            near |= {(x, z) for x in range(p0[0] - reach, p1[0] + reach + 1) for z in range(p0[1] - reach, p1[1] + reach + 1)}
        for (x, z) in road:
            near |= {(x + dx, z + dz) for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1)}
        xs, zs = [p[0] for p in near], [p[1] for p in near]
        lo, hi = (min(xs) - 8, min(zs) - 8), (max(xs) + 8, max(zs) + 8)
        cols = bridge.heightmap(lo, hi)
        floors = [p["floor_y"] for p in lay["plots"]]
        world = bridge.region((lo[0], min(floors) - 6, lo[1]), (hi[0], max(floors) + 28, hi[1]))
        ok = lambda p: ((p[0], p[2]) not in in_plots and (p[0], p[2]) not in road and  # noqa: E731
                        not terrain.is_water(cols.get((p[0], p[2]), (0, "air"))))
        seeds = [p for p, b in world.items() if (p[0], p[2]) in near and blocks.is_tree(b) and ok(p)]
        found = whole_trees(world, seeds, ok)
        if a.dry_run:
            print(f"tidy {name}: would remove {len(found)} tree blocks; nothing placed")
            return
        e = edits.place({p: "air" for p in found}, label="tidy-trees", run=journal.run_id(), task=f"town:{name}:tidy")
        print(f"tidied {name} as {e['id']}: {len(found)} tree blocks removed")
    elif a.action == "status":
        live = [e for e in edits.listing() if e.get("task", "").startswith(f"town:{name}")]
        for e in live:
            print(f"{e['id']:>5}  {e['task']:<36} {e['label']:<20} {e['changed']:>6} blocks")
        print(f"{len(live)} live edits in {name}")


def register(sub):
    tw = sub.add_parser("town")
    tw.add_argument("action", choices=["site", "show", "road", "terrace", "brief", "shots", "tidy", "status"])
    tw.add_argument("--tile", type=int, default=5)
    tw.add_argument("name")
    tw.add_argument("id", nargs="?")
    tw.add_argument("--dry-run", action="store_true")
    tw.add_argument("--refresh", action="store_true", help="site: re-read the terrain (before any building!)")
    tw.set_defaults(fn=cmd_town)
