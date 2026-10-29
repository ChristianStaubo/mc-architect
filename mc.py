#!/usr/bin/env python3
"""mc: the agent's one tool for the Minecraft test server.

Build
  mc site --task T | --plot TOWN/P | X,Z [W,D]
                                    terrain of a plot (or centred on X,Z): heights grid, water, slope, map
  mc place PLAN [--at X,Z | --near PLAYER] [--task T] [--dry-run]
             [--foundation BLOCK|none] [--y Y] [--no-clear] [--keep-trees]
                                    build a plan (plans/NAME or a .py path) on the ground there:
                                    local (0,0,0) at X,Z, y 0 one above the median ground; foundation
                                    fills down to the terrain, the hill inside the box is cleared,
                                    trees touching the build removed. With --task and no --at the
                                    build is centred in the plot. --dry-run previews on the real terrain
  mc undo [EDIT]                    undo the latest edit, or EDIT (e.g. e12); survives restarts
  mc edits                          live edits (id, label, task, box)
Look and judge
  mc shots [EDIT]                   contact sheet: 4 corner views, top-down, floor plan (critic input)
  mc render X1,Y1,Z1 X2,Y2,Z2 [--view se|sw|nw|ne] [--surface [N]]
                                    isometric picture of any region (--surface: no underground)
  mc audit [EDIT] [--friction]      hard checks (floating, doors, beds, sealed rooms, dark floors, panes)
                                    exit 2 on a fail; --friction files a friction report for it
  mc blueprint PLAN --at X,Z [--y Y] [--no-clear] [--foundation F] [--face west]
                                    the approval sheet: site + footprint, design x-ray, face before/after,
                                    floor plans, and the audit of the result. Places nothing.
When the tools fall short
  mc gap "<what was missing or awkward>"   note a tool gap and carry on (the fixer turns it into a tool)
  mc stuck "<goal> | <what you tried> | <what happened>"   save a friction report, then STOP
  mc incidents [--all] | incident ID [replay]   failures saved automatically: error, stack, last bridge
                                    requests and commands, the plan as it was, the server log; replay = dry rerun
  mc friction [--all] | resolve ID "<fix>" --cause C | stats
Evals
  mc eval list | brief T --run R | reset T | record T --run R [--critique FILE] | report [R]
Towns (towns/NAME/town.json + layout.json; docs/town.md)
  mc town site NAME                 the area's height grid, slope classes, terrain and slope maps
  mc town show NAME                 check the layout (plots, roads, doors, water, earthworks) + map; exit 2 on a fail
  mc town road NAME ROAD [--dry-run]       build a road (follows the land, bridges over water)
  mc town terrace NAME PLOT [--dry-run]    level a plot at its floor_y with retaining walls
  mc town brief NAME PLOT           a builder's brief for a plot; build it with place --plot NAME/PLOT
  mc town shots NAME                the whole town from four corners and above (the town critic's input)
  mc town tidy NAME [--dry-run]     remove whole trees touching plots and roads (never inside plots)
  mc town status NAME               what's built
Server
  mc doctor | status | restart | cmd "<command>"  (cmd refuses stop/restart/reload)

Every call is logged to local/runs/commands.jsonl and every bridge request to local/runs/trace/ (with
MC_RUN_ID); a failure saves an incident in local/runs/incidents/. Pictures: local/renders/.
"""

import argparse
import difflib
import importlib.util
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from architect import audit as auditing  # noqa: E402
from architect import bridge, edits, evals, incidents, journal, render, terrain, trace  # noqa: E402
from architect import town as towns  # noqa: E402

RENDERS = ROOT / "local" / "renders"


def out_path(stem):
    RENDERS.mkdir(parents=True, exist_ok=True)
    return RENDERS / f"{time.strftime('%Y%m%d-%H%M%S')}-{stem}.png"


def ints(s):
    return [int(v) for v in s.split(",")]


# ---- server ----

