"""Building: read a site, place a plan, undo, list edits, the approval blueprint."""

import statistics
import sys
import time
from collections import Counter

from .. import blocks, bridge, edits, evals, journal, render, terrain
from .. import audit as auditing
from .. import town as towns
from ..build import centre
from ..placement import bounds, check_blocks, clear_trees, ground_cells, overflow, water_depths
from .common import out_path, ints, player_pos, load_plan


def cmd_site(a):
    if a.task or a.plot:  # the task's or town plot's area exactly, plus a 4-block margin around it
        if a.plot:
            pl = towns.plot(*a.plot.split("/"))
            (px0, pz0), (px1, pz1) = pl["min"], pl["max"]
        else:
            t = evals.task(a.task)
            (px0, pz0), (px1, pz1) = t["plot"]["min"], t["plot"]["max"]
        lo, hi = (px0 - 4, pz0 - 4), (px1 + 4, pz1 + 4)
    elif a.center:
        x, z = ints(a.center)
        w, d = ints(a.size) if a.size else (48, 48)
        lo, hi = (x - w // 2, z - d // 2), (x + w // 2, z + d // 2)
    else:
        raise SystemExit("give X,Z [W,D] or --task T")
    cols = bridge.heightmap(lo, hi)
    ys = [v[0] for v in cols.values()]
    tops = Counter(blocks.name(b) for _, b in cols.values())
    w, d = hi[0] - lo[0] + 1, hi[1] - lo[1] + 1
    path = out_path(f"site-{lo[0]}_{lo[1]}")
    render.top_down(cols, path, scale=max(4, 480 // max(w, d)))
    print(f"site x {lo[0]}..{hi[0]}, z {lo[1]}..{hi[1]}: ground y {min(ys)}..{max(ys)} "
          f"(median {statistics.median(ys):.0f}, spread {max(ys) - min(ys)})")
    print("surface: " + ", ".join(f"{k} {v * 100 // len(ys)}%" for k, v in tops.most_common(6)))
    side = lambda pts: statistics.mean(cols[p][0] for p in pts)  # noqa: E731
    sides = {"north": side([(x, lo[1]) for x in range(lo[0], hi[0] + 1)]),
             "south": side([(x, hi[1]) for x in range(lo[0], hi[0] + 1)]),
             "west": side([(lo[0], z) for z in range(lo[1], hi[1] + 1)]),
             "east": side([(hi[0], z) for z in range(lo[1], hi[1] + 1)])}
    print("edges (mean ground y): " + ", ".join(f"{k} {v:.0f}" for k, v in sides.items()) +
          f"; highest side: {max(sides, key=sides.get)}")
    step = max(1, max(w, d) // 8)
    print(f"ground y every {step} blocks (rows = z north→south, cols = x west→east; ~ = water):")
    print("        " + " ".join(f"{x:>5}" for x in range(lo[0], hi[0] + 1, step)))
    grid_x, grid_z = range(lo[0], hi[0] + 1, step), range(lo[1], hi[1] + 1, step)
    wet = {(x, z) for x in grid_x for z in grid_z if terrain.is_water(cols[(x, z)])}
    depth = water_depths([(x, z, cols[(x, z)][0]) for x, z in wet])
    for z in grid_z:
        row = [f"{cols[(x, z)][0]:>4}{'~' if (x, z) in wet else ' '}" for x in grid_x]
        if any((x, z) in wet for x in grid_x):
            row.append("  depth: " + " ".join(str(depth[(x, z)]) if (x, z) in wet else "." for x in grid_x))
        print(f"{z:>7} " + " ".join(row))
    print(f"map (north up, brighter = higher): {path}")


def resolve(a):
    """A place-style command's plan put on the ground: (build, task or plot, at, cells, y0). Shared by place
    and preview, so a preview and the build placed from it are the same blocks."""
    build = load_plan(a.plan)
    t = evals.task(a.task) if a.task else None
    if getattr(a, "within", None) and not t:  # an area (a player's selection): fit inside, clear trees only there
        x0, z0, x1, z1 = ints(a.within)
        t = {"plot": {"min": [min(x0, x1), min(z0, z1)], "max": [max(x0, x1), max(z0, z1)]}}
    if a.plot:  # a town plot behaves like a task: fit inside it, centred by default, at its floor height
        tname, pid = a.plot.split("/")
        p = towns.plot(tname, pid)
        t = {"plot": {"min": p["min"], "max": p["max"]}}
        a.task = f"town:{tname}:{pid}"
        if a.y is None:
            a.y = p["floor_y"]
    if a.near:
        px, py, pz = player_pos(a.near)
        at = (px + 4, pz + 4)
    elif a.at:
        at = tuple(ints(a.at))
    (lx0, _, lz0), (lx1, _, lz1) = build.bounds()
    if not (a.near or a.at):
        if t:  # centre the footprint in the plot
            (px0, pz0), (px1, pz1) = t["plot"]["min"], t["plot"]["max"]
            at = ((px0 + px1 - lx0 - lx1) // 2, (pz0 + pz1 - lz0 - lz1) // 2)
        else:
            s = bridge.status()["spawn"]
            at = (s[0] + 4, s[2] + 4)
    print(f"{build.name}: {len(build.blocks)} blocks, footprint x {lx0}..{lx1} z {lz0}..{lz1} (local), " +
          ", ".join(f"{k} {v}" for k, v in list(build.counts().items())[:6]))
    if t and not evals.in_plot(t, (at[0] + lx0, 0, at[1] + lz0), (at[0] + lx1, 0, at[1] + lz1)):
        sys.exit(overflow(build, at, (t["plot"]["min"], t["plot"]["max"])))
    check_blocks(build.blocks)
    cells, y0 = ground_cells(build, at, a.foundation, a.y, not a.no_clear, a.task or "", journal.run_id())
    if not a.keep_trees:
        cells = clear_trees(cells, (t["plot"]["min"], t["plot"]["max"]) if t else None)
    return build, t, at, cells, y0


def show_on_terrain(build, at, y0, cells, stem="preview"):
    """The build drawn over the real terrain, exactly as place would leave it, rendered and audited."""
    (x0, y0_, z0), (x1, y1, z1) = bounds(cells)
    world = bridge.region((x0 - 3, y0_ - 4, z0 - 3), (x1 + 3, y1 + 2, z1 + 3))
    world.update(cells)
    path = out_path(f"{build.name}-{stem}")
    render.sheet([render.iso(world, view=v) for v in ("se", "nw")], path, columns=2)
    r = auditing.audit(world, bounds(cells))
    print(f"on the real terrain, two opposite corners: {path}")
    print(auditing.report(r, "audit of the preview: "))
    return r


def cmd_place(a):
    build, t, at, cells, y0 = resolve(a)
    if a.dry_run:
        print(f"dry run at {at[0]},{y0},{at[1]} (--at {at[0]},{at[1]}), nothing placed.")
        show_on_terrain(build, at, y0, cells)
        return
    t0 = time.time()
    ents = [(at[0] + x, y0 + y, at[1] + z, k) for (x, y, z, k) in build.entities]
    e = edits.place(cells, label=build.name, run=journal.run_id(), task=a.task or "",
                    floor_y=y0, at=list(at), plan=str(a.plan), entities=ents)
    for (x, y, z, k) in ents:  # after the blocks, so boats sit on water, not inside the old terrain
        bridge.command(f"summon minecraft:{k} {centre(x)} {y} {centre(z)}")
    for (x, y, z, lines, side) in build.signs:
        bridge.call("/sign", {"pos": [at[0] + x, y0 + y, at[1] + z], "lines": lines, "side": side})
    if ents or build.signs:
        print(f"  + {len(ents)} entities summoned, {len(build.signs)} signs written")
    print(f"placed {e['id']} at {at[0]},{y0},{at[1]}: {e['changed']} blocks changed in {time.time() - t0:.1f}s, "
          f"box {e['min']}..{e['max']}")
    lo, hi = e["min"], e["max"]
    shot = bridge.region((lo[0] - 3, lo[1] - 3, lo[2] - 3), (hi[0] + 3, hi[1] + 2, hi[2] + 3))
    path = out_path(f"{build.name}-placed")
    render.iso(shot, path)
    print(f"render: {path}")
    print(f"next: mc audit {e['id']} and mc shots {e['id']}. undo: mc undo {e['id']}")


def place_args(sp):
    """The arguments place and preview share."""
    sp.add_argument("plan")
    sp.add_argument("--at", help="X,Z of the build's local (0,0) corner")
    sp.add_argument("--near", help="a player's name: build a few blocks from them")
    sp.add_argument("--task", help="an eval task: the build must fit its plot")
    sp.add_argument("--plot", help="TOWN/PLOT: a town plot (must fit; default y = its floor_y)")
    sp.add_argument("--foundation", default="cobblestone", help="block under the footprint down to the ground, or none")
    sp.add_argument("--y", type=int, help="world y of the plan's y 0 (default: one above the median ground)")
    sp.add_argument("--no-clear", action="store_true", help="keep terrain inside the build's box")
    sp.add_argument("--keep-trees", action="store_true", help="don't remove trees touching the build")
    sp.add_argument("--within", help="X0,Z0,X1,Z1: an area the build must fit (trees are cleared only inside it)")


def cmd_undo(a):
    e = edits.undo(a.id, journal.run_id())
    print(f"undid {e['id']} ({e['label']}) via {e['undo_via']}")


def cmd_edits(_):
    for e in edits.listing():
        print(f"{e['id']:>5}  {e['label']:<18} task {e.get('task') or '-':<16} {e['changed']:>6} blocks  "
              f"{e['min']}..{e['max']}")


def cmd_blueprint(a):
    """Everything to approve a build before it exists, on one sheet (nothing is placed): the site with
    the footprint, x-ray views of the design itself (its blocks only), floor plans, and the face before
    and after (an elevation looking `--face`)."""
    build = load_plan(a.plan)
    at = tuple(ints(a.at))
    check_blocks(build.blocks)
    cells, y0 = ground_cells(build, at, a.foundation, a.y, not a.no_clear)
    (bx0, by0, bz0), (bx1, by1, bz1) = box = bounds(cells)
    lo, hi = (bx0 - 6, by0 - 3, bz0 - 6), (bx1 + 6, by1 + 6, bz1 + 6)
    before = bridge.region(lo, hi)
    after = dict(before)
    after.update(cells)
    imgs = []
    # 1. the site from above, the footprint outlined in red
    cols = bridge.heightmap((lo[0], lo[2]), (hi[0], hi[2]))
    scale = 4
    w, h, px = render.top_down(cols, scale=scale)
    foot = {(x, z) for x, _, z in cells}
    edge = {(x, z) for (x, z) in foot if any((x + dx, z + dz) not in foot for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    for (x, z) in edge:
        for dx in range(scale):
            for dz in range(scale):
                i = (((z - lo[2]) * scale + dz) * w + (x - lo[0]) * scale + dx) * 3
                px[i:i + 3] = bytes((220, 40, 40))
    imgs.append((w, h, px))
    # 2. the design itself, its own blocks only (no terrain): x-ray from two corners
    own = {p: b for p, b in cells.items() if not render.skipped(b)}
    imgs += [render.iso(own, tile=a.tile, view=v) for v in ("se", "nw")]
    # 3. the face before and after
    imgs.append(render.elevation(before, look=a.face, scale=6))
    imgs.append(render.elevation(after, look=a.face, scale=6))
    # 4. floor plans of the design at its storeys (from the audit of the result), up to 4
    r = auditing.audit(after, box)
    levels = r["stats"]["indoor_levels"][:4] or [y0 + 1]
    imgs += [render.plan(after, y, scale=6) for y in levels]
    path = out_path(f"{build.name}-blueprint")
    render.sheet(imgs, path, columns=3)
    print(f"{path}\norder: site with footprint (red), design x-ray SE and NW, the {a.face}-looking face before "
          f"and after, floor plans at y {', '.join(map(str, levels))}")
    print(auditing.report(r, "audit of the result: "))


def register(sub):
    s = sub.add_parser("site")
    s.add_argument("center", nargs="?", help="X,Z")
    s.add_argument("--task", help="show exactly this task's plot (with a 4-block margin)")
    s.add_argument("--plot", help="TOWN/PLOT: show exactly this town plot (with a 4-block margin)")
    s.add_argument("size", nargs="?", help="W,D (default 48,48)")
    s.set_defaults(fn=cmd_site)
    pl = sub.add_parser("place")
    place_args(pl)
    pl.add_argument("--dry-run", action="store_true")
    pl.set_defaults(fn=cmd_place)
    sub.add_parser("undo").add_argument("id", nargs="?")
    sub.choices["undo"].set_defaults(fn=cmd_undo)
    sub.add_parser("edits").set_defaults(fn=cmd_edits)
    bp = sub.add_parser("blueprint")
    bp.add_argument("plan")
    bp.add_argument("--at", required=True)
    bp.add_argument("--y", type=int)
    bp.add_argument("--foundation", default="cobblestone")
    bp.add_argument("--no-clear", action="store_true")
    bp.add_argument("--face", default="west", choices=["west", "east", "north", "south"],
                    help="the elevation looks this way (west = you stand east of it)")
    bp.add_argument("--tile", type=int, default=6)
    bp.set_defaults(fn=cmd_blueprint)
