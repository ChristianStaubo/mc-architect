"""The Kingsway waystation: inn, stables, smithy, watchtower, roadside shrine and road-keepers' houses.

Royal road style: grey stone-brick / cobble ground storeys, spruce and dark oak frames, whitewashed
(white terracotta / calcite) upper walls, steep dark roofs (deepslate tiles or dark oak), lanterns on
posts, the crown's blue and gold banners, hay, carts and barrels in the yards.

Every kind is drawn in one canonical frame: the road to the south (door on the south side), x along the
road, z away from it. The seed mirrors it east-west, then it is turned to the plot's door side.
"""

import random

from architect.build import Build
from architect.parts import (chimney, cone_roof, door, dormer_on, flower_box, gable_roof, hip_roof, roofs, shutters,
                             spiral_stairs, stamp, straight_stairs, window)

KINDS = ["house", "inn", "shrine", "smithy", "stable", "watchtower"]
PLOT = (0, 0)  # the canonical plot (W, D) being built
TURNS = {"south": 0, "west": 1, "north": 2, "east": 3}
FACE = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


# ---------------------------------------------------------------- palette and small helpers

ROOFS = {  # each kind its own roof colour, so they read apart at a glance
    "house": ["deepslate_tile", "dark_oak", "spruce", "deepslate_brick", "deepslate_tile"],
    "inn": ["dark_oak", "deepslate_tile", "dark_oak"],
    "smithy": ["deepslate_brick", "cobbled_deepslate"],
    "stable": ["spruce", "dark_oak", "spruce"],
    "shrine": ["waxed_oxidized_cut_copper", "waxed_weathered_cut_copper", "waxed_oxidized_cut_copper"],
    "watchtower": ["deepslate_tile", "deepslate_brick"],
}


class Pal:
    def __init__(self, rng, kind="house"):
        self.salt = rng.randrange(1 << 16)
        self.stone = rng.choice([
            ["stone_bricks"] * 6 + ["cracked_stone_bricks", "mossy_stone_bricks"],
            ["cobblestone"] * 5 + ["mossy_cobblestone", "andesite"],
            ["stone_bricks"] * 4 + ["cobblestone"] * 3 + ["mossy_stone_bricks"],
        ])
        self.band = "stone_bricks" if self.stone[0] == "cobblestone" else "polished_andesite"
        self.post = rng.choice(["spruce_log", "dark_oak_log"])
        self.beam = rng.choice(["dark_oak_log", "spruce_log", self.post])
        self.fill = rng.choice(["calcite", "calcite", "white_terracotta"])
        self.roofm = rng.choice(ROOFS[kind])
        self.wood = rng.choice(["spruce", "dark_oak", "spruce"])
        self.floor = rng.choice(["spruce_planks", "dark_oak_planks"])
        self.bed = rng.choice(["blue", "light_blue", "yellow", "white", "red"])

    def st(self, x, y, z):
        h = ((x * 73856093) ^ (y * 19349663) ^ (z * 83492791) ^ self.salt) & 0xffffff
        return self.stone[(h >> 3) % len(self.stone)]

    @property
    def rst(self):
        return f"{self.roofm}_stairs"


def S(mat, facing, half="bottom"):
    return f"{mat}_stairs[facing={facing},half={half},shape=straight]"


def free(b, x, y, z):
    return b.get(x, y, z) in (None, "air")


def ring(x1, z1, x2, z2):
    for x in range(x1, x2 + 1):
        yield x, z1
        yield x, z2
    for z in range(z1 + 1, z2):
        yield x1, z
        yield x2, z


def bed(b, x, y, z, facing, color):
    dx, dz = FACE[facing]
    b.set(x, y, z, f"{color}_bed[facing={facing},part=head,occupied=false]")
    b.set(x - dx, y, z - dz, f"{color}_bed[facing={facing},part=foot,occupied=false]")


def table(b, p, x, y, z, top=None):
    b.set(x, y, z, f"{p.wood}_fence[east=false,north=false,south=false,west=false]")
    b.set(x, y + 1, z, top or f"{p.wood}_pressure_plate")


def hang(b, x, y, z):
    b.set(x, y, z, "lantern[hanging=true]")


def lamp_post(b, p, x, z, h=2):
    for y in range(0, h):
        b.set(x, y, z, f"{p.wood}_fence[east=false,north=false,south=false,west=false]")
    b.set(x, h, z, "lantern[hanging=false]")


def fence_line(b, p, cells, y):
    cells = list(cells)
    s = set(cells)
    for (x, z) in cells:
        c = {d: str((x + dx, z + dz) in s).lower() for d, (dx, dz) in FACE.items()}
        b.set(x, y, z, f"{p.wood}_fence[east={c['east']},north={c['north']},south={c['south']},west={c['west']}]")


def cart(b, p, x, z, along="x", load=("hay_block[axis=x]", "barrel[facing=up]")):
    """A hand cart: a plank bed on wheels (open trapdoors) with a shaft, loaded."""
    cells = [(x, z), (x + 1, z)] if along == "x" else [(x, z), (x, z + 1)]
    for i, (cx, cz) in enumerate(cells):
        b.set(cx, 0, cz, f"{p.wood}_slab[type=top]")
        b.set(cx, 1, cz, load[i % len(load)])
    cx, cz = cells[0]
    W, D = PLOT

    def opt(x_, z_, blk):  # wheels and shaft only where they fit in the plot and nothing is there
        if 0 <= x_ < W and 0 <= z_ < D and free(b, x_, 0, z_):
            b.set(x_, 0, z_, blk)
    if along == "x":
        opt(cx, cz - 1, "dark_oak_trapdoor[facing=north,half=bottom,open=true]")
        opt(cx, cz + 1, "dark_oak_trapdoor[facing=south,half=bottom,open=true]")
        opt(x + 2, z, f"{p.wood}_fence[east=false,north=false,south=false,west=true]")
    else:
        opt(cx - 1, cz, "dark_oak_trapdoor[facing=west,half=bottom,open=true]")
        opt(cx + 1, cz, "dark_oak_trapdoor[facing=east,half=bottom,open=true]")
        opt(x, z + 2, f"{p.wood}_fence[east=false,north=true,south=false,west=false]")


def ground(b, W, D):
    for x in range(W):
        for z in range(D):
            b.set(x, -1, z, "grass_block")


def path(b, cells, rng=None, block="dirt_path"):
    for (x, z) in cells:
        b.set(x, -1, z, block)


def apron(b, p, x1, x2, z1, z2, mix=("cobblestone", "gravel", "stone_bricks", "cobblestone")):
    """A paved apron towards the highway (the ground layer, y -1), keeping any path already laid."""
    W, D = PLOT
    for x in range(max(0, x1), min(W - 1, x2) + 1):
        for z in range(max(0, z1), min(D - 1, z2) + 1):
            if b.get(x, -1, z) == "grass_block":
                b.set(x, -1, z, mix[((x * 31 + z * 17 + p.salt) * 2654435761 >> 7) % len(mix)])


def top_at(b, x, z):
    return max((y for (bx, y, bz) in b.blocks if bx == x and bz == z), default=0)


# ---------------------------------------------------------------- walls, windows, roofs

