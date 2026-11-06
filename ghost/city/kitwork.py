"""Building with kits (kits/README.md): agents design once, code builds many.

KitTownWorkflow: kit authors (agents) in parallel -> a critic scores each kit from its sample sheet, one
fix round below PASS -> the ground by code (roads, bridges fitted by the bridge kit, terraces) -> every
plot stamped by code -> the same plot critic as the city harness on a few sampled plots, so the
quality compares with Kingsreach's one-agent-per-plot."""

import json
import random
import re
import time
from datetime import timedelta
from pathlib import Path

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .. import db
    from ..db import J
    from . import activities as A
    from architect import edits, kits, run as mcrun, town as towns  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
PASS = 6

AUTHOR = """You are writing a kit: one parametric design that code will stamp on {n} plots of {town}.
Read kits/README.md (the contract) and STYLE.md, then the parts table in .claude/skills/mc-build/SKILL.md.
{what}
The town: {brief}
Its style: {style}
Write {file} (only that file). Check it with: ./mc.py kit sample {file} {sample_args}
and Read the sheet it prints. Iterate until every instance is clean and the sheet looks like a place you'd
ride through: each kind distinct and recognisable, seeds giving real variety (roof shapes, wings, porches,
materials, yard details), lived-in, lit inside. Good, not precious: it's built {n} times, so spend your
effort on the design, not on any one instance.
Bash runs only commands starting with ./mc.py (no cd, &&, cat or python). End with one line: kinds,
how the seed varies them, and the last sample result."""

WHAT_BUILDINGS = """It builds these kinds: {kinds}, at these sizes (w x d, door side): {sizes}."""
WHAT_BRIDGE = """It's a bridge kit (KIND = "bridge") for the highway's crossings: {crossings}. Make it a fine
stone bridge worth riding over: arches on piers, parapets, lanterns, and for long spans something
memorable (a middle tower or chapel, pier cutwaters, banner poles). The ramps join the road on the banks."""

KIT_CRITIC = """Score a kit, a family of buildings stamped by code, from its sample sheet (Read {sheet}): every
instance the kit will build, in order. The kinds: {kinds}. The brief: {brief}
Judge the family: does each kind read as itself, is there real variety, does it fit the style, would a
road of these look good? Use evals/RUBRIC.md's scale. Reply with JSON only: {{"score": 1-10, "keep": "what
works", "fix": "the two most important changes, concrete"}}."""


def _kit_path(name, key):
    return towns.town(name)["kits"][key]


@activity.defn
def author_kit(run: str, name: str, key: str, feedback: str | None, session: str | None) -> dict:
    t = towns.town(name)
    path = _kit_path(name, key)
    lay = towns.layout(name)
    if key == "bridge":
        n = len(lay.get("bridges", []))
        what = WHAT_BRIDGE.format(crossings=", ".join(
            f"{b['id']} {abs(b['b'][0] - b['a'][0]) + abs(b['b'][1] - b['a'][1])} blocks of water" for b in lay["bridges"]))
        sample_args = ""
    else:
        ps = [p for p in lay["plots"] if p.get("kit") == key]
        n = len(ps)
        kinds = sorted({p["kind"] for p in ps})
        sizes = ", ".join(f"{p['kind']} {p['max'][0] - p['min'][0] + 1}x{p['max'][1] - p['min'][1] + 1} {p['door']}" for p in ps)
        what = WHAT_BUILDINGS.format(kinds=", ".join(kinds), sizes=sizes)
        sample_args = f"--town {name}"
    prompt = (f"The critic's notes on your kit's sample sheet, fix them and resample:\n{feedback}" if feedback else
              AUTHOR.format(n=n, town=name, what=what, brief=t["brief"], style=t.get("style", ""), file=path,
                            sample_args=sample_args))
    out = A.run_agent(run, "kit", key, prompt, [path], "mc-builder", resume=session if feedback else None)
    rows, sheet = kits.sample(ROOT / path, out=ROOT / "local" / "renders" / f"{time.strftime('%Y%m%d-%H%M%S')}-kit-{key}.png",
                              town=None if key == "bridge" else name)
    bad = [r for r in rows if r["problems"]]
    return {"key": key, "clean": len(rows) - len(bad), "total": len(rows), "sheet": str(sheet),
            "problems": [p for r in bad for p in r["problems"]][:6],
            **{k: out[k] for k in ("session", "minutes", "usd", "denials")}}


