"""Kits: one parametric design, many buildings. A kit file (kits/README.md) has
build(w, d, door, kind, seed) -> Build, filling exactly a w x d plot; code stamps it on every plot of its
kind in seconds, instead of an agent designing each house (Kingsreach: ~1.5 agent-minutes and $0.25 a house).

sample() builds a spread of sizes, door sides, kinds and seeds offline (nothing placed), checks each one
(fits its plot, a door on the asked side, the audit on a flat pad) and draws them on one sheet: the kit's
author iterates on that, and a critic scores the kit from it once instead of scoring every house."""

import itertools
import time

from pathlib import Path

from . import audit as auditing
from . import render
from . import town as towns
from .blocks import parse
from .build import load, module

# a bridge kit (KIND = "bridge") is sampled over these crossings instead: (length, rise, depth, ramp_a, ramp_b)
# (the last two are the Kingsway's real crossings: a viaduct onto a cliff, and a deep river)
SPANS = [(24, 6, 3, 0, 0), (36, 8, 5, 4, 0), (44, 7, 6, 2, 3), (64, 10, 8, 6, 6), (58, 23, 24, 21, 0), (53, 16, 22, 0, 8)]
SIZES = [(9, 9), (11, 13), (14, 11), (16, 16), (12, 18), (10, 15), (18, 12), (13, 13)]
DOORS = ["south", "east", "north", "west"]


def kinds_of(path, mod=None):
    """The kinds a kit says it builds (its KINDS list), or just "house"."""
    return list(getattr(mod or module(path), "KINDS", ["house"]))


def walk_y(x, length, rise, ramp_a, ramp_b):
    """Where you stand at local x on a bridge: rise over the water, less the ramps at the ends."""
    return rise - max(0, ramp_a - x) - max(0, x - (length - 1 - ramp_b))


def check_bridge(b, length, width, rise, depth, ramp_a, ramp_b):
    """A bridge over a sampled crossing: inside its strip, a walkable deck along the middle at the right
    heights (ramps included), and held up: the audit on a pad of banks, water and a bed."""
    probs = []
    (x0, y0, z0), (x1, y1, z1) = b.bounds()
    if x0 < 0 or z0 < 0 or x1 > length - 1 or z1 > width - 1:
        probs.append(f"outside the {length}x{width} strip: x {x0}..{x1}, z {z0}..{z1}")
    if y0 < -depth - 1:
        probs.append(f"goes below the bed (y {y0} < {-depth - 1})")
    mid = width // 2
    gaps = []
    for x in range(length):
        y = walk_y(x, length, rise, ramp_a, ramp_b)
        under, feet, head = b.get(x, y - 1, mid), b.get(x, y, mid), b.get(x, y + 1, mid)
        if under is None and not (x < ramp_a or x > length - 1 - ramp_b):
            gaps.append((x, "no deck"))
        elif not (auditing.passable(feet) or auditing.is_step(feet)) or not auditing.passable(head):
            gaps.append((x, f"blocked by {feet or head}"))
    if gaps:
        probs.append(f"the way across fails at {len(gaps)} of {length} steps, e.g. " +
                     ", ".join(f"x {x}: {why}" for x, why in gaps[:4]))
    pad = dict(b.blocks)
    for x in range(-3, length + 3):
        bank = rise - ramp_a - 1 if x < max(ramp_a, 1) else rise - ramp_b - 1 if x > length - 1 - max(ramp_b, 1) else None
        for z in range(-2, width + 2):
            pad.setdefault((x, -depth - 1, z), "stone")
            for y in range(-depth, y1 + 3):
                if bank is not None and y <= bank:
                    pad.setdefault((x, y, z), "dirt")
                elif bank is None and y <= 0:
                    pad.setdefault((x, y, z), "water")
                else:
                    pad.setdefault((x, y, z), "air")
    r = auditing.audit(pad, b.bounds())  # (under a deck isn't a room: no "dark" for bridges)
    probs += [f"audit {c['check']}: {c['msg']}" for c in r["checks"] if c["level"] == "fail" and c["check"] != "dark"]
    return probs, pad


