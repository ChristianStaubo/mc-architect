"""The agent-behaviour suite (docs/in-game-architect.md): scripted /arc conversations with virtual players,
each checked by code. Steps go straight to the daemon's handlers (no inbox, so a running `mc architect
serve` isn't disturbed); every scenario starts on its own pristine site with a fresh session.

A scenario (evals/scenarios/<id>.json): where the player stands (`at`, `facing`, optional `selection`
with y offsets from the ground), the site (`plot`), and steps: what they say and what must then be true."""

import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import bridge, edits, evals, journal, sites
from .assistant import daemon, sessions
from .cli.assistant import MAX_HEIGHT, MAX_SIDE, RADIUS

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "evals" / "scenarios"
RESULTS = evals.RESULTS / "scenarios"
WORDS = ("yes", "no", "undo", "cancel", "status")
said = defaultdict(list)  # player -> what the daemon said to them (not "thinking..." notes)


def scenarios(ids=None):
    out = [json.loads(p.read_text()) for p in sorted(DIR.glob("*.json"))]
    return [s for s in out if not ids or s["id"] in ids]


def site_id(sc):
    return "scn-{}_{}".format(*sc["plot"]["min"])


def _record(original):
    def say(player, text, tone="info", buttons=()):
        if tone != "thinking":
            said[player].append(text)
        return original(player, text, tone, buttons)
    return say


def _busy(player):
    """Working for them, or their request is waiting for a free slot."""
    with daemon.lock:
        return player in daemon.jobs or any(e["player"] == player for e, _ in daemon.queue)


def _wait(player, limit=15 * 60):
    t0 = time.time()
    while _busy(player) and time.time() - t0 < limit:
        time.sleep(2)


def _gap(box, pos):
    """Blocks between a build's footprint and a point (0 if over it)."""
    (x0, _, z0), (x1, _, z1) = box
    return max(x0 - pos[0], 0, pos[0] - x1, z0 - pos[2], 0, pos[2] - z1)


def check(key, want, o):
    """One expectation against what a step left: (pass, detail)."""
    p, before = o["pending"], o["pending_before"]
    if key == "preview":
        ok = bool(p) and o["preview"]
        return ok == want, f"preview {'shown' if ok else 'none'}"
    if key == "no_preview":
        return (not p) == want, f"pending preview: {bool(p)}"
    if key == "placed":
        return bool(o["new_edits"]) == want, f"new edits {o['new_edits']}"
    if key == "no_place":
        return (not o["new_edits"]) == want, f"new edits {o['new_edits']}"
    if key == "said":
        return bool(o["said"]) == want, f"said: {(o['said'] or ['nothing'])[-1][:120]}"
    if key == "near":
        if not p:
            return False, "no preview"
        g = _gap(p["box"], o["pos"])
        return g <= want, f"{g} blocks from where they stood (max {want})"
    if key == "inside_selection":
        sel, (lo, hi) = o["selection"], p["box"] if p else (None, None)
        if not p:
            return False, "no preview"
        ok = sel["min"][0] <= lo[0] and hi[0] <= sel["max"][0] and sel["min"][2] <= lo[2] and hi[2] <= sel["max"][2]
        return ok == want, f"box {lo}..{hi} vs selection {sel['min']}..{sel['max']}"
    if key == "taller":
        if not (p and before):
            return False, "needs a preview before and after"
        d = p["box"][1][1] - before["box"][1][1]
        return d >= want, f"top {before['box'][1][1]} -> {p['box'][1][1]} (+{d}, want +{want})"
    if key == "resumed":
        ok = bool(o["claude_before"]) and o["claude"] == o["claude_before"]
        return ok == want, "same conversation" if ok else "a new conversation"
    if key == "matches_preview":
        e = o["new_edit_records"][0] if o["new_edit_records"] else None
        ok = bool(e and before and [list(e["min"]), list(e["max"])] == before["box"])
        return ok == want, f"placed {e and [e['min'], e['max']]} vs previewed {before and before['box']}"
    if key == "restored":
        ok = not o["site_changed"]
        return ok == want, f"{o['site_changed']} blocks differ from the pristine site"
    if key == "cleared":
        ok = not p and not o["preview"]
        return ok == want, "preview gone" if ok else "a preview is still there"
    if key == "within_limits":
        if not p:
            return True, "no preview (declined)"
        (x0, y0, z0), (x1, y1, z1) = p["box"]
        ok = (x1 - x0 < MAX_SIDE and z1 - z0 < MAX_SIDE and y1 - y0 < MAX_HEIGHT and _gap(p["box"], o["pos"]) <= RADIUS)
        return ok == want, f"preview {x1 - x0 + 1}x{y1 - y0 + 1}x{z1 - z0 + 1}"
    if key == "tools_before":
        cmds = o["cmds"]
        idx = [cmds.index(c) if c in cmds else -1 for c in want]
        ok = -1 not in idx and idx == sorted(idx)
        return ok, f"mc calls: {cmds}"
    if key == "max_minutes":
        m = o["minutes"]
        return m is not None and m <= want, f"{m} min (max {want})"
    if key == "stopped":
        return (o["end"] == "cancelled") == want, f"agent ended: {o['end']}"
    return False, f"unknown expectation {key}"


