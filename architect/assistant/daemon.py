"""`mc architect serve`: the loop between the game and the agent. Each /arc event is handled here: yes, no,
undo, cancel and status at once (no model), requests by an agent run in a thread (one per player, a few
at a time, the rest wait their turn). Everything said goes back through the bridge's /say."""

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque

from .. import bridge, journal
from . import agent, sessions
from .sessions import ROOT

MAX_JOBS = 2
FRESH = 30 * 60      # a conversation older than this (no preview waiting) starts over
lock = threading.Lock()
jobs = {}            # player -> agent.Run
queue = deque()      # (event, model) waiting for a free slot


def say(player, text, tone="info", buttons=()):
    try:
        bridge.say(player, text, tone, buttons)
    except bridge.BridgeError:
        pass


def mc(player, *argv):
    """Run an mc command for a player's job (journalled under their run id); (ok, output)."""
    with sessions.edit(player) as s:
        run_id = f"arc:{player}:{s['requests']}"
    env = {**os.environ, "MC_RUN_ID": run_id, "MC_PLAYER": player}
    r = subprocess.run([sys.executable, str(ROOT / "mc.py"), *argv], cwd=ROOT, env=env, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


# ---- the words that need no model ----

def on_yes(player):
    s = sessions.get(player)
    if player in jobs:
        return say(player, "Hang on, I'm still drawing. I'll show you a preview first.", "warn")
    p = s.get("pending")
    if not p:
        return say(player, "There's nothing waiting for a yes. Tell me what to build: /arc <idea>.", "warn")
    ok, out = mc(player, "place", p["plan"], *p["args"])
    m = re.search(r"placed (e\d+)", out)
    if not ok or not m:
        return say(player, f"I couldn't build it: {out.splitlines()[-1][:200] if out else 'no output'}", "warn")
    bridge.preview_clear(player)
    with sessions.edit(player) as s:
        s["builds"].append({"edit": m.group(1), "plan": p["plan"], "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        s.pop("pending", None)
        s.pop("claude", None)  # that conversation is done
    say(player, f"Built it ({m.group(1)}).", "done", [("Undo", "/arc undo")])


def on_no(player):
    bridge.preview_clear(player)
    with sessions.edit(player) as s:
        had = s.pop("pending", None)
        s.pop("claude", None)
    say(player, "Dropped it. Tell me something else to build any time." if had else "Nothing to drop.", "info")


def on_undo(player):
    s = sessions.get(player)
    if not s.get("builds"):
        return say(player, "You have no architect builds to take back.", "warn")
    eid = s["builds"][-1]["edit"]
    ok, out = mc(player, "undo", eid)
    if not ok:
        return say(player, f"I couldn't undo {eid}: {out.splitlines()[-1][:200]}", "warn")
    with sessions.edit(player) as s:
        s["builds"].pop()
    say(player, f"Took back {eid}; the ground is as it was.", "done")


def on_cancel(player):
    with lock:
        run = jobs.get(player)
        waiting = [q for q in queue if q[0]["player"] == player]
        for q in waiting:
            queue.remove(q)
    if run:
        run.cancel()  # the job's thread says so when it ends
    elif waiting:
        say(player, "Cancelled your request before I started it.")
    else:
        say(player, "I'm not working on anything for you.")


def on_status(player):
    s = sessions.get(player)
    bits = ["I'm working on your request." if player in jobs else "I'm free."]
    if s.get("pending"):
        bits.append("A preview is waiting for you: /arc yes or /arc no.")
    if s.get("builds"):
        bits.append(f"Your last build is {s['builds'][-1]['edit']} (/arc undo takes it back).")
    say(player, " ".join(bits))


# ---- requests: the agent ----

AHEAD = {"south": (0, 1), "north": (0, -1), "east": (1, 0), "west": (-1, 0)}


def site_ahead(player, ctx):
    """The ground where a build will most likely go (the selection, or a 16x16 patch just in front of
    them), read before Claude starts so the agent doesn't spend a turn on it."""
    sel, pos = ctx.get("selection"), ctx.get("pos") or [0, 0, 0]
    if sel:
        lo, hi = sel["min"], sel["max"]
        cx, cz, w, d = (lo[0] + hi[0]) // 2, (lo[2] + hi[2]) // 2, hi[0] - lo[0] + 5, hi[2] - lo[2] + 5
    else:
        dx, dz = AHEAD.get(ctx.get("facing"), (0, 1))
        cx, cz, w, d = int(pos[0]) + 10 * dx, int(pos[2]) + 10 * dz, 16, 16
    ok, out = mc(player, "site", f"{cx},{cz}", f"{w},{d}")
    return out if ok else ""


def start(event, model, log):
    t_req = time.time()  # the player's wait starts here
    player, text, ctx = event["player"], event["text"], event["context"]
    if text.lower().startswith("big "):
        text, model = text[4:], "opus"
    s = sessions.get(player)
    talking = s.get("claude") and (s.get("pending") or time.time() - s.get("last_request_t", 0) < FRESH)
    with sessions.edit(player) as s:
        s["requests"] += 1
        s["context"] = ctx
        s["last_request"] = text
        s["last_request_t"] = time.time()
        n = s["requests"]
    plan = sessions.workspace(player) / "plan.py"
    run_id = f"arc:{player}:{n}"
    say(player, "Changing the design..." if talking else f"On it: {text[:80]}", "thinking")
    site = "" if talking or not agent.LEAN else site_ahead(player, ctx)
    runs = sessions.workspace(player) / "runs"
    runs.mkdir(exist_ok=True)
    run = agent.Run(player, text, ctx, str(plan.relative_to(ROOT)), run_id, model,
                    resume=s.get("claude") if talking else None, transcript=runs / f"{n}.jsonl", site=site)
    run.t_req = t_req
    with lock:
        jobs[player] = run
    log(f"{player} #{n} ({model}{', resumed' if talking else ''}): {text}")
    threading.Thread(target=finish, args=(player, run, run_id, log), daemon=True).start()


def finish(player, run, run_id, log):
    r = run.wait()
    with sessions.edit(player) as s:
        if r["session_id"]:
            s["claude"] = r["session_id"]
        s["last_run"] = {k: r[k] for k in ("end", "api_usd", "minutes")} | {"run_id": run_id}
    es = journal.entries(run_id)
    said = {e["cmd"] for e in es}
    t0 = run.t_req
    at = lambda e: time.mktime(time.strptime(e["t"], "%Y-%m-%dT%H:%M:%S"))  # noqa: E731
    first = lambda c: next((round(at(e) - t0) for e in es if e["cmd"] == c and e["ok"] and at(e) >= t0 - 1), None)  # noqa: E731
    r["to_preview_s"], r["to_say_s"] = first("preview"), first("say")  # what the player waits for
    (sessions.workspace(player) / "runs" / f"{run_id.rsplit(':', 1)[1]}.json").write_text(json.dumps(r, indent=1))
    log(f"{player}: {r['end']} in {r['minutes']} min (preview at {r['to_preview_s']}s, told at {r['to_say_s']}s), "
        f"${r['api_usd'] or 0:.2f}, {len(r['tools'])} tool calls: "
        f"{r['result'].strip()[-160:]!r}")
    if r["end"] == "cancelled":
        say(player, "Stopped.", "warn")
    elif r["end"] != "done":
        say(player, f"Something went wrong on my side ({r['end']}). Try again, or ask the server owner.", "warn")
        log(r.get("stderr", ""))
    elif "say" not in said:  # the agent didn't talk to them: pass on its last words
        say(player, r["result"].strip().splitlines()[-1][:300] if r["result"].strip() else "Done.")
    with lock:
        jobs.pop(player, None)
        nxt = queue.popleft() if queue else None
    if nxt:
        start(*nxt, log)


def on_request(event, model, log):
    player = event["player"]
    with lock:
        busy, full = player in jobs, len(jobs) >= MAX_JOBS
        if not busy and full:
            queue.append((event, model))
    if busy:
        say(player, "I'm still on your last request. /arc cancel stops it.", "warn")
    elif full:
        say(player, "I'm drawing for someone else right now; you're next.", "thinking")
    else:
        start(event, model, log)


HANDLERS = {"yes": on_yes, "no": on_no, "undo": on_undo, "cancel": on_cancel, "status": on_status}


def serve(model="sonnet", log=print):
    log(f"architect listening (builder model {model}, {MAX_JOBS} at a time). Ctrl-C to stop.")
    while True:
        try:
            events = bridge.inbox(wait=25)
        except bridge.BridgeError as e:
            log(f"bridge unavailable ({e}); retrying in 10 s")
            time.sleep(10)
            continue
        for e in events:
            try:
                if e["kind"] == "request":
                    on_request(e, model, log)
                else:
                    log(f"{e['player']}: {e['kind']}")
                    HANDLERS[e["kind"]](e["player"])
            except Exception as ex:  # one bad event mustn't stop the architect
                log(f"error handling {e}: {ex!r}")
                say(e["player"], "Something went wrong on my side. Try again in a moment.", "warn")
            finally:
                bridge.ack([e["id"]])


def status():
    with lock:
        busy = list(jobs)
    out = [f"working for: {', '.join(busy) or 'nobody'}; waiting: {len(queue)}"]
    for name, s in sessions._read().items():
        out.append(f"  {s['player']}: {s['requests']} requests, {len(s['builds'])} builds"
                   + (", preview waiting" if s.get("pending") else "")
                   + (f", last: {s.get('last_run', {}).get('end')}" if s.get("last_run") else ""))
    return "\n".join(out)
