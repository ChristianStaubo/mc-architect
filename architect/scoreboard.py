"""The capability report (docs/evals.md §9): per task and overall, with bootstrap intervals, pass@k and
pass^k, and paired comparisons between runs."""

import json
import random
from collections import defaultdict
from pathlib import Path

from . import trials

ROOT = Path(__file__).resolve().parent.parent
COMMITTED = ROOT / "evals" / "results"


def boot(xs, stat=lambda v: sum(v) / len(v), n=2000, seed=7):
    """stat and its 90% bootstrap interval."""
    if not xs:
        return None, None, None
    rnd = random.Random(seed)
    sims = sorted(stat([rnd.choice(xs) for _ in xs]) for _ in range(n))
    return round(stat(xs), 2), round(sims[int(n * 0.05)], 2), round(sims[int(n * 0.95)], 2)


def by_task(recs):
    out = defaultdict(list)
    for r in recs:
        out[r["task"]].append(r)
    return dict(sorted(out.items()))


def summarise(run):
    recs = trials.trial_records(run)
    tasks = {}
    for tid, rs in by_task(recs).items():
        graded = [r for r in rs if r["end"] != "error"]
        qm, *qci = boot([r["quality"] for r in graded if r.get("quality") is not None])
        tasks[tid] = {
            "trials": len(rs), "errors": len(rs) - len(graded),
            "passed": sum(r["pass"] for r in graded),
            "pass_at_k": any(r["pass"] for r in graded), "pass_all_k": bool(graded) and all(r["pass"] for r in graded),
            "quality": qm, "quality_ci": qci,
            "api_usd": round(sum(r.get("api_usd") or 0 for r in rs) + sum(r.get("judge_api_usd") or 0 for r in rs), 2),
            "minutes": round(sum(r.get("minutes") or 0 for r in rs) / len(rs), 1),
            "calls": round(sum((r.get("tools") or {}).get("calls", 0) for r in rs) / len(rs), 1),
            "stucks": sum((r.get("tools") or {}).get("stucks", 0) for r in rs),
            "ends": sorted({r["end"] for r in rs}),
            "grader_fails": dict(_grader_fails(graded)),
        }
    qm, *qci = boot([r["quality"] for r in recs if r.get("quality") is not None])
    spread = [abs(a - b) for r in recs for a, b in r.get("judge_repeat", [])]
    s = {
        "run": run, "manifest": json.loads((trials.RESULTS / run / "manifest.json").read_text()),
        "trials": len(recs), "pass_rate": round(sum(r["pass"] for r in recs) / max(len(recs), 1), 2),
        "pass_at_k": round(sum(t["pass_at_k"] for t in tasks.values()) / max(len(tasks), 1), 2),
        "pass_all_k": round(sum(t["pass_all_k"] for t in tasks.values()) / max(len(tasks), 1), 2),
        "quality": qm, "quality_ci": qci,
        "judge_spread": round(sum(spread) / len(spread), 2) if spread else None,
        "api_usd": round(sum(t["api_usd"] for t in tasks.values()), 2),
        "tasks": tasks,
    }
    s["flags"] = flags(s)
    return s


def save(s):
    """The summary, committed (small) next to the code it measured."""
    COMMITTED.mkdir(parents=True, exist_ok=True)
    (COMMITTED / f"{s['run']}.json").write_text(json.dumps(s, indent=1))
    return s


def runs():
    """Capability runs, oldest first."""
    return sorted(p.parent.name for p in trials.RESULTS.glob("*/manifest.json"))


def _grader_fails(recs):
    out = defaultdict(int)
    for r in recs:
        for g in r.get("graders", []):
            if not g["pass"]:
                out[g["grader"]] += 1
    return out


def flags(s):
    out = []
    for tid, t in s["tasks"].items():
        if t["trials"] and not t["passed"]:
            out.append(f"{tid}: no trial passed (too hard, or a broken task/grader?)")
        if t["errors"]:
            out.append(f"{tid}: {t['errors']} trials errored (harness, not builder)")
    if s["pass_rate"] > 0.8:
        out.append("pass rate over 80%: add harder tasks")
    if s["judge_spread"] and s["judge_spread"] > 1.5:
        out.append(f"judges disagree with themselves by {s['judge_spread']} on average: the rubric is too vague")
    return out


def compare(new, old):
    """Two summaries paired by task: difference in mean quality and pass rate, with a bootstrap interval."""
    a, b = new["tasks"], old["tasks"]
    common = sorted(set(a) & set(b))
    dq = [a[t]["quality"] - b[t]["quality"] for t in common if a[t]["quality"] is not None and b[t]["quality"] is not None]
    dp = [a[t]["passed"] / a[t]["trials"] - b[t]["passed"] / b[t]["trials"] for t in common if a[t]["trials"] and b[t]["trials"]]
    gr = {}
    for t in common:
        for g in set(a[t]["grader_fails"]) | set(b[t]["grader_fails"]):
            if a[t]["grader_fails"].get(g, 0) != b[t]["grader_fails"].get(g, 0):
                gr[f"{t}/{g}"] = (b[t]["grader_fails"].get(g, 0), a[t]["grader_fails"].get(g, 0))
    return {"tasks": common, "quality_diff": boot(dq), "pass_diff": boot(dp), "grader_fail_changes": gr}