def cmd_doctor(_):
    ok = True
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", "mc-architect"],
                       capture_output=True, text=True)
    state = r.stdout.strip() or "missing (is Docker Desktop running?)"
    print(f"container: {state}")
    ok &= state == "running"
    try:
        s = bridge.status()
        print(f"bridge: ok, Minecraft {s['minecraft']}, TPS {s['tps']:.1f}, "
              f"{len(s['players'])} online, {len(edits.listing())} live edits")
    except bridge.BridgeError as e:
        print(f"bridge: {e}")
        ok = False
    if not ok:
        print("fix: open -a Docker; docker compose up -d  (plugin: scripts/build-plugin.sh, then mc restart)")
    return 0 if ok else 1


def cmd_status(_):
    print(json.dumps(bridge.status(), indent=2))


def cmd_restart(_):
    """Restart the container (the world saves first) and wait for the bridge."""
    subprocess.run(["docker", "compose", "up", "-d", "--force-recreate"], cwd=ROOT, check=True)
    for _ in range(60):
        time.sleep(2)
        try:
            bridge.status()
            print("server up")
            return 0
        except bridge.BridgeError:
            pass
    sys.exit("server did not come back in 2 minutes: docker logs mc-architect")


def cmd_cmd(a):
    first = a.command.lstrip("/").split()[0].lower() if a.command.strip() else ""
    if first in ("stop", "restart", "reload", "rl"):
        # Paper's /restart only stops the server here (no restart script); /reload breaks plugins.
        sys.exit(f"refused: '{first}' from inside the game. Use: mc restart")
    r = bridge.command(a.command)
    print("\n".join(r["output"]) or ("ok" if r["ok"] else "failed"))
    return 0 if r["ok"] else 1


# ---- build ----

