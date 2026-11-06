"""The city's steps (ghost/city/workflows.py). Each agent runs headless with tools scoped to its own files:
the macro planner writes districts.json and the layout's roads, a district planner only its district's
file, a builder only its plan; the critic only reads. Every run is a row in city_agents (the boundary and
cost data the evals read)."""

import json
import os
import re
import subprocess
import threading
import time

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .. import bridge as _path, config, db  # noqa: F401 (_path: architect/ on sys.path)
from ..db import J
from architect import claude, edits, run as mcrun, town as towns  # noqa: E402
from architect.cli.town import town_terrain  # noqa: E402

ROOT = config.ROOT
WORK = ROOT / "local" / "city"
QUEUE = "city"
MODELS = {"macro": "opus", "district": "sonnet", "builder": "sonnet", "critic": "sonnet"}
BUDGETS = {"macro": 8.0, "district": 4.0, "builder": 4.0, "critic": 1.0}   # caps per run (USD-equivalent)
MINUTES = {"macro": 40, "district": 30, "builder": 45, "critic": 10}


def model(role):
    return os.environ.get(f"CITY_MODEL_{role.upper()}", MODELS[role])


def city_dir(name):
    return ROOT / "towns" / name


def _settings(run, role, writable):
    """Permissions for one agent: read the repo, write only its own files, nothing secret."""
    p = WORK / run / "settings" / f"{role}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"permissions": {"deny": [
        "Read(server/plugins/MCBridge/**)", "Read(local/ghost/**)", "Read(local/ghost-memory/**)",
        "Bash(./mc.py ghost:*)", "Bash(./mc.py cmd:*)", "Bash(./mc.py restart:*)", "Bash(./mc.py undo:*)"]}}))
    return p


