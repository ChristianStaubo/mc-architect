"""Edits that survive restarts. Before every place we save what was in the box (a snapshot); undo uses
WorldEdit's own history when the edit is the server's latest, and otherwise puts the snapshot back.
Snapshots keep block states, not container contents (a chest comes back empty)."""

import contextlib
import fcntl
import gzip
import json
import time
from pathlib import Path

from . import bridge
from .build import payload

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "local" / "edits"
INDEX = DIR / "index.jsonl"


def _all():
    if not INDEX.exists():
        return []
    latest = {}
    for line in INDEX.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            latest[e["id"]] = e  # later lines update earlier ones
    return list(latest.values())


def _write(e):
    DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX, "a") as f:
        f.write(json.dumps(e) + "\n")


def listing(include_undone=False):
    return [e for e in _all() if include_undone or not e.get("undone")]


def get(eid):
    for e in _all():
        if e["id"] == eid:
            return e
    raise SystemExit(f"no edit {eid}")


@contextlib.contextmanager
def _locked():
    """One place or undo at a time across processes (parallel builders): ids and snapshots stay consistent."""
    DIR.mkdir(parents=True, exist_ok=True)
    with open(DIR / ".lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def place(cells, label, run="", task="", **extra):
    with _locked():
        return _place(cells, label, run, task, **extra)


def undo(eid=None):
    with _locked():
        return _undo(eid)


def _place(cells, label, run="", task="", **extra):
    """Snapshot the box, place, record (with any `extra` fields). Returns the edit record."""
    body = payload(cells, label=label)
    lo = body["origin"]
    hi = [lo[i] + body["size"][i] - 1 for i in range(3)]
    before = bridge.region(lo, hi)
    n = len(_all()) + 1
    eid = f"e{n}"
    DIR.mkdir(parents=True, exist_ok=True)
    snap = DIR / f"{eid}.json.gz"
    with gzip.open(snap, "wt") as f:
        json.dump({"min": lo, "max": hi, "cells": [[*k, v] for k, v in before.items()]}, f)
    r = bridge.place(body)
    e = {"id": eid, "server_id": r["id"], "label": label, "run": run, "task": task, "min": lo, "max": hi,
         "changed": r["changed"], "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "snapshot": snap.name, **extra}
    _write(e)
    return e


def _overlap(a, b):
    return all(a["min"][i] <= b["max"][i] and b["min"][i] <= a["max"][i] for i in range(3))


def _undo(eid=None):
    live = listing()
    if not live:
        raise SystemExit("nothing to undo")
    e = get(eid) if eid else max(live, key=lambda x: int(x["id"][1:]))
    if e.get("undone"):
        raise SystemExit(f"{e['id']} is already undone")
    later = [x for x in live if int(x["id"][1:]) > int(e["id"][1:]) and _overlap(x, e)]
    if later:
        raise SystemExit(f"undo {', '.join(x['id'] for x in later)} first: they overlap {e['id']}")
    hist = bridge.history()  # the server's, newest first; empty after a restart
    if hist and hist[0]["id"] == e.get("server_id") and hist[0]["min"] == e["min"]:
        bridge.undo(e["server_id"])
        how = "worldedit"
    else:  # server restarted, or a newer edit elsewhere: put the snapshot back
        with gzip.open(DIR / e["snapshot"], "rt") as f:
            snap = json.load(f)
        cells = {(x, y, z): b for x, y, z, b in snap["cells"]}
        bridge.place(payload(cells, label=f"undo {e['id']}"))
        how = "snapshot"
    e = {**e, "undone": time.strftime("%Y-%m-%dT%H:%M:%S"), "undo_via": how}
    _write(e)
    return e
