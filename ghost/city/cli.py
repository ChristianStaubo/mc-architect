"""python -m ghost city start | status: start the city harness, or see how it's going."""

import argparse
import asyncio
import json
import time

from temporalio.client import Client

from architect import town as towns

from .. import config, db
from . import activities as A


async def _launch(a, workflow, args, note=""):
    """Start a city workflow: run id (given or NAME-MMDD-HHMM), workflow id city-<run> (status, decide and
    workers find it by that)."""
    run = a.run or f"{a.name}-{time.strftime('%m%d-%H%M')}"
    c = await Client.connect(config.TEMPORAL)
    await c.start_workflow(workflow, {"run": run, "name": a.name, **args}, id=f"city-{run}", task_queue=A.QUEUE)
    print(f"started city-{run}{note} (watch it at http://localhost:8233)")


async def _start(a):
    await _launch(a, "CityWorkflow", {
        "plots": a.plots, "concurrency": a.concurrency, "build": not a.plan_only,
        "districts": a.districts.split(",") if a.districts else None, "max_plots": a.max_plots,
        "infill": json.loads(a.infill) if a.infill else None})


async def _kits(a):
    """Build a town from kits (ghost/city/kitwork.py): its town.json names the kits to write."""
    keys = list(towns.town(a.name).get("kits", {}))
    await _launch(a, "KitTownWorkflow", {"kits": keys, "skip_kits": a.skip_kits}, f": kits {keys}")


async def _decide(a):
    c = await Client.connect(config.TEMPORAL)
    await c.get_workflow_handle(f"city-{a.run}").signal("answer", args=[a.key, a.answer])
    db.run("UPDATE city_decisions SET answer = %s, answered_at = now() WHERE run = %s AND key = %s", a.answer, a.run, a.key)
    print(f"answered {a.key}: the planner carries on")


async def _workers(a):
    c = await Client.connect(config.TEMPORAL)
    await c.get_workflow_handle(f"city-{a.run}").signal("set_concurrency", a.concurrency)
    print(f"city-{a.run}: now {a.concurrency} builders at once")


async def _status(a):
    c = await Client.connect(config.TEMPORAL)
    runs = [a.run] if a.run else [r["run"] for r in db.all("SELECT DISTINCT run FROM city_agents WHERE run LIKE %s "
                                                            "ORDER BY run DESC LIMIT 1", f"{a.name}%")]
    for run in runs:
        try:
            s = await c.get_workflow_handle(f"city-{run}").query("status")
        except Exception as e:  # noqa: BLE001 (finished, or never started)
            s = {"phase": f"(no live workflow: {type(e).__name__})"}
        print(f"{run}: {s}")
        for r in db.all("SELECT role, count(*) AS n, sum((result->>'minutes')::float) AS min, "
                        "sum((result->>'usd')::float) AS usd, sum((result->>'denials')::int) AS denials, "
                        "count(*) FILTER (WHERE end_at IS NULL) AS live FROM city_agents WHERE run = %s GROUP BY role", run):
            print(f"  {r['role']:<9} {r['n']:>4} runs ({r['live']} live), {r['min'] or 0:.0f} agent-min, "
                  f"${r['usd'] or 0:.2f}, {r['denials'] or 0} denied tool calls")
        for r in db.all("SELECT key, question, options FROM city_decisions WHERE run = %s AND answer IS NULL", run):
            print(f"  DECISION NEEDED from {r['key']}: {r['question']}")
            for i, o in enumerate(r["options"], 1):
                print(f"    {i}. {o}")
            print(f"    answer: python -m ghost city decide {a.name} --run {run} --key {r['key']} --answer \"...\"")
        for r in db.all("SELECT state, count(*) AS n, avg((detail->>'score')::float) AS score FROM city_plots "
                        "WHERE run = %s GROUP BY state", run):
            print(f"  plots {r['state']:<8} {r['n']:>4}" + (f"  mean critic {r['score']:.1f}" if r["score"] else ""))


def main(argv):
    ap = argparse.ArgumentParser(prog="ghost city")
    ap.add_argument("action", choices=["start", "status", "workers", "decide", "kits"])
    ap.add_argument("--skip-kits", action="store_true", help="kits: the kits are written; lay, stamp and judge")
    ap.add_argument("--key", help="decide: the district (or plot) that asked")
    ap.add_argument("--answer", help="decide: your answer, in words")
    ap.add_argument("name")
    ap.add_argument("--run")
    ap.add_argument("--plots", type=int, default=140)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--districts")
    ap.add_argument("--max-plots", type=int)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--infill", help='JSON {district: {"covered": 0.35, "hole": 60, "count": 12}}: fill hollow districts')
    a = ap.parse_args(argv)
    db.migrate()
    asyncio.run({"start": _start, "workers": _workers, "decide": _decide, "status": _status, "kits": _kits}[a.action](a))
    return 0