@activity.defn
def judge_kit(run: str, name: str, key: str, sheet: str) -> dict:
    t = towns.town(name)
    path = ROOT / _kit_path(name, key)
    o = A.run_agent(run, "critic", f"kit-{key}", KIT_CRITIC.format(sheet=sheet, kinds=", ".join(kits.kinds_of(path))
                    if key != "bridge" else "bridge", brief=t["brief"]), [], "mc-critic")
    j = re.search(r"\{.*\}", o["full"], re.S)
    try:
        v = json.loads(j.group(0)) if j else {}
    except ValueError:
        v = {}
    return {"score": v.get("score"), "keep": v.get("keep", ""), "fix": v.get("fix", "")}


@activity.defn
def lay_bridges(run: str, name: str) -> list:
    """Every crossing, built by the bridge kit, each once."""
    done = {e.get("task") for e in edits.listing()}
    out = []
    for b in towns.layout(name).get("bridges", []):
        if f"town:{name}:bridge:{b['id']}" in done:
            continue
        t0 = time.time()
        ok, msg = mcrun.mc("town", "bridge", name, b["id"], timeout=600, MC_RUN_ID=f"city:{run}:ground")
        out.append({"bridge": b["id"], "ok": ok, "s": round(time.time() - t0, 1), "msg": msg.strip()[-300:]})
        activity.heartbeat()
    return out


@activity.defn
def stamp_plots(run: str, name: str) -> dict:
    """Every kit plot placed by code (`mc place KIT --plot`), each once, recorded like an agent's plot."""
    t = towns.town(name)
    done = {e.get("task") for e in edits.listing()}
    n, fails, t_all = 0, [], time.time()
    for p in towns.layout(name)["plots"]:
        if not p.get("kit") or f"town:{name}:{p['id']}" in done:
            continue
        t0 = time.time()
        ok, msg = mcrun.mc("place", t["kits"][p["kit"]], "--plot", f"{name}/{p['id']}", timeout=600,
                           MC_RUN_ID=f"city:{run}:stamp")
        s = round(time.time() - t0, 1)
        e = [x for x in edits.listing() if x.get("task") == f"town:{name}:{p['id']}"]
        A.record_plot(run, name, p["id"], "done" if ok else "flawed",
                      {"stamped": True, "seconds": s, "edit": e[-1]["id"] if e else None, "usd": 0, "minutes": s / 60,
                       **({} if ok else {"error": msg.strip()[-300:]})})
        if not ok:
            fails.append(p["id"])
        n += 1
        activity.heartbeat()
    return {"stamped": n, "failed": fails, "seconds": round(time.time() - t_all, 1)}


@activity.defn
def sample_plots(name: str, k: int) -> list:
    ps = [p["id"] for p in towns.layout(name)["plots"] if p.get("kit")]
    return sorted(random.Random(len(ps)).sample(ps, min(k, len(ps))))


KIT_ACTIVITIES = [author_kit, judge_kit, lay_bridges, stamp_plots, sample_plots]

AGENT = {"heartbeat_timeout": timedelta(minutes=2),
         "retry_policy": RetryPolicy(initial_interval=timedelta(minutes=2), maximum_attempts=3)}
QUICK = {"start_to_close_timeout": timedelta(minutes=10), "retry_policy": RetryPolicy(maximum_attempts=3)}
LONG = {"start_to_close_timeout": timedelta(hours=2), "heartbeat_timeout": timedelta(minutes=15),
        "retry_policy": RetryPolicy(maximum_attempts=3)}


