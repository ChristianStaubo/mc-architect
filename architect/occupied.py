"""What's already built where: town plots, walls and roads (towns/*/layout.json) and live builds placed
by the architect or the ghost (the edit journal). New builds may not land on any of them: the /arc preview
refuses the spot, and the ghost's policy forbids the build (context `overlaps_build`)."""

import json
from functools import lru_cache
from pathlib import Path

from . import terrain

ROOT = Path(__file__).resolve().parent.parent


@lru_cache
def _towns():
    """[(name, set of (x, z) cells)] for every town's plots, wall and roads."""
    out = []
    for f in sorted((ROOT / "towns").glob("*/layout.json")):
        town = f.parent.name
        layout = json.loads(f.read_text())
        for p in layout.get("plots", []):
            (x0, z0), (x1, z1) = p["min"], p["max"]
            out.append((f"{town}'s {p['id'].replace('_', ' ')}",
                        {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}))
        for key in ("points", "river_side"):
            pts = (layout.get("wall") or {}).get(key)
            if pts:
                out.append((f"{town}'s wall", set(map(tuple, terrain.polyline(pts)))))
        for r in layout.get("roads", []):
            pts = r.get("points") or r.get("path")
            if pts:
                half = max(1, int(r.get("width", 3)) // 2)
                cells = {(x + dx, z + dz) for (x, z) in terrain.polyline(pts)
                         for dx in range(-half, half + 1) for dz in range(-half, half + 1)}
                out.append((f"{town}'s {str(r.get('id', 'road')).replace('_', ' ')}", cells))
    return out


def occupied(lo, hi, ignore_runs=()):
    """Names of what the footprint (x0, z0)..(x1, z1) would land on, empty when it's clear."""
    (x0, z0), (x1, z1) = lo, hi
    foot = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    hits = [name for name, cells in _towns() if foot & cells]
    from . import edits
    for e in edits.listing():
        run = str(e.get("run", ""))
        if not run.startswith(("ghost:", "arc:")) or any(run.startswith(r) for r in ignore_runs):
            continue
        (ex0, _, ez0), (ex1, _, ez1) = e["min"], e["max"]
        if not (ex1 < x0 or ex0 > x1 or ez1 < z0 or ez0 > z1):
            hits.append(f"a build ({e['id']}, {e['label']})")
    return sorted(set(hits))