def check(b, w, d, door):
    """Problems with one instance: outside the plot, no door on the asked side, the audit's fails on a pad."""
    probs = []
    (x0, y0, z0), (x1, y1, z1) = b.bounds()
    if x0 < 0 or z0 < 0 or x1 > w - 1 or z1 > d - 1:
        probs.append(f"outside the {w}x{d} plot: x {x0}..{x1}, z {z0}..{z1}")
    doors = [parse(v)[1].get("facing") for v in b.blocks.values()
             if auditing.is_door(v) and parse(v)[1].get("half") == "lower"]
    if door not in doors:
        probs.append(f"no door facing {door} (doors face {sorted(set(doors)) or 'nowhere'})")
    pad = dict(b.blocks)  # on flat grass, with the air spelled out: the audit floods through listed cells
    gy = min(y0, 0) - 1
    for x in range(min(x0, 0) - 2, max(x1, w - 1) + 3):
        for z in range(min(z0, 0) - 2, max(z1, d - 1) + 3):
            pad.setdefault((x, gy, z), "grass_block")
            for y in range(gy + 1, y1 + 3):
                pad.setdefault((x, y, z), "air")
    r = auditing.audit(pad, b.bounds())
    probs += [f"audit {c['check']}: {c['msg']}" for c in r["checks"] if c["level"] == "fail"]
    return probs


def town_specs(path, town):
    """The params of every plot of `town` this kit builds, exactly as `mc place --plot` passes them."""
    mine = {k for k, v in towns.town(town).get("kits", {}).items() if Path(v).stem == Path(path).stem}
    return [towns.kit_params(town, p) for p in towns.layout(town)["plots"] if p.get("kit") in mine]


def sample(path, n=8, sizes=None, kinds=None, out=None, town=None):
    """n instances of the kit at varied sizes, door sides, kinds and seeds (or exactly the plots of `town`
    it builds): (rows, sheet path)."""
    mod = module(path)   # once: every instance below builds from it
    if getattr(mod, "KIND", "") == "bridge":
        return sample_bridge(path, n, out, mod=mod)
    kinds = kinds or kinds_of(path, mod)
    specs = town_specs(path, town) if town else [
        {"w": w, "d": d, "door": door, "kind": kind, "seed": seed} for (w, d), door, kind, seed in
        itertools.islice(zip(itertools.cycle(sizes or SIZES), itertools.cycle(DOORS), itertools.cycle(kinds),
                             itertools.count(1)), n)]
    rows, imgs = [], []
    for p in specs:
        t = time.time()
        try:
            b = load(path, p, mod)
            imgs.append(render.iso(b.blocks, tile=6))
            rows.append({**p, "blocks": len(b.blocks), "ms": round((time.time() - t) * 1000),
                         "problems": check(b, p["w"], p["d"], p["door"])})
        except Exception as e:  # noqa: BLE001 (a kit's bug is a row, not a crash: the author fixes it)
            rows.append({**p, "problems": [f"error: {e!r}"]})
    if imgs and out:
        render.sheet(imgs, out, columns=4)
    return rows, out


def sample_bridge(path, n=6, out=None, width=7, mod=None):
    rows, imgs = [], []
    for seed, (length, rise, depth, ra, rb) in enumerate(SPANS[:n], 1):
        t = time.time()
        p = {"length": length, "width": width, "rise": rise, "depth": depth, "ramp_a": ra, "ramp_b": rb, "seed": seed}
        row = {**p, "kind": "bridge", "w": length, "d": width, "door": f"rise {rise}"}
        try:
            b = load(path, p, mod)
            probs, pad = check_bridge(b, length, width, rise, depth, ra, rb)
            view = {k: v for k, v in pad.items() if v != "air" and (k in b.blocks or k[1] <= 0 or v == "dirt")}
            imgs.append(render.iso(view, tile=5))
            rows.append({**row, "blocks": len(b.blocks), "ms": round((time.time() - t) * 1000), "problems": probs})
        except Exception as e:  # noqa: BLE001
            rows.append({**row, "problems": [f"error: {e!r}"]})
    if imgs and out:
        render.sheet(imgs, out, columns=2)
    return rows, out
