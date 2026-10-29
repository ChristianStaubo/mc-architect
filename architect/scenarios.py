"""The agent-behaviour suite (docs/in-game-architect.md): scripted /arc conversations with virtual players,
each checked by code. Steps go to the daemon's handle() in this process (no inbox, so a running `mc
architect serve` isn't disturbed); every scenario starts on its own pristine site with a fresh session.

A scenario (evals/scenarios/<id>.json): where the player stands (`at`, `facing`, optional `selection`
with y offsets from the ground), the site (`plot`), and steps: what they say and what must then be true."""

import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import bridge, edits, evals, journal, sites
from .assistant import daemon, policy, sessions

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "evals" / "scenarios"
RESULTS = evals.RESULTS / "scenarios"
said = defaultdict(list)  # player -> what the daemon said to them (not "thinking..." notes)


def scenarios(ids=None):
    out = [json.loads(p.read_text()) for p in sorted(DIR.glob("*.json"))]
    return [s for s in out if not ids or s["id"] in ids]


def site_id(sc):
    return "scn-{}_{}".format(*sc["plot"]["min"])


def _hear(player, text, tone):
    if tone != "thinking":
        said[player].append(text)


def wait(player, limit=15 * 60):
    """Until the daemon has finished with them (working or queued)."""
    t0 = time.time()
    while daemon.busy(player) and time.time() - t0 < limit:
        time.sleep(1)


def context(sc, name):
    """What the plugin would tell the daemon about a virtual player standing where the scenario says."""
    x, z = sc["at"]
    g, block = bridge.heightmap((x, z), (x, z))[(x, z)]
    sel = sc.get("selection")
    if sel:
        sel = {k: [sel[k][0], g + sel[k][1], sel[k][2]] for k in ("min", "max")}
    return {"player": name, "world": "world", "pos": [x, g + 1, z], "facing": sc["facing"],
            "ground": {"y": g, "block": block}, "selection": sel}


def _gap(box, pos):
    """Blocks between a build's footprint and a point (0 if over it)."""
    (x0, _, z0), (x1, _, z1) = box
    return max(x0 - pos[0], 0, pos[0] - x1, z0 - pos[2], 0, pos[2] - z1)


def _frame(p):
    return p and (p.get("frame") or p["box"])


def _inside(sel, frame):
    (lo, hi) = frame
    return sel["min"][0] <= lo[0] and hi[0] <= sel["max"][0] and sel["min"][2] <= lo[2] and hi[2] <= sel["max"][2]


def _tools_before(o, want):
    idx = [o["cmds"].index(c) if c in o["cmds"] else -1 for c in want]
    return -1 not in idx and idx == sorted(idx), f"mc calls: {o['cmds']}"


# expectation -> (observations, wanted value) -> (pass, detail). Boolean ones are written `true` in the
# scenario files; `placed: true` is the opposite of `no_place: true`.
CHECKS = {
    "preview": lambda o, w: (bool(o["pending"]) and o["preview"]) == w,
    "no_preview": lambda o, w: (not o["pending"]) == w,
    "placed": lambda o, w: bool(o["new_edits"]) == w,
    "no_place": lambda o, w: (not o["new_edits"]) == w,
    "said": lambda o, w: bool(o["said"]) == w,
    "near": lambda o, w: bool(o["pending"]) and _gap(_frame(o["pending"]), o["pos"]) <= w,
    "inside_selection": lambda o, w: bool(o["pending"]) and _inside(o["selection"], _frame(o["pending"])) == w,
    "taller": lambda o, w: bool(o["pending"] and o["pending_before"])
    and _frame(o["pending"])[1][1] - _frame(o["pending_before"])[1][1] >= w,
    "resumed": lambda o, w: (bool(o["claude_before"]) and o["claude"] == o["claude_before"]) == w,
    "matches_preview": lambda o, w: bool(o["new_edit_records"] and o["pending_before"]
                                         and [list(o["new_edit_records"][0]["min"]), list(o["new_edit_records"][0]["max"])]
                                         == o["pending_before"]["box"]) == w,
    "restored": lambda o, w: (not o["site_changed"]) == w,
    "cleared": lambda o, w: (not o["pending"] and not o["preview"]) == w,
    "within_limits": lambda o, w: (not o["pending"] or policy.limits(o["ctx"], _frame(o["pending"])) is None) == w,
    "tools_before": lambda o, w: _tools_before(o, w)[0],
    "max_minutes": lambda o, w: o["minutes"] is not None and o["minutes"] <= w,
    "stopped": lambda o, w: (o["end"] == "cancelled") == w,
}


