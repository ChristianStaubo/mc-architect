"""Code graders (docs/notes/evals-design.md §5.1): checks of a task's outcome, the blocks in the world after a trial,
compared with the plot's pristine terrain. Pure functions over region dicts, like the audit, so they can
be tested and run on previews. Each returns {"pass": bool, "value": ..., "detail": "..."}."""

import builtins
import fnmatch
import inspect
import re
from collections import Counter, deque

from . import audit, blocks, placement

STEP = [(1, 0), (-1, 0), (0, 1), (0, -1)]
CLIMB = ("ladder", "scaffolding", "vine")


class Outcome:
    """What a trial left: `after` and `before` are region dicts over the same box (the plot plus a
    margin); `plot` is ((x0, z0), (x1, z1)); `floor_y` the plan's y 0 if known."""

    def __init__(self, after, before, plot, floor_y=None):
        self.after, self.before, self.plot, self.floor_y = after, before, plot, floor_y
        self.changed = {p for p in after if after[p] != before.get(p)}
        built = [p for p in self.changed if not blocks.is_air(after[p])]
        self.box = placement.bounds(built or self.changed) if self.changed else None
        self._audit = None
        self._walk = None
        self.before_top = placement.surface(before)  # the ground, not treetops or grass

    @property
    def audit(self):
        if self._audit is None:
            self._audit = audit.audit(self.after, self.box) if self.box else {"fails": 1, "warns": 0, "checks": [
                {"check": "nothing built", "level": "fail", "msg": "nothing changed on the plot"}], "stats": {
                "indoor_levels": [], "indoor_floor": 0, "doors": 0, "blocks": 0}}
        return self._audit

    @property
    def ground_y(self):
        """One above the lowest original ground under the build: where it stands."""
        ground = [self.before_top[(x, z)][0] for x, _, z in self.built() if (x, z) in self.before_top]
        return (builtins.min(ground) + 1) if ground else self.box[0][1]

    def as_edit(self, name):
        """An edit-shaped record of what was built, for `mc shots` (contact sheets of trials)."""
        return {"id": name, "label": name, "min": list(self.box[0]), "max": list(self.box[1]), "floor_y": self.ground_y}

    def built(self):
        """The non-air blocks the trial placed."""
        return {p: self.after[p] for p in self.changed if not blocks.is_air(self.after[p])}

    def in_box(self, p):
        (x0, _, z0), (x1, _, z1) = self.box
        return x0 <= p[0] <= x1 and z0 <= p[2] <= z1

    def on_plot(self, p):
        (x0, z0), (x1, z1) = self.plot
        return x0 <= p[0] <= x1 and z0 <= p[2] <= z1

    def walk(self):
        """Every spot a player can walk to from the edge of the region: steps up and down by one, doors
        and gates open, ladders climbable. Swimming doesn't count (water isn't standable)."""
        if self._walk is None:
            cells = self.after

            def stand(p):  # two open blocks (air, plants, an open-able door) over a solid one
                x, y, z = p
                below = cells.get((x, y - 1, z))
                return (_open(cells.get(p)) and _open(cells.get((x, y + 1, z))) and below is not None
                        and not audit.passable(below) and not _door(below))

            def moves(x, y, z):
                for dx, dz in STEP:
                    for dy in (0, 1, -1):
                        n = (x + dx, y + dy, z + dz)
                        if n in cells and stand(n) and (dy != 1 or _open(cells.get((x, y + 2, z)))):
                            yield n  # (stepping up needs headroom)
                            break
                for dy in (1, -1):  # ladders
                    n = (x, y + dy, z)
                    if n in cells and any(k in blocks.name(cells[n] or "air") for k in CLIMB):
                        yield n

            lo, hi = placement.bounds(cells)
            self._walk = _bfs([p for p in cells if (p[0] in (lo[0], hi[0]) or p[2] in (lo[2], hi[2])) and stand(p)], moves)
        return self._walk


def _bfs(starts, moves):
    """Everything reachable from `starts` through `moves(x, y, z)` -> next positions."""
    seen, q = set(starts), deque(starts)
    while q:
        for n in moves(*q.popleft()):
            if n not in seen:
                seen.add(n)
                q.append(n)
    return seen


def _door(b):
    return b is not None and (audit.is_door(b) or blocks.name(b).endswith("_fence_gate"))


def _open(b):
    return audit.passable(b) or _door(b)


SHAPES = re.compile(r"_(stairs|slab|wall|fence_gate|fence|planks)$")


def family(n):
    """A block's material: spruce_stairs and spruce_planks are both spruce, stone_brick_slab is stone_brick."""
    base = SHAPES.sub("", n)
    return base[:-1] if base.endswith("bricks") or base.endswith("tiles") else base


