"""What a build workflow's steps actually do (ghost/workflows.py). Activities do the I/O; Temporal retries
them, so each is safe to run again: the store remembers what's done and the bridge remembers keys.

Workers never talk to players: what the architect agent wanted to say is recorded (MC_SAY_FILE) and the
house ghost says it (tell)."""

import json
import re
import subprocess
import threading
import time

from temporalio import activity
from temporalio.exceptions import ApplicationError

from . import config, db, members, tools
from .db import J
from .policy import Who, build_context

ROOT = config.ROOT
TASKS = config.ROOT / "local" / "ghost-tasks"   # the agent writes plans here (local/ghost/ holds secrets it may not read)


def task(task_id):
    t = db.one("SELECT * FROM tasks WHERE id = %s", task_id)
    if not t:
        raise ApplicationError(f"no task {task_id}", non_retryable=True)
    return t


def update(task_id, state=None, **detail):
    db.run("UPDATE tasks SET state = coalesce(%s, state), detail = detail || %s, updated_at = now() WHERE id = %s",
           state, J(detail), task_id)


def say(ghost, player, text, buttons=(), task_id=None):
    """Into the outbox (sent by ghost-core's sender), and into the player's thread."""
    with db.tx() as c:
        c.execute("INSERT INTO outbox (ghost, player, text, buttons) VALUES (%s, %s, %s, %s)",
                  (ghost, player, text, J([list(b) for b in buttons])))
        th = c.execute("SELECT id FROM threads WHERE player = %s AND ghost = %s", (player, ghost)).fetchone()
        if th:
            c.execute("INSERT INTO messages (thread_id, who, text) VALUES (%s, 'ghost', %s)", (th["id"], text))


def _heartbeating(fn, every=10):
    """Run fn() in a thread, heartbeating to Temporal until it returns (a stuck worker gets noticed)."""
    box = {}

    def go():
        try:
            box["out"] = fn()
        except BaseException as e:  # noqa: BLE001 (re-raised below)
            box["err"] = e

    th = threading.Thread(target=go, daemon=True)
    th.start()
    while th.is_alive():
        th.join(every)
        activity.heartbeat()
    if "err" in box:
        raise box["err"]
    return box["out"]


@activity.defn
def design(task_id: int, revision: str | None) -> dict:
    """The mc-architect agent designs it and shows the preview (to the asker only). Revisions resume its
    conversation."""
    import sys
    sys.path.insert(0, str(ROOT))
    from architect.assistant import agent, daemon, sessions

    t = task(task_id)
    player, ctx = t["player"], t["detail"].get("context", {})
    update(task_id, "designing")
    work = TASKS / str(task_id)
    work.mkdir(parents=True, exist_ok=True)
    n = len(list(work.glob("design-*.jsonl"))) + 1
    said = work / f"said-{n}.jsonl"
    said.unlink(missing_ok=True)
    plan = str((work / "plan.py").relative_to(ROOT))
    with sessions.edit(player) as s:  # mc preview reads the player's context from here
        s.update(context=ctx)
        s.pop("pending", None)
    resume = t["detail"].get("claude") if revision else None
    text = (revision or t["request"]) + (" (You're working for the house ghost: the player answers with the ghost's "
                                         "buttons, so never mention /arc; keep what you say to one short line.)")
    run = agent.Run(player, text, ctx, plan, f"ghost:task{task_id}:{n}", config_model(), time.time(), resume=resume,
                    transcript=work / f"design-{n}.jsonl", site="" if resume else daemon.site_ahead(player, ctx),
                    env={"MC_SAY_FILE": str(said)})
    r = _heartbeating(run.wait)
    lines = [json.loads(x) for x in said.read_text().splitlines()] if said.exists() else []
    pending = sessions.get(player).get("pending")
    detail = {"claude": r["session_id"] or resume, "said": [x["text"] for x in lines], "end": r["end"],
              "minutes": r["minutes"]}
    if pending:
        detail |= {"plan": pending["plan"], "args": pending["args"], "box": pending["box"], "frame": pending["frame"],
                   "blocks": pending["blocks"], "plan_hash": tools.plan_hash(pending["plan"], pending["args"])}
    update(task_id, "waiting" if pending else "designing", **detail)
    return {"ok": bool(pending), "said": detail["said"], "end": r["end"],
            "last": (r["result"] or "").strip().splitlines()[-1:] or [""]}


