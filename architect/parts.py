"""Building parts: the vocabulary plans are written in. Each part writes into a Build in local coords.

Facing words are Minecraft's: north = -z, south = +z, west = -x, east = +x.
"""

OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def hip_roof(b, x1, z1, x2, z2, y, stair, top=None, overhang=1):
    """A roof sloping on all four sides (towers, pavilions): rings of stairs stepping in and up until it
    closes, capped with `top` (default: the stair's slab). Lakeside's church tower roof was 30 hand lines."""
    x1, z1, x2, z2 = x1 - overhang, z1 - overhang, x2 + overhang, z2 + overhang
    level = 0
    while x1 + level <= x2 - level and z1 + level <= z2 - level:
        a1, a2, c1, c2 = x1 + level, x2 - level, z1 + level, z2 - level
        if a1 == a2 or c1 == c2:
            b.fill(a1, y + level, c1, a2, y + level, c2, top or stair.replace("_stairs", "_slab") + "[type=bottom]")
            break
        for x in range(a1, a2 + 1):
            b.set(x, y + level, c1, f"{stair}[facing=south,half=bottom,shape=straight]")
            b.set(x, y + level, c2, f"{stair}[facing=north,half=bottom,shape=straight]")
        for z in range(c1 + 1, c2):
            b.set(a1, y + level, z, f"{stair}[facing=east,half=bottom,shape=straight]")
            b.set(a2, y + level, z, f"{stair}[facing=west,half=bottom,shape=straight]")
        for x, z, shape in ((a1, c1, "outer_left"), (a2, c1, "outer_right"), (a1, c2, "outer_right"), (a2, c2, "outer_left")):
            facing = "south" if z == c1 else "north"
            b.set(x, y + level, z, f"{stair}[facing={facing},half=bottom,shape={shape}]")
        level += 1


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


def gable_roof(b, x1, z1, x2, z2, y, stair, gable, ridge="x", overhang=1, slab=None, end_overhang=None):
    """A pitched roof over the box x1..x2, z1..z2 starting at height y. Slopes rise toward the ridge,
    which runs along `ridge`; the triangular gable ends are filled with `gable`. `overhang` is at the
    eaves; `end_overhang` (default the same) past the gable ends: 0 keeps a tight plot's ends flush."""
    end_overhang = overhang if end_overhang is None else end_overhang
    if ridge == "x":
        lo, hi, a1, a2 = z1, z2, x1 - end_overhang, x2 + end_overhang
        put = lambda a, c, yy, blk: b.set(a, yy, c, blk)  # noqa: E731
        up_lo, up_hi = "south", "north"  # stairs on the low-z slope rise toward +z (south)
    else:
        lo, hi, a1, a2 = x1, x2, z1 - end_overhang, z2 + end_overhang
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
            for a in (a1 + end_overhang, a2 - end_overhang):
                put(a, c, yy, gable)
        level += 1
    if lo_o + level == hi_o - level:  # odd span: a ridge row of slabs
        for a in range(a1, a2 + 1):
            put(a, lo_o + level, y + level, slab or f"{stair.replace('_stairs', '_slab')}[type=bottom]")


def light(b, x, y, z, block="lantern[hanging=false]"):
    b.set(x, y, z, block)


FACE_STEP = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def timber_frame(b, x1, z1, x2, z2, y1, y2, fill, post="oak_log[axis=y]", beam="oak_log", every=4):
    """Framed walls: `fill` panels between posts (corners and every `every` blocks) with horizontal beam
    bands at the bottom (y1) and top (y2). Gives walls depth without hand-written loops."""
    walls(b, x1, z1, x2, z2, y1, y2, fill)
    for x in list(range(x1, x2 + 1, every)) + [x2]:
        b.fill(x, y1, z1, x, y2, z1, post)
        b.fill(x, y1, z2, x, y2, z2, post)
    for z in list(range(z1, z2 + 1, every)) + [z2]:
        b.fill(x1, y1, z, x1, y2, z, post)
        b.fill(x2, y1, z, x2, y2, z, post)
    beam = beam.split("[")[0]  # the axis is set per side (r2: "dark_oak_log[axis=x]" became [axis=x][axis=x])
    for y in (y1, y2):
        for x in range(x1 + 1, x2):
            b.set(x, y, z1, f"{beam}[axis=x]")
            b.set(x, y, z2, f"{beam}[axis=x]")
        for z in range(z1 + 1, z2):
            b.set(x1, y, z, f"{beam}[axis=z]")
            b.set(x2, y, z, f"{beam}[axis=z]")


def straight_stairs(b, x, y, z, direction, steps, stair, width=1, support=None, headroom=3):
    """A flight going up toward `direction` from (x, y, z): one block up per step. Clears `headroom`
    blocks above every step, which also cuts the stairwell hole in the floor above. `support` fills
    under each step (else the flight hangs from its ends). Returns the landing cell at the top."""
    dx, dz = FACE_STEP[direction]
    sx, sz = (abs(dz), abs(dx))  # sideways, for width
    for i in range(steps):
        for w in range(width):
            cx, cz = x + dx * i + sx * w, z + dz * i + sz * w
            b.set(cx, y + i, cz, f"{stair}[facing={direction},half=bottom,shape=straight]")
            for h in range(1, headroom + 1):
                b.set(cx, y + i + h, cz, "air")
            if support:
                for yy in range(y, y + i):
                    b.set(cx, yy, cz, support)
    return x + dx * steps, y + steps, z + dz * steps


