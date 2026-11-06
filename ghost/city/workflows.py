"""The city as workflows: CityWorkflow orchestrates (plan, check, lay the ground, fan the plots out in a
sliding window), PlotWorkflow builds one plot (build, check, judge, one fix round). The orchestrator only
decides order and concurrency; every step that touches an agent, a file or the world is an activity."""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from . import activities as A

QUICK = {"start_to_close_timeout": timedelta(minutes=10), "retry_policy": RetryPolicy(maximum_attempts=3)}
AGENT = {"heartbeat_timeout": timedelta(minutes=2),
         "retry_policy": RetryPolicy(initial_interval=timedelta(minutes=2), backoff_coefficient=2.0,
                                     maximum_interval=timedelta(minutes=30), maximum_attempts=4)}
PASS_SCORE = 6   # a critic score below this (or a failing audit) earns one fix round


@workflow.defn
class PlotWorkflow:
    @workflow.run
    async def run(self, args: dict) -> dict:
        run, name, pid = args["run"], args["name"], args["plot"]
        await workflow.execute_activity(A.record_plot, args=[run, name, pid, "building", {}], **QUICK)
        b = await workflow.execute_activity(A.build_plot, args=[run, name, pid, None, None],
                                            start_to_close_timeout=timedelta(minutes=A.MINUTES["builder"] + 15), **AGENT)
        c = await workflow.execute_activity(A.check_plot, args=[run, name, pid], **QUICK)
        j = await workflow.execute_activity(A.judge_plot, args=[run, name, pid],
                                            start_to_close_timeout=timedelta(minutes=A.MINUTES["critic"] + 10), **AGENT)
        rounds = 1
        if b.get("session") and (not c["ok"] or (j.get("score") or 0) < PASS_SCORE):
            feedback = "\n".join(x for x in [f"Audit: {c['why']}" if not c["ok"] else "",
                                            f"Critic ({j.get('score')}/10): {j.get('fix', '')}"] if x)
            b2 = await workflow.execute_activity(A.build_plot, args=[run, name, pid, feedback, b["session"]],
                                                 start_to_close_timeout=timedelta(minutes=A.MINUTES["builder"] + 15), **AGENT)
            c = await workflow.execute_activity(A.check_plot, args=[run, name, pid], **QUICK)
            j2 = await workflow.execute_activity(A.judge_plot, args=[run, name, pid],
                                                 start_to_close_timeout=timedelta(minutes=A.MINUTES["critic"] + 10), **AGENT)
            j = {**j2, "first_score": j.get("score")}
            b = {**b2, "minutes": (b.get("minutes") or 0) + (b2.get("minutes") or 0),
                 "usd": (b.get("usd") or 0) + (b2.get("usd") or 0)}
            rounds = 2
        state = "done" if c["ok"] else "flawed"
        detail = {"edit": b.get("edit"), "rounds": rounds, "score": j.get("score"), "first_score": j.get("first_score"),
                  "audit_fails": c["fails"], "outside": c["outside"], "minutes": b.get("minutes"), "usd": b.get("usd"),
                  "denials": b.get("denials"), "fix": j.get("fix", "")[:300]}
        await workflow.execute_activity(A.record_plot, args=[run, name, pid, state, detail], **QUICK)
        return {"plot": pid, "state": state, **detail}


@workflow.defn
class CityWorkflow:
    def __init__(self):
        self.phase, self.done, self.total, self.running = "starting", 0, 0, []
        self.conc = None

    @workflow.signal
    def set_concurrency(self, n: int):
        """More (or fewer) builders at once, on a running build: the window grows as soon as it's set."""
        self.conc = max(1, int(n))

    @workflow.query
    def status(self) -> dict:
        return {"phase": self.phase, "done": self.done, "total": self.total, "running": self.running,
                "concurrency": self.conc}

    @workflow.run
    async def run(self, args: dict) -> dict:
        run, name = args["run"], args["name"]
        only, build = args.get("districts"), args.get("build", True)
        if self.conc is None:
            self.conc = args.get("concurrency", 4)

        self.phase = "planning the districts"
        await workflow.execute_activity(A.plan_macro, args=[run, name, args.get("plots", 140)],
                                        start_to_close_timeout=timedelta(minutes=A.MINUTES["macro"] + 15), **AGENT)
        dists = await workflow.execute_activity(A.districts, name, **QUICK)

        plan = lambda d, issues=None, infill=None: workflow.execute_activity(  # noqa: E731
            A.plan_district, args=[run, name, d, issues, infill],
            start_to_close_timeout=timedelta(minutes=A.MINUTES["district"] + 15), **AGENT)
        infill = args.get("infill") or {}   # {district: {covered, hole, count}}: fill hollow interiors
        if infill:
            self.phase = "filling in the districts"
            dists = [d for d in dists if d["id"] in infill]
            only = list(infill)
            await asyncio.gather(*(plan(d, None, infill[d["id"]]) for d in dists))
        else:
            self.phase = "planning the plots"   # every district planner at once: fan out, fan in
            await asyncio.gather(*(plan(d) for d in dists))
        for _ in range(2):  # repair rounds: each district fixes only its own problems
            chk = await workflow.execute_activity(A.merge_and_check, name, **QUICK)
            bad = {k: v for k, v in chk["by_district"].items() if v}
            if not bad:
                break
            await asyncio.gather(*(plan(d, bad[d["id"]]) for d in dists if d["id"] in bad))
        chk = await workflow.execute_activity(A.merge_and_check, name, **QUICK)
        if not build:
            self.phase = "planned"
            return {"phase": "planned", "plots": chk["plots"], "left": chk}

        self.phase = "laying the ground"
        await workflow.execute_activity(A.lay_ground, args=[run, name, only], start_to_close_timeout=timedelta(hours=3),
                                        heartbeat_timeout=timedelta(minutes=15), retry_policy=RetryPolicy(maximum_attempts=3))

        self.phase = "building"
        ids = await workflow.execute_activity(A.plot_ids, args=[name, only], **QUICK)
        ids = ids[: args.get("max_plots") or len(ids)]
        self.total, results, pending = len(ids), [], set()
        queue = list(ids)
        while queue or pending:  # a sliding window: never more than `conc` builders at once
            while queue and len(pending) < self.conc:
                pid = queue.pop(0)
                h = await workflow.start_child_workflow(PlotWorkflow.run, {"run": run, "name": name, "plot": pid},
                                                        id=f"city-{run}-{pid}", task_queue=A.QUEUE)
                pending.add(h)
                self.running = sorted(self.running + [pid])
            finished, still = await workflow.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            pending = set(still)   # (workflow.wait hands back lists)
            for h in finished:
                r = h.result()
                results.append(r)
                self.done += 1
                self.running = [p for p in self.running if p != r["plot"]]
        self.phase = "done"
        return {"plots": len(results), "done": sum(r["state"] == "done" for r in results)}