def config_model():
    import os
    return os.environ.get("GHOST_MODEL_WORKER", "sonnet")


@activity.defn
def tell(task_id: int, what: str, data: dict) -> None:
    """The house ghost tells the asker (code-written; the agent's own words when it left some)."""
    t = task(task_id)
    g, p, d = t["ghost"], t["player"], t["detail"]
    words = " ".join(data.get("said") or []) if data.get("said") else ""
    if what == "preview":
        say(g, p, words or f"Here's my design ({d.get('blocks', '?')} blocks). Only you can see it.",
            [("Build it", f"/ghost yes {task_id}"), ("No thanks", f"/ghost no {task_id}")], task_id)
    elif what == "failed":
        say(g, p, words or "I couldn't draw that one. Try describing it differently?", (), task_id)
    elif what == "needs":
        if d.get("asked") == data["needs"]:  # once per task and approval: a retried step doesn't ask twice
            return
        update(task_id, "approval", need=data["needs"], asked=data["needs"])
        approver = data["approver"]
        say(g, p, f"That needs {data['who']}'s yes first ({data['why']}). I've asked them.", (), task_id)
        if approver:
            box = d.get("frame") or d.get("box")
            say(g, approver, f"{p} wants to build {t['request'][:80]!r}: {d.get('blocks')} blocks at "
                             f"{box[0][0]},{box[0][2]}..{box[1][0]},{box[1][2]}.",
                [("Approve", f"/ghost approve {task_id}"), ("Deny", f"/ghost deny {task_id}")], task_id)
    elif what == "denied":
        say(g, p, f"I can't build that: {data['why']}.", (), task_id)
    elif what == "built":
        say(g, p, f"Built it ({data.get('edit')}).", [("Undo", f"/ghost undo {task_id}")], task_id)
    elif what == "dropped":
        say(g, p, data.get("text") or "Dropped it.", (), task_id)
    elif what == "busy":
        say(g, p, f"Someone else is building right there ({data['why']}). I'll try again in a moment.", (), task_id)


@activity.defn
def clear_preview(task_id: int) -> None:
    import sys
    sys.path.insert(0, str(ROOT))
    from architect import bridge as mcb
    mcb.preview_clear(task(task_id)["player"])


def _zones(d):
    (x0, _, z0), (x1, _, z1) = d["box"]
    return config.zones_touching((x0, z0, x1, z1))


def _approved(task_id, kind, plan_hash):
    return bool(db.one("SELECT 1 FROM approvals WHERE task_id = %s AND kind = %s AND plan_hash = %s",
                       task_id, kind, plan_hash))


def _decide(t, audit=True):
    """Every zone the build touches must allow it, for the asker and for their house's ghost."""
    d = t["detail"]
    requester = members.who(t["player"])
    head = _approved(t["id"], "head", d["plan_hash"])
    for z in _zones(d):
        # each zone's own ghost does the work there (the commons: the asker's ghost); the asker must be
        # allowed too, so building in another house's land still needs that house's head
        ghost = Who.ghost(z.house) if z.house else (Who.ghost(t["ghost"]) if t["ghost"] != "spirit" else None)
        zh = _approved(t["id"], f"zone_head:{z.house}", d["plan_hash"]) if z.house else False
        ctx = build_context(d["blocks"], head, zh)
        try:
            if audit:
                tools.act("Build", requester, ghost, z, ctx, task_id=t["id"])
            else:
                from .policy import both
                dec = both(requester, ghost, "Build", z, ctx)
                if not dec.allowed:
                    raise tools.Denied(dec)
        except tools.Denied as e:
            return {"allowed": False, "zone": z.id, "rules": e.decision.rules, **_what_would_help(requester, z, d)}
    return {"allowed": True}


