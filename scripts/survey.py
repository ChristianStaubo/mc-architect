"""Survey a big rectangle of the world into a coarse height/water grid: local/survey/<name>.json.

  python scripts/survey.py NAME X0 Z0 X1 Z1 [--step 4] [--tile 128]

Reads the heightmap tile by tile (the server generates chunks it hasn't yet: ~2 s a 64x64 tile) and keeps
one sample every `step` blocks: {"step", "x0", "z0", "w", "h", "y": [[...]], "water": [[...]]}. Resumable:
tiles already read are cached in local/survey/<name>.tiles/."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from architect import blocks, bridge  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("box", nargs=4, type=int)
ap.add_argument("--step", type=int, default=4)
ap.add_argument("--tile", type=int, default=128)
a = ap.parse_args()
x0, z0, x1, z1 = a.box
out = Path("local/survey")
tiles = out / f"{a.name}.tiles"
tiles.mkdir(parents=True, exist_ok=True)
w, h = (x1 - x0) // a.step + 1, (z1 - z0) // a.step + 1
Y = [[None] * w for _ in range(h)]
WET = [[0] * w for _ in range(h)]
t0, n = time.time(), 0
todo = [(tx, tz) for tz in range(z0, z1 + 1, a.tile) for tx in range(x0, x1 + 1, a.tile)]
for i, (tx, tz) in enumerate(todo):
    f = tiles / f"{tx}_{tz}.json"
    if f.exists():
        rows = json.loads(f.read_text())
    else:
        hi = (min(tx + a.tile - 1, x1), min(tz + a.tile - 1, z1))
        cols = bridge.heightmap((tx, tz), hi)
        rows = [[x, z, y, int(blocks.is_water(b))] for (x, z), (y, b) in cols.items()
                if (x - x0) % a.step == 0 and (z - z0) % a.step == 0]
        f.write_text(json.dumps(rows))
        n += 1
    for x, z, y, wet in rows:
        Y[(z - z0) // a.step][(x - x0) // a.step] = y
        WET[(z - z0) // a.step][(x - x0) // a.step] = wet
    if i % 10 == 0:
        print(f"{i + 1}/{len(todo)} tiles, {time.time() - t0:.0f} s", flush=True)
(out / f"{a.name}.json").write_text(json.dumps({"step": a.step, "x0": x0, "z0": z0, "w": w, "h": h, "y": Y, "water": WET}))
print(f"done: {w}x{h} samples, {n} tiles read in {time.time() - t0:.0f} s")