def player_pos(name):
    for p in bridge.status()["players"]:
        if p["name"].lower() == name.lower():
            return [int(v) for v in p["pos"]]
    raise SystemExit(f"{name} is not online")


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
    surface = {}
    for _, b in cols.values():
        n = render.block_name(b)
        surface[n] = surface.get(n, 0) + 1
    w, d = hi[0] - lo[0] + 1, hi[1] - lo[1] + 1
    path = out_path(f"site-{lo[0]}_{lo[1]}")
    render.top_down(cols, path, scale=max(4, 480 // max(w, d)))
    print(f"site x {lo[0]}..{hi[0]}, z {lo[1]}..{hi[1]}: ground y {min(ys)}..{max(ys)} "
          f"(median {statistics.median(ys):.0f}, spread {max(ys) - min(ys)})")
    print("surface: " + ", ".join(f"{k} {v * 100 // len(ys)}%" for k, v in
                                  sorted(surface.items(), key=lambda kv: -kv[1])[:6]))
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
    for z in range(lo[1], hi[1] + 1, step):
        row = []
        for x in range(lo[0], hi[0] + 1, step):
            y, b = cols[(x, z)]
            row.append(f"{y:>4}{'~' if render.block_name(b) == 'water' else ' '}")
        if any(render.block_name(cols[(x, z)][1]) == "water" for x in range(lo[0], hi[0] + 1, step)):
            row.append("  depth: " + " ".join(str(water_depth(x, z, cols[(x, z)][0])) if
                                              render.block_name(cols[(x, z)][1]) == "water" else "."
                                              for x in range(lo[0], hi[0] + 1, step)))
        print(f"{z:>7} " + " ".join(row))
    print(f"map (north up, brighter = higher): {path}")


def water_depth(x, z, surface):
    """Blocks of water below the surface at a column (where posts must reach)."""
    col = bridge.region((x, surface - 30, z), (x, surface, z))
    d = 0
    for y in range(surface, surface - 31, -1):
        if render.block_name(col.get((x, y, z), "")) != "water":
            break
        d += 1
    return d


def load_plan(name):
    path = Path(name)
    if not path.exists():
        path = ROOT / "plans" / f"{name.removesuffix('.py')}.py"
    if not path.exists():
        raise SystemExit(f"no plan {name}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    b = mod.build()
    if not b.blocks:
        raise SystemExit(f"plan {name} built nothing")
    return b


BLOCKS = ROOT / "local" / "blocks.json"


def check_blocks(cells):
    """Refuse before placing (or previewing) if any block-data string won't parse on this server, with
    the closest real names. r2: 'chain' (it's iron_chain) and 'dark_oak_log[axis=x][axis=z]' only
    failed at place time."""
    names = sorted({b for b in cells.values() if b not in ("air", None)})
    bad = bridge.call("/validate", {"blocks": names})["invalid"]
    if not bad:
        return
    if not BLOCKS.exists():
        BLOCKS.parent.mkdir(parents=True, exist_ok=True)
        BLOCKS.write_text(json.dumps(bridge.call("/blocks")["blocks"]))
    known = json.loads(BLOCKS.read_text())
    lines = []
    for x in bad:
        base = x["block"].split("[")[0].replace("minecraft:", "")
        hint = ""
        if base not in known:
            close = difflib.get_close_matches(base, known, n=3, cutoff=0.6) or [k for k in known if base in k][:3]
            hint = f" (did you mean {', '.join(close)}?)" if close else ""
        lines.append(f"  {x['block']}: {x['error']}{hint}")
    sys.exit("refused: blocks this server can't place:\n" + "\n".join(lines))


def original_ground(cols, task="", run=""):
    """Ground heights as they were before this task's (or run's) own live edits: re-previewing a plan
    over its own earlier build must not read that build as terrain (r2 tavern: y 122)."""
    mine = [e for e in edits.listing() if (task and e.get("task") == task) or (run and e.get("run") == run)]
    for e in mine:
        snap = edits.snapshot(e)
        tops = {}
        for (x, y, z), b in snap.items():
            if not render.skipped(b) and not any(k in b for k in TREE) and y > tops.get((x, z), (-999,))[0]:
                tops[(x, z)] = (y, b)
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
    cells = {}
    for (fx, fz) in foot:
        g = cols[(x + fx, z + fz)][0]
        if foundation != "none":
            for y in range(g + 1, y0 + ly0):  # foundation down to the ground
                cells[(x + fx, y, z + fz)] = foundation
        if clear:  # clear the hill inside the footprint, from the ground floor up (never below it:
            # posts and basements change only where the plan says; r1's boathouse got a flooded-out
            # air pocket under its floor when clearing started at its lowest post)
            for y in range(y0, max(g, y0 + ly1) + 1):
                cells[(x + fx, y, z + fz)] = "air"
    for (bx, by, bz), blk in build.blocks.items():
        cells[(x + bx, y0 + by, z + bz)] = blk
    return cells, y0


TREE = ("_log", "_leaves", "vine", "bee_nest", "_wood")


def clear_trees(cells, task=None, margin=2, reach=7):
    """Trees that touch the build (its box plus `margin`) go whole: every log, leaf, vine and the snow
    on them connected to a touching one, up to `reach` blocks beyond. r2: clearing only the touching
    blocks left snow-capped leaves floating around the watchtower. Within a task, only inside its plot."""
    xs, ys, zs = zip(*cells)
    box_lo = (min(xs) - margin, min(ys), min(zs) - margin)
    box_hi = (max(xs) + margin, max(ys) + 8, max(zs) + margin)
    world = bridge.region((box_lo[0] - reach, box_lo[1], box_lo[2] - reach),
                          (box_hi[0] + reach, box_hi[1] + reach, box_hi[2] + reach))
    treeish = lambda b: any(k in b for k in TREE)  # noqa: E731
    near = lambda p: all(box_lo[i] <= p[i] <= box_hi[i] for i in range(3))  # noqa: E731
    seeds = [p for p, b in world.items() if near(p) and p not in cells and treeish(b)]
    tree = auditing.flood(world, seeds, treeish)
    tree |= {(x, y + 1, z) for (x, y, z) in tree if render.block_name(world.get((x, y + 1, z), "")) == "snow"}
    out = dict(cells)
    for p in tree:
        if p not in cells and (not task or evals.in_plot(task, p, p)):
            out[p] = "air"
    return out


def cmd_place(a):
    build = load_plan(a.plan)
    t = evals.task(a.task) if a.task else None
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
        sys.exit(f"refused: the build would cover x {at[0] + lx0}..{at[0] + lx1}, z {at[1] + lz0}..{at[1] + lz1}; "
                 f"plot is x {t['plot']['min'][0]}..{t['plot']['max'][0]}, z {t['plot']['min'][1]}..{t['plot']['max'][1]}")
    check_blocks(build.blocks)
    cells, y0 = ground_cells(build, at, a.foundation, a.y, not a.no_clear, a.task or "", journal.run_id())
    if not a.keep_trees:
        cells = clear_trees(cells, t)
    if a.dry_run:  # the build drawn over the real terrain, exactly as place would leave it, and audited
        xs, ys, zs = zip(*cells)
        world = bridge.region((min(xs) - 3, min(ys) - 4, min(zs) - 3), (max(xs) + 3, max(ys) + 2, max(zs) + 3))
        world.update(cells)
        path = out_path(f"{build.name}-preview")
        render.sheet([render.iso(world, view=v) for v in ("se", "nw")], path, columns=2)
        r = auditing.audit(world, ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))))
        print(f"dry run at {at[0]},{y0},{at[1]} (--at {at[0]},{at[1]}), nothing placed. "
              f"preview on the real terrain, two opposite corners: {path}")
        print(f"audit of the preview: {r['fails']} fail, {r['warns']} warn")
        for c in r["checks"]:
            print(f"  {c['level'].upper():<4} {c['check']:<9} {c['msg']}" + (f"  e.g. {c['at'][:3]}" if c["at"] else ""))
        return
    t0 = time.time()
    e = edits.place(cells, label=build.name, run=journal.run_id(), task=a.task or "",
                    floor_y=y0, at=list(at), plan=str(a.plan))
    print(f"placed {e['id']} at {at[0]},{y0},{at[1]}: {e['changed']} blocks changed in {time.time() - t0:.1f}s, "
          f"box {e['min']}..{e['max']}")
    lo, hi = e["min"], e["max"]
    shot = bridge.region((lo[0] - 3, lo[1] - 3, lo[2] - 3), (hi[0] + 3, hi[1] + 2, hi[2] + 3))
    path = out_path(f"{build.name}-placed")
    render.iso(shot, path)
    print(f"render: {path}")
    print(f"next: mc audit {e['id']} and mc shots {e['id']}. undo: mc undo {e['id']}")


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
    xs, ys, zs = zip(*cells)
    lo, hi = (min(xs) - 6, min(ys) - 3, min(zs) - 6), (max(xs) + 6, max(ys) + 6, max(zs) + 6)
    before = bridge.region(lo, hi)
    after = dict(before)
    after.update(cells)
    imgs = []
    # 1. the site from above, the footprint outlined in red
    cols = bridge.heightmap((lo[0], lo[2]), (hi[0], hi[2]))
    scale = 4
    w, h, px = render.top_down(cols, scale=scale)
    foot = {(x, z) for (x, y, z), b in cells.items() if b != "air" or True}
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
    r = auditing.audit(after, ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))))
    levels = r["stats"]["indoor_levels"][:4] or [y0 + 1]
    imgs += [render.plan(after, y, scale=6) for y in levels]
    path = out_path(f"{build.name}-blueprint")
    render.sheet(imgs, path, columns=3)
    print(f"{path}\norder: site with footprint (red), design x-ray SE and NW, the {a.face}-looking face before "
          f"and after, floor plans at y {', '.join(map(str, levels))}")
    print(f"audit of the result: {r['fails']} fail, {r['warns']} warn")
    for c in r["checks"]:
        print(f"  {c['level'].upper():<4} {c['check']:<9} {c['msg']}")