def _match(b, patterns):
    n = blocks.name(b)
    return any(fnmatch.fnmatch(n, pat.replace("minecraft:", "")) for pat in patterns)


def _res(ok, value, detail):
    return {"pass": bool(ok), "value": value, "detail": detail}


# ---- the catalogue ----

def audit_clean(o):
    r = o.audit
    return _res(r["fails"] == 0, r["fails"], "; ".join(c["msg"] for c in r["checks"] if c["level"] == "fail") or "clean")


def inside_plot(o):
    out = [p for p in o.changed if not o.on_plot(p)]
    return _res(not out, len(out), f"{len(out)} blocks changed outside the plot" + (f", e.g. {sorted(out)[:3]}" if out else ""))


def storeys(o, min=1):
    n = len(o.audit["stats"]["indoor_levels"])
    return _res(n >= min, n, f"{n} storeys (need {min})")


def indoor_floor(o, min=1):
    n = o.audit["stats"]["indoor_floor"]
    return _res(n >= min, n, f"{n} indoor floor spots (need {min})")


def lit_indoors(o):
    dark = [c for c in o.audit["checks"] if c["check"] == "dark"]
    return _res(not dark, dark[0]["count"] if dark else 0, dark[0]["msg"] if dark else "every indoor floor lit")


def door_reaches_outside(o):
    walk = o.walk()
    doors = [p for p, b in o.after.items() if p in o.changed and _door(b) and blocks.parse(b)[1].get("half", "lower") == "lower"]
    if not doors:
        return _res(False, 0, "no doors")
    stuck = [p for p in doors if p not in walk]
    return _res(not stuck, len(doors) - len(stuck), f"{len(doors) - len(stuck)}/{len(doors)} doors reachable on foot")


def stairs_reach_every_storey(o):
    levels = o.audit["stats"]["indoor_levels"]
    if not levels:
        return _res(False, 0, "no storeys")
    reached = [y for y in levels if any(p[1] == y and o.in_box(p) for p in o.walk())]
    return _res(len(reached) == len(levels), f"{len(reached)}/{len(levels)}",
                f"storeys at y {levels}: reachable on foot {reached}")


def height(o, min=1):
    """From the ground it stands on (the lowest original ground under it, or the plan's floor) to its top."""
    if not o.box:
        return _res(False, 0, "nothing built")
    h = o.box[1][1] - (o.floor_y if o.floor_y is not None else o.ground_y) + 1
    return _res(h >= min, h, f"{h} blocks tall above the ground (need {min})")


def over_water(o, min=1):
    wet = [p for p in o.built() if blocks.is_water(o.before_top.get((p[0], p[2]), (0, "air"))[1])]
    cols = {(x, z) for x, _, z in wet}
    return _res(len(cols) >= min, len(cols), f"{len(cols)} columns built over water (need {min})")


def spans_water(o, frm, to):
    """On foot from one bank (frm: [x, z]) to the other (to), without swimming."""
    walk = o.walk()
    a = [p for p in walk if (p[0], p[2]) == tuple(frm)]
    b = [p for p in walk if (p[0], p[2]) == tuple(to)]
    if not a or not b:
        return _res(False, 0, f"no standing spot at {frm if not a else to}")
    # walk() floods from the region edge; check frm and to are in one connected piece of it
    near = lambda x, y, z: (n for n in ((x + dx, y + dy, z + dz) for dx, dz in STEP for dy in (0, 1, -1))  # noqa: E731
                            if n in walk)
    ladder = lambda x, y, z: (n for n in ((x, y + 1, z), (x, y - 1, z)) if n in walk)  # noqa: E731
    seen = _bfs([a[0]], lambda *p: [*near(*p), *ladder(*p)])
    ok = any(p in seen for p in b)
    return _res(ok, ok, f"{'a' if ok else 'no'} walkable way from {frm} to {to}")


def contains(o, any=(), min=1, on_floor=False):
    """Blocks matching the patterns; with on_floor, only those standing on an indoor floor (pews, not
    roof stairs: chapel reference)."""
    levels = set(o.audit["stats"]["indoor_levels"]) if on_floor else None
    n = sum(1 for p, b in o.built().items() if _match(b, any) and (levels is None or p[1] in levels))
    where = " on indoor floors" if on_floor else ""
    return _res(n >= min, n, f"{n} blocks matching {list(any)}{where} (need {min})")


def contains_not(o, any=()):
    n = sum(1 for b in o.built().values() if _match(b, any))
    return _res(n == 0, n, f"{n} blocks matching {list(any)} (need none)")


def floor_levels(o, min=2):
    """Distinct heights people stand at on and in the build (split levels, terraces, storeys)."""
    if not o.box:
        return _res(False, 0, "nothing built")
    ys = Counter(p[1] for p in o.walk() if o.in_box(p))
    levels = sorted(y for y, n in ys.items() if n >= 6)
    return _res(len(levels) >= min, len(levels), f"{len(levels)} levels people stand at, y {levels} (need {min})")


