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
  mc eval gate [--offline]          the regression suite (docs/evals.md): must be 100%; exit 1 on a failure
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
from collections import Counter
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
from architect import blocks, bridge, edits, evals, graders, incidents, journal, render, sites, terrain  # noqa: E402
from architect import town as towns  # noqa: E402
from architect.build import load as load_build  # noqa: E402
from architect.placement import (bounds, check_blocks, clear_trees, ground_cells, original_ground,  # noqa: E402
                                 overflow, water_depths, whole_trees)

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


def load_plan(name):
    path = Path(name)
    if not path.exists():
        path = ROOT / "plans" / f"{name.removesuffix('.py')}.py"
    if not path.exists():
        raise SystemExit(f"no plan {name}")
    b = load_build(path)
    if not b.blocks:
        raise SystemExit(f"plan {name} built nothing")
    return b


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
        sys.exit(overflow(build, at, (t["plot"]["min"], t["plot"]["max"])))
    check_blocks(build.blocks)
    cells, y0 = ground_cells(build, at, a.foundation, a.y, not a.no_clear, a.task or "", journal.run_id())
    if not a.keep_trees:
        cells = clear_trees(cells, (t["plot"]["min"], t["plot"]["max"]) if t else None)
    if a.dry_run:  # the build drawn over the real terrain, exactly as place would leave it, and audited
        (x0, y0_, z0), (x1, y1, z1) = bounds(cells)
        world = bridge.region((x0 - 3, y0_ - 4, z0 - 3), (x1 + 3, y1 + 2, z1 + 3))
        world.update(cells)
        path = out_path(f"{build.name}-preview")
        render.sheet([render.iso(world, view=v) for v in ("se", "nw")], path, columns=2)
        r = auditing.audit(world, bounds(cells))
        print(f"dry run at {at[0]},{y0},{at[1]} (--at {at[0]},{at[1]}), nothing placed. "
              f"preview on the real terrain, two opposite corners: {path}")
        print(auditing.report(r, "audit of the preview: "))
        return
    t0 = time.time()
    ents = [(at[0] + x, y0 + y, at[1] + z, k) for (x, y, z, k) in build.entities]
    e = edits.place(cells, label=build.name, run=journal.run_id(), task=a.task or "",
                    floor_y=y0, at=list(at), plan=str(a.plan), entities=ents)
    for (x, y, z, k) in ents:  # after the blocks, so boats sit on water, not inside the old terrain
        bridge.command(f"summon minecraft:{k} {x}.5 {y} {z}.5")
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


# ---- look and judge ----

def latest_edit(eid):
    """eid, or the newest live edit of this run (MC_RUN_ID), or the newest overall."""
    if eid:
        return edits.get(eid)
    return edits.newest(journal.run_id())


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
    st = r["stats"]
    print(auditing.report(r, f"audit {e['id']} ({e['label']}): ",
                          f"; {st['blocks']} blocks, {st['doors']} doors, {st['indoor_floor']} indoor floor spots"))
    if r["fails"] and a.friction:
        fid = journal.stuck(f"audit {e['id']} failed: " + "; ".join(c["msg"] for c in r["checks"] if c["level"] == "fail"))
        print(f"friction filed: {fid}")
    return 2 if r["fails"] else 0


def shots(e, path=None, cells=None, levels=None):
    """Contact sheet: 4 corner views, top-down, and a floor plan per storey (up to 4). `cells` and
    `levels`: a region already read around it and its storeys (eval trials), so nothing is fetched twice."""
    lo, hi = e["min"], e["max"]
    if cells is None:
        cells = around(e, margin=2, below=2, above=1)
    else:
        cells = {p: b for p, b in cells.items() if lo[0] - 2 <= p[0] <= hi[0] + 2 and lo[2] - 2 <= p[2] <= hi[2] + 2
                 and lo[1] - 2 <= p[1] <= hi[1] + 1}
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
    if levels is None:
        levels = auditing.audit(cells, (tuple(lo), tuple(hi)))["stats"]["indoor_levels"]
    levels = (levels or [floor + 1])[:4]
    imgs += [render.plan(cells, y) for y in levels]
    # Facades, straight on and close up: small details (a hoist beam, a round window, a sign, shutters)
    # vanished at corner-view scale and the critic couldn't credit them (lakeside).
    box = {p: b for p, b in cells.items() if lo[0] - 1 <= p[0] <= hi[0] + 1 and lo[2] - 1 <= p[2] <= hi[2] + 1
           and p[1] >= floor - 1}
    for look in ("north", "west", "south", "east"):  # the south, east, north and west faces
        try:
            imgs.append(render.elevation(box, look=look, scale=10))
        except ValueError:
            pass
    path = path or out_path(f"{e['label']}-{e['id']}-shots")
    render.sheet(imgs, path, columns=3)
    return path, levels