# ---- look and judge ----

def latest_edit(eid):
    """eid, or the newest live edit of this run (MC_RUN_ID), or the newest overall."""
    if eid:
        return edits.get(eid)
    run = journal.run_id()
    live = [e for e in edits.listing() if not run or e.get("run") == run]
    if not live:
        raise SystemExit("no live edits" + (f" in run {run}" if run else ""))
    return max(live, key=lambda x: int(x["id"][1:]))


def around(e, margin=3, below=4, above=2):
    lo, hi = e["min"], e["max"]
    return bridge.region((lo[0] - margin, lo[1] - below, lo[2] - margin),
                         (hi[0] + margin, hi[1] + above, hi[2] + margin))


def run_audit(e):
    cells = around(e)
    return auditing.audit(cells, (tuple(e["min"]), tuple(e["max"])))


def cmd_audit(a):
    e = latest_edit(a.id)
    r = run_audit(e)
    print(f"audit {e['id']} ({e['label']}): {r['fails']} fail, {r['warns']} warn; "
          f"{r['stats']['blocks']} blocks, {r['stats']['doors']} doors, {r['stats']['indoor_floor']} indoor floor spots")
    for c in r["checks"]:
        print(f"  {c['level'].upper():<4} {c['check']:<9} {c['msg']}" + (f"  e.g. {c['at'][:3]}" if c["at"] else ""))
    if r["fails"] and a.friction:
        fid = journal.stuck(f"audit {e['id']} failed: " + "; ".join(c["msg"] for c in r["checks"] if c["level"] == "fail"))
        print(f"friction filed: {fid}")
    return 2 if r["fails"] else 0


