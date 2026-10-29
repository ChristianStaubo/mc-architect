"""Pristine eval sites (docs/evals.md §6): each capability task's plot, plus a margin, captured once from
the seeded world into evals/sites/<task>.json.gz. A trial starts by putting the site back exactly, and is
graded by comparing the live world with it."""

import gzip
import json
from pathlib import Path

from . import bridge, edits, graders

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "evals" / "sites"
MARGIN = 6      # around the plot: trees cut at the edge, spill-over, the "nothing outside" check
BELOW = 10      # under the lowest ground: foundations and cellars
ABOVE = 48      # over the highest ground: towers and lighthouses


def path(tid):
    return DIR / f"{tid}.json.gz"


def box(task):
    """The site's box from the live heightmap: (lo, hi) as (x, y, z)."""
    (x0, z0), (x1, z1) = task["plot"]["min"], task["plot"]["max"]
    lo, hi = (x0 - MARGIN, z0 - MARGIN), (x1 + MARGIN, z1 + MARGIN)
    ys = [y for y, _ in bridge.heightmap(lo, hi).values()]
    return (lo[0], max(min(ys) - BELOW, -64), lo[1]), (hi[0], min(max(ys) + ABOVE, 319), hi[1])


def capture(task, force=False):
    p = path(task["id"])
    if p.exists() and not force:
        raise SystemExit(f"{p} exists: the site is captured once, from the pristine world (--force to redo)")
    lo, hi = box(task)
    r = bridge.call("/region", {"min": list(lo), "max": list(hi)})
    DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt") as f:
        json.dump(r, f, separators=(",", ":"))
    return r


def load(tid):
    with gzip.open(path(tid), "rt") as f:
        return json.load(f)


def bounds(r):
    (x, y, z), (w, h, d) = r["min"], r["size"]
    return (x, y, z), (x + w - 1, y + h - 1, z + d - 1)


def reset(tid):
    """Put the site back as captured, and remove what trials summoned (boats, armour stands)."""
    r = load(tid)
    (x0, y0, z0), (x1, y1, z1) = bounds(r)
    bridge.command(f"kill @e[type=!player,x={x0},y={y0},z={z0},dx={x1 - x0},dy={y1 - y0},dz={z1 - z0}]")
    bridge.place({"origin": r["min"], "size": r["size"], "palette": r["palette"], "rle": r["rle"],
                  "label": f"reset {tid}"})
    edits.retire(tid, "site reset")


def outcome(task, floor_y=None):
    """The live site against its pristine capture, ready for the graders."""
    r = load(task["id"])
    before = bridge.decode(r)
    after = bridge.region(*bounds(r))
    return graders.Outcome(after, before, (tuple(task["plot"]["min"]), tuple(task["plot"]["max"])), floor_y)