def spiral_stairs(b, x1, z1, x2, z2, y1, y2, stair, landing, headroom=3, support=None, start=0):
    """Stairs climbing around the inside of the rectangle x1..x2, z1..z2 (the shaft, inside the walls)
    from y1 to y2, one block up per step, with a full `landing` block at each corner. Clears headroom.
    `support` (default: the landing block) fills under the first lap, which would otherwise float (r2).
    `start` skips that many ring cells before the first step, leaving them open at floor level, e.g. in
    front of a ground-floor door (lakeside: the church and lighthouse both hand-cleared one).
    For towers: the middle of the rectangle stays free (a column, or open)."""
    support = support or landing
    ring = ([(x, z1) for x in range(x1, x2)] + [(x2, z) for z in range(z1, z2)] +
            [(x, z2) for x in range(x2, x1, -1)] + [(x1, z) for z in range(z2, z1, -1)])
    corners = {(x1, z1), (x2, z1), (x2, z2), (x1, z2)}
    y, i = y1, start
    while y < y2:
        cx, cz = ring[i % len(ring)]
        nx, nz = ring[(i + 1) % len(ring)]
        facing = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}[(nx - cx, nz - cz)]
        if (cx, cz) in corners:
            b.set(cx, y, cz, landing)
        else:
            b.set(cx, y, cz, f"{stair}[facing={facing},half=bottom,shape=straight]")
        for h in range(1, headroom + 1):
            b.set(cx, y + h, cz, "air")
        if i < len(ring):  # first lap only: the open start cells stay open
            for yy in range(y1, y):
                b.set(cx, yy, cz, support)
        y, i = y + 1, i + 1


def posts(b, points, y_top, y_bottom, block="spruce_log[axis=y]"):
    """Columns from y_top down to y_bottom (inclusive) at each (x, z): stilts, piers, dock posts.
    Over water, use place --foundation none and reach y_bottom below the waterline."""
    for x, z in points:
        b.fill(x, y_bottom, z, x, y_top, z, block)


ROT = {"north": "east", "east": "south", "south": "west", "west": "north"}


def _turn(block, k):
    """Rotate the facing/axis/connections in a block-data string by k quarter turns clockwise."""
    if "[" not in block or k % 4 == 0:
        return block
    name, rest = block.split("[", 1)
    props = dict(p.split("=", 1) for p in rest.rstrip("]").split(","))
    for _ in range(k % 4):
        if props.get("facing") in ROT:
            props["facing"] = ROT[props["facing"]]
        if props.get("axis") in ("x", "z"):
            props["axis"] = "z" if props["axis"] == "x" else "x"
        sides = {s: props[s] for s in ROT if s in props}
        for s, v in sides.items():
            props[ROT[s]] = v
    return name + "[" + ",".join(f"{k}={v}" for k, v in props.items()) + "]"


def stamp(b, piece, x, y, z, turns=0):
    """Copy another Build into b at (x, y, z), turned `turns` quarter turns clockwise (seen from above)
    around its own origin, with facings, axes and connections turned too. For repeated pieces: stalls
    round a square, houses along a street, towers at corners."""
    for (px, py, pz), blk in piece.blocks.items():
        for _ in range(turns % 4):
            px, pz = -pz, px
        b.set(x + px, y + py, z + pz, _turn(blk, turns))


def dormer(b, x, y, z, facing, roof_stair, wall, width=3, pane="glass_pane"):
    """A gabled dormer sticking out of a roof slope that faces `facing`, with its front wall's centre at
    (x, y, z) (y = the window's bottom). A window in the front, a small pitched roof on top. Place it
    after the main roof so it cuts through: it clears the roof behind its window."""
    dx, dz = FACE_STEP[facing]
    sx, sz = abs(dz), abs(dx)  # along the front
    half = width // 2
    for i in range(-half, half + 1):
        for h in range(0, 3):
            for d in range(0, 3):  # front wall back into the roof
                cx, cz = x + sx * i - dx * d, z + sz * i - dz * d
                edge = abs(i) == half or d == 2
                b.set(cx, y + h, cz, wall if edge or h == 2 else "air")
    for h in (0, 1):
        b.set(x, y + h, z, f"{pane}[{'east=true,west=true' if sx else 'north=true,south=true'}]")
    for i in range(-half - 1, half + 2):  # the little roof, pitched along `facing`
        lvl = half + 1 - abs(i)
        for d in range(-1, 3):
            cx, cz = x + sx * i - dx * d, z + sz * i - dz * d
            side = ("west" if i < 0 else "east") if sx else ("north" if i < 0 else "south")
            up = OPPOSITE[side]
            b.set(cx, y + 2 + lvl, cz, f"{roof_stair}[facing={up},half=bottom,shape=straight]" if i else
                  roof_stair.replace("_stairs", "_slab") + "[type=bottom]")