def cmd_shots(a):
    e = latest_edit(a.id)
    path, levels = shots(e)
    print(f"{path}\nlayout, left to right, top to bottom: views from the SE, SW, NW and NE corners; "
          f"top-down (north up); floor plans (north up) at y {', '.join(map(str, levels))}; then the facades "
          f"straight on, close up: south, east, north, west")


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
        changes_world = argv[0] == "place" or argv[:1] == ["town"] and argv[1] in ("road", "terrace", "tidy")
        if not changes_world and argv[0] not in ("blueprint", "site", "audit", "shots", "render", "status", "edits", "town"):
            raise SystemExit(f"won't replay '{argv[0]}' (it changes the world); run it yourself")
        if changes_world and "--dry-run" not in argv:
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


# ---- evals ----

def cmd_eval(a):
    if a.action == "gate":
        from architect import regression
        rec = regression.run(offline=a.offline)
        m = rec["manifest"]
        print(f"regression @ {m['commit']}{' (dirty)' if m['dirty'] else ''}, Minecraft {m['minecraft']}, "
              f"Paper {m['paper_build']}, WorldEdit {m['worldedit']}")
        for r in rec["checks"]:
            mark = {"pass": "ok  ", "fail": "FAIL", "skipped": "skip"}[r["status"]]
            print(f"  {mark} {r['group']:<7} {r['check']:<22} {r['seconds']:>5}s  {r['detail'][:90]}")
        print(f"{rec['passed']} passed, {rec['failed']} failed, {rec['skipped']} skipped")
        return 1 if rec["failed"] else 0
    if a.action == "list":
        for tid, t in evals.tasks().items():
            print(f"{tid:<18} {t['brief'][:90]}")
    elif a.action == "brief":
        print(evals.brief(a.task, a.run))
    elif a.action == "reset":
        sites.reset(evals.task(a.task)["id"])
        print(f"{a.task}: site restored from {sites.path(a.task).relative_to(ROOT)}")
    elif a.action == "check":  # reset the site, build a plan on it, run the task's code graders
        t = evals.task(a.task)
        plan = a.plan or t["reference"]
        args = load_plan(plan).place_args
        with sites.still():  # no plants popping off or grass spreading between the reset and the grading
            sites.reset(t["id"])
            r = subprocess.run([sys.executable, str(ROOT / "mc.py"), "place", plan, "--task", t["id"], *args],
                               capture_output=True, text=True)
            print(r.stdout.strip() or r.stderr.strip())
            if r.returncode:
                raise SystemExit(f"place failed: {r.stderr.strip()[-300:]}")
            o = sites.outcome(t)
        res = graders.run(t, o)
        if not a.plan and o.box:  # the reference's sheet, for the rating page's anchors
            evals.REFERENCES.mkdir(parents=True, exist_ok=True)
            print(f"sheet: {shots(o.as_edit(t['id']), evals.REFERENCES / (t['id'] + '.png'), cells=o.after, levels=o.audit['stats']['indoor_levels'])[0]}")
        for g in res:
            print(f"  {'ok  ' if g['pass'] else 'FAIL'} {g['grader']:<26} {g['detail'][:110]}")
        print(f"{sum(g['pass'] for g in res)}/{len(res)} code graders pass")
        return 0 if all(g["pass"] for g in res) else 2
    elif a.action == "run":  # the capability suite, headless (docs/evals.md §7)
        from architect import trials
        tids = a.tasks.split(",") if a.tasks else list(evals.tasks())
        print(f"capability run: {len(tids)} tasks x {a.trials} trials, builder {a.model}, judge {a.judge_model}")
        run, recs = trials.run(tids, a.trials, a.model, a.label or "", shots, judge_model=a.judge_model,
                               concurrency=a.concurrency, log=lambda m: print(m, flush=True))
        print(f"done: {run}. report: mc eval report {run}")
    elif a.action == "judge":  # (re)judge a run's trials, e.g. after a rubric change
        from architect import trials
        for rec in trials.trial_records(a.run):
            if rec.get("sheet") and (a.force or rec.get("quality") is None):
                trials.save(trials.judge_trial(rec, evals.task(rec["task"]), a.judge_model, repeat=rec["trial"] == 1))
                print(f"  {rec['task']} #{rec['trial']}: quality {rec['quality']}")
    elif a.action == "report":
        eval_report(a.run, a.vs)


