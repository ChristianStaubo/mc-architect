"""Per-player state, kept in local/assistant/sessions.json so the daemon and the agent's `mc preview` (a
separate process) agree: the Claude session to resume, the preview waiting for a yes, the player's builds,
and the context of their latest request."""

import contextlib
import fcntl
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "local" / "assistant"
FILE = DIR / "sessions.json"


@contextlib.contextmanager
def _locked():
    DIR.mkdir(parents=True, exist_ok=True)
    with open(DIR / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _read():
    return json.loads(FILE.read_text()) if FILE.exists() else {}


def get(player):
    return _read().get(player.lower(), {})


@contextlib.contextmanager
def edit(player):
    """with edit(player) as s: s["x"] = ... (read, change, write under the lock)."""
    with _locked():
        all_ = _read()
        s = all_.setdefault(player.lower(), {"player": player, "builds": [], "requests": 0})
        yield s
        s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        FILE.write_text(json.dumps(all_, indent=1))


def workspace(player):
    d = DIR / player.lower()
    d.mkdir(parents=True, exist_ok=True)
    return d


def set_pending(player, plan, args, box, blocks):
    """A preview waiting for a yes: a frozen copy of the plan and the exact place arguments."""
    n = int(time.time())
    frozen = workspace(player) / f"preview-{n}.py"
    shutil.copy(plan, frozen)
    with edit(player) as s:
        s["pending"] = {"plan": str(frozen.relative_to(ROOT)), "args": args, "box": box, "blocks": blocks,
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    return frozen


def forget(player):
    """Start a player over: no conversation, no pending preview, no builds (their workspace stays)."""
    with _locked():
        all_ = _read()
        all_.pop(player.lower(), None)
        FILE.write_text(json.dumps(all_, indent=1))