def run_agent(run, role, key, prompt, writable, agent, resume=None):
    """One headless agent run, heartbeating to Temporal. writable: the only paths it may Write/Edit."""
    tools = ["Bash(./mc.py *)", "Read", "Glob", "Grep", *(f"Write({w})" for w in writable), *(f"Edit({w})" for w in writable)]
    cmd = claude.command(prompt, model(role), tools, BUDGETS[role], agent=agent,
                         settings=_settings(run, f"{role}-{key}", writable), resume=resume)
    work = WORK / run / role
    work.mkdir(parents=True, exist_ok=True)
    attempt = len(list(work.glob(f"{key}-*.jsonl"))) + 1
    transcript = work / f"{key}-{attempt}.jsonl"
    env = {**os.environ, "MC_RUN_ID": f"city:{run}:{role}:{key}"}
    t0 = time.time()
    row = db.one("INSERT INTO city_agents (run, role, key, attempt, model) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                 run, role, key, attempt, model(role))
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines = []

    def read():
        with open(transcript, "w") as f:
            for line in proc.stdout:
                f.write(line)
                lines.append(line)
    th = threading.Thread(target=read, daemon=True)
    th.start()
    deadline = t0 + MINUTES[role] * 60
    try:
        while proc.poll() is None:
            if time.time() > deadline:
                proc.kill()
            time.sleep(5)
            activity.heartbeat()
    except BaseException:  # cancelled (or the worker is going down): don't leave the agent running
        proc.kill()
        raise
    th.join(10)
    res = claude.result_of(lines)
    end = "timeout" if time.time() > deadline else claude.end_of(res)
    denials = len(res.get("permission_denials") or [])
    out = {"end": end, "session": res.get("session_id"), "usd": res.get("total_cost_usd"),
           "turns": res.get("num_turns"), "minutes": round((time.time() - t0) / 60, 1), "denials": denials,
           "report": (res.get("result") or "")[-1200:]}
    full = res.get("result") or ""
    db.run("UPDATE city_agents SET end_at = now(), result = %s WHERE id = %s", J(out), row["id"])
    if end not in ("done", "budget"):
        # usage limits and crashes are worth retrying later; Temporal backs off
        raise ApplicationError(f"{role} {key} ended {end}: {out['report'][-200:]}")
    return {**out, "full": full}   # (the stored row keeps the tail; the caller gets the whole answer)


# ---- planning ----

MACRO = """You are planning the districts of a capital city, not its buildings: a team of district planners
will lay the plots inside each district at the same time, and builders build them in parallel after.

Read towns/{name}/town.json (brief, style, scope) and run `./mc.py town site {name}` (read both PNGs).
Then write two files:
1. towns/{name}/layout.json: {{"palette": {{...one city palette, see mc-planner}}, "roads": [the main avenues,
   the ring road inside the wall and the lanes that bound districts, as point lists with widths (avenues 5,
   streets 3)], "plots": [], "wall": {{"points": [...]}} if the city is walled}}. Roads follow the land and must
   connect; leave room for districts between them.
2. towns/{name}/districts.json: {{"districts": [{{"id", "name", "box": [x0, z0, x1, z1], "character": one
   paragraph a district planner can act on (what it is, its buildings, how fine or plain, its landmark if
   any), "plots": how many plots it should hold, "landmarks": [ids of landmark plots it must include]}}]}}.
   8 to 10 districts whose plot counts add up to about {plots}; boxes must not overlap and must sit between
   roads (roads run along box edges, not through them); every box inside the city area.
Run `./mc.py town show {name}` and fix every road FAIL. End with one line: the districts and their counts."""

DISTRICT = """You are one of several planners laying out a capital city at the same time. Yours is the
{did} district ("{dname}"): box x {x0}..{x1}, z {z0}..{z1}. Only plan plots inside that box.

District character: {character}
Plots: about {count}. Landmarks you must include: {landmarks}.
City style: {style}
The roads already laid out (don't put plots on them; every door within 4 blocks of one): read
towns/{name}/layout.json ("roads"). Follow the mc-planner method for plot sizes, gaps, floor_y and doors, and run
`./mc.py town site {name}` if you need the ground (then look only at your box).

Write towns/{name}/districts/{did}.json: {{"plots": [{{"id": "{did}_<name>", "district": "{did}", "type",
"min": [x, z], "max": [x, z], "floor_y", "door", "brief", "landmark": true|false}}]}}. Every plot id starts
with "{did}_". Every plot inside your box with a 1-block gap to every other plot and off every road.
End with one line: how many plots, and anything you couldn't fit."""

FIX = """The merged city layout has problems in your district. Fix them in towns/{name}/districts/{did}.json
(move, resize or drop plots; never touch other districts):
{issues}
End with one line saying what you changed."""


def _read(path, default):
    return json.loads(path.read_text()) if path.exists() else default


@activity.defn
def plan_macro(run: str, name: str, plots: int) -> dict:
    d = city_dir(name)
    (d / "districts").mkdir(parents=True, exist_ok=True)
    if (d / "districts.json").exists():  # done on an earlier attempt (or by hand): keep it
        return {"districts": len(_read(d / "districts.json", {}).get("districts", [])), "reused": True}
    out = run_agent(run, "macro", "city", MACRO.format(name=name, plots=plots),
                    [f"towns/{name}/layout.json", f"towns/{name}/districts.json"], "mc-planner")
    ds = _read(d / "districts.json", {}).get("districts", [])
    if not ds:
        raise ApplicationError("the macro planner wrote no districts")
    return {"districts": len(ds), **{k: out[k] for k in ("minutes", "usd")}}


@activity.defn
def districts(name: str) -> list:
    return _read(city_dir(name) / "districts.json", {}).get("districts", [])


@activity.defn
def plan_district(run: str, name: str, dist: dict, issues: list | None) -> dict:
    d = city_dir(name)
    f = d / "districts" / f"{dist['id']}.json"
    if f.exists() and not issues:  # planned on an earlier attempt
        return {"district": dist["id"], "plots": len(_read(f, {}).get("plots", [])), "reused": True}
    x0, z0, x1, z1 = dist["box"]
    if issues:
        prompt = FIX.format(name=name, did=dist["id"], issues="\n".join(f"- {i}" for i in issues))
    else:
        prompt = DISTRICT.format(name=name, did=dist["id"], dname=dist.get("name", dist["id"]), x0=x0, x1=x1, z0=z0,
                                 z1=z1, character=dist.get("character", ""), count=dist.get("plots", 12),
                                 landmarks=", ".join(dist.get("landmarks") or []) or "none",
                                 style=towns.town(name).get("style", ""))
    out = run_agent(run, "district", dist["id"], prompt, [f"towns/{name}/districts/{dist['id']}.json"], "mc-planner")
    plots = _read(f, {}).get("plots", [])
    bad = [p["id"] for p in plots if not (x0 <= p["min"][0] and p["max"][0] <= x1 and z0 <= p["min"][1] and p["max"][1] <= z1)]
    return {"district": dist["id"], "plots": len(plots), "outside_box": bad, **{k: out[k] for k in ("minutes", "usd", "denials")}}


@activity.defn
def merge_and_check(name: str) -> dict:
    """Merge every district's plots into layout.json and run the layout check: {district: [issues]}."""
    d = city_dir(name)
    lay = _read(d / "layout.json", {})
    plots = []
    for f in sorted((d / "districts").glob("*.json")):
        plots += _read(f, {}).get("plots", [])
    lay["plots"] = plots
    (d / "layout.json").write_text(json.dumps(lay, indent=1))
    issues = towns.check(name, town_terrain(name))
    by = {}
    owner = {p["id"]: p.get("district") for p in plots}
    roads = []
    for i in issues:
        if i["level"] != "fail":
            continue
        dist = owner.get(i["what"])
        (by.setdefault(dist, []) if dist else roads).append(f"{i['what']}: {i['msg']}")
    return {"plots": len(plots), "by_district": by, "roads": roads}


# ---- the ground: roads and terraces, by code ----

@activity.defn
def lay_ground(run: str, name: str, only: list | None = None) -> dict:
    """Every road, then the terraces of the plots about to be built (`only`: their districts or ids; all when
    None), each once (an edit with the same task is skipped)."""
    lay = _read(city_dir(name) / "layout.json", {})
    done = {e.get("task") for e in edits.listing()}
    n = 0
    for r in lay.get("roads", []):
        if f"town:{name}:road:{r['id']}" not in done:
            ok, out = mcrun.mc("town", "road", name, r["id"], timeout=900, MC_RUN_ID=f"city:{run}:ground")
            if not ok:
                raise ApplicationError(f"road {r['id']}: {out[-300:]}")
            n += 1
        activity.heartbeat()
    for p in lay.get("plots", []):
        if only and p.get("district") not in only and p["id"] not in only:
            continue
        if f"town:{name}:{p['id']}:terrace" not in done:
            ok, out = mcrun.mc("town", "terrace", name, p["id"], timeout=600, MC_RUN_ID=f"city:{run}:ground")
            if not ok:
                raise ApplicationError(f"terrace {p['id']}: {out[-300:]}")
            n += 1
        activity.heartbeat()
    return {"placed": n}


@activity.defn
def plot_ids(name: str, only: list | None) -> list:
    lay = _read(city_dir(name) / "layout.json", {})
    ps = [p for p in lay.get("plots", []) if not only or p.get("district") in only or p["id"] in only]
    # landmarks first: they set the tone the others follow
    return [p["id"] for p in sorted(ps, key=lambda p: (not p.get("landmark"), p["id"]))]


# ---- building one plot ----

def _plot_edits(name, pid):
    return [e for e in edits.listing() if e.get("task") == f"town:{name}:{pid}"]


@activity.defn
def build_plot(run: str, name: str, pid: str, feedback: str | None, session: str | None) -> dict:
    """A builder builds one plot. A fresh attempt first takes back what an earlier, interrupted attempt
    placed there (the plot is the unit of idempotence); a fix round resumes the builder's session."""
    work = WORK / run / "plots" / pid
    work.mkdir(parents=True, exist_ok=True)
    if not feedback:
        for e in sorted(_plot_edits(name, pid), key=edits.seq, reverse=True):
            edits.undo(e["id"], "")
    ok, brief = mcrun.mc("town", "brief", name, pid)
    if not ok:
        raise ApplicationError(f"no brief for {pid}: {brief[-200:]}", non_retryable=True)
    plan = (work / "plan.py").relative_to(ROOT)
    prompt = (f"Critique of your build, fix it:\n{feedback}" if feedback else
              f"{brief}\nYour plan file: {plan}\nYou are one of several builders working on this city at the same "
              "time, each on its own plot: stay inside yours. Work through the mc-build skill (preview, place, audit, "
              "shots, revise), then end with a short report (what you built, the last edit id, any gaps).")
    out = run_agent(run, "builder", pid, prompt, [str(plan)], "mc-builder", resume=session if feedback else None)
    es = _plot_edits(name, pid)
    return {"edit": es[-1]["id"] if es else None, "edits": len(es), **{k: out[k] for k in ("session", "minutes", "usd", "denials")}}


@activity.defn
def check_plot(run: str, name: str, pid: str) -> dict:
    """The code checks: an audit of the plot's newest edit, and whether every edit stayed inside the plot."""
    p = towns.plot(name, pid)
    es = _plot_edits(name, pid)
    if not es:
        return {"ok": False, "why": "nothing was built", "fails": 1, "outside": 0}
    (x0, z0), (x1, z1) = p["min"], p["max"]
    outside = [e["id"] for e in es if e["min"][0] < x0 - 4 or e["max"][0] > x1 + 4 or e["min"][2] < z0 - 4 or e["max"][2] > z1 + 4]
    ok, out = mcrun.mc("audit", es[-1]["id"], timeout=300)
    m = re.search(r"(\d+) fail", out)
    fails = int(m.group(1)) if m else (0 if ok else 1)
    return {"ok": fails == 0 and not outside, "fails": fails, "outside": len(outside),
            "why": out.strip().splitlines()[-1][:300] if out.strip() else ""}


CRITIC = """Score this city plot from its contact sheet (Read {sheet}). The brief: {brief}
Use evals/RUBRIC.md. Reply with JSON only: {{"score": 1-10, "keep": "what works", "fix": "the most important
change, concrete"}}."""


@activity.defn
def judge_plot(run: str, name: str, pid: str) -> dict:
    es = _plot_edits(name, pid)
    if not es:
        return {"score": 0, "fix": "nothing was built"}
    ok, out = mcrun.mc("shots", es[-1]["id"], timeout=300)
    m = re.search(r"(/\S+\.png)", out)
    if not ok or not m:
        return {"score": None, "fix": "", "error": out[-200:]}
    _, brief = mcrun.mc("town", "brief", name, pid)
    o = run_agent(run, "critic", pid, CRITIC.format(sheet=m.group(1), brief=brief), [], "mc-critic")
    j = re.search(r"\{.*\}", o["full"], re.S)
    try:
        v = json.loads(j.group(0)) if j else {}
    except ValueError:
        v = {}
    return {"score": v.get("score"), "keep": v.get("keep", ""), "fix": v.get("fix", ""), "sheet": m.group(1)}


@activity.defn
def record_plot(run: str, name: str, pid: str, state: str, detail: dict) -> None:
    db.run("INSERT INTO city_plots (run, city, plot, state, detail) VALUES (%s, %s, %s, %s, %s) "
           "ON CONFLICT (run, plot) DO UPDATE SET state = EXCLUDED.state, detail = city_plots.detail || EXCLUDED.detail, "
           "updated_at = now()", run, name, pid, state, J(detail))


ACTIVITIES = [plan_macro, districts, plan_district, merge_and_check, lay_ground, plot_ids, build_plot, check_plot,
              judge_plot, record_plot]