def run_one(sc, model, log):
    name = sc.get("player") or f"scn-{sc['id']}"
    sessions.forget(name)
    bridge.preview_clear(name)
    task = {"id": site_id(sc), "plot": sc["plot"]}
    if not sites.path(task["id"]).exists():
        sites.capture(task)
    sites.reset(task["id"])
    x, z = sc["at"]
    ground = bridge.heightmap((x, z), (x, z))[(x, z)]
    pos = [x, ground[0] + 1, z]
    sel = sc.get("selection")
    if sel:
        sel = {"min": [sel["min"][0], ground[0] + sel["min"][1], sel["min"][2]],
               "max": [sel["max"][0], ground[0] + sel["max"][1], sel["max"][2]]}
    ctx = {"player": name, "world": "world", "pos": pos, "facing": sc["facing"],
           "ground": {"y": ground[0], "block": ground[1]}, "selection": sel}
    steps = []
    for st in sc["steps"]:
        before_ids = {e["id"] for e in edits.listing()}
        s0 = sessions.get(name)
        said[name].clear()
        word = st["say"].strip().lower()
        kind = word if word in WORDS else "request"
        event = {"player": name, "kind": kind, "text": "" if kind != "request" else st["say"], "context": ctx}
        t0 = time.time()
        if kind == "request":
            daemon.on_request(event, model, log)
            if st.get("wait", True):
                _wait(name)
            else:
                time.sleep(8)  # let the agent get going before the next step
        else:
            daemon.HANDLERS[kind](name)
            if kind == "cancel":
                _wait(name)
        s = sessions.get(name)
        run_id = f"arc:{name}:{s.get('requests', 0)}"
        new = [e for e in edits.listing() if e["id"] not in before_ids and str(e.get("run", "")).startswith(f"arc:{name}:")]
        pv = bridge.preview_get(name)
        o = {"pending": s.get("pending"), "pending_before": s0.get("pending"), "preview": pv.get("preview", False),
             "new_edits": [e["id"] for e in new], "new_edit_records": new, "pos": pos, "selection": sel,
             "said": said[name] + ([f"(mc say) {e['argv'][1] if len(e['argv']) > 1 else ''}" for e in journal.entries(run_id)
                                     if e["cmd"] == "say"] if kind == "request" else []),
             "claude": s.get("claude"), "claude_before": s0.get("claude"),
             "cmds": [e["cmd"] for e in journal.entries(run_id)] if kind == "request" else [],
             "minutes": (s.get("last_run") or {}).get("minutes") if kind == "request" else None,
             "end": (s.get("last_run") or {}).get("end"), "site_changed": None}
        if "restored" in st["expect"]:
            o["site_changed"] = len(sites.outcome(task).changed)
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
    original = daemon.say
    daemon.say = _record(original)
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
        daemon.say = original
    rec = {"run": time.strftime("s%m%d-%H%M"), "model": model, "passed": sum(r["pass"] for r in results),
           "total": len(results), "scenarios": sorted(results, key=lambda r: r["id"])}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{rec['run']}.json").write_text(json.dumps(rec, indent=1))
    return rec