def shell(b, p, x1, z1, x2, z2, top, stone_to=3, every=4, fill=None, floor=None, beam_low=True):
    """Floor at y0 (stone rim), stone walls up to stone_to, then a timber frame with whitewash panels:
    posts every `every`, a beam band at the top (and at the bottom of the frame if it is a full storey)."""
    fill = fill or p.fill
    floor = floor or p.floor
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            edge = x in (x1, x2) or z in (z1, z2)
            b.set(x, 0, z, p.st(x, 0, z) if edge else floor)
    xs = set(range(x1, x2 + 1, every)) | {x2}
    zs = set(range(z1, z2 + 1, every)) | {z2}
    for y in range(1, top + 1):
        for x, z in ring(x1, z1, x2, z2):
            if y <= stone_to:
                blk = p.st(x, y, z)
            else:
                corner = x in (x1, x2) and z in (z1, z2)
                post = (z in (z1, z2) and x in xs) or (x in (x1, x2) and z in zs)
                beam = y == top or (beam_low and y == stone_to + 1 and top - stone_to >= 3)
                if beam and not corner:
                    blk = f"{p.beam}[axis={'x' if z in (z1, z2) else 'z'}]"
                elif post:
                    blk = f"{p.post}[axis=y]"
                else:
                    blk = fill
            b.set(x, y, z, blk)