def shots(e):
    """Contact sheet: 4 corner views, top-down, and a floor plan per storey (up to 4)."""
    cells = around(e, margin=2, below=2, above=1)
    lo, hi = e["min"], e["max"]
    floor = e.get("floor_y", lo[1])
    # Terrain more than 3 below the floor is cut away, except under the build itself (posts, cellars).
    inside = lambda p: lo[0] <= p[0] <= hi[0] and lo[2] <= p[2] <= hi[2]  # noqa: E731
    view = {p: b for p, b in cells.items() if p[1] >= floor - 3 or (inside(p) and p[1] >= lo[1])}
    imgs = [render.iso(view, view=v) for v in ("se", "sw", "nw", "ne")]
    cols = {}
    for (x, y, z), b in cells.items():
        if not render.skipped(b) and (cols.get((x, z), (-999,))[0] < y):
            cols[(x, z)] = (y, b)
    imgs.append(render.top_down(cols, scale=8))
    r = auditing.audit(cells, (tuple(lo), tuple(hi)))
    levels = r["stats"]["indoor_levels"] or [floor + 1]
    levels = levels[:4]
    imgs += [render.plan(cells, y) for y in levels]
    path = out_path(f"{e['label']}-{e['id']}-shots")
    render.sheet(imgs, path, columns=3)
    return path, levels


def cmd_shots(a):
    e = latest_edit(a.id)
    path, levels = shots(e)
    print(f"{path}\nlayout, left to right, top to bottom: views from the SE, SW, NW and NE corners; "
          f"top-down (north up); floor plans (north up) at y {', '.join(map(str, levels))}")


def cmd_render(a):
    lo, hi = ints(a.lo), ints(a.hi)
    lo, hi = [min(p) for p in zip(lo, hi)], [max(p) for p in zip(lo, hi)]
    cells = bridge.region(lo, hi)
    if a.surface:  # only the top few blocks of the land: what you'd see walking around, no cross-section
        cols = bridge.heightmap((lo[0], lo[2]), (hi[0], hi[2]))
        cells = {p: b for p, b in cells.items() if p[1] >= cols[(p[0], p[2])][0] - a.surface}
    path = out_path(f"region-{a.view}")
    w, h, _ = render.iso(cells, path, tile=a.tile, view=a.view)
    print(f"{path} ({w}x{h})")


# ---- incidents ----

def cmd_incidents(a):
    rows = incidents.listing()
    if not a.all:
        rows = [r for r in rows if r["kind"] in ("crash", "bridge")] or rows[-10:]
    for r in rows[-30:]:
        print(f"{r['id']:<40} {r['kind']:<8} {r['run'] or '-':<24} {r['error'].splitlines()[0][:90]}")
    print(f"{len(incidents.listing())} incidents kept (newest {incidents.KEEP}); --all shows refusals and errors too")


