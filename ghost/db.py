"""The store: Postgres through psycopg. One short connection per unit of work; transactions keep a state
change and its outbox message together."""

from contextlib import contextmanager
from pathlib import Path

import psycopg
import psycopg.sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import config

SCHEMA = Path(__file__).with_name("schema.sql")
J = Jsonb  # wrap dicts and lists for jsonb columns


@contextmanager
def tx():
    """A transaction: commits on success, rolls back on an exception."""
    with psycopg.connect(config.dsn(), row_factory=dict_row) as conn:
        with conn.transaction():
            yield conn


def one(sql, *args):
    with tx() as c:
        return c.execute(sql, args).fetchone()


def all(sql, *args):  # noqa: A001 (reads well at call sites: db.all(...))
    with tx() as c:
        return c.execute(sql, args).fetchall()


def run(sql, *args):
    with tx() as c:
        c.execute(sql, args)


def migrate():
    with tx() as c:
        c.execute(SCHEMA.read_text())
        # the ops room reads, never writes
        c.execute(psycopg.sql.SQL("ALTER ROLE ghost_ops PASSWORD {}").format(psycopg.sql.Literal(config.db_password())))
        c.execute("GRANT USAGE ON SCHEMA public TO ghost_ops")
        c.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO ghost_ops")


def beat_forever(process, every=5, **detail):
    """A daemon thread's loop: say `process` is alive every few seconds (the watchdog reads these)."""
    import os
    import time
    while True:
        try:
            heartbeat(process, pid=os.getpid(), **detail)
        except Exception:  # noqa: BLE001 (a missed beat is what the watchdog is for)
            pass
        time.sleep(every)


def heartbeat(process, **detail):
    run("INSERT INTO heartbeats (process, at, detail) VALUES (%s, now(), %s) "
        "ON CONFLICT (process) DO UPDATE SET at = now(), detail = EXCLUDED.detail", process, J(detail))
