"""Per-player state, kept in local/assistant/sessions.json so the daemon and the agent's `mc preview` (a
separate process) agree: the Claude session to resume, the preview waiting for a yes, the player's builds,
and the context of their latest request."""

import contextlib
import json
import shutil
import time
from pathlib import Path

from ..lock import locked

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "local" / "assistant"
FILE = DIR / "sessions.json"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def all_players():
    return json.loads(FILE.read_text()) if FILE.exists() else {}


def get(player):
    return all_players().get(player.lower(), {})


def run_id(player, n=None):
    """A request's id in the journal: arc:<player>:<n> (default: their latest request)."""
    return f"arc:{player}:{get(player).get('requests', 0) if n is None else n}"


@contextlib.contextmanager
def _all():
    with locked(DIR):
        everyone = all_players()
        yield everyone
        FILE.write_text(json.dumps(everyone, indent=1))


@contextlib.contextmanager
def edit(player):
    """with edit(player) as s: s["x"] = ... (read, change, write under the lock)."""
    with _all() as everyone:
        s = everyone.setdefault(player.lower(), {"player": player, "builds": [], "requests": 0})
        yield s
        s["updated"] = now()


def forget(player):
    """Start a player over: no conversation, no pending preview, no builds (their workspace stays)."""
    with _all() as everyone:
        everyone.pop(player.lower(), None)


def workspace(player):
    d = DIR / player.lower()
    d.mkdir(parents=True, exist_ok=True)
    return d


def set_pending(player, plan, args, box, frame, blocks):
    """A preview waiting for a yes: a frozen copy of the plan, the exact place arguments, the whole box it
    changes (`box`, cleared trees included) and the build's own box (`frame`)."""
    frozen = workspace(player) / f"preview-{int(time.time())}.py"
    shutil.copy(plan, frozen)
    with edit(player) as s:
        s["pending"] = {"plan": str(frozen.relative_to(ROOT)), "args": args, "box": box, "frame": frame,
                        "blocks": blocks, "at": now()}
    return frozen
