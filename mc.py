#!/usr/bin/env python3
"""mc: the agent's one tool for the Minecraft test server.

Build
  mc site X,Z [W,D]                 terrain around X,Z: heights, surface, top-down map
  mc place PLAN [--at X,Z | --near PLAYER] [--task T] [--dry-run]
             [--foundation BLOCK|none] [--y Y] [--no-clear]
                                    build a plan (plans/NAME or a .py path) on the ground there:
                                    local (0,0,0) at X,Z, y 0 one above the median ground; foundation
                                    fills down to the terrain, the hill inside the box is cleared
  mc undo [EDIT]                    undo the latest edit, or EDIT (e.g. e12); survives restarts
  mc edits                          live edits (id, label, task, box)
Look and judge
  mc shots [EDIT]                   contact sheet: 4 corner views, top-down, floor plan (critic input)
  mc render X1,Y1,Z1 X2,Y2,Z2       isometric picture of any region
  mc audit [EDIT] [--friction]      hard checks (floating, doors, beds, sealed rooms, dark floors, panes)
                                    exit 2 on a fail; --friction files a friction report for it
When the tools fall short
  mc stuck "<goal> | <what you tried> | <what happened>"   save a friction report, then STOP
  mc friction [--all] | resolve ID "<fix>" --cause C | stats
Evals
  mc eval list | brief T --run R | reset T | record T --run R [--critique FILE] | report [R]
Server
  mc doctor | status | restart | cmd "<command>"  (cmd refuses stop/restart/reload)

Every call is logged to local/runs/commands.jsonl with MC_RUN_ID. Pictures: local/renders/.
"""

