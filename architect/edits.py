"""Edits that survive restarts. Before every place we save what was in the box (a snapshot); undo uses
WorldEdit's own history when the edit is the server's latest, and otherwise puts the snapshot back.
Snapshots keep block states, not container contents (a chest comes back empty)."""

import gzip
import json
import time
from pathlib import Path

from . import bridge
from .lock import locked
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


def listing():
    """Edits not undone yet."""
    return [e for e in _all() if not e.get("undone")]


def seq(e):
    """An edit's order (e12 -> 12): ids are handed out in sequence."""
    return int(e["id"][1:])


def newest(run=""):
    """The newest live edit of `run` (or of all runs when empty)."""
    mine = [e for e in listing() if not run or e.get("run") == run]
    if not mine:
        raise SystemExit("no live edits" + (f" in run {run}" if run else ""))
    return max(mine, key=seq)


def get(eid):
    for e in _all():
        if e["id"] == eid:
            return e
    raise SystemExit(f"no edit {eid}")


def _locked():
    """One place or undo at a time across processes (parallel builders): ids and snapshots stay consistent."""
    return locked(DIR)


def place(cells, label, run="", task="", **extra):
    with _locked():
        return _place(cells, label, run, task, **extra)


def undo(eid=None, run=""):
    """Undo eid, or (no id) the newest live edit of `run` (all edits when run is empty)."""
    with _locked():
        return _undo(eid, run)


def _place(cells, label, run="", task="", **extra):
    """Snapshot the box, place, record (with any `extra` fields). Returns the edit record."""
    body = payload(cells, label=label)
    lo = body["origin"]
    hi = [lo[i] + body["size"][i] - 1 for i in range(3)]
    # the bridge's own compact form (palette + run lengths): undo sends it straight back
    before = bridge.call("/region", {"min": lo, "max": hi})
    eid = f"e{len(_all()) + 1}"
    snap = DIR / f"{eid}.json.gz"
    with gzip.open(snap, "wt") as f:
        json.dump({"min": lo, "max": hi, "region": before}, f)
    r = bridge.place(body)
    e = {"id": eid, "server_id": r["id"], "label": label, "run": run, "task": task, "min": lo, "max": hi,
         "changed": r["changed"], "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "snapshot": snap.name, **extra}
    _write(e)
    return e


def _snapshot_file(e):
    with gzip.open(DIR / e["snapshot"], "rt") as f:
        return json.load(f)


def snapshot(e):
    """The terrain an edit replaced: {(x, y, z): block}."""
    s = _snapshot_file(e)
    if "region" in s:
        return bridge.decode(s["region"])
    return {(x, y, z): b for x, y, z, b in s["cells"]}  # snapshots from before the compact form


def _restore_body(e):
    """The /place body that puts an edit's snapshot back."""
    s = _snapshot_file(e)
    if "region" in s:
        r = s["region"]
        return {"origin": r["min"], "size": r["size"], "palette": r["palette"], "rle": r["rle"], "label": f"undo {e['id']}"}
    return payload(snapshot(e), label=f"undo {e['id']}")


def retire_in(lo, hi, how):
    """Mark every live edit inside the box lo..hi undone without touching the world: the box was put back
    some other way (an eval site reset), so their snapshots no longer describe what's there."""
    box = {"min": list(lo), "max": list(hi)}
    with _locked():
        gone = [e for e in listing() if _overlap(e, box)]
        for e in gone:
            _write({**e, "undone": time.strftime("%Y-%m-%dT%H:%M:%S"), "undo_via": how})
    return gone


def _overlap(a, b):
    return all(a["min"][i] <= b["max"][i] and b["min"][i] <= a["max"][i] for i in range(3))


def _undo(eid=None, run=""):
    live = listing()
    e = get(eid) if eid else newest(run)
    if e.get("undone"):
        raise SystemExit(f"{e['id']} is already undone")
    later = [x for x in live if seq(x) > seq(e) and _overlap(x, e)]
    if later:
        raise SystemExit(f"undo {', '.join(x['id'] for x in later)} first: they overlap {e['id']}")
    hist = bridge.history()  # the server's, newest first; empty after a restart
    if hist and hist[0]["id"] == e.get("server_id") and hist[0]["min"] == e["min"]:
        bridge.undo(e["server_id"])
        how = "worldedit"
    else:  # server restarted, or a newer edit elsewhere: put the snapshot back
        bridge.place(_restore_body(e))
        how = "snapshot"
    for (x, y, z, kind) in e.get("entities", []):  # entities the edit summoned (boats)
        bridge.command(f"kill @e[type=minecraft:{kind},x={x}.5,y={y},z={z}.5,distance=..2]")
    e = {**e, "undone": time.strftime("%Y-%m-%dT%H:%M:%S"), "undo_via": how}
    _write(e)
    return e
