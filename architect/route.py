"""Long roads across the world: a route between two points over a surveyed area (scripts/survey.py), by
A* on the coarse grid. A step costs its length, plus steep grades, high ground and water; each water
crossing costs a fixed amount on top (one bridge is better than three) and must run straight along an
axis (a bridge kit builds straight spans). Returns world (x, z) waypoints: land stretches simplified,
every crossing kept as its two bank points."""

import heapq
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def survey(name):
    return json.loads((ROOT / "local" / "survey" / f"{name}.json").read_text())


def to_cell(s, x, z):
    return (round((x - s["x0"]) / s["step"]), round((z - s["z0"]) / s["step"]))


def to_world(s, c):
    return (s["x0"] + c[0] * s["step"], s["z0"] + c[1] * s["step"])


def plan(s, start, goal, grade=0.35, high=128, high_cost=0.25, water=2.5, crossing=40, turn=0.3):
    """Cells from start to goal (world x, z). State = (cell, direction) so turns can be priced: a turn
    over water is not allowed (straight spans), a turn on land costs a little (no zigzags)."""
    Y, W, w, h = s["y"], s["water"], s["w"], s["h"]
    a, b = to_cell(s, *start), to_cell(s, *goal)
    if Y[a[1]][a[0]] is None or Y[b[1]][b[0]] is None:
        raise ValueError("start or goal is outside the survey")
    est = lambda c: math.hypot(c[0] - b[0], c[1] - b[1])  # noqa: E731
    best = {(a, -1): 0.0}
    came = {}
    q = [(est(a), 0.0, a, -1)]
    while q:
        f, g, c, d = heapq.heappop(q)
        if c == b:
            path, k = [c], (c, d)
            while k in came:
                k = came[k]
                path.append(k[0])
            return path[::-1]
        if g > best.get((c, d), math.inf):
            continue
        wet_here = W[c[1]][c[0]]
        for nd, (dx, dz) in enumerate(DIRS8):
            n = (c[0] + dx, c[1] + dz)
            if not (0 <= n[0] < w and 0 <= n[1] < h) or Y[n[1]][n[0]] is None:
                continue
            wet = W[n[1]][n[0]]
            if (wet or wet_here) and dx and dz:
                continue  # crossings run along an axis
            if wet_here and d != -1 and nd != d:
                continue  # no turning on a bridge
            step = math.hypot(dx, dz)
            cost = step
            if wet:
                cost += water * step + (crossing if not wet_here else 0)
            else:
                dy = abs(Y[n[1]][n[0]] - Y[c[1]][c[0]]) if not wet_here else 0
                cost += grade * dy * dy / step
                cost += high_cost * max(0, Y[n[1]][n[0]] - high)
                if d != -1 and nd != d:
                    cost += turn
            ng = g + cost
            if ng < best.get((n, nd), math.inf):
                best[(n, nd)] = ng
                came[(n, nd)] = (c, d)
                heapq.heappush(q, (ng + est(n), ng, n, nd))
    raise ValueError("no route")


def _simplify(pts, tol):
    """Douglas-Peucker on a list of (x, z)."""
    if len(pts) < 3:
        return list(pts)
    (ax, az), (bx, bz) = pts[0], pts[-1]
    L = math.hypot(bx - ax, bz - az) or 1
    far, i = 0, 0
    for k, (x, z) in enumerate(pts[1:-1], 1):
        dist = abs((bx - ax) * (az - z) - (ax - x) * (bz - az)) / L
        if dist > far:
            far, i = dist, k
    if far <= tol:
        return [pts[0], pts[-1]]
    return _simplify(pts[:i + 1], tol)[:-1] + _simplify(pts[i:], tol)


def waypoints(s, cells, tol=6):
    """World waypoints and the crossings: ([(x, z), ...], [((x, z) bank, (x, z) bank), ...]). Land runs
    are simplified; each crossing is kept exactly, from the last land cell to the first land cell."""
    W = s["water"]
    wet = [bool(W[c[1]][c[0]]) for c in cells]
    pts, crossings, run = [], [], []
    k = 0
    while k < len(cells):
        if not wet[k]:
            run.append(to_world(s, cells[k]))
            k += 1
            continue
        j = k
        while j < len(cells) and wet[j]:
            j += 1
        bank_a = to_world(s, cells[k - 1]) if k else to_world(s, cells[k])
        bank_b = to_world(s, cells[j]) if j < len(cells) else to_world(s, cells[j - 1])
        pts += _simplify(run, tol)
        crossings.append((bank_a, bank_b))
        run = [bank_b]
        k = j
    pts += _simplify(run, tol)
    out = []
    for p in pts:
        if not out or out[-1] != p:
            out.append(p)
    return out, crossings
