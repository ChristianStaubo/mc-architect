"""The tool layer: the only way the ghost touches the world (docs/ghost/design.md, Layers).

Every action: ask the policy engine (requester AND ghost), write the audit row *before* acting, run it,
record the result. Builds also reserve budget, take leases on the chunks they touch, and carry a signed
grant the plugin checks; the bridge's idempotency key makes a retried step harmless.
"""

import hashlib
import hmac
import json
import time

from . import config, db, policy
from .db import J

LIMITS = {"requests": 40, "blocks": 60_000}   # per house per day (requests and blocks until we're on the API)
LEASE_S = 15 * 60


class Denied(Exception):
    def __init__(self, decision):
        super().__init__(decision.reason())
        self.decision = decision


class OverBudget(Exception):
    pass


class Busy(Exception):
    """Someone else holds a lease on part of the area."""


def act(action, requester, ghost, resource, context=None, task_id=None, trace_id=None, untrusted=False,
        detail=None, run=None):
    """Decide, audit, then run(). Raises Denied (audited) when either principal isn't allowed."""
    d = policy.both(requester, ghost, action, resource, context) if ghost and ghost != requester \
        else policy.authorize(requester, action, resource, context)
    res = resource.id if isinstance(resource, config.Zone) else str(resource)
    row = db.one("INSERT INTO audit (trace_id, task_id, ghost, requester, action, resource, decision, rules, "
                 "untrusted, detail, result) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                 trace_id, task_id, ghost and ghost.id, f"{requester.kind}:{requester.id}", action, res,
                 "allow" if d.allowed else "deny", d.rules, untrusted, J({"context": context, **(detail or {})}),
                 ("ok" if run is None else None) if d.allowed else "skipped")
    if not d.allowed:
        raise Denied(d)
    if run is None:
        return d
    try:
        out = run()
    except Exception as e:
        db.run("UPDATE audit SET result = %s WHERE id = %s", f"error: {e}"[:500], row["id"])
        raise
    db.run("UPDATE audit SET result = 'ok' WHERE id = %s", row["id"])
    return out


# ---- budgets: reserve before, settle after ----

def reserve(house, kind, amount, task_id, state="reserved", conn=None):
    """Hold `amount` of today's allowance (state 'settled' for an instant spend). Raises OverBudget."""
    if conn:
        return _reserve(conn, house, kind, amount, task_id, state)
    with db.tx() as c:
        return _reserve(c, house, kind, amount, task_id, state)


def _reserve(c, house, kind, amount, task_id, state):
    c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"budget:{house}",))
    used = c.execute("SELECT coalesce(sum(amount), 0) AS n FROM budget WHERE house = %s AND day = current_date "
                     "AND kind = %s AND state <> 'released'", (house, kind)).fetchone()["n"]
    if used + amount > LIMITS[kind]:
        raise OverBudget(f"{house} has used {used} of {LIMITS[kind]} {kind} today; this needs {amount}")
    return c.execute("INSERT INTO budget (house, task_id, kind, amount, state) VALUES (%s, %s, %s, %s, %s) "
                     "RETURNING id", (house, task_id, kind, amount, state)).fetchone()["id"]


def settle(budget_id, amount=None):
    db.run("UPDATE budget SET state = 'settled', amount = coalesce(%s, amount) WHERE id = %s", amount, budget_id)


def used_today(house):
    rows = db.all("SELECT kind, coalesce(sum(amount), 0) AS n FROM budget WHERE house = %s AND day = current_date "
                  "AND state <> 'released' GROUP BY kind", house)
    return {r["kind"]: r["n"] for r in rows}


# ---- leases on world areas (chunk columns) ----

def chunks(box, world="world"):
    (x0, _, z0), (x1, _, z1) = box
    return [f"{world}:{cx}:{cz}" for cx in range(x0 >> 4, (x1 >> 4) + 1) for cz in range(z0 >> 4, (z1 >> 4) + 1)]


def lease(areas, holder, seconds=LEASE_S):
    """Take (or renew) every area for `holder`, all or nothing."""
    with db.tx() as c:
        for a in areas:
            r = c.execute("INSERT INTO leases (area, holder, expires_at) VALUES (%s, %s, now() + %s * interval '1 second') "
                          "ON CONFLICT (area) DO UPDATE SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at "
                          "WHERE leases.holder = EXCLUDED.holder OR leases.expires_at < now() RETURNING area",
                          (a, holder, seconds)).fetchone()
            if not r:
                other = c.execute("SELECT holder FROM leases WHERE area = %s", (a,)).fetchone()
                raise Busy(f"{a} is leased to {other['holder']}")


def unlease(holder):
    db.run("DELETE FROM leases WHERE holder = %s", holder)


# ---- signed grants (checked by the plugin before it places anything) ----

def grant(task, world, lo, hi, max_blocks, seconds=600):
    g = {"task": str(task), "world": world, "min": list(lo), "max": list(hi), "max_blocks": int(max_blocks),
         "exp": int(time.time()) + seconds}
    msg = "|".join([g["task"], g["world"], json.dumps(g["min"], separators=(",", ":")),
                    json.dumps(g["max"], separators=(",", ":")), str(g["max_blocks"]), str(g["exp"])])
    key = bytes.fromhex(config.GRANT_KEY.read_text().strip())
    g["sig"] = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
    return g


def plan_hash(plan_path, args):
    """The plan's content and placement: an approval is bound to this, so the plan can't change after it."""
    return hashlib.sha256((config.ROOT / plan_path).read_bytes() + json.dumps(args).encode()).hexdigest()[:20]