def _detail(key, o):
    """What the step left, for this expectation (shown on a fail)."""
    p, b = o["pending"], o["pending_before"]
    return {"near": lambda: p and f"{_gap(_frame(p), o['pos'])} blocks from where they stood",
            "taller": lambda: p and b and f"top {_frame(b)[1][1]} -> {_frame(p)[1][1]}",
            "inside_selection": lambda: p and f"build {_frame(p)} vs selection {o['selection']}",
            "matches_preview": lambda: f"placed {[(e['min'], e['max']) for e in o['new_edit_records']]} vs previewed {b and b['box']}",
            "tools_before": lambda: _tools_before(o, [])[1],
            "said": lambda: (o["said"] or ["nothing"])[-1][:120],
            "restored": lambda: f"{o['site_changed']} blocks differ from the pristine site",
            "stopped": lambda: f"agent ended: {o['end']}",
            "max_minutes": lambda: f"{o['minutes']} min"}.get(key, lambda: f"preview {bool(p)}, new edits {o['new_edits']}")()


def check(key, want, o):
    """One expectation against what a step left: (pass, detail)."""
    if key not in CHECKS:
        return False, f"unknown expectation {key}"
    return bool(CHECKS[key](o, want)), _detail(key, o) or "no preview"


def run_one(sc, model, log):
    name = sc.get("player") or f"scn-{sc['id']}"
    sessions.forget(name)
    bridge.preview_clear(name)
    task = {"id": site_id(sc), "plot": sc["plot"]}
    if not sites.path(task["id"]).exists():
        sites.capture(task)
    sites.reset(task["id"])
    ctx = context(sc, name)
    steps = []
    for st in sc["steps"]:
        before_ids = {e["id"] for e in edits.listing()}
        s0 = sessions.get(name)
        said[name].clear()
        word = st["say"].strip().lower()
        kind = word if word in daemon.HANDLERS else "request"
        t0 = time.time()
        daemon.handle({"player": name, "kind": kind, "text": "" if kind != "request" else st["say"], "context": ctx},
                      model, log)
        if kind in ("request", "cancel"):
            wait(name) if st.get("wait", True) else time.sleep(8)  # (let the agent get going before a cancel)
        s = sessions.get(name)
        es = journal.entries(sessions.run_id(name)) if kind == "request" else []
        new = [e for e in edits.listing() if e["id"] not in before_ids and str(e.get("run", "")).startswith(f"arc:{name}:")]
        last = s.get("last_run") or {}
        o = {"pending": s.get("pending"), "pending_before": s0.get("pending"),
             "preview": bridge.preview_get(name).get("preview", False), "ctx": ctx,
             "new_edits": [e["id"] for e in new], "new_edit_records": new, "pos": ctx["pos"], "selection": ctx["selection"],
             "said": said[name] + [f"(mc say) {e['argv'][1] if len(e['argv']) > 1 else ''}" for e in es if e["cmd"] == "say"],
             "claude": s.get("claude"), "claude_before": s0.get("claude"), "cmds": [e["cmd"] for e in es],
             "minutes": last.get("minutes") if kind == "request" else None, "end": last.get("end"),
             "site_changed": len(sites.outcome(task).changed) if "restored" in st["expect"] else None}
        res = [{"check": k, "pass": ok, "detail": d} for k, v in st["expect"].items() for ok, d in [check(k, v, o)]]
        steps.append({"say": st["say"], "seconds": round(time.time() - t0), "checks": res,
                      "said": o["said"], "pass": all(r["pass"] for r in res)})
        log(f"  {sc['id']}: \"{st['say']}\" {'ok' if steps[-1]['pass'] else 'FAIL'} "
            + "; ".join(f"{r['check']}: {r['detail']}" for r in res if not r["pass"]))
    bridge.preview_clear(name)
    for b in reversed(sessions.get(name).get("builds", [])):  # leave the site as it was
        daemon.mc(name, "undo", b["edit"])
    return {"id": sc["id"], "player": name, "pass": all(s["pass"] for s in steps), "steps": steps}


def run(ids=None, model="sonnet", concurrency=3, log=print):
    scs = scenarios(ids)
    groups = defaultdict(list)  # scenarios on one site run one after another
    for sc in scs:
        groups[site_id(sc)].append(sc)
    daemon.listeners.append(_hear)
    lock = threading.Lock()
    results = []

    def group(g):
        out = [run_one(sc, model, log) for sc in g]
        with lock:
            results.extend(out)

    try:
        with sites.still(), ThreadPoolExecutor(concurrency) as ex:
            list(ex.map(group, groups.values()))
    finally:
        daemon.listeners.remove(_hear)
    rec = {"run": time.strftime("s%m%d-%H%M"), "model": model, "passed": sum(r["pass"] for r in results),
           "total": len(results), "scenarios": sorted(results, key=lambda r: r["id"])}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{rec['run']}.json").write_text(json.dumps(rec, indent=1))
    return rec
