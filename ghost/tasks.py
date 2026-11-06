"""A task's lifecycle, in one place: the states, which count as open, and the one way to change them.

new -> designing <-> waiting -> approval -> building -> done -> undone
                  \\-> failed / dropped / denied (from anywhere open)
A finished task never reopens; the only move out of done is undone."""

from . import db
from .db import J

OPEN = ("new", "designing", "waiting", "approval", "building")   # not finished
TALKING = ("designing", "waiting", "approval")                  # a design the player is discussing
BUSY = ("new", "designing", "approval", "building")             # can't take another request yet
FINAL = ("done", "dropped", "failed", "denied", "undone")


def get(task_id):
    return db.one("SELECT * FROM tasks WHERE id = %s", task_id)


def latest(player, states=OPEN):
    return db.one("SELECT * FROM tasks WHERE player = %s AND state = ANY(%s) ORDER BY id DESC LIMIT 1",
                  player, list(states))


def move(task_id, state=None, **detail):
    """Set the state (None: keep it) and merge `detail` in. Returns False when the task had already
    finished (a late step, or the watchdog racing a finished build): nothing changes then."""
    if state is None:
        r = db.one("UPDATE tasks SET detail = detail || %s, updated_at = now() WHERE id = %s RETURNING id",
                   J(detail), task_id)
    else:
        r = db.one("UPDATE tasks SET state = %s, detail = detail || %s, updated_at = now() WHERE id = %s AND "
                   "(state <> ALL(%s) OR (state = 'done' AND %s = 'undone')) RETURNING id",
                   state, J(detail), task_id, list(FINAL), state)
    return bool(r)