def eval_report(run, vs=None):
    """The capability report (docs/evals.md §9) of RUN (default: the newest), saved to evals/results/."""
    from architect import scoreboard
    run = run or (scoreboard.runs() or [None])[-1]
    if not run:
        raise SystemExit("no capability runs yet: mc eval run")
    s = scoreboard.save(scoreboard.summarise(run))
    m = s["manifest"]
    print(f"{run}: {m.get('label') or '-'} | builder {m['builder_model']}, judge {m.get('judge_model')} | "
          f"commit {m['commit']}{' (dirty)' if m['dirty'] else ''}")
    print(f"{'task':<18} {'pass':>5} {'@k':>3} {'^k':>3} {'quality':>8} {'90% CI':>12} {'calls':>6} {'min':>5} {'API $':>6}  failing graders")
    for tid, t in s["tasks"].items():
        ci = f"{t['quality_ci'][0]}-{t['quality_ci'][1]}" if t["quality"] is not None else "-"
        print(f"{tid:<18} {t['passed']:>2}/{t['trials']:<2} {'y' if t['pass_at_k'] else '-':>3} "
              f"{'y' if t['pass_all_k'] else '-':>3} {t['quality'] if t['quality'] is not None else '-':>8} {ci:>12} "
              f"{t['calls']:>6} {t['minutes']:>5} {t['api_usd']:>6}  "
              + ", ".join(f"{g} x{n}" for g, n in t["grader_fails"].items()))
    print(f"overall: pass {s['pass_rate']:.0%} of trials, pass@k {s['pass_at_k']:.0%} of tasks, pass^k "
          f"{s['pass_all_k']:.0%}; quality {s['quality']} (90% CI {s['quality_ci'][0]}-{s['quality_ci'][1]}); "
          f"judge self-spread {s['judge_spread']}; API-equivalent ${s['api_usd']} (subscription usage, not billed)")
    for f in s["flags"]:
        print(f"  flag: {f}")
    if vs:
        c = scoreboard.compare(s, scoreboard.summarise(vs))
        print(f"vs {vs} on {len(c['tasks'])} tasks: quality {c['quality_diff'][0]:+} "
              f"(90% CI {c['quality_diff'][1]:+}..{c['quality_diff'][2]:+}), pass rate {c['pass_diff'][0]:+} "
              f"(90% CI {c['pass_diff'][1]:+}..{c['pass_diff'][2]:+})")
        for k, (o, n) in c["grader_fail_changes"].items():
            print(f"  {k}: failed {o} -> {n}")


class Parser(argparse.ArgumentParser):
    """Coordinates like -68,-20 are values, not options. Subparsers are made with the parent's class,
    so every subcommand inherits this."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._negative_number_matcher = re.compile(r"^-\d+(,-?\d+)*$")


def main():
    p = Parser(prog="mc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
    ev.add_argument("action", choices=["gate", "list", "brief", "reset", "check", "run", "judge", "report"])
    ev.add_argument("--tasks", help="run: comma-separated task ids (default: all)")
    ev.add_argument("--trials", type=int, default=3)
    ev.add_argument("--model", default="sonnet", help="run: the builder's model")
    ev.add_argument("--judge-model", default="opus")
    ev.add_argument("--label", help="run: what changed, for the report")
    ev.add_argument("--concurrency", type=int, default=5)
    ev.add_argument("--vs", help="report: compare with this older run")
    ev.add_argument("--force", action="store_true", help="judge: re-judge trials that already have scores")
    ev.add_argument("--plan", help="check: the plan to grade (default: the task's reference)")
    ev.add_argument("--offline", action="store_true", help="gate: skip the checks that need the server")
    ev.add_argument("task", nargs="?")
    ev.add_argument("--run")
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
    sys.exit(code)


if __name__ == "__main__":
    main()
