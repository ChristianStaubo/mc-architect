"""What a build workflow's steps actually do (ghost/workflows.py). Activities do the I/O; Temporal retries
them, so each is safe to run again: the store remembers what's done and the bridge remembers keys.

Workers never talk to players: the architect agent runs with MC_GHOST (architect/cli/common.ghost_mode),
so what it says is recorded and the house ghost says it (tell), and its previews are answered with the
ghost's buttons."""

import json
import re
import threading
import time

from temporalio import activity
from temporalio.exceptions import ApplicationError

from . import bridge as _path, config, db, members, model, outbox, tasks, tools  # noqa: F401 (_path: architect/ on sys.path)
from .policy import acting_ghost, build_context
from architect import bridge as mcb, run  # noqa: E402
from architect.assistant import agent, daemon, sessions  # noqa: E402
from architect.occupied import occupied  # noqa: E402

TASKS = config.ROOT / "local" / "ghost-tasks"   # the agent writes plans here (local/ghost/ holds secrets it may not read)


def task(task_id):
    t = tasks.get(task_id)
    if not t:
        raise ApplicationError(f"no task {task_id}", non_retryable=True)
    return t


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


def brief(t, revision):
    """What the designer is told: the player's own words (never a paraphrase), the router's reading as a
    note, and the styles that matter: their house's, and the land's it goes on."""
    d = t["detail"]
    words, note = (revision["words"], revision.get("note")) if revision else (t["request"], d.get("note"))
    ctx = (revision or {}).get("context") or d.get("context") or {}
    land = config.zone_of(ctx)
    house = members.who(t["player"]).house
    lines = [f'{"Their change" if revision else "Their request"}, in their words: "{words}"']
    if note and note.strip() != words.strip():
        lines.append(f"(The house ghost took it as: {note})")
    if house:
        lines.append(f"Their house's style (\"our style\" means this): {config.style(house)}")
    if land.house and land.house != house:
        lines.append(f"It goes in {config.house(land.house)['name']}'s land, whose style is: {config.style(land.house)}")
    if ctx.get("target"):
        lines.append(f"They're looking at {ctx['target']['pos']} ({ctx['target'].get('block', '?')}); 'this', 'that' "
                     "and 'here' mean around there. To copy a building they point at, look at it (mc render).")
    lines.append("(You're working for the house ghost: the player answers with the ghost's buttons, so never mention "
                 "/arc; keep what you say to one short line.)")
    return "\n".join(lines), ctx


@activity.defn
def design(task_id: int, revision: dict | None) -> dict:
    """The mc-architect agent designs it and shows the preview (to the asker only). Revisions resume its
    conversation."""
    t = task(task_id)
    player = t["player"]
    work = TASKS / str(task_id)
    work.mkdir(parents=True, exist_ok=True)
    n = len(list(work.glob("design-*.jsonl"))) + 1
    said = work / f"said-{n}.jsonl"
    said.unlink(missing_ok=True)
    text, ctx = brief(t, revision)
    briefs = (t["detail"].get("briefs") or []) + [text]   # what each attempt was told (evals and replays read it)
    tasks.move(task_id, "designing", briefs=briefs, **({"context": ctx} if revision else {}))
    with sessions.edit(player) as s:  # mc preview reads the player's context from here
        s.update(context=ctx)
        s.pop("pending", None)
    resume = t["detail"].get("claude") if revision else None
    job = agent.Run(player, text, ctx, str((work / "plan.py").relative_to(config.ROOT)), f"ghost:task{task_id}:{n}",
                    model.name("worker"), time.time(), resume=resume, transcript=work / f"design-{n}.jsonl",
                    site="" if resume else daemon.site_ahead(player, ctx),
                    env={"MC_GHOST": json.dumps({"say_file": str(said), "preview_hint": outbox.PREVIEW_HINT})})
    r = _heartbeating(job.wait)
    lines = [json.loads(x) for x in said.read_text().splitlines()] if said.exists() else []
    pending = sessions.get(player).get("pending")
    detail = {"claude": r["session_id"] or resume, "said": [x["text"] for x in lines], "end": r["end"],
              "minutes": r["minutes"]}
    if pending:
        detail |= {"plan": pending["plan"], "args": pending["args"], "box": pending["box"], "frame": pending["frame"],
                   "blocks": pending["blocks"], "plan_hash": tools.plan_hash(pending["plan"], pending["args"])}
    tasks.move(task_id, "waiting" if pending else None, **detail)
    return {"ok": bool(pending), "said": detail["said"], "end": r["end"]}