def mids(a1, a2, every):
    ps = sorted(set(range(a1, a2 + 1, every)) | {a2})
    return [(u + v) // 2 for u, v in zip(ps, ps[1:]) if v - u >= 2]


def windows(b, x1, z1, x2, z2, rows, every, avoid=(), pane="glass_pane", sides="nsew"):
    """1-wide, 2-tall windows between the frame posts on the chosen sides, on each storey's row."""
    out = []
    for side in sides:
        if side in "ns":
            z = z1 if side == "n" else z2
            cells = [(x, z) for x in mids(x1, x2, every)]
        else:
            x = x1 if side == "w" else x2
            cells = [(x, z) for z in mids(z1, z2, every)]
        for (x, z) in cells:
            if (x, z) in avoid:
                continue
            for y in rows:
                window(b, x, y, z, "x" if side in "ns" else "z", 1, 2, pane)
            out.append((x, z, side))
    return out


def put(b, t, keep=False, gable=None):
    for k, v in t.blocks.items():
        if k in b.blocks and b.blocks[k] != "air" and (keep or v == gable):
            continue
        b.blocks[k] = v


FULL = {"deepslate_tile": "deepslate_tiles", "dark_oak": "dark_oak_planks", "deepslate_brick": "deepslate_bricks",
        "spruce": "spruce_planks", "cobbled_deepslate": "cobbled_deepslate",
        "waxed_oxidized_cut_copper": "waxed_oxidized_cut_copper", "waxed_weathered_cut_copper": "waxed_weathered_cut_copper"}


def steep_gable(b, x1, z1, x2, z2, y, mat, gable, ridge="x"):
    """A 2:1 gable roof (two blocks up per block in): a stair on a full block in every course, the gable
    ends filled under it, one block of overhang all round. The royal road's roofs are steep."""
    if ridge == "x":
        lo, hi, a1, a2 = z1, z2, x1 - 1, x2 + 1
        put_ = lambda a, c, yy, blk: b.set(a, yy, c, blk)  # noqa: E731
        up_lo, up_hi = "south", "north"
    else:
        lo, hi, a1, a2 = x1, x2, z1 - 1, z2 + 1
        put_ = lambda a, c, yy, blk: b.set(c, yy, a, blk)  # noqa: E731
        up_lo, up_hi = "east", "west"
    lo_o, hi_o = lo - 1, hi + 1
    for c in range(lo_o, hi_o + 1):
        j = min(c - lo_o, hi_o - c)
        mid = (c - lo_o) == (hi_o - c)
        t = y + 2 * j
        for a in range(a1, a2 + 1):
            if mid:
                put_(a, c, t - 1, FULL[mat])
                put_(a, c, t, f"{mat}_slab[type=bottom]")
            else:
                put_(a, c, t, S(mat, up_lo if c - lo_o < hi_o - c else up_hi))
                if j >= 1:
                    put_(a, c, t - 1, FULL[mat])
        if lo <= c <= hi and j >= 1:
            for a in (a1 + 1, a2 - 1):
                for yy in range(y + 1, t - 1):
                    put_(a, c, yy, gable)


def steep_roofs(b, *specs):
    """Steep gables that meet (a cross gable): blocks under another roof's surface are left out."""
    built = []
    for sp in specs:
        t = Build("roof")
        steep_gable(t, **sp)
        top = {}
        for (x, y, z) in t.blocks:
            top[(x, z)] = max(top.get((x, z), y), y)
        built.append((t, top))
    for i, (t, _) in enumerate(built):
        for (x, y, z), blk in t.blocks.items():
            if any(top.get((x, z), -10 ** 9) > y for j, (_, top) in enumerate(built) if j != i):
                continue
            b.set(x, y, z, blk)


def roof(b, p, style, x1, z1, x2, z2, y, keep=False, cross=None, gable=None, steep=False):
    """style x / z (gable, ridge along x or z), hip, or cross (ridge x with a front gable over cross=(xa, xb)).
    steep: 2:1 pitch instead of 45 degrees (gables only)."""
    g = gable or p.fill
    t = Build("roof")
    r = None
    if steep and style in ("x", "z"):
        steep_gable(t, x1, z1, x2, z2, y, p.roofm, g, ridge=style)
    elif steep and style == "cross":
        a, c = cross
        steep_roofs(t, dict(x1=x1, z1=z1, x2=x2, z2=z2, y=y, mat=p.roofm, gable=g, ridge="x"),
                    dict(x1=a, z1=(z1 + z2) // 2, x2=c, z2=z2, y=y, mat=p.roofm, gable=g, ridge="z"))
    elif style in ("x", "z"):
        r = gable_roof(t, x1, z1, x2, z2, y, p.rst, g, ridge=style)
    elif style == "hip":
        hip_roof(t, x1, z1, x2, z2, y, p.rst)
    else:
        a, c = cross
        roofs(t, dict(x1=x1, z1=z1, x2=x2, z2=z2, y=y, stair=p.rst, gable=g, ridge="x"),
              dict(x1=a, z1=(z1 + z2) // 2, x2=c, z2=z2, y=y, stair=p.rst, gable=g, ridge="z"))
        r = {"x1": x1, "z1": z1, "x2": x2, "z2": z2, "y": y, "ridge": "x", "overhang": 1, "stair": p.rst, "gable": g}
    put(b, t, keep, g)
    return r


def gable_windows(b, style, x1, z1, x2, z2, y, cross=None, pane="glass_pane"):
    """A small window high in each gable end (lights the attic, reads as a lived-in loft)."""
    if style == "x" and z2 - z1 >= 4:
        cz = (z1 + z2) // 2
        for x in (x1, x2):
            window(b, x, y + 1, cz, "z", 1, 2 if z2 - z1 >= 6 else 1, pane)
    if style == "z" and x2 - x1 >= 4:
        cx = (x1 + x2) // 2
        for z in (z1, z2):
            window(b, cx, y + 1, z, "x", 1, 2 if x2 - x1 >= 6 else 1, pane)
    if style == "cross":
        a, c = cross
        window(b, (a + c) // 2, y + 1, z2, "x", 1, 2, pane)


def banner(b, x, y, z, color, facing="south"):
    b.set(x, y, z, f"{color}_wall_banner[facing={facing}]")


def yard(b, p, rng, cols, z_lo, z_hi):
    """Fill a side strip (columns `cols`, rows z_lo..z_hi) with yard life: woodpile, hay, barrels, a cart."""
    if not cols:
        return
    x = cols[0]
    z = z_lo
    items = rng.sample(["wood", "hay", "barrels", "cart", "compost"], 3)
    for it in items:
        if z > z_hi:
            break
        if it == "wood":
            for zz in (z, z + 1):
                if zz <= z_hi:
                    b.set(x, 0, zz, "spruce_log[axis=x]")
                    b.set(x, 1, zz, "spruce_log[axis=x]" if rng.random() < 0.7 else "oak_log[axis=x]")
            z += 3
        elif it == "hay":
            b.set(x, 0, z, "hay_block[axis=y]")
            b.set(x, 1, z, "hay_block[axis=x]")
            if z + 1 <= z_hi:
                b.set(x, 0, z + 1, "hay_block[axis=z]")
            z += 3
        elif it == "barrels":
            b.set(x, 0, z, "barrel[facing=up]")
            if z + 1 <= z_hi:
                b.set(x, 0, z + 1, "barrel[facing=north]")
            z += 3
        elif it == "cart" and z + 2 <= z_hi:
            cart(b, p, x, z, along="z")
            z += 4
        elif it == "compost":
            b.set(x, 0, z, "composter[level=5]")
            z += 2
    if len(cols) > 1:  # a fence along the outer edge of a wide yard
        fence_line(b, p, [(cols[-1], zz) for zz in range(z_lo, z_hi)], 0)


def front_dress(b, p, rng, door_x, z2, wins, top, W, D, banner_xs=()):
    """Door hood with lanterns, flower boxes or shutters, banners, a bench and a lamp post."""
    hood = top >= 4
    if hood:
        for x in (door_x - 1, door_x, door_x + 1):
            b.set(x, 3, z2 + 1, S(p.roofm if "dark_oak" in p.roofm else p.wood, "north"))
        for x in (door_x - 1, door_x + 1):
            hang(b, x, 2, z2 + 1)
    deco = rng.choice(["boxes", "shutters", "both"])
    for (x, z, side) in wins:
        if side != "s":
            continue
        if deco in ("boxes", "both") and free(b, x, 1, z + 1) and free(b, x, 1, z + 2) and z + 2 < D:
            flower_box(b, x, 2, z, "x", 1, "south",
                       flowers=(rng.choice(["poppy", "cornflower", "dandelion", "azure_bluet", "allium"]),))
        if deco in ("shutters", "both"):
            for y in ((2, 5) if top >= 8 else (2,)):
                if all(free(b, xx, yy, z + 1) for xx in (x - 1, x + 1) for yy in (y, y + 1)):
                    shutters(b, x, y, z, "x", 1, 2, "south", p.wood)
    for i, x in enumerate(banner_xs):
        banner(b, x, 7, z2 + 1, ("blue", "yellow")[i % 2])
    for bx in (door_x + 2, door_x - 2):
        if rng.random() < 0.5 and free(b, bx, 0, z2 + 1) and free(b, bx, 1, z2 + 1):
            b.set(bx, 0, z2 + 1, S(p.wood, "north"))
            break
    lx = W - 1 if rng.random() < 0.5 else 0
    if free(b, lx, 0, D - 1):
        lamp_post(b, p, lx, D - 1)


# ---------------------------------------------------------------- kinds

def house(b, p, W, D, rng):
    if W >= 9 and D >= 9 and rng.random() < 0.4:
        return house_l(b, p, W, D, rng)
    two = rng.random() < 0.7
    top = 8 if two else 4
    style = rng.choice(["x", "z", "cross", "hip"]) if two else rng.choice(["x", "x", "z"])
    bw = W - 2 if (W - 2 <= 7 or rng.random() < 0.3) else 7
    x1, z1 = 1, 1
    x2, z2 = x1 + bw - 1, D - 3
    every = rng.choice([3, 4])
    shell(b, p, x1, z1, x2, z2, top, every=every)
    cx = (x1 + x2) // 2
    dx = cx + (rng.choice([0, 1]) if bw >= 8 else 0)
    avoid = {(dx + i, z2) for i in (-2, -1, 0, 1, 2)}
    wins = windows(b, x1, z1, x2, z2, [2, 5] if two else [2], every, avoid)
    door(b, dx, 1, z2, "south", p.wood)
    b.set(dx, 0, z2 + 1, S(p.wood, "north"))
    path(b, [(dx, z) for z in range(z2 + 1, D)])

    # inside
    side = ["smoker[facing=east,lit=true]", "crafting_table", "barrel[facing=up]", "chest[facing=east]"]
    rng.shuffle(side)
    if two:
        b.fill(x1 + 1, 4, z1 + 1, x2 - 1, 4, z2 - 1, p.floor)
        straight_stairs(b, x1 + 1, 1, z1 + 1, "east", 4, f"{p.wood}_stairs")
        zs = range(z1 + 3, z2)
        for z, it in zip(zs, side):
            b.set(x1 + 1, 1, z, it)
        table(b, p, x2 - 2, 1, z2 - 2)
        b.set(x2 - 1, 1, z2 - 2, S(p.wood, "east"))
        b.set(x2 - 3, 1, z2 - 2, S(p.wood, "west"))
        hang(b, x1 + 2, 3, z2 - 1)
        hang(b, x2 - 1, 3, z1 + 2)
        bed(b, x2 - 1, 5, z2 - 1, "south", p.bed)
        if bw >= 8:
            bed(b, x2 - 2, 5, z2 - 1, "south", p.bed)
        b.set(x1 + 1, 5, z2 - 1, "chest[facing=east]")
        b.set(x1 + 1, 5, z2 - 2, "lantern[hanging=false]")
        b.set(cx, 5, z2 - 2, "blue_carpet")
        b.set(x2 - 1, 5, z1 + 2, "lantern[hanging=false]") if free(b, x2 - 1, 5, z1 + 2) else None
    else:
        bed(b, x2 - 1, 1, z1 + 1, "north", p.bed)
        for z, it in zip(range(z1 + 1, z2), side):
            b.set(x1 + 1, 1, z, it)
            if it.startswith("barrel"):
                b.set(x1 + 1, 2, z, "lantern[hanging=false]")
        table(b, p, x2 - 1, 1, z2 - 2, top="lantern[hanging=false]")
        b.set(x2 - 2, 1, z2 - 2, S(p.wood, "west"))

    cross = (dx - 2, dx + 2)
    steep = style != "hip" and rng.random() < 0.55
    r = roof(b, p, style, x1, z1, x2, z2, top, cross=cross, steep=steep)
    gable_windows(b, style, x1, z1, x2, z2, top, cross)
    if style == "x" and not steep and (not two or rng.random() < 0.4):
        ats = [cx] if bw < 9 else [x1 + 2, x2 - 2]
        for a in ats:
            dormer_on(b, r, a, "back", p.fill)
    if rng.random() < 0.7:  # a stone chimney up the gable end
        zc = (z1 + z2) // 2
        chimney(b, x2 + 1, zc, 0, top_at(b, x2 + 1, zc) + 2, p.stone[0], smoke=True)
    if two and rng.random() < 0.6:
        posts = sorted(set(range(x1, x2 + 1, every)) - {x1, x2})
        front_dress(b, p, rng, dx, z2, wins, top, W, D, banner_xs=posts[:1])
    else:
        front_dress(b, p, rng, dx, z2, wins, top, W, D)
    yard(b, p, rng, list(range(x2 + 2, W)), z1, z2 + 1)
    if x2 + 2 < W and free(b, x2 + 1, 0, z1 + 1):  # woodpile under the eave
        for z in (z1 + 1, z1 + 2):
            if free(b, x2 + 1, 0, z):
                b.set(x2 + 1, 0, z, "spruce_log[axis=x]")
    apron(b, p, dx - 1, dx + 1, D - 1, D - 1, ("gravel", "cobblestone", "dirt_path"))


def house_l(b, p, W, D, rng):
    """An L: a main range along the back, a gabled wing coming forward to the road, the door in the notch."""
    two = rng.random() < 0.65
    top = 8 if two else 4
    x1, z1, x2, z2 = 1, 1, W - 2, D - 3
    zb, wx2 = z2 - 2, x1 + 4  # main range z1..zb; wing x1..wx2, z1..z2
    every = rng.choice([3, 4])
    shell(b, p, x1, z1, x2, zb, top, every=every)
    shell(b, p, x1, z1, wx2, z2, top, every=every)
    for y in range(1, top):
        if y == 4:
            continue
        for x in range(x1 + 1, wx2):
            b.set(x, y, zb, "air")
        for z in range(z1 + 1, zb):
            b.set(wx2, y, z, "air")
    dx = rng.randint(wx2 + 1, x2 - 1)
    rows = [2, 5] if two else [2]
    wins = windows(b, x1, z1, x2, zb, rows, every,
                   {(x, zb) for x in range(x1, wx2 + 1)} | {(dx + i, zb) for i in (-1, 0, 1)}, sides="nes")
    wins += windows(b, x1, z1, wx2, z2, rows, every, {(wx2, z) for z in range(z1, zb + 1)}, sides="wse")
    door(b, dx, 1, zb, "south", p.wood)
    b.set(dx, 0, zb + 1, S(p.wood, "north"))
    path(b, [(dx, z) for z in range(zb + 1, D)])
    side = ["smoker[facing=east,lit=true]", "crafting_table", "barrel[facing=up]", "chest[facing=south]"]
    rng.shuffle(side)
    if two:
        b.fill(x1 + 1, 4, z1 + 1, x2 - 1, 4, zb - 1, p.floor)
        b.fill(x1 + 1, 4, z1 + 1, wx2 - 1, 4, z2 - 1, p.floor)
        straight_stairs(b, x1 + 1, 1, z1 + 1, "east", 4, f"{p.wood}_stairs")
        for z, it in zip(range(zb, z2), side):
            b.set(x1 + 1, 1, z, it)
        table(b, p, x1 + 3, 1, z2 - 1)
        b.set(x2 - 1, 1, z1 + 1, "chest[facing=south]")
        hang(b, x1 + 2, 3, z2 - 1)
        hang(b, x2 - 1, 3, zb - 1)
        bed(b, x1 + 1, 5, z2 - 1, "south", p.bed)
        b.set(x1 + 3, 5, z2 - 1, "chest[facing=south]")
        b.set(x1 + 3, 5, z2 - 2, "lantern[hanging=false]")
        if free(b, x2 - 1, 5, zb - 1):
            b.set(x2 - 1, 5, zb - 1, "lantern[hanging=false]")
    else:
        for x, it in zip(range(x1 + 1, x2), side):
            b.set(x, 1, z1 + 1, it)
            if it.startswith("barrel"):
                b.set(x, 2, z1 + 1, "lantern[hanging=false]")
        table(b, p, x1 + 2, 1, zb - 1, top="lantern[hanging=false]")
        bed(b, x1 + 1, 1, z2 - 1, "south", p.bed)
        b.set(x1 + 3, 1, z2 - 1, "lantern[hanging=false]")
    steep = rng.random() < 0.6
    g = p.fill
    t = Build("roof")
    main = dict(x1=x1, z1=z1, x2=x2, z2=zb, y=top, gable=g, ridge="x")
    wing = dict(x1=x1, z1=z1, x2=wx2, z2=z2, y=top, gable=g, ridge="z")
    if steep:
        steep_roofs(t, dict(main, mat=p.roofm), dict(wing, mat=p.roofm))
    else:
        roofs(t, dict(main, stair=p.rst), dict(wing, stair=p.rst))
    put(b, t, False, g)
    window(b, x1 + 2, top + 1, z2, "x", 1, 2)
    if rng.random() < 0.7:
        zc = (z1 + zb) // 2
        chimney(b, x2 + 1, zc, 0, top_at(b, x2 + 1, zc) + 2, p.stone[0])
    front_dress(b, p, rng, dx, zb, wins, top, W, D)
    for x in range(wx2 + 1, x2 + 1):  # the notch: a little paved court with a bench or barrels
        for z in range(zb + 1, z2 + 1):
            if b.get(x, -1, z) == "grass_block":
                b.set(x, -1, z, "cobblestone" if (x + z) % 3 else "mossy_cobblestone")
    if free(b, x2, 0, z2) and free(b, x2, 1, z2):
        b.set(x2, 0, z2, rng.choice(["barrel[facing=up]", "hay_block[axis=y]", "composter[level=4]"]))
    apron(b, p, dx - 1, dx + 1, D - 1, D - 1, ("gravel", "cobblestone", "dirt_path"))


INN_NAMES = [("The Crown", "& Anchor"), ("The King's", "Rest"), ("The Golden", "Lantern"), ("The Blue", "Stag"),
             ("The Old", "Coach"), ("The Bell", "& Bridle"), ("The Royal", "Horseshoe"), ("The Gilded", "Mile")]


def inn(b, p, W, D, rng):
    wing = rng.random() < 0.5
    style = rng.choice(["x", "cross", "x", "hip"])
    z1, z2 = 1, D - 4
    mx1, mx2 = 1, (9 if wing else W - 2)
    if wing:  # a lower kitchen wing, set back, its gable to the road
        shell(b, p, mx2, z1 + 1, W - 2, z2, 4, every=3)
        windows(b, mx2, z1 + 1, W - 2, z2, [2], 3, sides="nse")
    shell(b, p, mx1, z1, mx2, z2, 8, every=4)
    dx = (mx1 + mx2) // 2
    wins = windows(b, mx1, z1, mx2, z2, [2, 5], 4, {(dx + i, z2) for i in (-1, 0, 1)},
                   sides="nsw" if wing else "nsew")
    b.fill(mx1 + 1, 4, z1 + 1, mx2 - 1, 4, z2 - 1, p.floor)
    door(b, dx, 1, z2, "south", p.wood)
    straight_stairs(b, mx1 + 2, 1, z1 + 1, "east", 4, f"{p.wood}_stairs")

    # tap room: kegs and a counter at the back, tables at the front
    for x in range(mx1 + 7, mx2):
        b.set(x, 1, z1 + 1, "barrel[facing=south]")
    if mx2 - mx1 >= 12:
        for x in range(mx1 + 8, mx2 - 1):
            b.set(x, 1, z1 + 3, f"{p.wood}_slab[type=top]" if x % 2 else "barrel[facing=up]")
    for x in range(mx1 + 2, mx2 - 1, 4):
        table(b, p, x, 1, z2 - 2)
        for cxx, f in ((x - 1, "west"), (x + 1, "east")):
            if cxx != dx:
                b.set(cxx, 1, z2 - 2, S(p.wood, f))
    for x in range(mx1 + 2, mx2, 4):
        if x != dx:
            hang(b, x, 3, z2 - 1)
    for x in range(mx1 + 4, mx2, 4):
        hang(b, x, 3, z1 + 3)
    # rooms upstairs
    for x in range(mx1 + 1, mx2, 3):
        bed(b, x, 5, z2 - 1, "south", rng.choice(["blue", "yellow", "white", p.bed]))
        if x + 1 < mx2:
            b.set(x + 1, 5, z2 - 1, "chest[facing=south]")
            b.set(x + 1, 5, z2 - 2, "lantern[hanging=false]")
    for x in range(mx1 + 8, mx2, 2):
        bed(b, x, 5, z1 + 1, "north", p.bed)
    for x in range(mx1 + 1, mx2):
        if free(b, x, 5, z1 + 3):
            b.set(x, 5, z1 + 3, "blue_carpet" if x % 2 else "yellow_carpet")
    b.set(mx1 + 1, 5, z1 + 1, "lantern[hanging=false]")

    if wing:  # kitchen through an opening in the shared wall
        b.fill(mx2, 1, (z1 + z2) // 2 + 1, mx2, 2, (z1 + z2) // 2 + 1, "air")
        b.set(W - 3, 1, z1 + 2, "smoker[facing=west,lit=true]")
        b.set(W - 3, 1, z1 + 3, "furnace[facing=west,lit=true]")
        b.set(W - 3, 1, z2 - 1, "barrel[facing=up]")
        b.set(W - 3, 2, z2 - 1, "lantern[hanging=false]")
        b.set(mx2 + 1, 1, z1 + 2, "water_cauldron[level=3]")
        table(b, p, mx2 + 2, 1, z1 + 4, top="lantern[hanging=false]")

    cross = (dx - 2, dx + 2)
    steep = style != "hip" and rng.random() < 0.5
    r = roof(b, p, style, mx1, z1, mx2, z2, 8, cross=cross, steep=steep)
    gable_windows(b, style, mx1, z1, mx2, z2, 8, cross)
    if style == "x" and not steep:
        for a in range(mx1 + 2, mx2 - 1, 4):
            dormer_on(b, r, a, "back", p.fill)
    if wing:
        roof(b, p, "z", mx2, z1 + 1, W - 2, z2, 4, keep=True, steep=steep)
        gable_windows(b, "z", mx2, z1 + 1, W - 2, z2, 4)
        chimney(b, W - 3, z1 + 2, 1, top_at(b, W - 3, z1 + 2) + 2, p.stone[0])
    zc = (z1 + z2) // 2
    chimney(b, mx1 - 1, zc, 0, top_at(b, mx1 - 1, zc) + 2, p.stone[0])

    # the veranda: a deck, a slab roof on posts, benches, lanterns
    vz, sz = z2 + 1, z2 + 2
    posts = sorted(set(range(mx1, mx2 + 1, 4)) | {mx2})
    for x in range(mx1, mx2 + 1):
        b.set(x, 0, vz, p.floor)
        b.set(x, 4, vz, f"{p.wood}_slab[type=bottom]")
        b.set(x, 4, sz, f"{p.wood}_slab[type=bottom]")
        if x in posts:
            b.fill(x, 0, sz, x, 3, sz, f"{p.post}[axis=y]")
        else:
            b.set(x, 0, sz, S(p.wood, "north"))
    for a, c in zip(posts, posts[1:]):
        hang(b, (a + c) // 2, 3, sz)
    for (x, z, side) in wins:
        if side == "s" and abs(x - dx) > 1:
            b.set(x, 1, vz, S(p.wood, "north"))
    b.set(mx1, 1, vz, "barrel[facing=up]")
    b.set(mx2, 1, vz, "barrel[facing=up]")
    first, second = rng.choice(INN_NAMES)
    b.sign(dx, 3, vz, f"{p.wood}_hanging_sign[attached=false,rotation=0]", ["~ Inn ~", first, second, "Rooms & Ale"])
    for i, x in enumerate(posts[1:-1]):
        banner(b, x, 7, vz, ("blue", "yellow")[i % 2])
    b.set(dx, -1, D - 1, "dirt_path")
    apron(b, p, 0, W - 1, D - 1, D - 1, ("cobblestone", "stone_bricks", "cobblestone", "andesite"))
    lamp_post(b, p, 0, D - 1, 3)
    lamp_post(b, p, W - 1, D - 1, 3)
    # a horse trough and a hitching rail on the apron
    b.set(mx1 + 1, 0, D - 1, "water_cauldron[level=3]")
    b.set(mx1 + 2, 0, D - 1, "water_cauldron[level=3]")
    fence_line(b, p, [(x, D - 1) for x in range(dx + 2, min(dx + 5, W - 1))], 0)
    if wing:  # stable yard in front of the wing: hay and a cart
        b.set(W - 2, 0, D - 3, "hay_block[axis=y]")
        b.set(W - 2, 1, D - 3, "hay_block[axis=x]")
        cart(b, p, mx2 + 1, D - 2)


SMITH_NAMES = [("Royal Forge", "Smith & Farrier"), ("The Anvil", "Horseshoes"), ("Ironwright", "& Wheelwright"),
               ("Kingsway Forge", "Shoeing Done")]


def smithy(b, p, W, D, rng):
    """All stone and soot-dark: the smith's tall house, a forge open to the road under a lean-to (or one
    big roof), a 2x2 forge chimney, an anvil yard with a trough and an ore cart."""
    x1, z1, x2, z2 = 1, 1, W - 2, D - 3
    rx = x1 + 4  # the house part x1..rx, the forge rx..x2
    lean = rng.random() < 0.6
    rt = 7 if lean else 4
    shell(b, p, x1, z1, rx, z2, rt, stone_to=rt - 1, every=4)
    dx = x1 + 2
    windows(b, x1, z1, rx, z2, [2, 5] if lean else [2], 4, {(dx + i, z2) for i in (-1, 0, 1)}, sides="nsw")
    door(b, dx, 1, z2, "south", p.wood)
    b.set(dx, 0, z2 + 1, "stone_brick_stairs[facing=north,half=bottom,shape=straight]")
    path(b, [(dx, z) for z in range(z2 + 1, D)])
    # the forge floor and walls
    for x in range(rx + 1, x2 + 1):
        for z in range(z1, z2 + 1):
            b.set(x, 0, z, p.st(x, 0, z))
    h = (lambda x: rt + rx + 1 - x) if lean else (lambda x: 4)
    for x in range(rx + 1, x2 + 1):
        for y in range(1, h(x)):
            b.set(x, y, z1, p.st(x, y, z1))
    for z in range(z1, z1 + 3):
        for y in (1, 2, 3):
            b.set(x2, y, z, p.st(x2, y, z))
    b.fill(x2, 1, z2, x2, 3, z2, f"{p.post}[axis=y]")
    if lean:  # the lean-to: stairs falling from the house wall to the road side
        for x in range(rx + 1, x2 + 2):
            for z in range(z1 - 1, z2 + 2):
                b.set(x, h(x), z, S(p.roofm, "west"))
        style = rng.choice(["z", "x", "z"])
        roof(b, p, style, x1, z1, rx, z2, rt, keep=True, steep=rng.random() < 0.6)
        gable_windows(b, style, x1, z1, rx, z2, rt)
        # a loft up a ladder: the smith sleeps over the shop
        b.fill(x1 + 1, 4, z1 + 1, rx - 1, 4, z2 - 1, p.floor)
        for y in range(1, 5):
            b.set(x1 + 1, y, z1 + 1, "ladder[facing=south]")
        bed(b, rx - 1, 5, z1 + 1, "north", p.bed)
        b.set(x1 + 1, 5, z2 - 1, "lantern[hanging=false]")
        b.set(rx - 1, 5, z2 - 1, "chest[facing=north]")
        hang(b, x1 + 2, 3, z2 - 1)
        hang(b, rx + 2, h(rx + 2) - 1, z2)
    else:
        for x in range(rx + 1, x2 + 1):
            b.set(x, 4, z1, f"{p.beam}[axis=x]")
            b.set(x, 4, z2, f"{p.beam}[axis=x]")
        for z in range(z1, z2 + 1):
            b.set(x2, 4, z, f"{p.beam}[axis=z]")
        style = rng.choice(["x", "z", "hip"])
        roof(b, p, style, x1, z1, x2, z2, 4, steep=style != "hip" and rng.random() < 0.6)
        gable_windows(b, style, x1, z1, x2, z2, 4)
        bed(b, x1 + 1, 1, z1 + 1, "north", p.bed)
        hang(b, rx + 2, 3, z2)
    b.set(rx - 1, 1, z1 + 1, "chest[facing=south]")
    b.set(rx - 1, 1, z1 + 2, "barrel[facing=up]")
    b.set(rx - 1, 2, z1 + 2, "lantern[hanging=false]")
    b.set(rx - 1, 1, z1 + 3, "furnace[facing=west,lit=true]")
    # the hearth: a 2x2 stone chimney well above the roofs, lava before it, the smith's tools around
    fx = rx + 1
    b.set(fx, 1, z1 + 1, "smithing_table")
    b.set(fx + 1, 1, z1 + 1, "blast_furnace[facing=south,lit=true]")
    b.set(x2 - 1, 1, z1 + 2, "lava_cauldron")
    b.set(fx + 1, 1, z1 + 3, "anvil[facing=east]")
    b.set(fx, 1, z2 - 1, "grindstone[face=floor,facing=east]")
    b.set(x2 - 1, 1, z2 - 1, "water_cauldron[level=3]")
    peak = max(top_at(b, x, z) for x in range(x1, x2 + 1) for z in (z1, (z1 + z2) // 2))
    chimney(b, x2 - 1, z1, 1, peak + 2, "stone_bricks" if p.stone[0] == "cobblestone" else "cobblestone", width=2)
    # the anvil yard on the apron
    name, sub = rng.choice(SMITH_NAMES)
    b.sign(dx + 1, 2, z2 + 1, f"{p.wood}_wall_sign[facing=south]", ["", name, sub, ""])
    apron(b, p, 0, W - 1, z2 + 1, D - 1, ("cobblestone", "gravel", "coarse_dirt", "cobblestone"))
    b.set(x1, 0, z2 + 1, "barrel[facing=up]")
    b.set(x2 - 1, 0, D - 1, "anvil[facing=east]")
    b.set(x2, 0, D - 1, "water_cauldron[level=3]")
    cart(b, p, rx + 1, D - 1, along="x", load=("iron_ore", "coal_ore"))
    lamp_post(b, p, 0, D - 1)
    if free(b, W - 1, 0, z1):
        for z in (z1, z1 + 1):  # charcoal wood under the eave
            b.set(W - 1, 0, z, "dark_oak_log[axis=z]")


def stable(b, p, W, D, rng):
    """A plank barn with an open-fronted lean-to of stalls along the road side, a fenced paddock with a
    gate, hay and a trough, horses, a signboard."""
    x1, z1, x2 = 1, 1, W - 2
    zb, z2 = z1 + 3, D - 3  # barn z1..zb, lean-to zb+1..z2
    bt = 6
    plank = f"{p.wood}_planks"
    shell(b, p, x1, z1, x2, zb, bt, stone_to=1, every=3, fill=plank, beam_low=False)
    windows(b, x1, z1, x2, zb, [2], 3, sides="nwe")
    dx = x1 + 1
    door(b, dx, 1, zb, "south", p.wood)
    # barn: tack corner and a hay store
    b.set(x1 + 1, 1, z1 + 1, "chest[facing=south]")
    b.set(x1 + 2, 1, z1 + 1, "barrel[facing=up]")
    b.set(x1 + 2, 2, z1 + 1, "lantern[hanging=false]")
    for x in range(x1 + 4, x2):
        b.set(x, 1, z1 + 1, "hay_block[axis=y]")
    lx = (x1 + 4 + x2) // 2
    b.set(lx, 2, z1 + 1, "lantern[hanging=false]")
    b.set(x2 - 1, 2, z1 + 1, "hay_block[axis=x]")
    style = rng.choice(["x", "x", "hip"])
    roof(b, p, style, x1, z1, x2, zb, bt, steep=style == "x" and rng.random() < 0.6)
    if style == "x":  # a hay door high in the gable
        for z in range(z1 + 1, zb):
            if b.get(x2, bt + 1, z) == p.fill:
                b.set(x2, bt + 1, z, "air")
    # the lean-to of stalls
    hl = lambda z: bt - (z - zb)  # noqa: E731
    for x in range(x1 - 1, x2 + 2):
        for z in range(zb + 1, z2 + 2):
            b.set(x, hl(z), z, S(p.roofm, "north"))
    for x in range(x1, x2 + 1):
        for z in range(zb + 1, z2 + 1):
            b.set(x, 0, z, p.st(x, 0, z) if x < x1 + 3 else ("coarse_dirt" if (x + z) % 3 else "packed_mud"))
    parts = list(range(x1 + 3, x2, 3)) + [x2]
    for x in [x1] + parts:
        b.fill(x, 1, z2, x, hl(z2) - 1, z2, f"{p.post}[axis=y]")
        if x != x1:
            fence_line(b, p, [(x, z) for z in range(zb + 1, z2)], 1)
    for a, c in zip(parts, parts[1:]):
        b.set(a + 1, 1, zb + 1, "hay_block[axis=y]")
        if c - a > 2:
            b.set(c - 1, 1, zb + 1, "water_cauldron[level=3]")
        hang(b, (a + c + 1) // 2, hl(z2) - 1, z2)
    hang(b, x1 + 1, hl(z2) - 1, z2)
    b.set(dx, 0, z2, "stone_brick_stairs[facing=north,half=bottom,shape=straight]")
    # the paddock: fence with a gate, hay, a trough, horses
    px1 = x1 + 3
    fence = [(px1, z) for z in range(z2 + 1, D)] + [(x, D - 1) for x in range(px1 + 1, W)] + \
            [(W - 1, z) for z in range(z2 + 1, D - 1)]
    fence_line(b, p, fence, 0)
    gx = (px1 + W - 1) // 2
    b.set(gx, 0, D - 1, f"{p.wood}_fence_gate[facing=south,in_wall=false,open=false,powered=false]")
    b.set(px1 + 1, 0, z2 + 1, "hay_block[axis=y]")
    b.set(px1 + 1, 1, z2 + 1, "hay_block[axis=x]")
    b.set(W - 2, 0, z2 + 1, "water_cauldron[level=3]")
    b.set(W - 3, 0, z2 + 1, "water_cauldron[level=3]")
    for x in range(px1 + 1, W - 1):
        for z in range(z2 + 1, D - 1):
            b.set(x, -1, z, "coarse_dirt" if (x * 7 + z) % 4 else "podzol")
    b.entity(px1 + 3, 0, D - 2, "horse")
    if rng.random() < 0.6:
        b.entity(W - 3, 0, D - 2, "horse")
    # the way in, a signboard and a lamp
    apron(b, p, x1 - 1, px1 - 1, z2 + 1, D - 1, ("gravel", "dirt_path", "cobblestone"))
    b.sign(x1 + 2, 0, D - 1, f"{p.wood}_sign[rotation=0]", ["Royal", "Stables", "Post Horses", "& Livery"])
    lamp_post(b, p, 0, D - 1)
    if free(b, W - 1, 0, z1):
        b.set(W - 1, 0, z1, "hay_block[axis=y]")
        b.set(W - 1, 1, z1, "hay_block[axis=z]")
        b.set(W - 1, 0, z1 + 1, "hay_block[axis=x]")


def shrine(b, p, W, D, rng):
    """A wayside chapel on a stone terrace: a green copper roof, blue and gold glass, a bell (in a cote on
    the gable, or a round chapel with a gilded cone), an arch at the door, candles on the altar."""
    cx = W // 2
    round_ = rng.random() < 0.45
    for x in range(W):
        for z in range(D):
            b.set(x, 0, z, p.band if (x + z) % 5 else "chiseled_stone_bricks")
    for x in range(cx - 1, cx + 2):
        b.set(x, 0, D - 1, "stone_brick_stairs[facing=north,half=bottom,shape=straight]")
    if round_:
        r, cz = 2, D - 4
        for y in range(1, 5):
            for x in range(cx - r, cx + r + 1):
                for z in range(cz - r, cz + r + 1):
                    d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
                    if r - 0.5 <= d < r + 0.5:
                        b.set(x, y, z, p.band if y == 4 else p.st(x, y, z))
        zf = cz + r  # the front wall
        window(b, cx - r, 2, cz, "z", 1, 2, "yellow_stained_glass_pane")
        window(b, cx + r, 2, cz, "z", 1, 2, "yellow_stained_glass_pane")
        window(b, cx, 2, cz - r, "x", 1, 2, "blue_stained_glass_pane")
        cone = Build("cone")
        cone_roof(cone, cx, cz, 4, r, p.rst)
        put(b, cone)
        ridge = top_at(b, cx, cz)
        b.set(cx, ridge, cz, "gold_block")
        b.set(cx, ridge + 1, cz, "lantern[hanging=false]")
        b.set(cx, 1, zf + 1, "air")
        alt_z = cz - 1
        lo, hi = cx - 1, cx + 1
        carpet_z = range(cz, zf)
    else:
        x1, z1, x2, z2 = 1, 1, W - 2, D - 3
        zf = z2
        shell(b, p, x1, z1, x2, z2, 4, stone_to=4, every=4, beam_low=False, floor=p.band)
        windows(b, x1, z1, x2, z2, [2], 4, sides="we", pane="yellow_stained_glass_pane")
        windows(b, x1, z1, x2, z2, [2], 4, sides="n", pane="blue_stained_glass_pane")
        roof(b, p, "z", x1, z1, x2, z2, 4, gable=p.band, steep=rng.random() < 0.7)
        window(b, cx, 5, z2, "x", 1, 1, "blue_stained_glass_pane")
        # a bell cote on the front gable
        hgt = top_at(b, cx, z2) + 1
        for xx in (cx - 1, cx + 1):
            b.fill(xx, top_at(b, xx, z2) + 1, z2, xx, hgt + 1, z2, "stone_bricks")
        b.fill(cx - 1, hgt + 2, z2, cx + 1, hgt + 2, z2, "stone_bricks")
        b.set(cx, hgt + 3, z2, "gold_block")
        b.set(cx, hgt + 1, z2, "bell[attachment=ceiling,facing=east]")
        # an arch before the door
        for xx in (cx - 1, cx + 1):
            b.fill(xx, 1, zf + 1, xx, 2, zf + 1, "stone_brick_wall")
            b.set(xx, 3, zf + 1, "chiseled_stone_bricks")
        b.set(cx, 3, zf + 1, "stone_brick_stairs[facing=north,half=top,shape=straight]")
        banner(b, x1, 3, zf + 1, "blue")
        banner(b, x2, 3, zf + 1, "yellow")
        alt_z = z1 + 1
        lo, hi = x1 + 1, x2 - 1
        carpet_z = range(z1 + 2, z2)
    door(b, cx, 1, zf, "south", p.wood)
    if zf + 1 < D - 1:
        b.set(cx, 0, zf + 1, "stone_brick_stairs[facing=north,half=bottom,shape=straight]")
    # the altar: candles, flowers, a blue and gold runner
    b.set(cx, 1, alt_z, "chiseled_stone_bricks")
    b.set(cx, 2, alt_z, f"{rng.choice(['white', 'yellow', 'blue'])}_candle[candles=4,lit=true]")
    b.set(cx - 1, 1, alt_z, "potted_cornflower")
    b.set(cx + 1, 1, alt_z, "potted_dandelion")
    for z in carpet_z:
        for x in range(lo, hi + 1):
            if free(b, x, 1, z):
                b.set(x, 1, z, "blue_carpet" if x == cx else "yellow_carpet")
    if round_:
        banner(b, cx - 1, 3, zf + 1, "blue")
        banner(b, cx + 1, 3, zf + 1, "yellow")
    for x in (0, W - 1):  # lanterns on posts at the terrace corners, flowers in pots behind
        b.set(x, 1, D - 1, f"{p.wood}_fence[east=false,north=false,south=false,west=false]")
        b.set(x, 2, D - 1, "lantern[hanging=false]")
        b.set(x, 1, 0, rng.choice(["potted_red_tulip", "potted_cornflower", "potted_allium", "potted_azure_bluet"]))


def watchtower(b, p, W, D, rng):
    """A square or round stone shaft with a spiral stair, corbelled out at the top into a wide crenellated
    platform with a lit beacon brazier; some carry a roofed lookout, the beacon on its peak."""
    H = rng.randint(11, 17)
    round_ = rng.random() < 0.4
    roofed = rng.random() < 0.5
    x1, z1, x2, z2 = 1, 1, W - 2, D - 2
    cx, cz = (x1 + x2) // 2, (z1 + z2) // 2
    for x in range(W):
        for z in range(D):
            b.set(x, 0, z, p.st(x, 0, z) if not (x1 < x < x2 and z1 < z < z2) else p.band)

    def wall(x, z):
        if round_:
            d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
            return 1.5 <= d < 2.5
        return x in (x1, x2) or z in (z1, z2)
    for y in range(1, H):
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                if wall(x, z):
                    b.set(x, y, z, p.band if y % 4 == 0 else p.st(x, y, z))
    for y in range(1, H):
        b.set(cx, y, cz, "lantern[hanging=false]" if y % 4 == 3 else f"{p.post}[axis=y]")
    door(b, cx, 1, z2, "south", p.wood)
    b.set(cx, 0, z2 + 1, "stone_brick_stairs[facing=north,half=bottom,shape=straight]")
    for y in range(5, H - 2, 4):
        window(b, cx, y, z1, "x", 1, 2)
        window(b, x1, y, cz, "z", 1, 2)
        window(b, x2, y, cz, "z", 1, 2)
        window(b, cx, y, z2, "x", 1, 2)
    # the platform: corbelled out to the whole plot, then the stair up through it
    b.fill(0, H, 0, W - 1, H, D - 1, p.band)
    sx1, sz1, sx2, sz2 = x1 + 1, z1 + 1, x2 - 1, z2 - 1
    spiral_stairs(b, sx1, sz1, sx2, sz2, 1, H, f"{p.wood}_stairs", p.floor, start=7)
    rg = ([(x, sz1) for x in range(sx1, sx2)] + [(sx2, z) for z in range(sz1, sz2)] +
          [(x, sz2) for x in range(sx2, sx1, -1)] + [(sx1, z) for z in range(sz2, sz1, -1)])
    i = 7 + H - 1
    ax, az = rg[i % len(rg)]
    nx, nz = rg[(i + 1) % len(rg)]
    corners = {(sx1, sz1), (sx2, sz1), (sx2, sz2), (sx1, sz2)}
    if (ax, az) not in corners:
        f = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}[(nx - ax, nz - az)]
        b.set(ax, H, az, S(p.wood, f))
    else:
        b.set(ax, H, az, p.floor)
    b.set(cx, H, cz, p.band)
    for x, z in ring(0, 0, W - 1, D - 1):
        corner = x in (0, W - 1) and z in (0, D - 1)
        if corner:
            b.set(x, H - 1, z, p.band)
        else:
            f = "south" if z == 0 else "north" if z == D - 1 else "east" if x == 0 else "west"
            b.set(x, H - 1, z, f"stone_brick_stairs[facing={f},half=top,shape=straight]")
        if corner or (x + z) % 2 == 0:
            b.set(x, H + 1, z, p.st(x, H + 1, z))
        if corner:
            b.set(x, H + 2, z, "lantern[hanging=false]")
    for x in range(1, W - 1):  # the corbels' undersides read as machicolations
        for z in (1, D - 2):
            if not wall(x, z) and free(b, x, H - 1, z):
                b.set(x, H - 1, z, p.band)
    if roofed:  # a roofed lookout on the platform, the beacon on its peak, the alarm bell inside
        for (x, z) in [(x1, z1), (x1, z2), (x2, z1), (x2, z2)]:
            b.fill(x, H + 1, z, x, H + 3, z, f"{p.post}[axis=y]")
        for (x, z) in ring(x1, z1, x2, z2):
            if not (x in (x1, x2) and z in (z1, z2)):
                b.set(x, H + 3, z, f"{p.beam}[axis={'x' if z in (z1, z2) else 'z'}]")
        hang(b, cx, H + 2, z1)
        hang(b, cx, H + 2, z2)
        b.set(cx, H + 1, cz, "bell[attachment=floor,facing=south]")
        hip_roof(b, x1, z1, x2, z2, H + 3, p.rst)
        peak = top_at(b, cx, cz)
        b.set(cx, peak, cz, "chiseled_stone_bricks")
        b.set(cx, peak + 1, cz, "campfire[lit=true,signal_fire=true,facing=north,waterlogged=false]")
    else:  # an open platform: a beacon brazier in the middle, a bell, the crown's flag
        b.set(cx, H + 1, cz, "chiseled_stone_bricks")
        b.set(cx, H + 2, cz, "campfire[lit=true,signal_fire=true,facing=north,waterlogged=false]")
        b.set(cx, H + 1, z2, "bell[attachment=floor,facing=south]")
        b.fill(x1, H + 1, z1, x1, H + 4, z1, f"{p.wood}_fence[east=false,north=false,south=false,west=false]")
        b.set(x1, H + 4, z1, f"{p.wood}_fence[east=true,north=false,south=false,west=false]")
        b.set(x1, H + 3, z1, f"{p.wood}_fence[east=true,north=false,south=false,west=false]")
        for i2, x in enumerate(range(x1 + 1, x1 + 4)):
            for y in (H + 3, H + 4):
                b.set(x, y, z1, "yellow_wool" if i2 == 1 else "blue_wool")
    banner(b, cx - 1, 3, z2 + 1, "blue")
    banner(b, cx + 1, 3, z2 + 1, "yellow")
    b.set(0, 1, D - 1, "lantern[hanging=false]")
    b.set(W - 1, 1, D - 1, "lantern[hanging=false]")
    b.set(0, 1, 0, "hay_block[axis=y]")
    b.set(W - 1, 1, 0, "barrel[facing=up]")
    if rng.random() < 0.5:  # a guard's bench by the door
        b.set(cx + 2, 1, D - 1, "spruce_stairs[facing=north,half=bottom,shape=straight]")


MAKERS = {"house": house, "inn": inn, "smithy": smithy, "stable": stable, "shrine": shrine, "watchtower": watchtower}


# ---------------------------------------------------------------- mirror, turn, build

def _flip(blk):
    if "[" not in blk:
        return blk
    n, rest = blk.split("[", 1)
    props = dict(kv.split("=", 1) for kv in rest.rstrip("]").split(","))
    sw = {"east": "west", "west": "east"}
    if props.get("facing") in sw:
        props["facing"] = sw[props["facing"]]
    if "shape" in props:
        props["shape"] = props["shape"].replace("left", "L").replace("right", "left").replace("L", "right")
    if "hinge" in props:
        props["hinge"] = "right" if props["hinge"] == "left" else "left"
    if "east" in props and "west" in props:
        props["east"], props["west"] = props["west"], props["east"]
    if "rotation" in props:
        props["rotation"] = str((16 - int(props["rotation"])) % 16)
    return n + "[" + ",".join(f"{k}={v}" for k, v in props.items()) + "]"


def _spin(blk, t):
    """Standing and hanging signs carry rotation=0..15, which stamp() doesn't turn: a quarter turn is +4."""
    if "rotation=" not in blk or not t:
        return blk
    n, rest = blk.split("[", 1)
    props = dict(kv.split("=", 1) for kv in rest.rstrip("]").split(","))
    props["rotation"] = str((int(props["rotation"]) + 4 * t) % 16)
    return n + "[" + ",".join(f"{k}={v}" for k, v in props.items()) + "]"


def mirrored(c, W):
    m = Build(c.name)
    for (x, y, z), v in c.blocks.items():
        m.blocks[(W - 1 - x, y, z)] = _flip(v)
    m.signs = [(W - 1 - x, y, z, lines, side) for (x, y, z, lines, side) in c.signs]
    m.entities = [(W - 1 - x, y, z, k) for (x, y, z, k) in c.entities]
    return m


def build(w=10, d=9, door="south", kind="house", seed=0):
    rng = random.Random(seed)
    t = TURNS[door]
    W, D = (w, d) if t % 2 == 0 else (d, w)
    p = Pal(rng, kind)
    global PLOT
    PLOT = (W, D)
    c = Build("canon")
    ground(c, W, D)
    MAKERS[kind](c, p, W, D, rng)
    if kind != "watchtower" and rng.random() < 0.5:
        c = mirrored(c, W)
    out = Build(f"kingsway {kind}")
    ox, oz = {0: (0, 0), 1: (D - 1, 0), 2: (W - 1, D - 1), 3: (0, W - 1)}[t]
    stamp(out, c, ox, 0, oz, t)
    for k, v in out.blocks.items():
        out.blocks[k] = _spin(v, t)

    def turn(x, z):
        for _ in range(t):
            x, z = -z, x
        return x + ox, z + oz
    for (x, y, z, lines, side) in c.signs:
        x, z = turn(x, z)
        out.signs.append((x, y, z, lines, side))
    for (x, y, z, k) in c.entities:
        x, z = turn(x, z)
        out.entity(x, y, z, k)
    return out
