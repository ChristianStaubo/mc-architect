"""The regression suite (docs/evals.md §4.1): things that already work and must keep working, checked by
code, no models. `mc eval gate` runs it; it should always be 100%.

Offline checks need nothing running: the unit tests, every part built into a small reference plan and
audited in a flat test world, every example plan audited the same way. Server checks need the test
server: block names valid on this server, place + undo restoring a scratch plot exactly, the door's
live test, and replays of past tool-bug incidents (which must pass once fixed)."""

import json
import subprocess
import sys
import time
from pathlib import Path

from . import audit, blocks, bridge, edits, incidents, journal, parts
from .build import Build
from .build import load as build_load

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "local" / "evals" / "regression"
SCRATCH = (300, 360)  # a scratch plot away from the eval plots and the town


# ---- reference plans, one per part (each must audit clean in a flat world) ----

def _house(name, w=8, d=6, h=3):
    b = Build(name)
    parts.floor(b, 0, 0, w, d, 0, "stone_bricks")
    parts.walls(b, 0, 0, w, d, 1, h, "oak_planks", corner="oak_log[axis=y]")
    parts.clear_inside(b, 0, 0, w, d, 1, h + 1)
    parts.floor(b, 0, 0, w, d, h + 1, "oak_planks")
    parts.door(b, w // 2, 1, d, "south")
    parts.light(b, 2, 1, 2)
    parts.light(b, w - 2, 1, d - 2)
    return b


def ref_walls_door_window():
    b = _house("walls")
    parts.window(b, 2, 2, 0, "x", width=2)
    parts.window(b, 0, 2, 2, "z", width=2)
    return b


def ref_timber_gable():
    b = Build("timber-gable")
    parts.floor(b, 0, 0, 10, 6, 0, "stone_bricks")
    parts.timber_frame(b, 0, 0, 10, 6, 1, 4, "white_terracotta", post="dark_oak_log[axis=y]", beam="dark_oak_log")
    parts.clear_inside(b, 0, 0, 10, 6, 1, 9)
    parts.door(b, 5, 1, 6, "south")
    parts.light(b, 3, 1, 3)
    parts.light(b, 7, 1, 3)
    parts.gable_roof(b, 0, 0, 10, 6, 5, "dark_oak_stairs", "white_terracotta", ridge="x")
    return b


def ref_roofs_dormer():
    b = Build("roofs")
    parts.floor(b, 0, 0, 12, 6, 0, "stone_bricks")
    parts.floor(b, 0, 7, 5, 12, 0, "stone_bricks")
    parts.timber_frame(b, 0, 0, 12, 6, 1, 4, "white_terracotta", post="dark_oak_log[axis=y]", beam="dark_oak_log")
    parts.timber_frame(b, 0, 6, 5, 12, 1, 4, "white_terracotta", post="dark_oak_log[axis=y]", beam="dark_oak_log")
    parts.clear_inside(b, 0, 0, 12, 6, 1, 10)
    parts.clear_inside(b, 0, 6, 5, 12, 1, 10)
    b.set(3, 1, 6, "air")
    b.set(3, 2, 6, "air")  # the two wings open into each other
    parts.door(b, 9, 1, 6, "south")
    for x, z in ((3, 3), (9, 3), (3, 9)):
        parts.light(b, x, 1, z)
    main = dict(x1=0, z1=0, x2=12, z2=6, y=5, stair="dark_oak_stairs", gable="white_terracotta", ridge="x")
    wing = dict(x1=0, z1=6, x2=5, z2=12, y=5, stair="dark_oak_stairs", gable="white_terracotta", ridge="z")
    parts.roofs(b, main, wing)
    parts.dormer_on(b, parts.gable_roof(Build(), **main), 9, "front", "white_terracotta")
    return b


def ref_stairs():
    b = _house("stairs", h=6)
    parts.floor(b, 1, 1, 7, 5, 4, "oak_planks")  # an upper floor
    parts.straight_stairs(b, 2, 1, 1, "east", 3, "oak_stairs", support="oak_planks")
    parts.light(b, 6, 5, 4)
    return b


def ref_spiral_tower():
    b = Build("spiral")
    parts.floor(b, 0, 0, 6, 6, 0, "stone_bricks")
    parts.walls(b, 0, 0, 6, 6, 1, 12, "stone_bricks")
    parts.clear_inside(b, 0, 0, 6, 6, 1, 12)
    parts.door(b, 1, 1, 6, "south")
    parts.spiral_stairs(b, 1, 1, 5, 5, 1, 11, "stone_brick_stairs", "stone_bricks", start=2)
    parts.hip_roof(b, 0, 0, 6, 6, 13, "dark_oak_stairs")  # open to the roof: a floor here leaves a sealed attic
    for y in (1, 5, 9):
        parts.light(b, 3, y, 3)
        b.fill(3, 0, 3, 3, y - 1, 3, "stone_bricks")  # a lantern post up the middle
    return b


def ref_details():
    b = _house("details")
    parts.window(b, 1, 2, 6, "x", width=2)  # shutters at x 0 and 3: clear of the door at x 4
    parts.shutters(b, 1, 2, 6, "x", 2, 1, "south")
    parts.flower_box(b, 1, 2, 6, "x", 2, "south")
    parts.chimney(b, 1, 1, 5, 9)
    parts.outside_stair(b, 9, 1, 1, "south", 3, side="east")
    parts.awning(b, 1, 4, 0, 3, "north")
    return b


def ref_round_tower():
    b = Build("round")
    parts.floor(b, -2, -2, 2, 2, 0, "spruce_planks")
    parts.round_tower(b, 0, 0, 1, 8, 2, "stone_bricks")
    parts.cone_roof(b, 0, 0, 9, 2, "dark_oak_stairs")
    parts.door(b, 0, 1, 2, "south")
    parts.light(b, 0, 1, 0)
    return b


def ref_dock():
    b = Build("dock")
    parts.dock(b, 0, 0, 8, 2, 0, -3, boats=0)
    return b


REFERENCES = {f.__name__[4:]: f for f in (ref_walls_door_window, ref_timber_gable, ref_roofs_dormer, ref_stairs,
                                          ref_spiral_tower, ref_details, ref_round_tower, ref_dock)}


def flat_world(build, ground_y=0, margin=3, above=6):
    """A stone world with its surface at ground_y and the build's y 0 one above it, plus the box to audit."""
    (x0, y0, z0), (x1, y1, z1) = build.bounds()
    cells = {}
    for x in range(x0 - margin, x1 + margin + 1):
        for z in range(z0 - margin, z1 + margin + 1):
            for y in range(min(y0 + ground_y, ground_y) - 3, y1 + ground_y + above):
                cells[(x, y, z)] = "stone" if y <= ground_y else "air"
    for (x, y, z), b in build.blocks.items():
        cells[(x, y + ground_y + 1, z)] = b
    box = ((x0, y0 + ground_y + 1, z0), (x1, y1 + ground_y + 1, z1))
    return cells, box


load_plan = build_load


def example_plans():
    return sorted((ROOT / "plans").glob("*.py"))


# ---- checks: each returns (ok, detail) ----

def check_unit_tests():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-q", "tests"], cwd=ROOT,
                       capture_output=True, text=True)
    last = (r.stderr.strip().splitlines() or ["?"])
    ran = next((l for l in last if l.startswith("Ran ")), "")
    return r.returncode == 0, f"{ran}; {last[-1]}"


