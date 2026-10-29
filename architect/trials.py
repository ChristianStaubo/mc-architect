"""The capability runner (docs/evals.md §7): every task, N trials each, one headless builder per trial.

A trial resets its site, runs `claude -p --agent mc-builder` in the repo with the tools fenced in, then
grades what's on the site with the task's code graders and draws its contact sheet. Trials of one task
run one after another (they share a plot); different tasks run side by side."""

import hashlib
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from . import claude, evals, graders, journal, judges, regression, sites

ROOT = evals.ROOT
RESULTS = evals.RESULTS
WORK = ROOT / "local" / "trials"  # live workspaces; moved under RESULTS (which builders can't read) when done
SECRET = ["local/evals/**", "local/plans/**", "evals/reference/**", "evals/sites/**", "evals/results/**",
          "evals/ratings.jsonl"]
HASHED = [".claude/agents/mc-builder.md", ".claude/skills/mc-build/SKILL.md", "STYLE.md", "CLAUDE.md",
          "evals/RUBRIC.md", "architect/parts.py"]


def _hash(paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(p.encode())
        h.update((ROOT / p).read_bytes() if (ROOT / p).exists() else b"-")
    return h.hexdigest()[:12]


def manifest(run, tids, trials, model, judge_model, label):
    """What this run ran on: the regression manifest (commit, versions) plus the run's own settings."""
    return {**regression.manifest(), "run": run, "suite": "capability", "label": label,
            "start": time.strftime("%Y-%m-%dT%H:%M:%S"), "builder_model": model, "judge_model": judge_model,
            "trials": trials, "tasks": tids,
            "hashes": {"harness": _hash(HASHED), "tasks": _hash([f"evals/tasks/{t}.json" for t in tids]),
                       "rubric": _hash(["evals/RUBRIC.md", "architect/judges.py"])}}


def trial_path(run, tid, i):
    d = RESULTS / run / tid / str(i)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(rec):
    (trial_path(rec["run"], rec["task"], rec["trial"]) / "trial.json").write_text(json.dumps(rec, indent=1))


def settings_file(run):
    """Builder permissions: read the repo, never the answers (other trials, references, scores)."""
    p = WORK / run / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"permissions": {"deny": [f"Read(./{s})" for s in SECRET]}}, indent=1))
    return p


def prompt(t, run_id, plan):
    return "\n".join([
        evals.brief(t["id"], run_id, plan=plan),
        "",
        "You are running headless in an eval: nobody will answer questions. Work through the mc-build "
        "skill, then end your turn with a short report (what you built, the last edit id, any gaps).",
    ])


def judge_trial(rec, t, model, repeat=False):
    """Judge scores on a trial record (in place); `repeat` judges it a second time to measure spread."""
    if not rec.get("sheet"):
        rec.update(scores=None, quality=None, judge_api_usd=0.0)
        return rec
    with ThreadPoolExecutor(2) as ex:  # the repeat runs alongside the first judging
        runs = list(ex.map(lambda _: judges.judge(t, rec["sheet"], model), range(2 if repeat else 1)))
    (scores, cost), again = runs[0], runs[1][0] if repeat else None
    cost += runs[1][1] if repeat else 0
    rec.update(scores=scores, quality=judges.quality(scores), judge_model=model)
    if repeat:
        rec["judge_repeat"] = [(scores[d]["score"], again[d]["score"]) for d in scores
                               if isinstance(scores[d]["score"], (int, float)) and isinstance(again[d]["score"], (int, float))]
    rec["judge_api_usd"] = round(cost, 3)
    return rec


def trial(run, t, i, model, settings, sheet, judge_model=None):
    tid = t["id"]
    run_id = f"{run}:{tid}:{i}"
    work = WORK / run / f"{tid}-{i}"
    work.mkdir(parents=True, exist_ok=True)
    plan = (work / "plan.py").relative_to(ROOT)
    sites.reset(tid)
    b = t["budget"]
    cmd = claude.command(prompt(t, run_id, str(plan)), model, claude.MC_TOOLS, b.get("usd", 3.0),
                         agent="mc-builder", settings=settings)
    env = {**os.environ, "MC_RUN_ID": run_id}
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=(b["minutes"] + 10) * 60)
        out, end = p.stdout, None
    except subprocess.TimeoutExpired as e:
        out, end = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
    minutes = round((time.time() - t0) / 60, 1)
    res = claude.result_of(out.splitlines())
    if end is None:
        end = claude.end_of(res)
    tools = evals.tool_stats(run_id)
    if tools["stucks"] and end == "done":
        end = "stuck"
    o = sites.outcome(t)
    grades = graders.run(t, o)
    d = trial_path(run, tid, i)
    (d / "transcript.jsonl").write_text(out)
    if (work / "plan.py").exists():
        shutil.copy(work / "plan.py", d / "plan.py")
    shutil.rmtree(work, ignore_errors=True)
    sheet_path = None
    if o.box:
        sheet_path = str(sheet(o.as_edit(f"{tid}-{i}"), d / "sheet.png", cells=o.after,
                               levels=o.audit["stats"]["indoor_levels"])[0])
    rec = {"run": run, "task": tid, "trial": i, "run_id": run_id, "model": model, "end": end,
           "pass": bool(grades) and all(g["pass"] for g in grades), "graders": grades,
           "box": [list(o.box[0]), list(o.box[1])] if o.box else None, "sheet": sheet_path,
           "tools": tools, "minutes": minutes, "api_usd": res.get("total_cost_usd"),
           "turns": res.get("num_turns"), "usage": res.get("usage"),
           "report": (res.get("result") or "")[-1500:]}
    if judge_model:
        judge_trial(rec, t, judge_model, repeat=(i == 1))
    save(rec)
    return rec


def run(tids, trials, model, label, sheet, judge_model=None, concurrency=5, log=print):
    run = "c" + time.strftime("%m%d-%H%M")
    (RESULTS / run).mkdir(parents=True, exist_ok=True)
    m = manifest(run, tids, trials, model, judge_model, label)
    (RESULTS / run / "manifest.json").write_text(json.dumps(m, indent=1))
    settings = settings_file(run)

    def one_task(tid):
        t = evals.task(tid)
        out = []
        for i in range(1, trials + 1):
            try:
                r = trial(run, t, i, model, settings, sheet, judge_model)
            except Exception as e:  # a harness failure is an error, not a fail
                r = {"run": run, "task": tid, "trial": i, "end": "error", "pass": False, "error": repr(e)}
                save(r)
            log(f"  {tid} #{i}: {'PASS' if r['pass'] else 'fail'} ({r['end']}, "
                f"{sum(g['pass'] for g in r.get('graders', []))}/{len(r.get('graders', []))} graders, "
                f"q {r.get('quality') or '-'}, API-equiv ${r.get('api_usd') or 0:.2f}, {r.get('minutes', '?')} min)")
            out.append(r)
        return out

    try:
        with sites.still(), ThreadPoolExecutor(concurrency) as ex:
            results = [r for rs in ex.map(one_task, tids) for r in rs]
    finally:
        m["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (RESULTS / run / "manifest.json").write_text(json.dumps(m, indent=1))
    journal.log("eval-run", [run], 0, True)
    return run, results


def trial_records(run):
    return [json.loads(p.read_text()) for p in sorted((RESULTS / run).glob("*/*/trial.json"))]
