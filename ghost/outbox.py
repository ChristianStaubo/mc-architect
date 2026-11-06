"""What the ghosts say: written to the outbox (with the state change that caused it, when there's a
transaction) and to the player's thread, then sent by one loop woken by LISTEN/NOTIFY. Every writer
(ghost-core, the workers, the watchdog) goes through say(), so every reply follows the same rules and the
router sees all of them in the conversation."""

import select

import psycopg

from . import bridge, config, db
from .db import J

MAX_CHARS = 440
YES, NO = "Build it", "No thanks"   # a preview's answers: the buttons, and the hint on the preview bar
PREVIEW_HINT = f"{YES} / {NO} in chat"


def preview_buttons(task_id):
    return ((YES, f"/ghost yes {task_id}"), (NO, f"/ghost no {task_id}"))


def say(ghost, player, text, buttons=(), thread_id=None, conn=None, key=None):
    """Queue a line from `ghost` to `player` (None: everyone). The thread is found when not given.
    key: an idempotency key; a retried step saying the same thing again (same key) queues nothing."""
    text = text[:MAX_CHARS]

    def write(c):
        if not c.execute("INSERT INTO outbox (ghost, player, text, buttons, key) VALUES (%s, %s, %s, %s, %s) "
                         "ON CONFLICT (key) DO NOTHING RETURNING id",
                         (ghost, player, text, J([list(b) for b in buttons]), key)).fetchone():
            return
        th = thread_id or (player and (c.execute("SELECT id FROM threads WHERE player = %s AND ghost = %s",
                                                 (player, ghost)).fetchone() or {}).get("id"))
        if th:
            c.execute("INSERT INTO messages (thread_id, who, text) VALUES (%s, 'ghost', %s)", (th, text))
    if conn:
        return write(conn)
    with db.tx() as c:
        write(c)


def send_pending():
    """Send what's queued. Rows are read, then sent outside any transaction (a slow bridge holds no locks);
    there is one sender, so nothing is sent twice."""
    rows = db.all("SELECT * FROM outbox WHERE sent_at IS NULL AND tries < 5 ORDER BY id LIMIT 20")
    for r in rows:
        try:
            bridge.say(r["ghost"], r["player"], r["text"], r["buttons"])
            db.run("UPDATE outbox SET sent_at = now() WHERE id = %s", r["id"])
        except bridge.BridgeError:
            db.run("UPDATE outbox SET tries = tries + 1 WHERE id = %s", r["id"])


def sender():
    """Forever: send, then sleep until NOTIFY outbox (or 5 s)."""
    conn = psycopg.connect(config.dsn(), autocommit=True)
    conn.execute("LISTEN outbox")
    while True:
        try:
            send_pending()
        except Exception as e:  # noqa: BLE001 (the loop must survive a bad row or a bridge hiccup)
            print(f"outbox: {e}", flush=True)
        if select.select([conn], [], [], 5) != ([], [], []):
            for _ in conn.notifies(timeout=0):
                pass