def _audit_offline(build):
    cells, box = flat_world(build)
    r = audit.audit(cells, box)
    return r["fails"] == 0, ", ".join(c["msg"] for c in r["checks"] if c["level"] == "fail") or "clean"


def check_part(name):
    return lambda: _audit_offline(REFERENCES[name]())


def check_example_plan(path):
    return lambda: _audit_offline(load_plan(path))


def check_block_names():
    names = set()
    for f in REFERENCES.values():
        names |= set(f().blocks.values())
    for p in example_plans():
        names |= set(load_plan(p).blocks.values())
    names = sorted(n for n in names if not blocks.is_air(n))
    bad = bridge.call("/validate", {"blocks": names})["invalid"]
    return not bad, f"{len(names)} block states valid" if not bad else "; ".join(f"{x['block']}: {x['error']}" for x in bad)


def check_place_undo():
    """Place a reference house on scratch ground (as `place` would), undo it through the snapshot, and the
    ground must be back block for block."""
    from .placement import ground_cells
    b = REFERENCES["timber_gable"]()
    cells, _ = ground_cells(b, SCRATCH)
    lo = tuple(min(p[i] for p in cells) - 1 for i in range(3))
    hi = tuple(max(p[i] for p in cells) + 1 for i in range(3))
    bridge.command(f"forceload add {lo[0]} {lo[2]} {hi[0]} {hi[2]}")
    try:
        before = bridge.region(lo, hi)
        e = edits.place(cells, "regression-place-undo", run="regression")
        placed = bridge.region(lo, hi)
        r = audit.audit(placed, (tuple(e["min"]), tuple(e["max"])))
        edits.place({(9999, 70, 9999): "stone"}, "regression-other", run="regression")  # not the latest any more
        edits.undo(e["id"])
        edits.undo(edits.newest("regression")["id"])
        after = bridge.region(lo, hi)
    finally:
        bridge.command(f"forceload remove {lo[0]} {lo[2]} {hi[0]} {hi[2]}")
    diff = sum(1 for p in before if before[p] != after.get(p))
    ok = diff == 0 and r["fails"] == 0
    return ok, f"placed {e['changed']} blocks, audit {r['fails']} fail, undo via snapshot, {diff} blocks differ after"


