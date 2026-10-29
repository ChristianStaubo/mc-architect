#!/usr/bin/env python3
"""mc: the agent's one tool for the Minecraft test server.

  mc doctor                         is Docker, the server and the bridge up?
  mc status                         players, world, recent edits
  mc cmd "<command>"                run a server command (as the console; not stop/restart/reload)
  mc restart                        restart the server container (world saves first)
  mc site X,Z [W,D]                 terrain around X,Z: heights, surface, top-down map
  mc place PLAN [--at X,Z | --near PLAYER] [--dry-run]
                                    build plans/PLAN.py on the ground there (foundation + clearing)
  mc render X1,Y1,Z1 X2,Y2,Z2       isometric picture of a region of the world
  mc undo [ID]                      undo the latest edit (or check it is ID)
  mc history                        edits that can be undone

Pictures go to local/renders/. Plans are Python files whose build() returns an architect.build.Build.
"""

import argparse
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from architect import bridge, render  # noqa: E402
from architect.build import payload  # noqa: E402

RENDERS = ROOT / "local" / "renders"


def out_path(stem):
    RENDERS.mkdir(parents=True, exist_ok=True)
    return RENDERS / f"{time.strftime('%Y%m%d-%H%M%S')}-{stem}.png"


def ints(s):
    return [int(v) for v in s.split(",")]


def cmd_doctor(_):
    ok = True
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", "mc-architect"],
                       capture_output=True, text=True)
    state = r.stdout.strip() or "missing"
    print(f"container: {state}")
    ok &= state == "running"
    try:
        s = bridge.status()
        print(f"bridge: ok, Minecraft {s['minecraft']}, TPS {s['tps']:.1f}, "
              f"{len(s['players'])} online, {s['edits']} undoable edits")
    except bridge.BridgeError as e:
        print(f"bridge: {e}")
        ok = False
    if not ok:
        print("fix: docker compose up -d  (plugin: scripts/build-plugin.sh, then docker compose restart)")
    return 0 if ok else 1


def cmd_status(_):
    print(json.dumps(bridge.status(), indent=2))


def cmd_cmd(a):
    first = a.command.lstrip("/").split()[0].lower() if a.command.strip() else ""
    if first in ("stop", "restart", "reload", "rl"):
        # Paper's /restart only stops the server here (no restart script); /reload breaks plugins.
        sys.exit(f"refused: '{first}' from inside the game. Use: mc restart")
    r = bridge.command(a.command)
    print("\n".join(r["output"]) or ("ok" if r["ok"] else "failed"))
    return 0 if r["ok"] else 1


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
    print(f"site {w}x{d} around {x},{z}: ground y {min(ys)}..{max(ys)} "
          f"(median {statistics.median(ys):.0f}, spread {max(ys) - min(ys)})")
    print("surface: " + ", ".join(f"{k} {v * 100 // len(ys)}%" for k, v in
                                  sorted(surface.items(), key=lambda kv: -kv[1])[:6]))
    print(f"map (north up): {path}")


def load_plan(name):
    path = Path(name)
    if not path.exists():
        path = ROOT / "plans" / f"{name.removesuffix('.py')}.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build()


def ground_cells(build, at, foundation="cobblestone"):
    """World cells for a build whose local (0, 0, 0) corner goes at X,Z on the ground: the floor sits one
    above the median ground height; columns below the footprint are filled down to the terrain, and
    terrain inside the build's box (a hill) is cleared to air."""
    (lx0, ly0, lz0), (lx1, ly1, lz1) = build.bounds()
    x, z = at
    cols = bridge.heightmap((x + lx0, z + lz0), (x + lx1, z + lz1))
    foot = build.footprint()
    heights = [cols[(x + fx, z + fz)][0] for fx, fz in foot]
    y0 = int(statistics.median(heights)) + 1
    cells = {}
    for (fx, fz) in foot:
        g = cols[(x + fx, z + fz)][0]
        for y in range(g + 1, y0 + ly0):  # foundation down to the ground
            cells[(x + fx, y, z + fz)] = foundation
        for y in range(y0 + ly0, max(g, y0 + ly1) + 1):  # clear the hill inside the footprint
            cells[(x + fx, y, z + fz)] = "air"
    for (bx, by, bz), blk in build.blocks.items():
        cells[(x + bx, y0 + by, z + bz)] = blk
    return cells, y0


def cmd_place(a):
    build = load_plan(a.plan)
    if a.near:
        px, py, pz = player_pos(a.near)
        at = (px + 4, pz + 4)
    elif a.at:
        at = tuple(ints(a.at))
    else:
        s = bridge.status()["spawn"]
        at = (s[0] + 4, s[2] + 4)
    print(f"{build.name}: {len(build.blocks)} blocks, " +
          ", ".join(f"{k} {v}" for k, v in list(build.counts().items())[:6]))
    if a.dry_run:
        path = out_path(f"{build.name}-preview")
        render.iso(build.blocks, path)
        print(f"dry run, nothing placed. preview: {path}")
        return
    cells, y0 = ground_cells(build, at)
    t = time.time()
    edit = bridge.place(payload(cells, label=build.name))
    print(f"placed edit {edit['id']} at {at[0]},{y0},{at[1]}: {edit['changed']} blocks changed "
          f"in {time.time() - t:.1f}s, box {edit['min']}..{edit['max']}")
    lo, hi = edit["min"], edit["max"]
    shot = bridge.region((lo[0] - 3, lo[1] - 3, lo[2] - 3), (hi[0] + 3, hi[1] + 2, hi[2] + 3))
    path = out_path(f"{build.name}-placed")
    render.iso(shot, path)
    print(f"render: {path}")
    print(f"see it: /tp {at[0] + 4} {y0 + 2} {at[1] + 12}  (undo: mc undo {edit['id']})")


def cmd_render(a):
    lo, hi = ints(a.lo), ints(a.hi)
    cells = bridge.region([min(p) for p in zip(lo, hi)], [max(p) for p in zip(lo, hi)])
    path = out_path("region")
    w, h = render.iso(cells, path, tile=a.tile)
    print(f"{path} ({w}x{h})")


def cmd_undo(a):
    r = bridge.undo(a.id)
    u = r["undone"]
    print(f"undid edit {u['id']} ({u['label']}): {u['changed']} blocks restored")


def cmd_history(_):
    for e in bridge.history():
        print(f"{e['id']:>4}  {e['label']:<20} {e['changed']:>7} blocks  {e['min']}..{e['max']}")


def main():
    p = argparse.ArgumentParser(prog="mc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("status")
    sub.add_parser("restart")
    c = sub.add_parser("cmd")
    c.add_argument("command")
    s = sub.add_parser("site")
    s.add_argument("center", help="X,Z")
    s.add_argument("size", nargs="?", help="W,D (default 48,48)")
    pl = sub.add_parser("place")
    pl.add_argument("plan")
    pl.add_argument("--at", help="X,Z of the build's corner")
    pl.add_argument("--near", help="a player's name: build a few blocks from them")
    pl.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("render")
    r.add_argument("lo")
    r.add_argument("hi")
    r.add_argument("--tile", type=int, default=8)
    u = sub.add_parser("undo")
    u.add_argument("id", nargs="?", type=int)
    sub.add_parser("history")
    a = p.parse_args()
    try:
        sys.exit(globals()["cmd_" + a.cmd.replace("-", "_")](a) or 0)
    except bridge.BridgeError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
