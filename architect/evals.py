"""The eval tasks: fixed briefs on fixed plots of the seeded world (evals/tasks/<id>.json: brief, plot,
budget, graders), the builder's brief, and what a builder did according to the journal. Runs, grading
and reports: trials.py, graders.py, judges.py, scoreboard.py (docs/evals.md)."""

import json
from pathlib import Path

from . import graders, journal

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"
RESULTS = ROOT / "local" / "evals"   # capability runs, the regression suite's records, reference sheets
REFERENCES = RESULTS / "references"


def tasks():
    return {p.stem: json.loads(p.read_text()) for p in sorted(TASKS.glob("*.json"))}


def task(tid):
    t = tasks().get(tid)
    if not t:
        raise SystemExit(f"no task {tid}: {', '.join(tasks())}")
    return t


def in_plot(t, lo, hi):
    (px0, pz0), (px1, pz1) = t["plot"]["min"], t["plot"]["max"]
    return px0 <= lo[0] and hi[0] <= px1 and pz0 <= lo[2] and hi[2] <= pz1


def checks(t):
    return [graders.describe(g) for g in t.get("graders", []) if "code" in g]


def brief(tid, run, plan=None):
    """The builder's brief. With `plan`, run is the full MC_RUN_ID and is already in the environment."""
    t = task(tid)
    (x0, z0), (x1, z1) = t["plot"]["min"], t["plot"]["max"]
    b = t["budget"]
    lines = [
        f"TASK {tid} (run {run})",
        f"Brief: {t['brief']}",
        f"Style: {t.get('style', 'your choice, consistent')}",
        f"Plot: x {x0}..{x1}, z {z0}..{z1} (the whole build, roof overhangs included, must fit inside).",
        f"Budget: {b['calls']} mc calls, {b['minutes']} minutes" + (f", ${b['usd']}" if "usd" in b else "") + ".",
        "Checks your build must pass:", *([f"  - {c}" for c in checks(t)] or ["  -"]),
    ]
    if plan:
        lines += [f"Run commands as plain `./mc.py ...` (MC_RUN_ID is set for you); place with --task {tid}.",
                  f"Your plan file: {plan}"]
    else:
        lines += [f"Every command: MC_RUN_ID={run}:{tid} ./mc.py ... ; place with --task {tid}.",
                  f"Your plan file: local/plans/{run}/{tid}.py"]
    return "\n".join(lines)


def tool_stats(run_task):
    """What the builder did, from the journal: run_task is "<run>:<task>" (its MC_RUN_ID)."""
    es = journal.entries(run_task)
    by = lambda c: [e for e in es if e["cmd"] == c]  # noqa: E731
    # An audit that fails is the judge working, not a failed call: counted on its own.
    return {"calls": len(es), "failed": sum(not e["ok"] and e["cmd"] != "audit" for e in es),
            "audit_fails": sum(not e["ok"] and e["cmd"] == "audit" for e in es),
            "places": sum(1 for e in by("place") if "--dry-run" not in e["argv"]),
            "dry_runs": sum(1 for e in by("place") if "--dry-run" in e["argv"]),
            "undos": len(by("undo")), "stucks": len(by("stuck")),
            "seconds": round(sum(e["ms"] for e in es) / 1000, 1)}