@workflow.defn
class KitTownWorkflow:
    def __init__(self):
        self.phase, self.kits, self.timing = "starting", {}, {}

    @workflow.query
    def status(self) -> dict:
        return {"phase": self.phase, "kits": self.kits, "timing": self.timing}

    async def _kit(self, run, name, key):
        tmo = timedelta(minutes=A.MINUTES["builder"] + 15)
        r = await workflow.execute_activity(author_kit, args=[run, name, key, None, None], start_to_close_timeout=tmo, **AGENT)
        j = await workflow.execute_activity(judge_kit, args=[run, name, key, r["sheet"]],
                                            start_to_close_timeout=timedelta(minutes=20), **AGENT)
        first = j.get("score")
        if r["clean"] < r["total"] or (j.get("score") or 0) < PASS:
            fb = "\n".join(x for x in [f"Sample: {r['total'] - r['clean']} of {r['total']} not clean: {r['problems']}"
                                       if r["clean"] < r["total"] else "", f"Critic ({j.get('score')}/10): {j.get('fix', '')}"] if x)
            r2 = await workflow.execute_activity(author_kit, args=[run, name, key, fb, r["session"]],
                                                 start_to_close_timeout=tmo, **AGENT)
            j = await workflow.execute_activity(judge_kit, args=[run, name, key, r2["sheet"]],
                                                start_to_close_timeout=timedelta(minutes=20), **AGENT)
            r = {**r2, "minutes": r["minutes"] + r2["minutes"], "usd": r["usd"] + r2["usd"]}
        self.kits[key] = {"score": j.get("score"), "first_score": first, "clean": f"{r['clean']}/{r['total']}",
                          "minutes": round(r["minutes"], 1), "usd": round(r["usd"], 2), "fix": j.get("fix", "")[:200]}

    @workflow.run
    async def run(self, args: dict) -> dict:
        run, name = args["run"], args["name"]
        t0 = workflow.now()
        if not args.get("skip_kits"):
            self.phase = "designing the kits"   # every kit's author at once
            await asyncio_gather(*(self._kit(run, name, k) for k in args["kits"]))
        t1 = workflow.now()
        self.phase = "laying the road"
        await workflow.execute_activity(A.lay_ground, args=[run, name, None], **LONG)
        self.phase = "building the bridges"
        bridges = await workflow.execute_activity(lay_bridges, args=[run, name], **LONG)
        t2 = workflow.now()
        self.phase = "stamping the plots"
        st = await workflow.execute_activity(stamp_plots, args=[run, name], **LONG)
        t3 = workflow.now()
        self.phase = "judging a sample"
        pids = await workflow.execute_activity(sample_plots, args=[name, args.get("judge", 6)], **QUICK)
        js = []
        for pid in pids:
            j = await workflow.execute_activity(A.judge_plot, args=[run, name, pid],
                                                start_to_close_timeout=timedelta(minutes=20), **AGENT)
            js.append({"plot": pid, **j})
            await workflow.execute_activity(A.record_plot, args=[run, name, pid, "done", {"score": j.get("score")}], **QUICK)
        self.timing = {"kits_min": round((t1 - t0).total_seconds() / 60, 1), "ground_min": round((t2 - t1).total_seconds() / 60, 1),
                       "stamp_min": round((t3 - t2).total_seconds() / 60, 1),
                       "judge_min": round((workflow.now() - t3).total_seconds() / 60, 1)}
        self.phase = "done"
        scores = [j["score"] for j in js if j.get("score")]
        return {"kits": self.kits, "bridges": bridges, "stamp": st, "sampled": js, "timing": self.timing,
                "mean_score": round(sum(scores) / len(scores), 1) if scores else None}


async def asyncio_gather(*aws):
    import asyncio
    return await asyncio.gather(*aws)
