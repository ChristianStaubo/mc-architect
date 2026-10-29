"""The eval suite: fixed briefs on fixed plots of the seeded world, and the scoreboard.

A task (evals/tasks/<id>.json) is a brief, a plot, a budget and expectations. A run builds every task
once; `record` joins what happened (edits, audit, the critic's scores, the journal's tool calls) into
local/evals/<run>/<task>.json, and `report` turns runs into the scoreboard."""

import json
from pathlib import Path

from . import journal

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"
RESULTS = ROOT / "local" / "evals"


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


def brief(tid, run):
    t = task(tid)
    (x0, z0), (x1, z1) = t["plot"]["min"], t["plot"]["max"]
    b = t["budget"]
    return "\n".join([
        f"TASK {tid} (run {run})",
        f"Brief: {t['brief']}",
        f"Style: {t.get('style', 'your choice, consistent')}",
        f"Plot: x {x0}..{x1}, z {z0}..{z1} (the whole build, roof overhangs included, must fit inside).",
        f"Budget: {b['calls']} mc calls, {b['minutes']} minutes.",
        f"Must have: {', '.join(t.get('must', [])) or '-'}",
        f"Every command: MC_RUN_ID={run}:{tid} ./mc.py ... ; place with --task {tid}.",
        f"Your plan file: local/plans/{run}/{tid}.py",
    ])


def tool_stats(run_task):
    """What the builder did, from the journal: run_task is "<run>:<task>" (its MC_RUN_ID)."""
    es = journal.entries(run_task)
    by = lambda c: [e for e in es if e["cmd"] == c]  # noqa: E731
    return {"calls": len(es), "failed": sum(not e["ok"] for e in es),
            "places": sum(1 for e in by("place") if "--dry-run" not in e["argv"]),
            "dry_runs": sum(1 for e in by("place") if "--dry-run" in e["argv"]),
            "undos": len(by("undo")), "stucks": len(by("stuck")),
            "seconds": round(sum(e["ms"] for e in es) / 1000, 1)}


def record(tid, run, edit, audit, critique):
    t = task(tid)
    tools = tool_stats(f"{run}:{tid}")
    quality = critique.get("overall") if critique else None
    must_fail = []
    if "door" in t.get("must", []) and audit["stats"]["doors"] < 1:
        must_fail.append("door")
    if "interior" in t.get("must", []) and audit["stats"]["indoor_floor"] < t.get("min_indoor_floor", 1):
        must_fail.append("interior")
    out = {"task": tid, "run": run, "edit": edit["id"] if edit else None,
           "pass": bool(edit) and audit["fails"] == 0 and not must_fail,
           "audit": {"fails": audit["fails"], "warns": audit["warns"],
                     "failed_checks": [c["check"] for c in audit["checks"] if c["level"] == "fail"]},
           "must_missing": must_fail, "quality": quality,
           "critique": critique, "tools": tools,
           "within_budget": tools["calls"] <= t["budget"]["calls"]}
    d = RESULTS / run
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tid}.json").write_text(json.dumps(out, indent=2))
    return out


def runs():
    return sorted(p.name for p in RESULTS.glob("*") if p.is_dir()) if RESULTS.exists() else []


def results(run):
    return [json.loads(p.read_text()) for p in sorted((RESULTS / run).glob("*.json"))
            if not p.name.endswith(".critique.json")]


def summary(run):
    rs = results(run)
    if not rs:
        return None
    q = [r["quality"] for r in rs if r["pass"] and r["quality"] is not None]
    return {"run": run, "tasks": len(rs), "passed": sum(r["pass"] for r in rs),
            "quality": round(sum(q) / len(q), 2) if q else None,
            "calls": round(sum(r["tools"]["calls"] for r in rs) / len(rs), 1),
            "failed_calls": sum(r["tools"]["failed"] for r in rs),
            "stops": sum(r["tools"]["stucks"] for r in rs),
            "over_budget": sum(not r["within_budget"] for r in rs)}