import argparse
import importlib.util
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from architect import audit as auditing  # noqa: E402
from architect import bridge, edits, evals, journal, render  # noqa: E402

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
    x, z = ints(a.center)
    w, d = ints(a.size) if a.size else (48, 48)
    cols = bridge.heightmap((x - w // 2, z - d // 2), (x + w // 2, z + d // 2))
    ys = [v[0] for v in cols.values()]
    surface = {}
    for _, b in cols.values():
        n = render.block_name(b)
        surface[n] = surface.get(n, 0) + 1
    path = out_path(f"site-{x}_{z}")
    render.top_down(cols, path)
    print(f"site {w}x{d} around {x},{z} (x {x - w // 2}..{x + w // 2}, z {z - d // 2}..{z + d // 2}): "
          f"ground y {min(ys)}..{max(ys)} (median {statistics.median(ys):.0f}, spread {max(ys) - min(ys)})")
    print("surface: " + ", ".join(f"{k} {v * 100 // len(ys)}%" for k, v in
                                  sorted(surface.items(), key=lambda kv: -kv[1])[:6]))
    print(f"map (north up, brighter = higher): {path}")


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


def ground_cells(build, at, foundation="cobblestone", floor_y=None, clear=True):
    """World cells for a build whose local (0, 0, 0) corner goes at X,Z on the ground: local y 0 sits one
    above the median ground height (or at floor_y); columns below the footprint are filled down to the
    terrain with `foundation` ("none": leave them, e.g. posts over water), and terrain inside the build's
    box (a hill) is cleared to air unless clear is False."""
    (lx0, ly0, lz0), (lx1, ly1, lz1) = build.bounds()
    x, z = at
    cols = bridge.heightmap((x + lx0, z + lz0), (x + lx1, z + lz1))
    foot = build.footprint()
    heights = [cols[(x + fx, z + fz)][0] for fx, fz in foot]
    y0 = floor_y if floor_y is not None else int(statistics.median(heights)) + 1
    cells = {}
    for (fx, fz) in foot:
        g = cols[(x + fx, z + fz)][0]
        if foundation != "none":
            for y in range(g + 1, y0 + ly0):  # foundation down to the ground
                cells[(x + fx, y, z + fz)] = foundation
        if clear:
            for y in range(y0 + ly0, max(g, y0 + ly1) + 1):  # clear the hill inside the footprint
                cells[(x + fx, y, z + fz)] = "air"
    for (bx, by, bz), blk in build.blocks.items():
        cells[(x + bx, y0 + by, z + bz)] = blk
    return cells, y0


def cmd_place(a):
    build = load_plan(a.plan)
    t = evals.task(a.task) if a.task else None
    if a.near:
        px, py, pz = player_pos(a.near)
        at = (px + 4, pz + 4)
    elif a.at:
        at = tuple(ints(a.at))
    elif t:
        at = tuple(t["plot"]["min"])
    else:
        s = bridge.status()["spawn"]
        at = (s[0] + 4, s[2] + 4)
    (lx0, _, lz0), (lx1, _, lz1) = build.bounds()
    print(f"{build.name}: {len(build.blocks)} blocks, footprint x {lx0}..{lx1} z {lz0}..{lz1} (local), " +
          ", ".join(f"{k} {v}" for k, v in list(build.counts().items())[:6]))
    if t and not evals.in_plot(t, (at[0] + lx0, 0, at[1] + lz0), (at[0] + lx1, 0, at[1] + lz1)):
        sys.exit(f"refused: the build would cover x {at[0] + lx0}..{at[0] + lx1}, z {at[1] + lz0}..{at[1] + lz1}; "
                 f"plot is x {t['plot']['min'][0]}..{t['plot']['max'][0]}, z {t['plot']['min'][1]}..{t['plot']['max'][1]}")
    if a.dry_run:
        path = out_path(f"{build.name}-preview")
        imgs = [render.iso(build.blocks, view=v) for v in ("se", "nw")]
        render.sheet(imgs, path, columns=2)
        print(f"dry run, nothing placed. preview (two opposite corners): {path}")
        return
    cells, y0 = ground_cells(build, at, a.foundation, a.y, not a.no_clear)
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
    cells = around(e, margin=2, below=2, above=1)
    lo, hi = e["min"], e["max"]
    build = {p: b for p, b in cells.items() if lo[1] - 1 <= p[1]}
    imgs = [render.iso(build, view=v) for v in ("se", "sw", "nw", "ne")]
    cols = {}
    for (x, y, z), b in cells.items():
        if not render.skipped(b) and (cols.get((x, z), (-999,))[0] < y):
            cols[(x, z)] = (y, b)
    imgs.append(render.top_down(cols, scale=8))
    floor = e.get("floor_y", lo[1]) + 1
    imgs.append(render.plan(cells, floor))
    path = out_path(f"{e['label']}-{e['id']}-shots")
    render.sheet(imgs, path, columns=3)
    return path, floor


def cmd_shots(a):
    e = latest_edit(a.id)
    path, floor = shots(e)
    print(f"{path}\nlayout: row 1 = views from four corners (SE, SW, NW, NE: the first three), "
          f"row 2 = NE view, top-down (north up), floor plan at y {floor} (north up)")


def cmd_render(a):
    lo, hi = ints(a.lo), ints(a.hi)
    cells = bridge.region([min(p) for p in zip(lo, hi)], [max(p) for p in zip(lo, hi)])
    path = out_path("region")
    w, h, _ = render.iso(cells, path, tile=a.tile, view=a.view)
    print(f"{path} ({w}x{h})")


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
              f"{builds} builds placed: {builds / max(1, len(rs)):.1f} builds per stop")
        print("by cause: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: -kv[1])))
        print(f"repeats (a fix that didn't hold): {sum(1 for r in rs if r.get('repeat_of'))}")
    else:
        for r in journal.reports(include_resolved=a.all):
            print(f"{r['id']}  [{r['status']}] run {r['run'] or '-'}: {r['report'][:150]}")


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
    s.add_argument("center", help="X,Z")
    s.add_argument("size", nargs="?", help="W,D (default 48,48)")
    pl = sub.add_parser("place")
    pl.add_argument("plan")
    pl.add_argument("--at", help="X,Z of the build's local (0,0) corner")
    pl.add_argument("--near", help="a player's name: build a few blocks from them")
    pl.add_argument("--task", help="an eval task: the build must fit its plot")
    pl.add_argument("--dry-run", action="store_true")
    pl.add_argument("--foundation", default="cobblestone", help="block under the footprint down to the ground, or none")
    pl.add_argument("--y", type=int, help="world y of the plan's y 0 (default: one above the median ground)")
    pl.add_argument("--no-clear", action="store_true", help="keep terrain inside the build's box")
    r = sub.add_parser("render")
    r.add_argument("lo")
    r.add_argument("hi")
    r.add_argument("--tile", type=int, default=8)
    r.add_argument("--view", default="se", choices=list(render.ROTATIONS))
    for n in ("undo", "shots", "audit"):
        x = sub.add_parser(n)
        x.add_argument("id", nargs="?")
        if n == "audit":
            x.add_argument("--friction", action="store_true")
    st = sub.add_parser("stuck")
    st.add_argument("text")
    f = sub.add_parser("friction")
    f.add_argument("action", nargs="?", choices=["list", "resolve", "stats"], default="list")
    f.add_argument("id", nargs="?")
    f.add_argument("fix", nargs="?")
    f.add_argument("--cause")
    f.add_argument("--repeat-of")
    f.add_argument("--all", action="store_true")
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
    code, err = 0, None
    try:
        code = globals()["cmd_" + a.cmd](a) or 0
    except bridge.BridgeError as e:
        code, err = 1, f"error: {e}"
    except SystemExit as e:
        code, err = (e.code if isinstance(e.code, int) else 1), (e.code if isinstance(e.code, str) else None)
    except Exception as e:  # a tool bug: record it, then show it
        journal.log(a.cmd, sys.argv[2:], int((time.time() - t0) * 1000), False, repr(e))
        raise
    journal.log(a.cmd, sys.argv[2:], int((time.time() - t0) * 1000), code == 0, err)
    if err:
        print(err, file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
