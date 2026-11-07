"""The Kingsway's stone bridges: arches on cutwater piers, parapets with lantern and banner pillars,
ramps onto the banks, and on long spans a gatehouse astride the road at mid-river (a crenellated
watch-gate or a whitewashed bridge chapel with a bell)."""
import math
import random

from architect.build import Build
from architect.parts import gable_roof, hip_roof, window

KIND = "bridge"

BLUE, GOLD = "blue_banner", "yellow_banner"
GATE_MIN = 30          # a bridge this long or longer gets the mid-river gatehouse


def build(length=36, width=7, rise=7, depth=5, ramp_a=0, ramp_b=0, seed=0):
    rng = random.Random(seed)
    b = Build("kingsway_bridge")
    L, W = length, width
    mid = W // 2
    zl, zr = 0, W - 1

    # materials (grey stone family, varied by seed)
    span = rng.choice([7, 8, 9, 10])
    ring = rng.choice(["polished_andesite", "smooth_stone", "stone_bricks", "polished_deepslate"])
    ring_stair = {"polished_andesite": "polished_andesite_stairs", "smooth_stone": "stone_brick_stairs",
                  "stone_bricks": "stone_brick_stairs", "polished_deepslate": "polished_deepslate_stairs"}[ring]
    moss = rng.choice([0.08, 0.15, 0.25])
    pave = rng.choice([["stone_bricks", "stone_bricks", "cobblestone", "andesite"],
                       ["polished_andesite", "stone_bricks", "andesite"],
                       ["cobblestone", "stone_bricks", "mossy_cobblestone", "cobblestone"]])
    parapet = rng.choice(["wall", "solid"])
    pillar_every = rng.choice([5, 6])
    gate_style = rng.choice(["tower", "spire", "chapel"])
    arch = rng.choice(["round", "pointed"])

    def stone():
        r = rng.random()
        return "mossy_stone_bricks" if r < moss else "cracked_stone_bricks" if r < moss + 0.1 else "stone_bricks"

    def walk(x):
        return rise - max(0, ramp_a - x) - max(0, x - (L - 1 - ramp_b))

    wa, wb = max(ramp_a, 1), L - 1 - max(ramp_b, 1)      # water from wa to wb

    def bank(x):  # top of the bank's ground at x, or None over water
        if x < wa:
            return rise - ramp_a - 1
        if x > wb:
            return rise - ramp_b - 1
        return None

    def floor_y(x):  # lowest air row an arch may open down to
        g = bank(x)
        return 1 if g is None else g + 1

    def bottom(x):  # where a pier's footing starts
        g = bank(x)
        return -depth if g is None else g - 1

    # ---- piers -------------------------------------------------------------------------------
    gate = L >= GATE_MIN
    c = (wa + wb) // 2
    piers = []  # (x1, x2)
    if gate:
        piers.append((c - 2, c + 2))
        k = c - 2 - span
        while k > 1:
            piers.append((k - 1, k))
            k -= span + 2
        k = c + 2 + span + 1
        while k < L - 2:
            piers.append((k, k + 1))
            k += span + 2
    else:
        k = c - span // 2 - 2
        while k > 1:
            piers.append((k - 1, k))
            k -= span + 2
        k = c - span // 2 + span - 1
        while k < L - 2:
            piers.append((k, k + 1))
            k += span + 2
    # abutments at both ends
    piers.append((0, 0))
    piers.append((L - 1, L - 1))
    piers.sort()
    in_pier = set()
    for p1, p2 in piers:
        in_pier.update(range(p1, p2 + 1))

    # ---- spandrels and arches ------------------------------------------------------------------
    springs = {}
    x = 0
    while x < L:
        if x in in_pier:
            for z in range(W):
                for y in range(bottom(x), walk(x) - 1):
                    b.set(x, y, z, stone())
            x += 1
            continue
        a = x
        while x < L and x not in in_pier:
            x += 1
        e = x - 1  # opening a..e
        n = e - a + 1
        top = min(walk(i) - 1 for i in range(a, e + 1)) - 2
        fl = max(floor_y(i) for i in range(a, e + 1))
        avail = top - fl + 1
        if n < 3 or avail < 2:
            for i in range(a, e + 1):
                for z in range(W):
                    for y in range(bottom(i), walk(i) - 1):
                        b.set(i, y, z, stone())
            continue
        half = n / 2
        r = min(math.ceil(half), avail - 1)
        spring = top - r
        springs[a - 1] = springs[e + 1] = min(springs.get(a - 1, 99), springs.get(e + 1, 99), spring)
        cm = (a + e) / 2
        air_top = {}
        for i in range(a, e + 1):
            d = abs(i - cm)
            u = min(1.0, d / (half + 0.35))
            curve = math.sqrt(max(0.0, 1 - u * u)) if arch == "round" else math.sqrt(max(0.0, 1 - u)) * (1 - 0.25 * u)
            air_top[i] = spring + int(r * curve + 0.5)
        for i in range(a, e + 1):
            for z in range(W):
                for y in range(air_top[i] + 1, walk(i) - 1):
                    b.set(i, y, z, stone())
            # the arch ring on both faces, and stair-rounded soffit steps
            for z in (zl, zr):
                b.set(i, air_top[i] + 1, z, ring)
                if air_top[i] + 2 < walk(i) - 1 and (air_top.get(i - 1, 99) > air_top[i] + 1 or air_top.get(i + 1, 99) > air_top[i] + 1):
                    b.set(i, air_top[i] + 2, z, ring)
            inner = air_top.get(i + 1 if i < cm else i - 1)
            if inner is not None and inner > air_top[i]:
                face = "west" if i < cm else "east"
                for z in range(W):
                    b.set(i, air_top[i] + 1, z, f"{ring_stair}[facing={face},half=top]")
        # a hanging lantern under the crown of water arches
        if bank(int(cm)) is None and avail >= 4:
            ci = int(cm)
            b.set(ci, air_top[ci], mid, "lantern[hanging=true]")

    # ---- cutwaters: piers narrow to a point on both faces below the springing ----------------
    for p1, p2 in piers:
        if p2 - p1 < 1 or bank(p1) is not None or bank(p2) is not None:
            continue
        top_cw = min(springs.get(p1, 99), springs.get(p2, 99), springs.get(p1 - 1, 99), springs.get(p2 + 1, 99)) - 1
        top_cw = max(2, min(top_cw, rise - 4))
        pc = (p1 + p2) // 2
        for z, inward in ((zl, "south"), (zr, "north")):
            for i in range(p1, p2 + 1):
                if i in (pc, pc + (1 if (p2 - p1) % 2 else 0)):
                    continue
                for y in range(-depth, top_cw + 1):
                    b.blocks.pop((i, y, z), None)
                b.set(i, top_cw + 1, z, f"stone_brick_stairs[facing={'east' if i < pc else 'west'},half=bottom]")
            for i in range(p1, p2 + 1):
                if (i, top_cw, z) in b.blocks:
                    b.set(i, top_cw + 1, z, f"stone_brick_stairs[facing={inward},half=bottom]")

    # ---- deck, ramps, cornice --------------------------------------------------------------------
    for x in range(L):
        dy = walk(x) - 1
        on_ramp = 0 < x <= ramp_a or L - 1 - ramp_b <= x < L - 1
        up = x <= ramp_a  # climbing toward +x
        for z in range(W):
            if z in (zl, zr):
                b.set(x, dy, z, ring if ring != "stone_bricks" else "polished_andesite")
            elif on_ramp and (x <= ramp_a and ramp_a > 0 or x >= L - 1 - ramp_b and ramp_b > 0):
                b.set(x, dy, z, f"stone_brick_stairs[facing={'east' if up else 'west'},half=bottom]")
                b.set(x, dy - 1, z, stone())
            else:
                b.set(x, dy, z, rng.choice(pave))
            # keep the way open
            for y in range(dy + 1, dy + 4):
                if z not in (zl, zr):
                    b.set(x, y, z, "air")

    # ---- gatehouse ---------------------------------------------------------------------------
    gx0, gx1 = (c - 2, c + 2) if gate else (None, None)
    if gate:
        build_gate(b, rng, gx0, gx1, W, rise, gate_style, stone)

    # ---- parapets, pillars, lanterns, banners ----------------------------------------------------
    pillars = set()
    for x in [0, L - 1] + [(p1 + p2) // 2 for p1, p2 in piers]:
        pillars.add(x)
    for x in range(pillar_every, L - 2, pillar_every):
        if min(abs(x - p) for p in pillars) >= 3:
            pillars.add(x)
    banner_turn = 0
    walls = []
    for x in range(L):
        if gate and gx0 <= x <= gx1:
            continue
        y = walk(x)
        for z in (zl, zr):
            if x in pillars:
                b.set(x, y, z, "chiseled_stone_bricks" if x in (0, L - 1) else "stone_bricks")
                b.set(x, y + 1, z, "stone_brick_wall[up=true]" if parapet == "wall" else "chiseled_stone_bricks")
            elif parapet == "wall":
                b.set(x, y, z, "stone_brick_wall")
                walls.append((x, y, z))
            else:
                b.set(x, y, z, stone())
                b.set(x, y + 1, z, "stone_brick_slab[type=bottom]")
    # tops of pillars: lanterns, and blue/gold banner poles on the piers of long bridges
    for x in sorted(pillars):
        if gate and gx0 <= x <= gx1:
            continue
        y = walk(x) + 2
        is_pier = any(p1 <= x <= p2 for p1, p2 in piers) and x not in (0, L - 1)
        for z in (zl, zr):
            if is_pier and L >= 30:
                b.set(x, y, z, "spruce_fence")
                b.set(x, y + 1, z, "spruce_fence")
                col = BLUE if banner_turn % 2 == 0 else GOLD
                b.set(x, y + 2, z, f"{col}[rotation={8 if z == zl else 0}]")
            else:
                b.set(x, y, z, "lantern[hanging=false]")
        if is_pier and L >= 30:
            banner_turn += 1
    # wall connections
    wallset = {(x, z): y for x, y, z in walls}
    for x, y, z in walls:
        def joins(nx):
            nb = b.get(nx, y, z)
            return nb is not None and nb != "air" and "lantern" not in nb and "stairs" not in nb
        e, w_ = joins(x + 1), joins(x - 1)
        upv = "false" if (e and w_) else "true"
        b.set(x, y, z, f"stone_brick_wall[east={'low' if e else 'none'},west={'low' if w_ else 'none'},"
                       f"north=none,south=none,up={upv}]")
    # ends: lanterns already on the end pillars; small mile marker on the a-bank end
    return b


def build_gate(b, rng, x0, x1, W, rise, style, stone):
    """A gate astride the road over the middle pier: side walls, a 4-high passage, a chamber above
    reached by a ladder, then a crenellated top (tower) or a whitewashed gable with a bell (chapel)."""
    t = 1 if W < 7 else 2               # side wall thickness
    mid = W // 2
    zl, zr = 0, W - 1
    top_pass = rise + 3
    # side walls
    for x in range(x0, x1 + 1):
        for y in range(rise, rise + 4):
            for z in list(range(0, t)) + list(range(W - t, W)):
                b.set(x, y, z, stone())
            for z in range(t, W - t):
                b.set(x, y, z, "air")
    # corner quoins and portal arches
    for x in (x0, x1):
        for y in range(rise, rise + 4):
            for z in (zl, zr):
                b.set(x, y, z, "polished_andesite")
        b.set(x, top_pass, t, f"stone_brick_stairs[facing=north,half=top]")
        b.set(x, top_pass, W - 1 - t, f"stone_brick_stairs[facing=south,half=top]")
    # lintel / chamber floor
    fy = rise + 4
    b.fill(x0, fy, 0, x1, fy, W - 1, "stone_bricks")
    for x in range(x0, x1 + 1):
        for z in (zl, zr):
            b.set(x, fy, z, "chiseled_stone_bricks" if x in (x0, x1) else "polished_andesite")
    # passage lights and ladder up
    cx = (x0 + x1) // 2
    b.set(cx, top_pass, mid, "lantern[hanging=true]")
    lx = x0 + 1
    for y in range(rise, fy + 1):
        b.set(lx, y, t, "ladder[facing=south]")
    # chamber
    wy1, wy2 = fy + 1, fy + (3 if style == "chapel" else 5)
    if style == "chapel":
        for x in range(x0, x1 + 1):
            for z in range(W):
                edge = x in (x0, x1) or z in (zl, zr)
                for y in range(wy1, wy2 + 1):
                    if not edge:
                        b.set(x, y, z, "air")
                    elif x in (x0, x1) and z in (zl, zr):
                        b.set(x, y, z, "spruce_log[axis=y]")
                    else:
                        b.set(x, y, z, "white_terracotta" if rng.random() < 0.5 else "calcite")
        for x in range(x0, x1 + 1):
            for z in (zl, zr):
                b.set(x, wy2, z, "dark_oak_log[axis=x]")
        for z in range(W):
            for x in (x0, x1):
                b.set(x, wy2, z, "dark_oak_log[axis=z]")
        # tall windows facing the river, a door-like opening is the ladder hole
        window(b, cx, wy1, zl, "x", 1, 2, "blue_stained_glass_pane")
        window(b, cx, wy1, zr, "x", 1, 2, "blue_stained_glass_pane")
        for x in (x0, x1):
            window(b, x, wy1 + 1, mid, "z", 1, 1, "glass_pane")
        roof = rng.choice(["deepslate_tile_stairs", "dark_oak_stairs"])
        gable_roof(b, x0, 0, x1, W - 1, wy2 + 1, roof, "white_terracotta", ridge="z", overhang=1, end_overhang=0)
        # bell turret on the ridge
        ry = wy2 + 1 + (x1 - x0) // 2 + 1
        b.set(cx, ry, mid, "spruce_fence")
        b.set(cx, ry + 1, mid, "bell[attachment=floor,facing=east]")
        b.set(cx, ry + 2, mid, "dark_oak_slab[type=bottom]")
        # inside: an altar, candles, a pew and a lantern
        b.set(cx, wy1, mid + 1 if W > 5 else mid, "chiseled_stone_bricks")
        b.set(cx, wy1 + 1, mid + 1 if W > 5 else mid, "candle[candles=3,lit=true]")
        b.set(x1 - 1, wy1, mid, "spruce_stairs[facing=east,half=bottom]")
        b.set(x0 + 2, wy2, mid, "lantern[hanging=true]")
    else:
        for x in range(x0, x1 + 1):
            for z in range(W):
                edge = x in (x0, x1) or z in (zl, zr)
                for y in range(wy1, wy2 + 1):
                    if not edge:
                        b.set(x, y, z, "air")
                    elif x in (x0, x1) and z in (zl, zr):
                        b.set(x, y, z, "polished_andesite")
                    else:
                        b.set(x, y, z, stone())
        # arrow slits and windows
        for z in (zl, zr):
            window(b, cx, wy1 + 1, z, "x", 1, 2, "glass_pane")
        for x in (x0, x1):
            b.set(x, wy1 + 3, mid, "air")
            b.set(x, wy1 + 1, mid, "iron_bars")
        # a string course and machicolation-like corbels
        b.fill(x0, wy2 + 1, 0, x1, wy2 + 1, W - 1, "stone_bricks")
        for x in range(x0, x1 + 1):
            for z in (zl, zr):
                b.set(x, wy2 + 1, z, "polished_andesite")
        if style == "spire":  # a steep slate pyramid over the whole tower instead of battlements
            for x in range(x0 + 1, x1):
                for z in range(1, W - 1):
                    b.set(x, wy2 + 1, z, "air")  # the chamber opens into the roof
            hip_roof(b, x0, 0, x1, W - 1, wy2 + 2, "deepslate_tile_stairs", top="deepslate_tile_slab[type=bottom]",
                     overhang=0)
            py = max(y for (x, y, z) in b.blocks if x == cx and z == mid) + 1
            b.set(cx, py, mid, "lightning_rod")
            b.set(cx, wy2, mid, "lantern[hanging=true]")
            b.set(x1 - 1, wy1, mid, "barrel[facing=up]")
            for y in range(wy1, wy2 + 1):
                b.set(lx, y, t, "ladder[facing=south]")
            return
        # battlements
        for x in range(x0, x1 + 1):
            for z in range(W):
                if x in (x0, x1) or z in (zl, zr):
                    if (x + z) % 2 == 0:
                        b.set(x, wy2 + 2, z, "stone_bricks")
                    else:
                        b.set(x, wy2 + 2, z, "stone_brick_slab[type=bottom]")
        # a flagpole with the crown's banners and lanterns on the corners
        hip_roof(b, x0 + 1, 1, x1 - 1, W - 2, wy2 + 2, rng.choice(["deepslate_tile_stairs", "dark_oak_stairs"]),
                 overhang=0)
        py = max(y for (x, y, z) in b.blocks if x == cx and z == mid) + 1
        b.set(cx, py, mid, "spruce_fence")
        b.set(cx, py + 1, mid, "spruce_fence")
        b.set(cx, py + 2, mid, f"{BLUE}[rotation=4]")
        for x in (x0, x1):
            for z in (zl, zr):
                b.set(x, wy2 + 3, z, "lantern[hanging=false]")
        b.set(cx, wy2, mid, "lantern[hanging=true]")
        b.set(x1 - 1, wy1, mid, "barrel[facing=up]")
        # the ladder continues up the chamber wall
        for y in range(wy1, wy2 + 1):
            b.set(lx, y, t, "ladder[facing=south]")
