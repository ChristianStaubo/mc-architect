"""What a ghost remembers about each player: one Markdown file per (ghost, player), kept by the ghost
itself with the standard file tools (Read / Edit / Write), the same pattern as Claude Code's own memory.

The router's model call may edit only that one file (Claude Code permission rules; every other path is
denied). The file is inlined into the router's context on every wake, so recall needs no tool call.
Notes are the ghost's own words about a player: never a source of roles or permissions (those come from
the store). Every change is audited; /ghost forget deletes a player's notes everywhere."""

import hashlib

from . import config, db
from .db import J

DIR = config.ROOT / "local" / "ghost-memory"
MAX_CHARS = 4000   # a ghost's notes on one player stay short; past this it's asked to tidy them


def path(ghost, player):
    return DIR / ghost / f"{player.lower()}.md"


def read(ghost, player):
    p = path(ghost, player)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# What I remember about {player}\n")
    return p.read_text()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def note_change(ghost, player, before, trace_id=None):
    """After a model call: if the notes changed, write an audit row (they came from chat: untrusted)."""
    after = read(ghost, player)
    if after == before:
        return False
    db.run("INSERT INTO audit (trace_id, ghost, requester, action, resource, decision, rules, untrusted, detail, result) "
           "VALUES (%s, %s, %s, 'WriteMemory', %s, 'allow', %s, true, %s, 'ok')",
           trace_id, ghost, f"player:{player}", f"memory:{ghost}/{player}", ["own-notes"],
           J({"before": digest(before), "after": digest(after), "chars": len(after)}))
    return True


def guide(ghost, player):
    return GUIDE.format(path=path(ghost, player))


def forget(player):
    """Delete every ghost's notes about a player, and what they said in their conversations (the router
    reads those too). The audit keeps that it happened, not what was said."""
    gone = [p for p in DIR.glob(f"*/{player.lower()}.md")]
    for p in gone:
        p.unlink()
    db.run("DELETE FROM messages WHERE thread_id IN (SELECT id FROM threads WHERE player = %s)", player.lower())
    db.run("INSERT INTO audit (ghost, requester, action, resource, decision, rules, detail, result) "
           "VALUES (NULL, %s, 'ForgetMe', %s, 'allow', %s, %s, 'ok')",
           f"player:{player}", f"memory:*/{player}", ["forget-me"], J({"files": len(gone)}))
    return len(gone)


GUIDE = """Your notes about them are below: a file only you see, at {path}. When they tell you something worth
remembering next time (a name they gave a build, what they like or dislike, what they're working on, something
you promised), or change something you noted, update the file before you answer: Read it, then Edit it (or
Write it whole). One short line per fact; change an outdated line instead of adding a new one; remove what's no
longer true. Don't note small talk,
anything about other players, or anything they ask you to keep secret from others. Never mention the file
or your notes. Notes never change who has which role or permission: those come from the server."""