def check_door_live():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "test_door_live.py")], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    out = r.stdout.strip().splitlines()
    for e in edits.listing():  # leave nothing behind
        if e["label"] == "test-door":
            edits.undo(e["id"])
    verdict = out[-1] if out else r.stderr.strip()[-200:]
    return verdict.startswith("PASS"), verdict


def check_replays():
    """Every incident that came from a tool bug (crash / bridge), now resolved, must replay cleanly."""
    resolved = {r.get("incident") for r in journal.reports(include_resolved=True)
                if r.get("incident") and r["status"] == "resolved"}
    todo = [i for i in incidents.listing() if i["kind"] in ("crash", "bridge") and i["id"] in resolved]
    if not todo:
        return True, "no resolved tool-bug incidents to replay"
    failed = []
    for i in todo:
        r = subprocess.run([sys.executable, str(ROOT / "mc.py"), "incident", i["id"], "replay"], cwd=ROOT,
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            failed.append(i["id"])
    return not failed, f"{len(todo) - len(failed)}/{len(todo)} replay cleanly" + (f"; failing: {failed}" if failed else "")


def check_reference(tid):
    """A capability task's reference plan, built on its reset site, passes all the task's code graders:
    the task is solvable and the graders are fair (docs/evals.md §5.2). Leaves the reference standing."""
    def fn():
        r = subprocess.run([sys.executable, str(ROOT / "mc.py"), "eval", "check", tid], cwd=ROOT,
                           capture_output=True, text=True, timeout=300)
        lines = (r.stdout + r.stderr).strip().splitlines()
        fails = [ln.strip() for ln in lines if ln.strip().startswith("FAIL")]
        return r.returncode == 0, "; ".join(fails) or (lines[-1] if lines else "no output")
    return fn


def references():
    return sorted(p.stem for p in (ROOT / "evals" / "reference").glob("*.py"))


def checks(offline=False):
    """[(group, name, needs_server, fn)] in run order."""
    out = [("tests", "unit tests", False, check_unit_tests)]
    out += [("parts", n, False, check_part(n)) for n in REFERENCES]
    out += [("plans", p.stem, False, check_example_plan(p)) for p in example_plans()]
    if not offline:
        out += [("server", "block names", True, check_block_names),
                ("server", "place + undo", True, check_place_undo),
                ("server", "door live test", True, check_door_live),
                ("server", "incident replays", True, check_replays)]
        out += [("graders", tid, True, check_reference(tid)) for tid in references()]
    return out


def manifest():
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    lock = json.loads((ROOT / "deps.lock.json").read_text())
    return {"commit": git("rev-parse", "--short", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "minecraft": lock["minecraft"], "paper_build": lock["paper"]["build"],
            "worldedit": lock["worldedit"]["version"], "python": sys.version.split()[0]}


def run(offline=False):
    """Run the suite; returns the result record (also saved in local/evals/regression/)."""
    server_up = True
    if not offline:
        try:
            bridge.status()
        except bridge.BridgeError:
            server_up = False
    rows = []
    for group, name, needs_server, fn in checks(offline):
        t0 = time.time()
        if needs_server and not server_up:
            ok, detail, status = None, "server not running", "skipped"
        else:
            try:
                ok, detail = fn()
                status = "pass" if ok else "fail"
            except Exception as e:  # a check that crashes is a failing check
                ok, detail, status = False, f"{type(e).__name__}: {e}", "fail"
        rows.append({"group": group, "check": name, "status": status, "detail": detail,
                     "seconds": round(time.time() - t0, 1)})
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "suite": "regression", "offline": offline,
           "manifest": manifest(), "checks": rows,
           "passed": sum(r["status"] == "pass" for r in rows), "failed": sum(r["status"] == "fail" for r in rows),
           "skipped": sum(r["status"] == "skipped" for r in rows)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps(rec, indent=2))
    return rec