def cmd_incident(a):
    d = incidents.get(a.id)
    info = json.loads((d / "incident.json").read_text())
    if a.action == "replay":
        argv = info["argv"]
        if argv[0] == "place" and "--dry-run" not in argv:
            argv = argv + ["--dry-run"]
        elif argv[0] not in ("place", "blueprint", "site", "audit", "shots", "render", "status", "edits", "town"):
            raise SystemExit(f"won't replay '{argv[0]}' (it changes the world); run it yourself")
        if argv[0] == "town" and argv[1] in ("road", "terrace", "tidy") and "--dry-run" not in argv:
            argv = argv + ["--dry-run"]
        env = dict(os.environ, MC_RUN_ID=info["run"] or "")
        print(f"replaying (dry): mc {' '.join(argv)}")
        return subprocess.run([sys.executable, str(ROOT / "mc.py"), *argv], env=env).returncode
    print(f"{info['id']}  [{info['kind']}]  run {info['run'] or '-'}  {info['t']}")
    print(f"command: mc {' '.join(info['argv'])}")
    print(f"error: {info['error']}")
    if info.get("stack"):
        print("stack (last lines):\n  " + "\n  ".join(info["stack"].strip().splitlines()[-6:]))
    print("\nlast bridge requests:")
    for l in [json.loads(x) for x in (d / "trace.jsonl").read_text().splitlines() if x.strip()][-8:]:
        print(f"  {l['t'][11:]} {l['path']:<11} {l['status']:>4} {l['ms']:>5}ms {json.dumps(l['req'])[:70]}"
              + (f"  ERROR {l['error'][:60]}" if l.get("error") else ""))
    print("\nlast mc commands:")
    for l in [json.loads(x) for x in (d / "journal.jsonl").read_text().splitlines() if x.strip()][-8:]:
        print(f"  {l['t'][11:]} {l['run'] or '-':<22} {l['cmd']:<8} {' '.join(l['argv'])[:50]:<50} {'ok' if l['ok'] else 'FAIL'}")
    log = (d / "server.log").read_text().splitlines() if (d / "server.log").exists() else []
    bad = [x for x in log if any(k in x for k in ("ERROR", "WARN", "Exception"))]
    print(f"\nserver log: {len(log)} lines kept, {len(bad)} warnings/errors" + ("".join("\n  " + x[:140] for x in bad[-4:])))
    print(f"\nfiles: {d}" + ("  (plan.py = the plan as it was)" if (d / "plan.py").exists() else ""))
    print(f"replay it (dry): mc incident {info['id']} replay")


def cmd_gap(a):
    fid = journal.stuck(a.text, kind="gap")
    print(f"gap {fid} noted. Carry on; the fixer turns gaps into tools.")


# ---- friction ----

def cmd_stuck(a):
    fid = journal.stuck(a.text)
    print(f"friction {fid} saved. STOP now and report it: the fixer takes it from here.")


