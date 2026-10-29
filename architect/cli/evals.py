"""Evals: the regression gate, task checks, capability runs, judging and the report (docs/evals.md)."""


from .. import evals, graders, sites
from ..run import mc as run_mc
from .common import load_plan, shots, ROOT


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
            ok, out = run_mc("place", plan, "--task", t["id"], *args)
            print(out)
            if not ok:
                raise SystemExit(f"place failed: {out[-300:]}")
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
    elif a.action == "scenarios":  # the in-game architect's behaviour suite (docs/in-game-architect.md)
        from .. import scenarios
        rec = scenarios.run(a.tasks.split(",") if a.tasks else None, a.model,
                            log=lambda m: print(m, flush=True))
        for r in rec["scenarios"]:
            print(f"{'PASS' if r['pass'] else 'FAIL'} {r['id']}")
        print(f"{rec['passed']}/{rec['total']} scenarios pass ({rec['run']})")
        return 0 if rec["passed"] == rec["total"] else 1
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


def register(sub):
    ev = sub.add_parser("eval")
    ev.add_argument("action", choices=["gate", "list", "brief", "reset", "check", "run", "judge", "report", "scenarios"])
    ev.add_argument("--tasks", help="run/scenarios: comma-separated task or scenario ids (default: all)")
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
    ev.set_defaults(fn=cmd_eval)