def not_symmetric(o, max_ratio=0.8):
    built = o.built()
    if not built:
        return _res(False, 1.0, "nothing built")
    (x0, _, z0), (x1, _, z1) = o.box
    ratios = []
    for mirror in (lambda x, y, z: (x0 + x1 - x, y, z), lambda x, y, z: (x, y, z0 + z1 - z)):
        same = sum(1 for p, b in built.items() if blocks.name(built.get(mirror(*p), "air")) == blocks.name(b))
        ratios.append(same / len(built))
    r = max(ratios)
    return _res(r <= max_ratio, round(r, 2), f"mirror symmetry {r:.0%} on its most symmetric axis (max {max_ratio:.0%})")


def materials(o, min=3, max=6, share=0.05):
    names = Counter(family(blocks.name(b)) for b in o.built().values())
    total = sum(names.values()) or 1
    main = sorted(n for n, c in names.items() if c / total >= share)
    return _res(min <= len(main) <= max, len(main), f"{len(main)} main materials {main} (want {min}-{max})")


def water_untouched(o):
    hit = [p for p in o.changed if blocks.is_water(o.before.get(p, "air"))]
    return _res(not hit, len(hit), f"{len(hit)} water blocks changed")


def keeps_trees(o, min_share=0.6):
    """Of the logs on the plot before, the share still standing."""
    logs = [p for p, b in o.before.items() if blocks.name(b).endswith("_log") and o.on_plot(p)]
    if not logs:
        return _res(True, 1.0, "no trees on the plot")
    kept = sum(1 for p in logs if o.after.get(p) == o.before[p]) / len(logs)
    return _res(kept >= min_share, round(kept, 2), f"{kept:.0%} of {len(logs)} logs still standing (need {min_share:.0%})")


def light_near_top(o, within=4):
    if not o.box:
        return _res(False, 0, "nothing built")
    top = o.box[1][1]
    lights = [p for p, b in o.built().items() if p[1] >= top - within and audit.emits(b)]
    return _res(bool(lights), len(lights), f"{len(lights)} light sources in the top {within} blocks")


CATALOGUE = {f.__name__: f for f in (audit_clean, inside_plot, storeys, indoor_floor, lit_indoors,
                                    door_reaches_outside, stairs_reach_every_storey, height, over_water,
                                    spans_water, contains, contains_not, floor_levels, not_symmetric,
                                    materials, water_untouched, keeps_trees, light_near_top)}

# The checks in words, for the builder's brief; {arg} is filled from the task, else the grader's default.
TEXT = {
    "audit_clean": "`mc audit` shows no FAIL",
    "inside_plot": "nothing changes outside the plot (tree clearing and foundations included)",
    "door_reaches_outside": "every door can be walked to from outside",
    "indoor_floor": "at least {min} indoor floor spots",
    "lit_indoors": "every indoor floor is lit",
    "storeys": "at least {min} storeys",
    "stairs_reach_every_storey": "every storey can be walked to (stairs or ladders)",
    "height": "at least {min} blocks tall above the ground",
    "over_water": "at least {min} columns of the build stand over water",
    "spans_water": "walkable without swimming from {frm} to {to} (x, z)",
    "contains": "at least {min} of {any}",
    "contains_not": "none of {any}",
    "floor_levels": "people stand at {min}+ different heights (split levels, terraces)",
    "not_symmetric": "not a mirror image of itself",
    "materials": "{min}-{max} main materials",
    "water_untouched": "no water block changes",
    "keeps_trees": "at least {min_share:.0%} of the plot's tree logs still standing",
    "light_near_top": "a light in the top {within} blocks",
}


def describe(g):
    """A task's grader entry ({"code": ..., args}) in words."""
    f = CATALOGUE[g["code"]]
    args = {k: v.default for k, v in inspect.signature(f).parameters.items() if v.default is not inspect.Parameter.empty}
    args.update({k: v for k, v in g.items() if k != "code"})
    return TEXT[g["code"]].format(**args) + (" on an indoor floor" if args.get("on_floor") else "")


def run(task, outcome):
    """Every code grader of a task on an outcome: [{"grader", "pass", "value", "detail"}]."""
    out = []
    for g in task.get("graders", []):
        if "code" not in g:
            continue
        args = {k: v for k, v in g.items() if k != "code"}
        try:
            r = CATALOGUE[g["code"]](outcome, **args)
        except Exception as e:  # a grader that crashes fails, with the reason
            r = _res(False, None, f"grader error: {type(e).__name__}: {e}")
        out.append({"grader": g["code"], **r})
    return out