def cmd_friction(a):
    if a.action == "resolve":
        r = journal.resolve(a.id, a.fix, a.cause, a.repeat_of)
        print(f"resolved {r['id']} ({r['cause']}): {r['fix']}")
    elif a.action == "stats":
        rs = journal.reports(include_resolved=True)
        by = {}
        for r in rs:
            k = r.get("cause", "open")
            by[k] = by.get(k, 0) + 1
        builds = sum(1 for e in journal.entries() if e["cmd"] == "place" and "--dry-run" not in e["argv"] and e["ok"])
        print(f"{len(rs)} friction reports ({sum(r['status'] == 'open' for r in rs)} open), "
              f"{builds} builds placed: {builds / max(1, len(rs)):.1f} builds per friction report")
        print("by cause: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: -kv[1])))
        print(f"repeats (a fix that didn't hold): {sum(1 for r in rs if r.get('repeat_of'))}")
        kinds = {}
        for r in rs:
            k = r.get("kind", "stuck")
            kinds[k] = kinds.get(k, 0) + 1
        print("by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
        crashes = [i for i in incidents.listing() if i["kind"] in ("crash", "bridge")]
        print(f"incidents: {len(incidents.listing())} kept, {len(crashes)} crashes/bridge failures")
    else:
        for r in journal.reports(include_resolved=a.all):
            print(f"{r['id']}  [{r['status']}] {r.get('kind', 'stuck'):<8} run {r['run'] or '-'}: {r['report'][:140]}")


# ---- towns ----

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
        numbering, colors = towns.draw(name, cols, path)
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
        in_plot = lambda x, z: any(p0[0] <= x <= p1[0] and p0[1] <= z <= p1[1] for p0, p1 in plots)  # noqa: E731
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
        ok = lambda p: (not in_plot(p[0], p[2]) and (p[0], p[2]) not in road and  # noqa: E731
                        not terrain.is_water(cols.get((p[0], p[2]), (0, "air"))))
        tree = lambda b: any(k in b for k in TREE)  # noqa: E731
        seeds = [p for p, b in world.items() if (p[0], p[2]) in near and tree(b) and ok(p)]
        found = auditing.flood(world, seeds, tree)
        found = {p for p in found if ok(p)}
        found |= {(x, y + 1, z) for (x, y, z) in found if render.block_name(world.get((x, y + 1, z), "")) == "snow"}
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


# ---- evals ----

def cmd_eval(a):
    if a.action == "list":
        for tid, t in evals.tasks().items():
            print(f"{tid:<18} {t['brief'][:90]}")
    elif a.action == "brief":
        print(evals.brief(a.task, a.run))
    elif a.action == "reset":
        live = [e for e in edits.listing() if e.get("task") == a.task]
        for e in sorted(live, key=lambda x: -int(x["id"][1:])):
            edits.undo(e["id"])
            print(f"undid {e['id']}")
        print(f"{a.task}: plot back to its terrain ({len(live)} edits undone)")
    elif a.action == "record":
        run_task = f"{a.run}:{a.task}"
        mine = [e for e in edits.listing() if e.get("task") == a.task and e.get("run") == run_task]
        e = max(mine, key=lambda x: int(x["id"][1:])) if mine else None
        r = run_audit(e) if e else {"fails": 1, "warns": 0, "checks": [{"check": "nothing built", "level": "fail"}],
                                    "stats": {"doors": 0, "indoor_floor": 0}}
        crit = json.loads(Path(a.critique).read_text()) if a.critique else None
        out = evals.record(a.task, a.run, e, r, crit)
        print(json.dumps({k: out[k] for k in ("task", "pass", "quality", "audit", "must_missing", "tools")}, indent=1))
    elif a.action == "report":
        runs = [a.run] if a.run else evals.runs()
        print(f"{'run':<14} {'pass':>6} {'quality':>8} {'calls/task':>10} {'failed':>7} {'stops':>6} {'over budget':>11}")
        for r in runs:
            s = evals.summary(r)
            if s:
                print(f"{r:<14} {s['passed']:>3}/{s['tasks']:<2} {s['quality'] if s['quality'] is not None else '-':>8} "
                      f"{s['calls']:>10} {s['failed_calls']:>7} {s['stops']:>6} {s['over_budget']:>11}")
        if a.run:
            for res in evals.results(a.run):
                c = res.get("critique") or {}
                print(f"  {res['task']:<18} {'PASS' if res['pass'] else 'FAIL':<5} q {res['quality'] or '-':<4} "
                      f"calls {res['tools']['calls']:<3} {', '.join(res['audit']['failed_checks'] + res['must_missing'])} "
                      f"{('| ' + c.get('summary', '')[:90]) if c else ''}")


def main():
    p = argparse.ArgumentParser(prog="mc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for n in ("doctor", "status", "restart", "edits"):
        sub.add_parser(n)
    c = sub.add_parser("cmd")
    c.add_argument("command")
    s = sub.add_parser("site")
    s.add_argument("center", nargs="?", help="X,Z")
    s.add_argument("--task", help="show exactly this task's plot (with a 4-block margin)")
    s.add_argument("--plot", help="TOWN/PLOT: show exactly this town plot (with a 4-block margin)")
    s.add_argument("size", nargs="?", help="W,D (default 48,48)")
    pl = sub.add_parser("place")
    pl.add_argument("plan")
    pl.add_argument("--at", help="X,Z of the build's local (0,0) corner")
    pl.add_argument("--near", help="a player's name: build a few blocks from them")
    pl.add_argument("--task", help="an eval task: the build must fit its plot")
    pl.add_argument("--plot", help="TOWN/PLOT: a town plot (must fit; default y = its floor_y)")
    pl.add_argument("--dry-run", action="store_true")
    pl.add_argument("--foundation", default="cobblestone", help="block under the footprint down to the ground, or none")
    pl.add_argument("--y", type=int, help="world y of the plan's y 0 (default: one above the median ground)")
    pl.add_argument("--no-clear", action="store_true", help="keep terrain inside the build's box")
    pl.add_argument("--keep-trees", action="store_true", help="don't remove trees touching the build")
    r = sub.add_parser("render")
    r.add_argument("lo")
    r.add_argument("hi")
    r.add_argument("--tile", type=int, default=8)
    r.add_argument("--view", default="se", choices=list(render.ROTATIONS))
    r.add_argument("--surface", type=int, nargs="?", const=3, default=0,
                   help="keep only the top N blocks of the land (default 3): no underground cross-section")
    for n in ("undo", "shots", "audit"):
        x = sub.add_parser(n)
        x.add_argument("id", nargs="?")
        if n == "audit":
            x.add_argument("--friction", action="store_true")
    g = sub.add_parser("gap")
    g.add_argument("text")
    sub.add_parser("incidents").add_argument("--all", action="store_true")
    ic = sub.add_parser("incident")
    ic.add_argument("id")
    ic.add_argument("action", nargs="?", choices=["show", "replay"], default="show")
    st = sub.add_parser("stuck")
    st.add_argument("text")
    f = sub.add_parser("friction")
    f.add_argument("action", nargs="?", choices=["list", "resolve", "stats"], default="list")
    f.add_argument("id", nargs="?")
    f.add_argument("fix", nargs="?")
    f.add_argument("--cause")
    f.add_argument("--repeat-of")
    f.add_argument("--all", action="store_true")
    bp = sub.add_parser("blueprint")
    bp.add_argument("plan")
    bp.add_argument("--at", required=True)
    bp.add_argument("--y", type=int)
    bp.add_argument("--foundation", default="cobblestone")
    bp.add_argument("--no-clear", action="store_true")
    bp.add_argument("--face", default="west", choices=["west", "east", "north", "south"],
                    help="the elevation looks this way (west = you stand east of it)")
    bp.add_argument("--tile", type=int, default=6)
    tw = sub.add_parser("town")
    tw.add_argument("action", choices=["site", "show", "road", "terrace", "brief", "shots", "tidy", "status"])
    tw.add_argument("--tile", type=int, default=5)
    tw.add_argument("name")
    tw.add_argument("id", nargs="?")
    tw.add_argument("--dry-run", action="store_true")
    tw.add_argument("--refresh", action="store_true", help="site: re-read the terrain (before any building!)")
    ev = sub.add_parser("eval")
    ev.add_argument("action", choices=["list", "brief", "reset", "record", "report"])
    ev.add_argument("task", nargs="?")
    ev.add_argument("--run")
    ev.add_argument("--critique")
    # Coordinates like -68,-20 are values, not options.
    coords = re.compile(r"^-\d+(,-?\d+)*$")
    for parser in [p, *sub.choices.values()]:
        parser._negative_number_matcher = coords
        parser._has_negative_number_optionals = []
    a = p.parse_args()
    if a.cmd == "eval" and a.action == "report" and a.task and not a.run:
        a.run = a.task  # `mc eval report RUN`
    t0 = time.time()
    code, err, kind, exc = 0, None, None, None
    try:
        code = globals()["cmd_" + a.cmd](a) or 0
    except bridge.BridgeError as e:
        # 4xx = the request was wrong (too big, unknown block): the caller's error, not the bridge's
        code, err, exc = 1, f"error: {e}", e
        kind = "error" if 400 <= getattr(e, "status", 0) < 500 else "bridge"
    except SystemExit as e:
        code, err = (e.code if isinstance(e.code, int) else 1), (e.code if isinstance(e.code, str) else None)
        if err:
            kind = "refused" if err.startswith("refused") else "error"
    except Exception as e:  # a tool bug: record it with everything around it, then show it
        code, err, kind, exc = 1, repr(e), "crash", e
    argv = sys.argv[1:]
    journal.log(a.cmd, argv[1:], int((time.time() - t0) * 1000), code == 0, err)
    # Judges failing (audit, town show: exit 2) are the system working, not incidents.
    if kind and a.cmd not in ("incidents", "incident"):
        iid = incidents.save(a.cmd, argv, kind, err, exc)
        err = f"{err}\n(incident {iid}: mc incident {iid})"
    if kind == "crash":
        import traceback
        traceback.print_exception(exc)
    if err:
        print(err, file=sys.stderr)
    trace.prune()
    sys.exit(code)


if __name__ == "__main__":
    main()