def _what_would_help(requester, z, d):
    if requester.role == "guest":
        return {"needs": None, "why": "you haven't picked a house yet (/ghost house)"}
    if z.protected:
        return {"needs": None, "why": f"{z.id.replace('_', ' ')} is protected"}
    if d["blocks"] > 20000:
        return {"needs": None, "why": f"it's {d['blocks']} blocks; the most is 20,000"}
    if z.house and z.house != requester.house:
        head = members.head_of(z.house) or config.houses()["owner"].lower()
        return {"needs": f"zone_head:{z.house}", "approver": head,
                "who": f"{config.house(z.house)['name']}'s head ({head})",
                "why": f"it's in {config.house(z.house)['name']}'s land"}
    head = members.head_of(requester.house) or config.houses()["owner"].lower()
    return {"needs": "head", "approver": head, "who": f"your house head ({head})",
            "why": f"it's {d['blocks']} blocks; over 2,000 needs your head's yes"}


@activity.defn
def check(task_id: int) -> dict:
    return _decide(task(task_id))


@activity.defn
def place(task_id: int) -> dict:
    """Authorize again (approvals are bound to the plan hash), reserve budget, lease the chunks, sign a
    grant, place with an idempotency key. A retry after a crash finds the key and changes nothing."""
    t = task(task_id)
    d = t["detail"]
    if d.get("edit"):  # finished on an earlier attempt
        return {"edit": d["edit"], "repeat": True}
    if tools.plan_hash(d["plan"], d["args"]) != d["plan_hash"]:
        raise ApplicationError("the plan changed after it was approved", non_retryable=True)
    v = _decide(t)
    if not v["allowed"]:
        raise ApplicationError(f"not allowed any more: {v.get('why')}", non_retryable=True)
    house = members.who(t["player"]).house or t["ghost"]
    bud = d.get("budget_id")
    if not bud:
        try:
            bud = tools.reserve(house, "blocks", d["blocks"], task_id)
        except tools.OverBudget as e:
            raise ApplicationError(str(e), non_retryable=True) from e
        update(task_id, budget_id=bud)
    holder = f"task{task_id}"
    try:
        tools.lease(tools.chunks(d["box"]), holder)
    except tools.Busy as e:
        raise ApplicationError(str(e), type="Busy") from e  # retried with backoff
    update(task_id, "building")
    lo, hi = d["box"]
    g = tools.grant(task_id, "world", lo, hi, int(d["blocks"] * 1.5) + 64)
    env = {"MC_PLACE_KEY": f"ghost-task{task_id}", "MC_PLACE_GRANT": json.dumps(g), "MC_RUN_ID": f"ghost:task{task_id}"}
    import os
    r = _heartbeating(lambda: subprocess.run(["./mc.py", "place", d["plan"], *d["args"]], cwd=ROOT, text=True,
                                             capture_output=True, env={**os.environ, **env}, timeout=600))
    out = r.stdout + r.stderr
    m = re.search(r"(?:placed|already placed) (e\d+)", out)
    if r.returncode != 0 or not m:
        raise ApplicationError(f"place failed: {out.strip().splitlines()[-1][:300] if out.strip() else r.returncode}")
    tools.settle(bud)
    tools.unlease(holder)
    update(task_id, "done", edit=m.group(1))
    return {"edit": m.group(1), "repeat": "already placed" in out}


@activity.defn
def finish(task_id: int, state: str) -> None:
    update(task_id, state)
    db.run("UPDATE threads SET task_id = NULL WHERE task_id = %s", task_id)
    tools.unlease(f"task{task_id}")
