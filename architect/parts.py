"""Building parts: the vocabulary plans are written in. Each part writes into a Build in local coords.

Facing words are Minecraft's: north = -z, south = +z, west = -x, east = +x.
"""

OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def floor(b, x1, z1, x2, z2, y, block):
    b.fill(x1, y, z1, x2, y, z2, block)


def walls(b, x1, z1, x2, z2, y1, y2, block, corner=None):
    """A hollow rectangle of walls; `corner` (e.g. a log) for the four corner posts."""
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            b.set(x, y, z1, block)
            b.set(x, y, z2, block)
        for z in range(z1, z2 + 1):
            b.set(x1, y, z, block)
            b.set(x2, y, z, block)
        if corner:
            for x, z in ((x1, z1), (x1, z2), (x2, z1), (x2, z2)):
                b.set(x, y, z, corner)


def clear_inside(b, x1, z1, x2, z2, y1, y2):
    """Air inside the walls, so the interior is hollow even where the hill was."""
    b.fill(x1 + 1, y1, z1 + 1, x2 - 1, y2, z2 - 1, "air")


def window(b, x, y, z, along, width=1, height=1, pane="glass_pane"):
    """Glass panes in a wall running along "x" or "z", with their connections set explicitly."""
    sides = ("east", "west") if along == "x" else ("north", "south")
    for i in range(width):
        for j in range(height):
            px, pz = (x + i, z) if along == "x" else (x, z + i)
            conn = {s: "false" for s in ("north", "south", "east", "west")}
            if i > 0:
                conn[sides[1]] = "true"
            if i < width - 1:
                conn[sides[0]] = "true"
            if width == 1:
                conn[sides[0]] = conn[sides[1]] = "true"
            state = ",".join(f"{k}={v}" for k, v in sorted(conn.items()))
            b.set(px, y + j, pz, f"{pane}[{state}]")


def door(b, x, y, z, facing, wood="oak"):
    """A two-block door; `facing` is the direction you face when walking out through it."""
    b.set(x, y, z, f"{wood}_door[facing={facing},half=lower,hinge=left,open=false]")
    b.set(x, y + 1, z, f"{wood}_door[facing={facing},half=upper,hinge=left,open=false]")


def gable_roof(b, x1, z1, x2, z2, y, stair, gable, ridge="x", overhang=1, slab=None):
    """A pitched roof over the box x1..x2, z1..z2 starting at height y. Slopes rise toward the ridge,
    which runs along `ridge`; the triangular gable ends are filled with `gable`."""
    if ridge == "x":
        lo, hi, a1, a2 = z1, z2, x1 - overhang, x2 + overhang
        put = lambda a, c, yy, blk: b.set(a, yy, c, blk)  # noqa: E731
        up_lo, up_hi = "south", "north"  # stairs on the low-z slope rise toward +z (south)
    else:
        lo, hi, a1, a2 = x1, x2, z1 - overhang, z2 + overhang
        put = lambda a, c, yy, blk: b.set(c, yy, a, blk)  # noqa: E731
        up_lo, up_hi = "east", "west"
    lo_o, hi_o = lo - overhang, hi + overhang
    level = 0
    while lo_o + level < hi_o - level:
        yy = y + level
        for a in range(a1, a2 + 1):
            put(a, lo_o + level, yy, f"{stair}[facing={up_lo},half=bottom,shape=straight]")
            put(a, hi_o - level, yy, f"{stair}[facing={up_hi},half=bottom,shape=straight]")
        # gable triangle under this roof row, between the walls
        for c in range(max(lo, lo_o + level + 1), min(hi, hi_o - level - 1) + 1):
            for a in (a1 + overhang, a2 - overhang):
                put(a, c, yy, gable)
        level += 1
    if lo_o + level == hi_o - level:  # odd span: a ridge row of slabs
        for a in range(a1, a2 + 1):
            put(a, lo_o + level, y + level, slab or f"{stair.replace('_stairs', '_slab')}[type=bottom]")


def light(b, x, y, z, block="lantern[hanging=false]"):
    b.set(x, y, z, block)
