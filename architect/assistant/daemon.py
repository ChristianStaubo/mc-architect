"""`mc architect serve`: the loop between the game and the agent. Each /arc event is handled here: yes, no,
undo, cancel and status at once (no model), requests by an agent run in a thread (one per player, a few
at a time, the rest wait their turn). Everything said goes back through the bridge's /say."""

import json
import re
import threading
import time
from collections import deque

from .. import bridge, journal, run
from ..parts import FACE_STEP
from . import agent, sessions
from .sessions import ROOT

MAX_JOBS = 2
FRESH = 30 * 60      # a conversation older than this (no preview waiting) starts over
lock = threading.Lock()
jobs = {}            # player -> agent.Run
queue = deque()      # (event, model) waiting for a free slot
listeners = []       # callables(player, text, tone) told everything said (the scenario suite listens)


def say(player, text, tone="info", buttons=()):
    for hear in listeners:
        hear(player, text, tone)
    try:
        bridge.say(player, text, tone, buttons)
    except bridge.BridgeError:
        pass


def mc(player, *argv):
    """Run an mc command for a player's job (journalled under their run id); (ok, output)."""
    return run.mc(*argv, MC_RUN_ID=sessions.run_id(player), MC_PLAYER=player)


def busy(player):
    """Working for them, or their request is waiting for a free slot."""
    with lock:
        return player in jobs or any(e["player"] == player for e, _ in queue)


# ---- the words that need no model ----

def on_yes(player):
    if busy(player):
        return say(player, "Hang on, I'm still drawing. I'll show you a preview first.", "warn")
    p = sessions.get(player).get("pending")
    if not p:
        return say(player, "There's nothing waiting for a yes. Tell me what to build: /arc <idea>.", "warn")
    ok, out = mc(player, "place", p["plan"], *p["args"])
    m = re.search(r"placed (e\d+)", out)
    if not ok or not m:
        return say(player, f"I couldn't build it: {out.splitlines()[-1][:200] if out else 'no output'}", "warn")
    bridge.preview_clear(player)
    with sessions.edit(player) as s:
        s["builds"].append({"edit": m.group(1), "plan": p["plan"], "at": sessions.now()})
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
    bits = ["I'm working on your request." if busy(player) else "I'm free."]
    if s.get("pending"):
        bits.append("A preview is waiting for you: /arc yes or /arc no.")
    if s.get("builds"):
        bits.append(f"Your last build is {s['builds'][-1]['edit']} (/arc undo takes it back).")
    say(player, " ".join(bits))


# ---- requests: the agent ----

def site_ahead(player, ctx):
    """The ground where a build will most likely go (the selection, or a 16x16 patch just in front of
    them), read before Claude starts so the agent doesn't spend a turn on it."""
    sel, pos = ctx.get("selection"), ctx.get("pos") or [0, 0, 0]
    if sel:
        lo, hi = sel["min"], sel["max"]
        cx, cz, w, d = (lo[0] + hi[0]) // 2, (lo[2] + hi[2]) // 2, hi[0] - lo[0] + 5, hi[2] - lo[2] + 5
    else:
        dx, dz = FACE_STEP.get(ctx.get("facing"), (0, 1))
        cx, cz, w, d = int(pos[0]) + 10 * dx, int(pos[2]) + 10 * dz, 16, 16
    ok, out = mc(player, "site", f"{cx},{cz}", f"{w},{d}")
    return out if ok else ""


def start(event, model, log):
    t0 = time.time()  # the player's wait starts here
    player, text, ctx = event["player"], event["text"], event["context"]
    if text.lower().startswith("big "):
        text, model = text[4:], "opus"
    before = sessions.get(player)
    talking = before.get("claude") and (before.get("pending") or t0 - before.get("last_request_t", 0) < FRESH)
    with sessions.edit(player) as s:
        s["requests"] += 1
        s.update(context=ctx, last_request=text, last_request_t=t0)
        n = s["requests"]
    run_id = sessions.run_id(player, n)
    say(player, "Changing the design..." if talking else f"On it: {text[:80]}", "thinking")
    runs = sessions.workspace(player) / "runs"
    runs.mkdir(exist_ok=True)
    job = agent.Run(player, text, ctx, str((sessions.workspace(player) / "plan.py").relative_to(ROOT)), run_id, model,
                    t0, resume=before.get("claude") if talking else None, transcript=runs / f"{n}.jsonl",
                    site="" if talking else site_ahead(player, ctx))
    with lock:
        jobs[player] = job
    log(f"{player} #{n} ({model}{', resumed' if talking else ''}): {text}")
    threading.Thread(target=finish, args=(player, job, run_id, log), daemon=True).start()


def _timings(run_id, t0):
    """Seconds from the player's /arc to each mc command's first success in this request."""
    firsts = {}
    for e in journal.entries(run_id):
        t = time.mktime(time.strptime(e["t"], "%Y-%m-%dT%H:%M:%S"))
        if e["ok"] and t >= t0 - 1:
            firsts.setdefault(e["cmd"], round(t - t0))
    return firsts


def finish(player, job, run_id, log):
    r = job.wait()
    with sessions.edit(player) as s:
        if r["session_id"]:
            s["claude"] = r["session_id"]
        s["last_run"] = {k: r[k] for k in ("end", "api_usd", "minutes")} | {"run_id": run_id}
    firsts = _timings(run_id, job.t0)
    r["to_preview_s"], r["to_say_s"] = firsts.get("preview"), firsts.get("say")  # what the player waits for
    (sessions.workspace(player) / "runs" / f"{run_id.rsplit(':', 1)[1]}.json").write_text(json.dumps(r, indent=1))
    log(f"{player}: {r['end']} in {r['minutes']} min (preview at {r['to_preview_s']}s, told at {r['to_say_s']}s), "
        f"${r['api_usd'] or 0:.2f}, {len(r['tools'])} tool calls: {r['result'].strip()[-160:]!r}")
    if r["end"] == "cancelled":
        say(player, "Stopped.", "warn")
    elif r["end"] != "done":
        say(player, f"Something went wrong on my side ({r['end']}). Try again, or ask the server owner.", "warn")
    elif "say" not in firsts:  # the agent didn't talk to them: pass on its last words
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


def handle(event, model="sonnet", log=print):
    """One /arc event: a request goes to the agent, the other words are answered here."""
    if event["kind"] == "request":
        on_request(event, model, log)
    else:
        log(f"{event['player']}: {event['kind']}")
        HANDLERS[event["kind"]](event["player"])


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
                handle(e, model, log)
            except Exception as ex:  # one bad event mustn't stop the architect
                log(f"error handling {e}: {ex!r}")
                say(e["player"], "Something went wrong on my side. Try again in a moment.", "warn")
            finally:
                bridge.ack([e["id"]])


def status():
    with lock:
        busy = list(jobs)
    out = [f"working for: {', '.join(busy) or 'nobody'}; waiting: {len(queue)}"]
    for s in sessions.all_players().values():
        out.append(f"  {s['player']}: {s['requests']} requests, {len(s['builds'])} builds"
                   + (", preview waiting" if s.get("pending") else "")
                   + (f", last: {s.get('last_run', {}).get('end')}" if s.get("last_run") else ""))
    return "\n".join(out)
