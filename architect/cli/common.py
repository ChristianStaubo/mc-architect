"""Helpers every command group shares: paths, argument parsing, plans, edits and contact sheets."""

import argparse
import re
import time
from pathlib import Path

from .. import bridge, edits, journal, render
from .. import audit as auditing
from ..build import load as load_build

ROOT = Path(__file__).resolve().parents[2]
RENDERS = ROOT / "local" / "renders"


def out_path(stem):
    RENDERS.mkdir(parents=True, exist_ok=True)
    return RENDERS / f"{time.strftime('%Y%m%d-%H%M%S')}-{stem}.png"


def ints(s):
    return [int(v) for v in s.split(",")]


class Parser(argparse.ArgumentParser):
    """Coordinates like -68,-20 are values, not options. Subparsers are made with the parent's class,
    so every subcommand inherits this."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._negative_number_matcher = re.compile(r"^-\d+(,-?\d+)*$")


def player_pos(name):
    for p in bridge.status()["players"]:
        if p["name"].lower() == name.lower():
            return [int(v) for v in p["pos"]]
    raise SystemExit(f"{name} is not online")


def load_plan(name):
    path = Path(name)
    if not path.exists():
        path = ROOT / "plans" / f"{name.removesuffix('.py')}.py"
    if not path.exists():
        raise SystemExit(f"no plan {name}")
    b = load_build(path)
    if not b.blocks:
        raise SystemExit(f"plan {name} built nothing")
    return b


def latest_edit(eid):
    """eid, or the newest live edit of this run (MC_RUN_ID), or the newest overall."""
    if eid:
        return edits.get(eid)
    return edits.newest(journal.run_id())


def around(e, margin=3, below=4, above=2):
    lo, hi = e["min"], e["max"]
    return bridge.region((lo[0] - margin, lo[1] - below, lo[2] - margin),
                         (hi[0] + margin, hi[1] + above, hi[2] + margin))


def run_audit(e):
    cells = around(e)
    return auditing.audit(cells, (tuple(e["min"]), tuple(e["max"])))


def shots(e, path=None, cells=None, levels=None):
    """Contact sheet: 4 corner views, top-down, and a floor plan per storey (up to 4). `cells` and
    `levels`: a region already read around it and its storeys (eval trials), so nothing is fetched twice."""
    lo, hi = e["min"], e["max"]
    if cells is None:
        cells = around(e, margin=2, below=2, above=1)
    else:
        cells = {p: b for p, b in cells.items() if lo[0] - 2 <= p[0] <= hi[0] + 2 and lo[2] - 2 <= p[2] <= hi[2] + 2
                 and lo[1] - 2 <= p[1] <= hi[1] + 1}
    floor = e.get("floor_y", lo[1])
    # Terrain more than 3 below the floor is cut away, except under the build itself (posts, cellars).
    inside = lambda p: lo[0] <= p[0] <= hi[0] and lo[2] <= p[2] <= hi[2]  # noqa: E731
    view = {p: b for p, b in cells.items() if p[1] >= floor - 3 or (inside(p) and p[1] >= lo[1])}
    imgs = [render.iso(view, view=v) for v in ("se", "sw", "nw", "ne")]
    cols = {}
    for (x, y, z), b in cells.items():
        if not render.skipped(b) and (cols.get((x, z), (-999,))[0] < y):
            cols[(x, z)] = (y, b)
    imgs.append(render.top_down(cols, scale=8))
    if levels is None:
        levels = auditing.audit(cells, (tuple(lo), tuple(hi)))["stats"]["indoor_levels"]
    levels = (levels or [floor + 1])[:4]
    imgs += [render.plan(cells, y) for y in levels]
    # Facades, straight on and close up: small details (a hoist beam, a round window, a sign, shutters)
    # vanished at corner-view scale and the critic couldn't credit them (lakeside).
    box = {p: b for p, b in cells.items() if lo[0] - 1 <= p[0] <= hi[0] + 1 and lo[2] - 1 <= p[2] <= hi[2] + 1
           and p[1] >= floor - 1}
    for look in ("north", "west", "south", "east"):  # the south, east, north and west faces
        try:
            imgs.append(render.elevation(box, look=look, scale=10))
        except ValueError:
            pass
    path = path or out_path(f"{e['label']}-{e['id']}-shots")
    render.sheet(imgs, path, columns=3)
    return path, levels