@activity.defn
def tell(task_id: int, what: str, data: dict) -> None:
    """The house ghost tells the asker (code-written; the agent's own words when it left some)."""
    t = task(task_id)
    g, p, d = t["ghost"], t["player"], t["detail"]
    words = " ".join(data.get("said") or [])
    if what == "preview":
        outbox.say(g, p, words or f"Here's my design ({d.get('blocks', '?')} blocks). Only you can see it.",
                   outbox.preview_buttons(task_id))
    elif what == "failed":
        outbox.say(g, p, words or "I couldn't draw that one. Try describing it differently?")
    elif what == "needs":
        if d.get("asked") == data["needs"]:  # once per task and approval: a retried step doesn't ask twice
            return
        tasks.move(task_id, "approval", need=data["needs"], asked=data["needs"])
        outbox.say(g, p, f"That needs {data['who']}'s yes first ({data['why']}). I've asked them.")
        (x0, _, z0), (x1, _, z1) = d.get("frame") or d["box"]
        outbox.say(g, data["approver"], f"{p} wants to build {t['request'][:80]!r}: {d.get('blocks')} blocks at "
                                        f"{x0},{z0}..{x1},{z1}.",
                   [("Approve", f"/ghost approve {task_id}"), ("Deny", f"/ghost deny {task_id}")])
    elif what == "denied":
        outbox.say(g, p, f"I can't build that: {data['why']}.")
    elif what == "built":
        outbox.say(g, p, f"Built it ({data.get('edit')}).", [("Undo", f"/ghost undo {task_id}")])
    elif what == "dropped":
        outbox.say(g, p, data.get("text") or "Dropped it.")


@activity.defn
def clear_preview(task_id: int) -> None:
    mcb.preview_clear(task(task_id)["player"])


def _approved(task_id, kind, plan_hash):
    return bool(db.one("SELECT 1 FROM approvals WHERE task_id = %s AND kind = %s AND plan_hash = %s",
                       task_id, kind, plan_hash))


def _decide(t):
    """Every zone the build touches must allow it, for the asker and for the ghost that works there."""
    d = t["detail"]
    requester = members.who(t["player"])
    head = _approved(t["id"], "head", d["plan_hash"])
    (bx0, _, bz0), (bx1, _, bz1) = d.get("frame") or d["box"]
    on = occupied((bx0, bz0), (bx1, bz1), ignore_runs=(f"ghost:task{t['id']}",))
    (x0, _, z0), (x1, _, z1) = d["box"]
    for z in config.zones_touching((x0, z0, x1, z1)):
        zh = _approved(t["id"], f"zone_head:{z.house}", d["plan_hash"]) if z.house else False
        try:
            tools.act("Build", requester, acting_ghost(z, t["ghost"]), z, build_context(d["blocks"], head, zh, bool(on)),
                      task_id=t["id"])
        except tools.Denied as e:
            return {"allowed": False, "zone": z.id, "rules": e.decision.rules, **_what_would_help(requester, z, d, on)}
    return {"allowed": True}


def _what_would_help(requester, z, d, on=()):
    if on:
        return {"needs": None, "why": f"it would land on {', '.join(on[:3])}; ask me for it on clear ground"}
    if requester.role == "guest":
        return {"needs": None, "why": "you haven't picked a house yet (/ghost house)"}
    if z.protected:
        return {"needs": None, "why": f"{z.id.replace('_', ' ')} is protected"}
    if d["blocks"] > 20000:
        return {"needs": None, "why": f"it's {d['blocks']} blocks; the most is 20,000"}
    if z.house and z.house != requester.house:
        name, head = config.house(z.house)["name"], members.approver(z.house)
        return {"needs": f"zone_head:{z.house}", "approver": head, "who": f"{name}'s head ({head})",
                "why": f"it's in {name}'s land"}
    head = members.approver(requester.house)
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
        return {"edit": d["edit"]}
    if tools.plan_hash(d["plan"], d["args"]) != d["plan_hash"]:
        raise ApplicationError("the plan changed after it was approved", non_retryable=True)
    v = _decide(t)
    if not v["allowed"]:
        raise ApplicationError(f"not allowed any more: {v.get('why')}", non_retryable=True)
    bud = d.get("budget_id")
    if not bud:
        try:
            bud = tools.reserve(members.who(t["player"]).house or t["ghost"], "blocks", d["blocks"], task_id)
        except tools.OverBudget as e:
            raise ApplicationError(str(e), non_retryable=True) from e
        tasks.move(task_id, None, budget_id=bud)
    holder = f"task{task_id}"
    try:
        tools.lease(tools.chunks(d["box"]), holder)
    except tools.Busy as e:
        raise ApplicationError(str(e), type="Busy") from e  # retried with backoff
    tasks.move(task_id, "building")
    lo, hi = d["box"]
    g = tools.grant(task_id, "world", lo, hi, int(d["blocks"] * 1.5) + 64)
    ok, out = _heartbeating(lambda: run.mc("place", d["plan"], *d["args"], timeout=600, MC_PLACE_KEY=f"ghost-task{task_id}",
                                           MC_PLACE_GRANT=json.dumps(g), MC_RUN_ID=f"ghost:task{task_id}"))
    m = re.search(r"(?:placed|already placed) (e\d+)", out)
    if not ok or not m:
        raise ApplicationError(f"place failed: {out.splitlines()[-1][:300] if out else 'no output'}")
    tools.settle(bud)
    tools.unlease(holder)
    tasks.move(task_id, "done", edit=m.group(1))
    return {"edit": m.group(1)}


@activity.defn
def finish(task_id: int, state: str) -> None:
    tasks.move(task_id, state)
    tools.unlease(f"task{task_id}")
