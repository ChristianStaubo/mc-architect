"""Lakeside castle: a princess's castle on the western summit (the town brief's "keep or temple on the
western ridge", district 1), seen from both lakes and the market.

Written in WORLD coordinates (the W helper converts): local (0,0,0) = world (OX, OY, OZ).
Blueprint: ./mc.py blueprint towns/lakeside/plans/castle.py --at 240,-290 --y 125 --no-clear --foundation none
Preview:   ./mc.py place towns/lakeside/plans/castle.py --at 240,-290 --y 125 --no-clear --foundation none --dry-run
The plan does its own earthwork (terraces, wall footings down to the rock, cut where the hill is high)
from the ground heights cached in castle_ground.json (bridge.heightmap, x 236..305, z -296..-222), so it is
placed with --no-clear --foundation none and nothing else is touched.

Layout (north up):
  - curtain wall on the summit plateau, x 248..288, z -282..-238, with seven towers (round and square)
    and a gatehouse in the south wall; the east wall runs on the cliff edge over the north lake
  - inner ward (y 125) with the keep against the north wall, a cherry garden south of it
  - outer bailey (y 121) with the well, stable and smithy; a grand stair up to the inner ward
  - east terraces stepping down to the cliff (y 125 / 121 / 117): an orchard and a herb garden
  - the keep: great hall, the princess's bedchamber, a library, a roof walk; the princess tower at its
    south-east corner with a bower room at the top (the tallest spire)
  - outside the gate a stair road on arches down toward the upper quarter (and the market road)
"""

import json
import os
import random
from pathlib import Path

from architect.build import Build
from architect.parts import hip_roof, spiral_stairs, window

OX, OY, OZ = 240, 125, -290

G = {}
for k, v in json.loads((Path(__file__).parent / "castle_ground.json").read_text()).items():
    x, z = map(int, k.split(","))
    G[(x, z)] = v[0]


def ground(x, z):
    if (x, z) in G:
        return G[(x, z)]
    cx, cz = min(max(x, 236), 305), min(max(z, -296), -222)
    return G[(cx, cz)]


def rnd(x, y, z, salt=0):
    return random.Random((x * 73856093) ^ (y * 19349663) ^ (z * 83492791) ^ salt).random()


def brick(x, y, z):
    r = rnd(x, y, z)
    return "mossy_stone_bricks" if r < 0.13 else "cracked_stone_bricks" if r < 0.22 else "stone_bricks"


def rubble(x, y, z):
    r = rnd(x, y, z, 3)
    return ("mossy_cobblestone" if r < 0.25 else "andesite" if r < 0.45 else "cobblestone" if r < 0.75
            else "tuff" if r < 0.85 else "stone")


def stair(facing, half="bottom", block="stone_brick_stairs", shape="straight"):
    return f"{block}[facing={facing},half={half},shape={shape}]"


ROOF = "deepslate_tile_stairs"


def cone_roof(b, cx, cz, y, radius, stair_, top=None, pitch=2):
    """A steep spire (parts.cone_roof is 1:1, which reads as a squat pyramid on a castle): each ring is
    `pitch` blocks tall (a course of full tiles under a course of stairs), overhanging one block, with a
    wall-block finial. Local coordinates, like parts.cone_roof."""
    full_ = "deepslate_tiles"
    level = 0
    for r in range(radius + 1, 0, -1):
        for k in range(pitch):
            for x in range(cx - r, cx + r + 1):
                for z in range(cz - r, cz + r + 1):
                    d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
                    if r - 0.5 <= d < r + 0.5:
                        dx, dz = cx - x, cz - z
                        f = ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")
                        last = k == pitch - 1
                        b.set(x, y + level, z, f"{stair_}[facing={f},half=bottom,shape=straight]" if last else full_)
                    elif d < r - 0.5:
                        b.set(x, y + level, z, "air")
            level += 1
    b.set(cx, y + level, cz, full_)
    b.set(cx, y + level + 1, cz, top or "deepslate_tile_wall")
    return y + level + 2
OUT = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}


class W:
    """Set blocks by world coordinates."""

    def __init__(self, b):
        self.b = b

    def set(self, x, y, z, blk):
        self.b.set(x - OX, y - OY, z - OZ, blk(x, y, z) if callable(blk) else blk)

    def get(self, x, y, z):
        return self.b.get(x - OX, y - OY, z - OZ)

    def fill(self, x1, y1, z1, x2, y2, z2, blk):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.set(x, y, z, blk)

    def air(self, x1, y1, z1, x2, y2, z2):
        self.fill(x1, y1, z1, x2, y2, z2, "air")

    def door(self, x, y, z, facing, wood="dark_oak", hinge="left"):
        self.set(x, y, z, f"{wood}_door[facing={facing},half=lower,hinge={hinge},open=false]")
        self.set(x, y + 1, z, f"{wood}_door[facing={facing},half=upper,hinge={hinge},open=false]")

    def window(self, x, y, z, along, width=1, height=1, pane="glass_pane"):
        window(self.b, x - OX, y - OY, z - OZ, along, width, height, pane)

    def bed(self, x, y, z, facing, color="pink"):
        """head at (x,y,z), foot one block opposite to facing."""
        dx, dz = OUT[facing]
        self.set(x, y, z, f"{color}_bed[facing={facing},part=head,occupied=false]")
        self.set(x - dx, y, z - dz, f"{color}_bed[facing={facing},part=foot,occupied=false]")


# ---------------------------------------------------------------- the site: courtyard levels
YIN, YOUT = 125, 121                    # inner ward, outer bailey (floor block y)
CX0, CX1, CZ0, CZ1 = 250, 286, -280, -240   # inside the curtain
EAST_X = 274                            # east terraces from here


def smooth(x, z):
    pts = [ground(x + i, z + k) for i in (-2, -1, 0, 1, 2) for k in (-2, -1, 0, 1, 2)]
    return sum(pts) / len(pts)


def _levels():
    lv = {}
    for z in range(CZ0, CZ1 + 1):
        prev = YIN if z <= -254 else YOUT
        for x in range(CX0, CX1 + 1):
            if x < EAST_X:
                lv[(x, z)] = prev
                continue
            s = smooth(x, z)
            L = 125 if s >= 122.5 else 121 if s >= 118.5 else 117
            L = min(L, prev)
            lv[(x, z)] = prev = L
    return lv


LEVEL = _levels()


def level(x, z):
    return LEVEL.get((x, z))


# ---------------------------------------------------------------- curtain walls
# (name, rows (outer, inner) along the fixed axis, range along, out direction, walk y)
SEGMENTS = [
    ("N", "z", (-282, -281), (249, 287), "north", 133),
    ("Wn", "x", (248, 249), (-281, -254), "west", 133),
    ("Ws", "x", (248, 249), (-253, -239), "west", 129),
    ("Sw", "z", (-238, -239), (249, 263), "south", 129),
    ("Se", "z", (-238, -239), (279, 287), "south", 126),
    ("En", "x", (288, 287), (-281, -263), "east", 129),
    ("Es", "x", (288, 287), (-262, -239), "east", 126),
]


def seg_cells(seg):
    _, axis, rows, (a0, a1), out, wy = seg
    for a in range(a0, a1 + 1):
        for i, r in enumerate(rows):
            x, z = (a, r) if axis == "z" else (r, a)
            yield a, i, x, z


def curtain(w):
    for seg in SEGMENTS:
        name, axis, rows, (a0, a1), out, wy = seg
        ox, oz = OUT[out]
        for a, i, x, z in seg_cells(seg):
            g = ground(x, z)
            base = g - 2
            w.fill(x, base, z, x, wy, z, lambda X, Y, Z: rubble(X, Y, Z) if Y <= g + 1 else brick(X, Y, Z))
            w.set(x, wy, z, "polished_andesite" if i == 1 and rnd(x, wy, z, 9) < 0.5 else "stone_bricks")
            if i == 0:  # outer face: skirt, buttresses, corbelled parapet with merlons
                px, pz = x + ox, z + oz
                gp = ground(px, pz)
                w.set(px, gp + 1, pz, stair(OPP[out], block="cobblestone_stairs"))
                if a % 6 == 0 and wy - gp > 5:   # buttress
                    w.fill(px, gp - 1, pz, px, wy - 2, pz, lambda X, Y, Z: rubble(X, Y, Z) if Y <= gp + 1 else brick(X, Y, Z))
                    w.set(px, wy - 1, pz, stair(OPP[out], "bottom"))
                    w.set(px + ox, gp + 1, pz + oz, stair(OPP[out], block="cobblestone_stairs"))
                w.set(px, wy, pz, stair(OPP[out], "top"))           # corbel
                w.set(px, wy + 1, pz, brick)                          # parapet
                if a % 2 == 0:
                    w.set(px, wy + 2, pz, brick)                      # merlon
                    if a % 8 == 0:
                        w.set(px, wy + 3, pz, "lantern[hanging=false]")
                # arrow slit every 6, mid-height (a dark niche in the face)
                if a % 6 == 3 and wy - g > 8:
                    w.set(x, wy - 4, z, "iron_bars[north=false,south=false,east=false,west=false]")
                    w.set(x, wy - 3, z, "iron_bars[north=false,south=false,east=false,west=false]")
            else:  # inner face: a band of polished andesite under the walk, lanterns on the inner side
                L = level(x - ox, z - oz)
                if L is not None and a % 7 == 0 and wy - L > 4:
                    w.set(x - ox, wy - 2, z - oz, f"lantern[hanging=false]" if False else "air")


def wall_lamps(w):
    """Lanterns on wall brackets on the inner faces of the curtain (they light the courtyards)."""
    for seg in SEGMENTS:
        name, axis, rows, (a0, a1), out, wy = seg
        ox, oz = OUT[out]
        for a in range(a0 + 3, a1 - 2, 7):
            x, z = (a, rows[1]) if axis == "z" else (rows[1], a)
            ix, iz = x - ox, z - oz
            L = level(ix, iz)
            if L is None or w.get(ix, L + 3, iz) not in (None, "air"):
                continue
            w.set(ix, L + 4, iz, stair(out, "top"))   # bracket
            w.set(ix, L + 3, iz, "lantern[hanging=true]")


# ---------------------------------------------------------------- towers
TOWER_INSIDE = {}   # name -> set of (x, z) interior cells


def tower_body(w, name, cx, cz, shape, r, top, floors, wall=brick):
    """A tower from the rock up to `top`: round (radius r) or square (half-size r). Solid below the
    lowest floor, hollow above, with a floor block at each y in floors. Returns the interior cells."""
    cells, inside = [], set()
    for x in range(cx - r - 1, cx + r + 2):
        for z in range(cz - r - 1, cz + r + 2):
            if shape == "round":
                d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
                if r - 0.5 <= d < r + 0.5:
                    cells.append((x, z))
                elif d < r - 0.5:
                    inside.add((x, z))
            else:
                if max(abs(x - cx), abs(z - cz)) == r:
                    cells.append((x, z))
                elif max(abs(x - cx), abs(z - cz)) < r:
                    inside.add((x, z))
    low = min(floors)
    for x, z in cells:
        g = ground(x, z)
        w.fill(x, g - 2, z, x, top, z, lambda X, Y, Z: rubble(X, Y, Z) if Y <= g + 1 else wall(X, Y, Z))
        # battered skirt on the outside where the tower stands on the slope
        d = (x - cx, z - cz)
        sx = (d[0] > 0) - (d[0] < 0)
        sz = (d[1] > 0) - (d[1] < 0)
        if abs(d[0]) >= abs(d[1]):
            sz = 0
        else:
            sx = 0
        ox, oz = x + sx, z + sz
        if (ox, oz) not in inside and w.get(ox, ground(ox, oz) + 1, oz) in (None, "air"):
            f = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[(sx, sz)]
            w.set(ox, ground(ox, oz) + 1, oz, stair(f, block="cobblestone_stairs"))
    for x, z in inside:
        g = ground(x, z)
        w.fill(x, min(g, low) - 2, z, x, low, z, rubble)
        w.air(x, low + 1, z, x, top, z)
        for f in floors:
            w.set(x, f, z, "spruce_planks" if low < f < max(floors) else "stone_bricks")
    TOWER_INSIDE[name] = inside
    return cells, inside


def tower_stairs(w, cx, cz, y_floor, y_top):
    """A 3x3 spiral round a central post from the floor at y_floor up to the floor block at y_top."""
    spiral_stairs(w.b, cx - 1 - OX, cz - 1 - OZ, cx + 1 - OX, cz + 1 - OZ, y_floor + 1 - OY, y_top + 1 - OY,
                  "spruce_stairs", "spruce_planks", support="stone_bricks")
    w.fill(cx, y_floor + 1, cz, cx, y_top + 2, cz, "dark_oak_log[axis=y]")


def tower_lights(w, cx, cz, floors, r):
    for f in floors:
        w.set(cx, f + 3, cz, "lantern[hanging=true]") if w.get(cx, f + 3, cz) == "dark_oak_log[axis=y]" else None
        # a lantern on the floor in a corner of the landing (never on the stair ring)
        for dx, dz in ((r - 1, r - 1), (-(r - 1), r - 1), (r - 1, -(r - 1)), (-(r - 1), -(r - 1))):
            if r == 4:
                dx, dz = (dx - (1 if dx > 0 else -1), dz - (1 if dz > 0 else -1))
            x, z = cx + dx, cz + dz
            if max(abs(dx), abs(dz)) >= 2 and w.get(x, f + 1, z) == "air" and w.get(x, f, z) not in (None, "air"):
                w.set(x, f + 1, z, "lantern[hanging=false]")
                break


def round_windows(w, cx, cz, r, ys, dirs=("north", "south", "east", "west")):
    for d in dirs:
        ox, oz = OUT[d]
        x, z = cx + ox * r, cz + oz * r
        for y in ys:
            w.window(x, y, z, "x" if oz else "z", 1, 2)


def crenellate_round(w, cx, cz, r, y):
    """Corbelled parapet ring at radius r+1 on a round tower whose top floor is y."""
    for x in range(cx - r - 2, cx + r + 3):
        for z in range(cz - r - 2, cz + r + 3):
            d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
            if r + 0.5 <= d < r + 1.5:
                dx, dz = cx - x, cz - z
                f = ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")
                w.set(x, y, z, stair(f, "top"))
                w.set(x, y + 1, z, brick)
                if (x + z) % 2 == 0:
                    w.set(x, y + 2, z, brick)
            elif r - 0.5 <= d < r + 0.5:
                w.set(x, y, z, brick)
                w.set(x, y + 1, z, "air")
                w.set(x, y + 2, z, "air")


def crenellate_square(w, cx, cz, r, y, lamps=True):
    for x in range(cx - r - 1, cx + r + 2):
        for z in range(cz - r - 1, cz + r + 2):
            m = max(abs(x - cx), abs(z - cz))
            if m == r + 1:
                dx, dz = cx - x, cz - z
                if abs(dx) == abs(dz):
                    w.set(x, y, z, brick)
                else:
                    f = ("east" if dx > 0 else "west") if abs(dx) > abs(dz) else ("south" if dz > 0 else "north")
                    w.set(x, y, z, stair(f, "top"))
                w.set(x, y + 1, z, brick)
                if (x + z) % 2 == 0 or abs(x - cx) == abs(z - cz):
                    w.set(x, y + 2, z, brick)
                if lamps and abs(x - cx) == abs(z - cz):
                    w.set(x, y + 3, z, "lantern[hanging=false]")
            elif m == r:
                w.set(x, y, z, brick)
                w.set(x, y + 1, z, "air")
                w.set(x, y + 2, z, "air")


# (name, cx, cz, shape, r, base floor, walk floors, top floor, roof)
TOWERS = [
    ("NW", 248, -282, "round", 3, 133, [], 133, "cone"),
    ("NE", 287, -281, "round", 4, None, [129, 133], 137, "cone"),
    ("Wm", 248, -253, "round", 4, 121, [129, 133], 137, "cone"),
    ("E", 288, -262, "square", 3, None, [126, 129], 133, "flat"),
    ("SE", 287, -239, "round", 4, None, [126], 131, "cone"),
    ("SW", 248, -239, "square", 3, 121, [129], 133, "hip"),
]


TOWER_DOORS = {"NE": (283, -280, "west"), "Wm": (252, -252, "east"), "E": (285, -261, "west"),
               "SE": (283, -240, "west"), "SW": (251, -240, "east")}
DOOR_FRONTS = []


def towers(w):
    for name, cx, cz, shape, r, base, walks, topf, roof in TOWERS:
        if base is None:   # the courtyard level at its door
            x, z, f = TOWER_DOORS[name]
            base = level(x + OUT[f][0], z + OUT[f][1])
        floors = sorted({base, *walks, topf})
        top_wall = topf + (5 if roof == "cone" else 0) + (3 if roof == "hip" else 0)
        tower_body(w, name, cx, cz, shape, r, top_wall, floors)
        if base < topf and (shape == "square" or r >= 4):
            tower_stairs(w, cx, cz, base, topf)
        # door from the courtyard
        if name in TOWER_DOORS:
            x, z, f = TOWER_DOORS[name]
            ox, oz = x + OUT[f][0], z + OUT[f][1]
            base_d = level(ox, oz)
            w.air(x, base_d + 1, z, x, base_d + 3, z)
            w.door(x, base_d + 1, z, f)
            DOOR_FRONTS.append((ox, base_d, oz, f))
            if base_d != base:
                print("tower door level mismatch", name, base_d, base)
        tower_lights(w, cx, cz, floors, r)
        ys = [f + 2 for f in floors if f > base] + [topf + 2]
        if shape == "round":
            round_windows(w, cx, cz, r, [y for y in ys if y <= top_wall - 2])
        else:
            for d in ("north", "south", "east", "west"):
                ox, oz = OUT[d]
                for y in ys:
                    if y <= top_wall - 2:
                        w.window(cx + ox * r, y, cz + oz * r, "x" if oz else "z", 1, 2)
        if roof == "cone":
            cone_roof(w.b, cx - OX, cz - OZ, top_wall + 1 - OY, r, ROOF, top="deepslate_tile_wall")
            w.set(cx, top_wall + r + 3, cz, "lightning_rod[facing=up]") if False else None
            w.set(cx, top_wall + 1, cz, "air")
            w.set(cx, top_wall + 1 + r + 1 + 1, cz, "end_rod[facing=up]") if False else None
            banner_pole(w, cx, cz, top_wall + 1 + 2 * (r + 1) + 2)
            # eaves lantern ring under the overhang
            for dx, dz in ((r + 1, 0), (-(r + 1), 0), (0, r + 1), (0, -(r + 1))):
                w.set(cx + dx, top_wall, cz + dz, "lantern[hanging=true]")
        elif roof == "hip":
            hip_roof(w.b, cx - r - OX, cz - r - OZ, cx + r - OX, cz + r - OZ, top_wall + 1 - OY, ROOF)
            banner_pole(w, cx, cz, top_wall + 1 + r + 1)
        else:
            crenellate_square(w, cx, cz, r, topf) if shape == "square" else crenellate_round(w, cx, cz, r, topf)


def banner_pole(w, x, z, y, color="red"):
    """A pennant on the roof tip: a fence pole with a banner hung on it, a lantern at the top."""
    w.fill(x, y, z, x, y + 2, z, "dark_oak_fence")
    w.set(x, y + 3, z, "lantern[hanging=false]")
    w.set(x + 1, y + 2, z, f"{color}_wall_banner[facing=east]")


def walk_doors(w):
    """Cut the openings where the wall walks run into towers and the keep."""
    for name, axis, rows, (a0, a1), out, wy in SEGMENTS:
        for end, step in ((a0, -1), (a1, 1)):
            for r in rows:
                for k in range(-6, 6):
                    a = end + step * k
                    x, z = (a, r) if axis == "z" else (r, a)
                    if any((x, z) in ins for ins in TOWER_INSIDE.values()):
                        break
                    w.set(x, wy + 1, z, "air")
                    w.set(x, wy + 2, z, "air")
                    if w.get(x, wy, z) in (None, "air"):
                        w.set(x, wy, z, "stone_bricks")


# ---------------------------------------------------------------- courtyards
def terraces(w):
    """Level the courtyards: fill or cut each column to its level; retaining walls with a parapet where a
    terrace drops to the next; paths and grass."""
    for (x, z), L in LEVEL.items():
        g = ground(x, z)
        if g < L:
            w.fill(x, g + 1, z, x, L - 1, z, "dirt")
        if g > L:
            w.air(x, L + 1, z, x, g + 1, z)
        w.set(x, L, z, "grass_block")
    for (x, z), L in LEVEL.items():
        low = [level(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        low = [v for v in low if v is not None and v < L]
        if low:
            w.fill(x, min(low) + 1, z, x, L, z, brick)
            w.set(x, L + 1, z, "stone_brick_wall")
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v = level(x + dx, z + dz)
                if v is not None and v < L:   # a coping band on the face of the retaining wall
                    pass


def flight(w, x1, x2, z, y_top, steps, down):
    """Stairs (width x1..x2 along x, or z-flights when down is east/west) descending `down` from a cell at
    y_top: step k at y_top - k. Clears headroom and the parapet, fills under each step."""
    dx, dz = OUT[down]
    for k in range(steps):
        for a in range(x1, x2 + 1):
            x, zz = (a + dx * k, z + dz * k) if dz else (x1 + dx * k, a + 0)  # dz: along x
            if not dz:
                x, zz = z + dx * k, a
            y = y_top - k
            w.set(x, y, zz, stair(OPP[down]))
            g = ground(x, zz)
            w.fill(x, min(g, y - 1), zz, x, y - 1, zz, brick)
            w.air(x, y + 1, zz, x, y + 4, zz)


def cheeks(w, cells, y_top, n):
    pass


# ---------------------------------------------------------------- keep
KX0, KX1, KZ0, KZ1 = 256, 270, -282, -268
KF = [126, 133, 138, 143]   # ground floor, bedchamber floor, library floor, roof walk
PT = (270, -268)            # princess tower centre (r 4)
PT_TOP = 157                # bower floor


def in_pt(x, z, r=4.5):
    return ((x - PT[0]) ** 2 + (z - PT[1]) ** 2) ** 0.5 < r - 1.0  # inside the tower (wall ring excluded)


def pt_ring(x, z):
    d = ((x - PT[0]) ** 2 + (z - PT[1]) ** 2) ** 0.5
    return 3.5 <= d < 4.5


def keep(w):
    top = 143
    # shell
    for x in range(KX0, KX1 + 1):
        for z in range(KZ0, KZ1 + 1):
            g = ground(x, z)
            edge = x in (KX0, KX1) or z in (KZ0, KZ1)
            if edge:
                w.fill(x, g - 2, z, x, top, z, lambda X, Y, Z: rubble(X, Y, Z) if Y <= 126 else brick(X, Y, Z))
            else:
                w.fill(x, min(g, 125) - 1, z, x, 126, z, rubble)
                w.air(x, 127, z, x, max(g, 142) + 1, z)
                for f in KF:
                    w.set(x, f, z, "stone_bricks" if f == 126 else "spruce_planks" if f < 143 else "stone_bricks")
    # plinth and string courses, pilasters (depth)
    for x in range(KX0 - 1, KX1 + 2):
        for z in range(KZ0 - 1, KZ1 + 2):
            if not (x in (KX0 - 1, KX1 + 1) or z in (KZ0 - 1, KZ1 + 1)):
                continue
            if x in (KX0 - 1, KX1 + 1) and z in (KZ0 - 1, KZ1 + 1):
                continue
            f = "east" if x == KX0 - 1 else "west" if x == KX1 + 1 else "south" if z == KZ0 - 1 else "north"
            g = ground(x, z)
            if g < 127 and level(x, z) is not None or g < 127:
                w.set(x, max(g, 125) + 1, z, stair(f, block="cobblestone_stairs"))
            # pilasters every 4 (and at the corners), up to the corbel table
            a = z if x in (KX0 - 1, KX1 + 1) else x
            lo = KZ0 if x in (KX0 - 1, KX1 + 1) else KX0
            if ((a - lo) % 7 in (0,) or a in (KX0, KX1, KZ0, KZ1)) and not (z == KZ1 + 1 and 260 <= x <= 266):
                w.fill(x, max(g, 125) + 1, z, x, 141, z, brick)
                w.set(x, max(g, 125) + 1, z, rubble)
            # string course between ground floor and bedchamber
            if w.get(x, 133, z) in (None, "air"):
                w.set(x, 133, z, stair(f, "top"))
            # corbels and the roof-walk parapet
            w.set(x, 142, z, stair(f, "top"))
            w.set(x, 143, z, brick)
            w.set(x, 144, z, brick)
            if (x + z) % 2 == 0:
                w.set(x, 145, z, brick)
    for x, z in ((KX0 - 1, KZ0 - 1), (KX1 + 1, KZ0 - 1), (KX0 - 1, KZ1 + 1)):
        w.fill(x, 141, z, x, 144, z, brick)
    # roof walk floor over the shell
    w.fill(KX0, 143, KZ0, KX1, 143, KZ1, "stone_bricks")
    # bartizans on three corners (round, corbelled out, cone roofs)
    for bx, bz in ((KX0 - 1, KZ0 - 1), (KX1 + 1, KZ0 - 1), (KX0 - 1, KZ1 + 1)):
        for x in range(bx - 2, bx + 3):
            for z in range(bz - 2, bz + 3):
                d = ((x - bx) ** 2 + (z - bz) ** 2) ** 0.5
                if d < 2.5:
                    w.set(x, 140, z, brick if d < 1.5 else stair("south" if z < bz else "north", "top")
                          if abs(z - bz) >= abs(x - bx) else stair("east" if x < bx else "west", "top"))
                    w.set(x, 141, z, "stone_bricks")
                    w.set(x, 143, z, "stone_bricks")
                if 1.5 <= d < 2.5:
                    w.fill(x, 144, z, x, 147, z, brick)
                elif d < 1.5:
                    w.air(x, 144, z, x, 147, z)
        w.set(bx, 144, bz, "lantern[hanging=false]")
        for x in range(bx - 2, bx + 3):     # open the bartizan to the roof walk
            for z in range(bz - 2, bz + 3):
                if ((x - bx) ** 2 + (z - bz) ** 2) ** 0.5 < 2.5 and KX0 <= x <= KX1 and KZ0 <= z <= KZ1:
                    w.air(x, 144, z, x, 145, z)
        for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            if not (KX0 <= bx + dx <= KX1 and KZ0 <= bz + dz <= KZ1) and not (KX0 <= bx + dx <= KX1 and abs(dz) == 0) \
                    and not (KZ0 <= bz + dz <= KZ1 and dx == 0):
                w.window(bx + dx, 145, bz + dz, "x" if dz else "z", 1, 1)
        cone_roof(w.b, bx - OX, bz - OZ, 148 - OY, 2, ROOF, top="deepslate_tile_wall")
        banner_pole(w, bx, bz, 148 + 2 * 3 + 2)
    # doorways from the roof walk into the bartizans
    w.air(KX0, 144, KZ0, KX0, 145, KZ0)
    w.air(KX1, 144, KZ0, KX1, 145, KZ0)
    w.air(KX0, 144, KZ1, KX0, 145, KZ1)
    # the great roof: a hipped roof over the middle of the keep
    t = Build("roof")
    hip_roof(t, KX0 + 2, KZ0 + 2, KX1 - 2, KZ1 - 2, 144, ROOF, overhang=0)
    tops = {}
    for (x, y, z) in t.blocks:
        tops[(x, z)] = min(tops.get((x, z), 999), y)
    for (x, z), y in tops.items():   # solid under the roof: no hollow attic nobody can reach
        w.fill(x, 144, z, x, y - 1, z, "stone_bricks")
    for (x, y, z), blk in t.blocks.items():
        w.set(x, y, z, blk)
    w.fill(KX0 + 2, 143, KZ0 + 2, KX1 - 2, 143, KZ1 - 2, "stone_bricks")
    # dormers? a little lucarne on the south slope
    for x in (KX0 + 2, KX1 - 2):
        pass
    # chimney stack from the great hall fireplace (west wall)
    w.fill(KX0 + 3, 144, KZ0 + 6, KX0 + 3, 151, KZ0 + 6, brick)
    w.set(KX0 + 3, 152, KZ0 + 6, "campfire[lit=true,signal_fire=false,facing=north]")
    # entrance: a pointed arch portal in the south face, double doors, steps
    ex = 263
    w.air(ex - 1, 127, KZ1, ex + 1, 130, KZ1)
    w.door(ex - 1, 127, KZ1, "south", hinge="left")
    w.door(ex, 127, KZ1, "south", hinge="right")
    w.set(ex + 1, 127, KZ1, brick)
    w.set(ex + 1, 128, KZ1, brick)
    w.set(ex - 1, 129, KZ1, "chiseled_stone_bricks")
    w.set(ex, 129, KZ1, "chiseled_stone_bricks")
    w.set(ex + 1, 129, KZ1, "chiseled_stone_bricks")
    w.set(ex - 1, 130, KZ1, brick)
    w.set(ex, 130, KZ1, brick)
    w.set(ex + 1, 130, KZ1, brick)
    # porch: steps up from the garden (125) to the door sill (126), lanterns either side
    for x in range(ex - 2, ex + 2):
        w.set(x, 126, KZ1 + 1, stair("north"))
    for x in (ex - 3, ex + 2):
        w.fill(x, 126, KZ1 + 1, x, 128, KZ1 + 1, "stone_bricks")
        w.set(x, 129, KZ1 + 1, "lantern[hanging=false]")
    w.set(ex - 1, 131, KZ1 + 1, "red_wall_banner[facing=south]")
    w.set(ex, 131, KZ1 + 1, "red_wall_banner[facing=south]")
    great_hall(w)
    bedchamber(w)
    library(w)
    keep_windows(w)
    princess_tower(w)


def keep_windows(w):
    # great hall: tall lancets (1 x 3) east and west, and on the south either side of the door
    for z in (-279, -276, -273):
        w.window(KX0, 128, z, "z", 1, 3)
        w.set(KX0, 131, z, "chiseled_stone_bricks")
        w.set(KX0 - 1, 127, z, stair("east", "top")) if False else None
    for z in (-279, -276):
        w.window(KX1, 128, z, "z", 1, 3)
    for x in (259, 267):
        w.window(x, 128, KZ1, "x", 1, 3)
    # bedchamber: pairs, flower boxes under the east ones
    for z in (-280, -279):
        w.window(KX1, 134, z, "z", 1, 2) if z == -280 else None
    w.window(KX1, 134, -280, "z", 2, 2)
    w.window(KX1, 134, -275, "z", 2, 2)
    w.window(KX0, 134, -280, "z", 2, 2)
    w.window(KX0, 134, -274, "z", 2, 2)
    w.window(259, 134, KZ1, "x", 2, 2)
    w.window(260, 134, KZ0, "x", 2, 2)
    w.window(265, 134, KZ0, "x", 2, 2)
    for z in (-280, -279):
        w.set(KX1 + 1, 133, z, "flowering_azalea_leaves[persistent=true]")
    for z in (-275, -274):
        w.set(KX1 + 1, 133, z, "flowering_azalea_leaves[persistent=true]")
    # library: small square windows all round
    for z in (-280, -276, -272):
        w.window(KX0, 139, z, "z", 1, 2)
    for z in (-280, -276):
        w.window(KX1, 139, z, "z", 1, 2)
    for x in (259, 263, 267):
        w.window(x, 139, KZ0, "x", 1, 2)
    for x in (259, 263):
        w.window(x, 139, KZ1, "x", 1, 2)
    # banners down the south face between the floors
    for x in (258, 268):
        w.set(x, 132, KZ1 + 1, "red_wall_banner[facing=south]")
        w.set(x, 137, KZ1 + 1, "red_wall_banner[facing=south]")
    for z in (-281, -270):
        w.set(KX1 + 1, 137, z, "pink_wall_banner[facing=east]")


def great_hall(w):
    y = 127
    # red runner from the door to the dais, the dais at the north end
    for z in range(-271, KZ1):
        for x in (262, 263, 264):
            w.set(x, y, z, "red_carpet" if x == 263 else "air")
    for x in range(KX0 + 1, KX1):
        for z in (KZ0 + 1, KZ0 + 2):
            if not in_pt(x, z) and not pt_ring(x, z):
                w.set(x, y, z, "dark_oak_planks")
        if not in_pt(x, KZ0 + 3) and not pt_ring(x, KZ0 + 3):
            w.set(x, y, KZ0 + 3, "dark_oak_slab[type=bottom]")
    # the two thrones and a tapestry behind
    for x in (262, 264):
        w.set(x, 128, KZ0 + 1, stair("north", block="dark_oak_stairs"))
        w.set(x, 129, KZ0 + 1, "air")
    w.set(263, 128, KZ0 + 1, "gold_block")
    w.set(263, 129, KZ0 + 1, "candle[candles=3,lit=true]")
    for x in (261, 262, 264, 265):
        w.set(x, 130, KZ0 + 1, "red_wall_banner[facing=south]")
    w.set(263, 130, KZ0 + 1, "pink_wall_banner[facing=south]")
    # the long table with benches
    for z in range(-277, -271):
        w.set(261, y, z, stair("east", block="spruce_stairs"))
        for x in (262, 263, 264):
            w.set(x, y, z, "dark_oak_slab[type=top]")
        w.set(265, y, z, stair("west", block="spruce_stairs"))
    for z in (-276, -274, -272):
        w.set(263, 128, z, "candle[candles=3,lit=true]")
    w.set(263, 128, -275, "cake[bites=0]")
    w.set(262, 128, -273, "potted_red_tulip")
    # the fireplace in the west wall
    fz = KZ0 + 6
    w.fill(KX0 + 1, 127, fz - 1, KX0 + 1, 130, fz + 1, brick)
    w.fill(KX0 + 2, 127, fz - 1, KX0 + 3, 131, fz + 1, brick)
    w.air(KX0 + 2, 127, fz, KX0 + 2, 128, fz)
    w.set(KX0 + 2, 126, fz, "campfire[lit=true,signal_fire=false,facing=east]")
    w.set(KX0 + 2, 127, fz, "air")
    w.set(KX0 + 3, 127, fz, "air")
    w.set(KX0 + 3, 128, fz, "air")
    w.fill(KX0 + 3, 132, fz - 1, KX0 + 3, 132, fz + 1, brick)
    w.set(KX0 + 4, 129, fz - 1, stair("west", "top"))
    w.set(KX0 + 4, 129, fz + 1, stair("west", "top"))
    w.set(KX0 + 4, 129, fz, stair("west", "top"))
    w.set(KX0 + 4, 130, fz, "red_wall_banner[facing=east]")
    w.fill(KX0 + 3, 129, fz, KX0 + 3, 143, fz, brick)
    # armchairs by the fire
    w.set(KX0 + 5, y, fz - 2, stair("east", block="dark_oak_stairs"))
    w.set(KX0 + 5, y, fz + 2, stair("east", block="dark_oak_stairs"))
    # tie beams across the hall and chandeliers on chains
    for z in (-278, -274, -270):
        for x in range(KX0 + 1, KX1):
            if not in_pt(x, z) and not pt_ring(x, z):
                w.set(x, 132, z, "dark_oak_log[axis=x]")
    for z in (-276, -272):
        w.set(263, 132, z, "iron_chain[axis=y]")
        w.set(263, 131, z, "lantern[hanging=true]")
    for x, z in ((259, -279), (267, -279), (259, -270), (259, -275), (267, -275)):
        w.set(x, 131, z, "lantern[hanging=true]") if not in_pt(x, z) else None
        w.set(x, 132, z, "iron_chain[axis=y]") if not in_pt(x, z) else None
    # banners between the lancets, barrels and a cask rack by the door
    for z in (-278, -275):
        w.set(KX1 - 1, 130, z, "red_wall_banner[facing=west]")
    for z in (-277, -274):
        w.set(KX0 + 1, 130, z, "red_wall_banner[facing=east]")
    w.set(KX0 + 1, y, KZ1 - 1, "barrel[facing=up,open=false]")
    w.set(KX0 + 2, y, KZ1 - 1, "barrel[facing=up,open=false]")
    w.set(KX0 + 1, y + 1, KZ1 - 1, "barrel[facing=up,open=false]")
    w.set(KX0 + 1, y, KZ1 - 2, "lantern[hanging=false]")


def bedchamber(w):
    f = 133
    y = f + 1
    # partition between the bedchamber (north) and the solar (south), with a door
    pz = -274
    for x in range(KX0 + 1, KX1):
        if not in_pt(x, pz) and not pt_ring(x, pz):
            w.fill(x, y, pz, x, 137, pz, "spruce_planks" if x % 3 else "dark_oak_log[axis=y]")
    w.door(263, y, pz, "south", wood="spruce")
    # carpets: pink and white checker in the bedchamber
    for x in range(KX0 + 1, KX1):
        for z in range(KZ0 + 1, pz):
            if w.get(x, y, z) in (None, "air"):
                w.set(x, y, z, "pink_carpet" if (x + z) % 2 else "white_carpet")
    # the canopy bed (two pink beds), head to the north wall
    for x in (262, 263):
        w.bed(x, y, KZ0 + 1, "north")
    for x, z in ((261, KZ0 + 1), (264, KZ0 + 1), (261, KZ0 + 3), (264, KZ0 + 3)):
        w.fill(x, y, z, x, y + 2, z, "dark_oak_fence")
        w.set(x, y, z, "dark_oak_fence")
    for x in range(261, 265):
        for z in range(KZ0 + 1, KZ0 + 4):
            w.set(x, 137, z, "pink_wool" if (x + z) % 2 else "white_wool")
    w.set(262, 136, KZ0 + 2, "air")
    w.set(260, y, KZ0 + 1, "spruce_slab[type=top]")      # bedside tables
    w.set(260, y + 1, KZ0 + 1, "candle[candles=2,lit=true]")
    w.set(265, y, KZ0 + 1, "spruce_slab[type=top]")
    w.set(265, y + 1, KZ0 + 1, "potted_pink_tulip")
    w.set(263, y, KZ0 + 4, "pink_carpet")
    # wardrobe and chests along the west wall
    for z in (KZ0 + 1, KZ0 + 2):
        w.set(KX0 + 1, y, z, "barrel[facing=east,open=false]")
        w.set(KX0 + 1, y + 1, z, "barrel[facing=east,open=false]")
    w.set(KX0 + 1, y, KZ0 + 5, "chest[facing=east,type=single]")
    # a vanity by the east window: table, stool, mirror (a glass pane in a frame), flowers
    w.set(KX1 - 1, y, -277, "spruce_slab[type=top]")
    w.set(KX1 - 1, y + 1, -277, "potted_azalea_bush")
    w.set(KX1 - 2, y, -277, stair("west", block="spruce_stairs"))
    w.set(KX1 - 1, y, -278, "loom[facing=west]")
    # a little harp corner (note block) and bookshelf
    w.set(KX0 + 1, y, -276, "note_block")
    w.set(KX0 + 1, y, -277, "bookshelf")
    w.set(KX0 + 1, y + 1, -277, "potted_lily_of_the_valley")
    # light: lanterns hanging from the ceiling corners and candles
    for x, z in ((259, -279), (267, -279), (259, -276), (266, -276)):
        if not in_pt(x, z):
            w.set(x, 137, z, "lantern[hanging=true]")
    w.set(KX1 - 1, y, -276, "lantern[hanging=false]")
    # the solar: a sitting room with a rug, armchairs round a low table, bookshelves
    for x in range(KX0 + 2, KX0 + 8):
        for z in range(-272, -269):
            w.set(x, y, z, "purple_carpet" if (x in (KX0 + 2, KX0 + 7) or z in (-272, -270)) else "magenta_carpet")
    w.set(KX0 + 4, y, -271, "spruce_slab[type=top]")
    w.set(KX0 + 5, y, -271, "spruce_slab[type=top]")
    w.set(KX0 + 4, y + 1, -271, "candle[candles=4,lit=true]")
    w.set(KX0 + 3, y, -271, stair("east", block="dark_oak_stairs"))
    w.set(KX0 + 6, y, -271, stair("west", block="dark_oak_stairs"))
    for z in range(-273, -268):
        w.set(KX0 + 1, y, z, "bookshelf")
        w.set(KX0 + 1, y + 1, z, "bookshelf")
    w.set(KX0 + 1, y + 2, -271, "lantern[hanging=false]")
    for x, z in ((261, -271), (266, -272)):
        w.set(x, 137, z, "lantern[hanging=true]")
    w.set(266, y, -269, "lantern[hanging=false]") if not in_pt(266, -269) else None


def library(w):
    f = 138
    y = f + 1
    for x in range(KX0 + 1, KX1):
        for z in (KZ0 + 1,):
            if w.get(x, y, z) in (None, "air"):
                w.fill(x, y, z, x, y + 2, z, "bookshelf")
    for z in range(KZ0 + 2, KZ1 - 2):
        if w.get(KX0 + 1, y, z) in (None, "air"):
            w.fill(KX0 + 1, y, z, KX0 + 1, y + 1, z, "bookshelf")
    for x in (259, 263, 267):   # keep the windows clear
        w.air(x, y, KZ0 + 1, x, y + 1, KZ0 + 1)
    for z in (-280, -276, -272):
        w.air(KX0 + 1, y, z, KX0 + 1, y + 1, z)
    # reading tables and a map table
    w.set(262, y, -276, "lectern[facing=south,has_book=false]")
    w.set(264, y, -276, "cartography_table")
    w.set(263, y, -274, "spruce_slab[type=top]")
    w.set(264, y, -274, "spruce_slab[type=top]")
    w.set(263, y + 1, -274, "candle[candles=3,lit=true]")
    w.set(263, y, -273, stair("north", block="spruce_stairs"))
    w.set(264, y, -273, stair("north", block="spruce_stairs"))
    for x, z in ((260, -278), (266, -278), (260, -272), (266, -273), (263, -270)):
        if not in_pt(x, z) and not pt_ring(x, z):
            w.set(x, 142, z, "lantern[hanging=true]")
    for x in (259, 260, 266, 267):        # free-standing shelf rows
        if not in_pt(x, -278) and not pt_ring(x, -278):
            w.fill(x, y, -279, x, y + 1, -278, "bookshelf")
    for x in range(260, 267):           # a blue rug under the reading table
        for z in range(-275, -271):
            if w.get(x, y, z) in (None, "air"):
                w.set(x, y, z, "light_blue_carpet" if x in (260, 266) or z in (-275, -272) else "blue_carpet")
    w.set(KX0 + 2, y, -270, "chest[facing=east,type=single]")
    w.set(KX0 + 2, y, -271, stair("east", block="dark_oak_stairs"))
    w.set(KX0 + 3, y, -271, "spruce_slab[type=top]") if False else None


def princess_tower(w):
    cx, cz = PT
    r = 4
    floors = KF + [PT_TOP]
    top_wall = PT_TOP + 5
    cells = []
    for x in range(cx - r - 1, cx + r + 2):
        for z in range(cz - r - 1, cz + r + 2):
            d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
            if r - 0.5 <= d < r + 0.5:
                g = ground(x, z)
                w.fill(x, g - 2, z, x, top_wall, z, lambda X, Y, Z: rubble(X, Y, Z) if Y <= 126 else brick(X, Y, Z))
            elif d < r - 0.5:
                g = ground(x, z)
                w.fill(x, min(g, 125) - 1, z, x, 126, z, rubble)
                w.air(x, 127, z, x, top_wall, z)
                for f in floors:
                    w.set(x, f, z, "spruce_planks" if f != 126 else "stone_bricks")
    tower_stairs(w, cx, cz, 126, PT_TOP)
    # doors from the keep on each floor (the ring wall cell inside the keep, west of the stair)
    for f in KF:
        w.air(cx - 4, f + 1, cz - 1, cx - 4, f + 2, cz - 1)
        w.air(cx - 1, f + 1, cz - 4, cx - 1, f + 2, cz - 4) if f == 143 else None
    # the roof-walk door: out onto the keep roof
    w.air(cx - 4, 144, cz - 1, cx - 4, 145, cz - 1)
    # landings lit
    for f in floors:
        w.set(cx + 2, f + 1, cz + 2, "lantern[hanging=false]")
    # windows: slits up the shaft, big windows in the bower
    for y in (130, 135, 140, 146):
        for d in ("east", "south"):
            ox, oz = OUT[d]
            w.window(cx + ox * r, y, cz + oz * r, "x" if oz else "z", 1, 2)
    for d in ("north", "south", "east", "west"):
        ox, oz = OUT[d]
        w.window(cx + ox * r - (oz != 0) * 1, PT_TOP + 2, cz + oz * r - (ox != 0) * 1,
                 "x" if oz else "z", 3, 2)
    # the bower: a window seat, a bed of flowers, a telescope (spyglass stand), lanterns
    y = PT_TOP + 1
    w.set(cx + 2, y, cz - 1, "pink_bed[facing=north,part=head,occupied=false]") if False else None
    for dx, dz in ((-2, 2), (-1, 3)):
        pass
    w.set(cx - 2, y, cz + 2, "potted_pink_tulip")
    w.set(cx + 2, y, cz - 2, "potted_allium")
    w.set(cx - 2, y, cz - 2, stair("east", block="dark_oak_stairs"))
    w.set(cx + 3, y, cz, "pink_carpet") if False else None
    # balcony ring at the bower floor (corbelled), with a railing
    for x in range(cx - r - 2, cx + r + 3):
        for z in range(cz - r - 2, cz + r + 3):
            d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
            if r + 0.5 <= d < r + 2.5 and not (x <= KX1 + 1 and z <= KZ1 + 1):
                dx, dz = cx - x, cz - z
                f = ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")
                w.set(x, PT_TOP, z, "stone_brick_slab[type=top]")
                if d < r + 1.5:
                    w.set(x, PT_TOP - 1, z, stair(f, "top"))
                    w.set(x, PT_TOP - 2, z, stair(f, "top") if (x + z) % 2 else "air")
                else:
                    w.set(x, PT_TOP - 1, z, "air")
                    w.set(x, PT_TOP + 1, z, "stone_brick_wall")
    for d in ("east", "south"):
        ox, oz = OUT[d]
        x, z = cx + ox * r, cz + oz * r
        w.set(x, PT_TOP + 1, z, "air")
        w.set(x, PT_TOP + 2, z, "air")
        w.door(x, PT_TOP + 1, z, d, wood="spruce")
    # string courses at each keep floor (continuing the keep's)
    # cone roof, the tallest in the castle, pennant on top
    cone_roof(w.b, cx - OX, cz - OZ, top_wall + 1 - OY, r, ROOF, top="deepslate_tile_wall", pitch=3)
    banner_pole(w, cx, cz, top_wall + 1 + 3 * (r + 1) + 2, color="pink")
    for dx, dz in ((r + 1, 0), (0, r + 1), (-(r + 1), 0), (0, -(r + 1))):
        w.set(cx + dx, top_wall, cz + dz, "lantern[hanging=true]")
    # pink banners down the tower faces
    for d in ("east", "south"):
        ox, oz = OUT[d]
        w.set(cx + ox * (r + 1) - (oz != 0) * 2, 148, cz + oz * (r + 1) - (ox != 0) * 2, f"pink_wall_banner[facing={d}]")
        w.set(cx + ox * (r + 1) + (oz != 0) * 2, 148, cz + oz * (r + 1) + (ox != 0) * 2, f"pink_wall_banner[facing={d}]")


# ---------------------------------------------------------------- gatehouse
GX0, GX1 = 263, 279            # two 7x7 towers (x 263..269, 273..279), passage x 270..272
GZ0, GZ1 = -241, -235
GTOP = 133


def gatehouse(w):
    cw, ce = (266, -238), (276, -238)
    tower_body(w, "Gw", cw[0], cw[1], "square", 3, GTOP, [121, 126, 129, GTOP])
    tower_body(w, "Ge", ce[0], ce[1], "square", 3, GTOP, [121, 126, GTOP])
    for c in (cw, ce):
        tower_stairs(w, c[0], c[1], 121, GTOP)
        crenellate_square(w, c[0], c[1], 3, GTOP)
        tower_lights(w, c[0], c[1], [121, 126, GTOP], 3)
        for y in (128, 131):
            w.window(c[0], y, c[1] + 3, "x", 1, 2)
        for y in (123,):
            w.set(c[0], y, GZ1, "iron_bars[east=false,west=false,north=false,south=false]")
            w.set(c[0], y + 1, GZ1, "iron_bars[east=false,west=false,north=false,south=false]")
    # guard-room doors into the gate towers off the passage
    w.door(269, 122, -239, "east")
    w.door(273, 122, -239, "west")
    # the passage block between the towers: x 270..272 (+ the inner walls at 269/273 are the towers')
    for x in range(270, 273):
        for z in range(GZ0, GZ1 + 1):
            g = ground(x, z)
            w.fill(x, min(g, 121) - 2, z, x, 120, z, rubble)
            w.set(x, 121, z, "cobblestone" if rnd(x, 121, z) < 0.5 else "stone_bricks")
            w.air(x, 122, z, x, max(g, 125) + 1, z)
            w.fill(x, 126, z, x, 126, z, "spruce_planks")       # gate room floor
            w.air(x, 127, z, x, 130, z)
            w.set(x, 131, z, brick)                             # gate room ceiling / roof base
    # front and back faces of the passage block: walls with the arch openings
    for z in (GZ0, GZ1):
        for x in range(270, 273):
            w.fill(x, 125, z, x, 131, z, brick)
        w.set(270, 125, z, stair("west", "top"))
        w.set(272, 125, z, stair("east", "top"))
        w.set(271, 125, z, "air") if False else None
        w.air(270, 122, z, 272, 124, z)
        w.set(270, 124, z, stair("east", "top")) if False else None
    # portcullis raised in the arch (bars across the top course) and gate doors folded back
    for x in range(270, 273):
        w.set(x, 124, GZ1 + 0, "iron_bars[east=true,west=true,north=false,south=false]")
    # openings from the towers into the gate room (floor 126)
    for x, z in ((269, -238), (273, -238)):
        w.air(x, 127, z, x, 128, z)
    # gate room windows over the arch, banners, lanterns
    w.window(271, 128, GZ1, "x", 1, 2)
    w.window(271, 128, GZ0, "x", 1, 2)
    for x in (270, 272):
        w.set(x, 127, -238, "lantern[hanging=false]")
    for x in (268, 274):
        w.set(x, 126, GZ1 + 1, "red_wall_banner[facing=south]")
        w.set(x, 130, GZ1 + 1, "red_wall_banner[facing=south]")
    w.set(271, 130, GZ1 + 1, "pink_wall_banner[facing=south]")
    # lanterns either side of the arch outside and inside
    for x in (269, 273):
        w.set(x, 124, GZ1 + 1, "lantern[hanging=false]") if False else None
    for z in (GZ0 - 1, GZ1 + 1):
        w.set(269 if z == GZ1 + 1 else 269, 123, z, "lantern[hanging=false]") if False else None
    for x in range(270, 273):
        w.set(x, 125, -238, "lantern[hanging=true]") if x == 271 else None
    # a gabled roof over the gate room between the towers
    for x in range(270, 273):
        for z in range(GZ0, GZ1 + 1):
            w.set(x, 131, z, brick)
    for z in range(GZ0, GZ1 + 1):
        w.set(270, 132, z, stair("east", block=ROOF))
        w.set(272, 132, z, stair("west", block=ROOF))
        w.set(271, 132, z, "deepslate_tiles")
        w.set(271, 133, z, "deepslate_tile_slab[type=bottom]")
    for z in (GZ0, GZ1):
        w.set(271, 132, z, brick)
    # tower walk doors
    w.air(GX0, 130, -239, GX0, 131, -238)


# ---------------------------------------------------------------- the bailey: well, stable, smithy
def well(w, cx, cz, y):
    for x in range(cx - 1, cx + 2):
        for z in range(cz - 1, cz + 2):
            if (x, z) != (cx, cz):
                w.fill(x, y - 3, z, x, y + 1, z, rubble)
                w.set(x, y + 1, z, "stone_brick_wall") if False else None
    w.fill(cx, y - 3, cz, cx, y - 3, cz, "stone_bricks")
    w.fill(cx, y - 2, cz, cx, y, cz, "water")
    w.set(cx, y + 1, cz, "air")
    for x, z in ((cx - 1, cz - 1), (cx + 1, cz - 1), (cx - 1, cz + 1), (cx + 1, cz + 1)):
        w.fill(x, y + 2, z, x, y + 3, z, "dark_oak_fence")
    for x in range(cx - 2, cx + 3):
        w.set(x, y + 4, cz - 1, stair("south", block="dark_oak_stairs"))
        w.set(x, y + 4, cz + 1, stair("north", block="dark_oak_stairs"))
        w.set(x, y + 5, cz, "dark_oak_slab[type=bottom]")
        w.set(x, y + 4, cz, "dark_oak_planks")
    w.set(cx, y + 3, cz, "iron_chain[axis=y]")
    w.set(cx, y + 2, cz, "lantern[hanging=true]")
    w.set(cx + 2, y + 1, cz, "barrel[facing=up,open=false]") if False else None


def bailey(w):
    y = YOUT
    well(w, 258, -246, y)
    # cobbled yard paths: gate -> stair, gate -> well, round the well
    for z in range(-252, -239):
        for x in range(270, 273):
            w.set(x, y, z, "cobblestone" if rnd(x, y, z) < 0.4 else "gravel" if rnd(x, y, z, 2) < 0.3 else "stone_bricks")
    for x in range(256, 273):
        for z in range(-248, -245):
            if w.get(x, y, z) == "grass_block":
                w.set(x, y, z, "cobblestone" if rnd(x, y, z) < 0.5 else "dirt_path")
    for x in range(256, 261):
        for z in range(-248, -243):
            if w.get(x, y, z) == "grass_block":
                w.set(x, y, z, "cobblestone" if rnd(x, y, z) < 0.5 else "mossy_cobblestone")
    # stable lean-to against the west wall: x 250..254, z -250..-242
    sx0, sx1, sz0, sz1 = 250, 253, -251, -242
    for z in range(sz0, sz1 + 1):
        for x in range(sx0, sx1 + 1):
            w.set(x, y, z, "coarse_dirt" if rnd(x, y, z) < 0.5 else "dirt")
        if z % 3 == 0 or z in (sz0, sz1):
            w.fill(sx1, y + 1, z, sx1, y + 3, z, "dark_oak_log[axis=y]")
        else:
            w.set(sx1, y + 1, z, "dark_oak_fence")
        w.set(sx0, y + 1, z, "hay_block[axis=y]") if z % 2 else None
    w.set(sx1, y + 1, -246, "dark_oak_fence_gate[facing=east,open=false,in_wall=false,powered=false]")
    for z in range(sz0 - 1, sz1 + 2):
        w.set(sx0, y + 4, z, "dark_oak_planks")
        w.set(sx0 + 1, y + 4, z, stair("west", block="spruce_stairs"))
        w.set(sx0 + 2, y + 3, z, stair("west", block="spruce_stairs")) if False else None
        w.set(sx0 + 2, y + 4, z, stair("west", block="spruce_stairs"))
        w.set(sx1, y + 4, z, stair("west", block="spruce_stairs"))
        w.set(sx1 + 1, y + 3, z, stair("west", block="spruce_stairs"))
    for z in (sz0 + 2, sz1 - 2):
        w.set(sx0 + 1, y + 3, z, "lantern[hanging=true]")
    w.set(sx0 + 1, y + 1, sz0 + 1, "composter[level=3]") if False else None
    w.set(sx0, y + 1, sz0 + 3, "water_cauldron[level=3]")
    # smithy corner by the SW tower: anvil, grindstone, a forge (campfire in a brick hood)
    w.set(254, y + 1, -241, "anvil[facing=north]")
    w.set(256, y + 1, -241, "grindstone[face=floor,facing=north]")
    w.set(257, y + 1, -241, "smithing_table")
    w.fill(259, y + 1, -241, 260, y + 1, -241, "stone_bricks")
    w.set(259, y + 2, -241, "campfire[lit=true,signal_fire=false,facing=north]")
    w.fill(259, y + 3, -241, 260, y + 3, -241, stair("north", "top", "brick_stairs"))
    w.set(260, y + 2, -241, "barrel[facing=up,open=false]")
    # carts of barrels and hay by the gate
    for x, z, b in ((267, -245, "barrel[facing=up,open=false]"), (268, -245, "hay_block[axis=x]"),
                    (267, -244, "barrel[facing=north,open=false]"), (275, -244, "hay_block[axis=y]")):
        if level(x, z) is not None and w.get(x, level(x, z) + 1, z) in (None, "air"):
            w.set(x, level(x, z) + 1, z, b)
    # lamp posts in the bailey
    for x, z in ((262, -250), (266, -243), (255, -244)):
        w.fill(x, y + 1, z, x, y + 2, z, "dark_oak_fence")
        w.set(x, y + 3, z, "lantern[hanging=false]")


# ---------------------------------------------------------------- the inner ward: cherry garden
def cherry(w, x, y, z, h=4):
    w.fill(x, y + 1, z, x, y + h, z, "cherry_log[axis=y]")
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            for dy in (h - 1, h, h + 1):
                rr = abs(dx) + abs(dz)
                if (dy == h + 1 and rr > 1) or (dy == h - 1 and rr > 3) or rr > 3:
                    continue
                if rnd(x + dx, y + dy, z + dz, 5) < 0.12 and rr > 1:
                    continue
                if w.get(x + dx, y + dy, z + dz) in (None, "air"):
                    w.set(x + dx, y + dy, z + dz, "cherry_leaves[persistent=true]")
    for dx, dz in ((1, 1), (-1, 2), (2, -1), (-2, -1)):
        if w.get(x + dx, y + 1, z + dz) in (None, "air"):
            w.set(x + dx, y + 1, z + dz, "pink_petals[flower_amount=3,facing=north]")


def garden(w):
    y = YIN
    # path: from the grand stair north to the keep door, a cross path, a fountain at the crossing
    for z in range(-266, -253):
        for x in range(262, 265):
            w.set(x, y, z, "polished_andesite" if x == 263 else "stone_bricks")
    for x in range(251, 274):
        for z in (-261,):
            if w.get(x, y, z) == "grass_block":
                w.set(x, y, z, "dirt_path" if rnd(x, y, z) < 0.6 else "coarse_dirt")
    # the fountain at the crossing
    fx, fz = 263, -261
    for x in range(fx - 2, fx + 3):
        for z in range(fz - 2, fz + 3):
            edge = max(abs(x - fx), abs(z - fz)) == 2
            w.set(x, y, z, "stone_bricks" if edge else "water")
            w.set(x, y - 1, z, "stone_bricks")
            if edge:
                w.set(x, y + 1, z, "stone_brick_slab[type=bottom]")
    w.fill(fx, y, fz, fx, y + 2, fz, "chiseled_stone_bricks")
    w.set(fx, y + 3, fz, "water")
    w.set(fx, y - 1, fz, "sea_lantern")
    # flower beds either side, hedges along the edges
    flowers = ["pink_tulip", "white_tulip", "allium", "lily_of_the_valley", "oxeye_daisy", "cornflower", "peony"]
    for x in range(251, 274):
        for z in range(-266, -254):
            if w.get(x, y, z) != "grass_block" or w.get(x, y + 1, z) not in (None, "air"):
                continue
            if abs(x - fx) <= 3 and abs(z - fz) <= 3:
                continue
            r = rnd(x, y, z, 11)
            if (x in (258, 268)) and z % 2 == 0:
                w.set(x, y + 1, z, "azalea_leaves[persistent=true]" if r < 0.5 else "flowering_azalea_leaves[persistent=true]")
            elif r < 0.45:
                fl = flowers[int(r * 100) % len(flowers)]
                if fl == "peony":
                    w.set(x, y + 1, z, "peony[half=lower]")
                    w.set(x, y + 2, z, "peony[half=upper]")
                else:
                    w.set(x, y + 1, z, fl)
            elif r < 0.6:
                w.set(x, y + 1, z, "short_grass")
    for tx, tz in ((254, -264), (254, -257), (271, -257)):
        cherry(w, tx, y, tz)
    # benches facing the fountain
    for x in (260, 266):
        w.set(x, y + 1, fz, stair("east" if x < fx else "west", block="dark_oak_stairs"))
    for x, z in ((259, -258), (267, -258), (259, -265), (267, -265)):
        w.fill(x, y + 1, z, x, y + 2, z, "dark_oak_fence")
        w.set(x, y + 3, z, "lantern[hanging=false]")


def east_terraces(w):
    """An orchard and herb beds on the east terraces, a stair between each pair of levels."""
    for (x, z), L in LEVEL.items():
        if x < EAST_X or w.get(x, L, z) != "grass_block" or w.get(x, L + 1, z) not in (None, "air"):
            continue
        r = rnd(x, L, z, 21)
        if L == 117 and (x + z) % 2 == 0 and r < 0.5:
            w.set(x, L, z, "farmland[moisture=7]")
            w.set(x, L + 1, z, "wheat[age=7]" if r < 0.25 else "carrots[age=7]")
        elif r < 0.12:
            w.set(x, L + 1, z, "rose_bush[half=lower]")
            w.set(x, L + 2, z, "rose_bush[half=upper]")
        elif r < 0.3:
            w.set(x, L + 1, z, "short_grass")
    for tx, tz in ((279, -272), (281, -255), (278, -247)):
        L = level(tx, tz)
        if L is not None:
            w.fill(tx, L + 1, tz, tx, L + 3, tz, "oak_log[axis=y]")
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    for dy in (3, 4):
                        if abs(dx) + abs(dz) <= (3 if dy == 3 else 1) and w.get(tx + dx, L + dy, tz + dz) in (None, "air"):
                            w.set(tx + dx, L + dy, tz + dz, "oak_leaves[persistent=true]")


# ---------------------------------------------------------------- the approach
ROAD = [(271, -234), (271, -229), (282, -229), (290, -229)]


def road_cells():
    pts = []
    for (x0, z0), (x1, z1) in zip(ROAD, ROAD[1:]):
        n = max(abs(x1 - x0), abs(z1 - z0))
        for i in range(n):
            pts.append((x0 + (x1 - x0) * i // n, z0 + (z1 - z0) * i // n))
    pts.append(ROAD[-1])
    return pts


def approach(w):
    pts = road_cells()
    t = 122
    heights = []
    for (x, z) in pts:
        g = max(ground(x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1)) if False else ground(x, z)
        t = max(t - 1, min(t, g))
        heights.append(t)
    for i, ((x, z), t) in enumerate(zip(pts, heights)):
        nxt = pts[i + 1] if i + 1 < len(pts) else None
        prv = pts[i - 1] if i else (271, -235)
        dx, dz = x - prv[0], z - prv[1]
        sx, sz = abs(dz), abs(dx)      # sideways
        uphill = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[(dx, dz)]
        down = nxt is not None and heights[i + 1] < t
        for s in (-1, 0, 1):
            cx, cz = x + sx * s, z + sz * s
            g = ground(cx, cz)
            if g < t:   # causeway: solid near the ground, arches where it is tall
                high = t - g
                if high >= 4 and i % 4 != 0:
                    w.fill(cx, t - 2, cz, cx, t - 1, cz, brick)
                    w.set(cx, t - 3, cz, stair(uphill if i % 4 == 1 else OPP[uphill], "top"))
                else:
                    w.fill(cx, g - 1, cz, cx, t - 1, cz, lambda X, Y, Z: rubble(X, Y, Z) if Y <= g + 1 else brick(X, Y, Z))
            w.air(cx, t + 1, cz, cx, max(t + 3, g + 1), cz)
            if down:
                w.set(cx, t, cz, stair(uphill, block="stone_brick_stairs"))
            else:
                w.set(cx, t, cz, "stone_bricks" if s == 0 else "cobblestone")
        # parapets on both sides where it stands high, lamp posts every 5
        for s in (-2, 2):
            cx, cz = x + sx * s // 2 * 2, z + sz * s // 2 * 2
            g = ground(cx, cz)
            if g < t:
                if t - g >= 4 and i % 4 != 0:
                    w.fill(cx, t - 2, cz, cx, t, cz, brick)
                    w.set(cx, t - 3, cz, stair(uphill if i % 4 == 1 else OPP[uphill], "top"))
                else:
                    w.fill(cx, g - 1, cz, cx, t, cz, lambda X, Y, Z: rubble(X, Y, Z) if Y <= g + 1 else brick(X, Y, Z))
            w.set(cx, t + 1, cz, "stone_brick_wall")
            if i % 5 == 2:
                w.set(cx, t + 2, cz, "lantern[hanging=false]")
    # fill the arch piers' footings: every 4th cell is a solid pier (done above). Done.
    return heights


# ---------------------------------------------------------------- connections
FULL_NOT = ("air", "stairs", "slab", "wall", "fence", "pane", "bars", "door", "lantern", "torch", "carpet",
            "banner", "sign", "bed", "chain", "potted", "candle", "flower", "tulip", "allium", "daisy", "lily",
            "peony", "rose", "grass", "petals", "leaves", "campfire", "water", "chest", "anvil", "grindstone",
            "lectern", "cauldron", "rod", "wheat", "carrots", "farmland", "path", "bell", "cornflower")


def full(blk):
    return blk is not None and not any(k in blk.split("[")[0] for k in FULL_NOT)


def connect(w):
    for (lx, ly, lz), blk in list(w.b.blocks.items()):
        if "[" in blk:
            continue
        x, y, z = lx + OX, ly + OY, lz + OZ
        nb = {d: w.get(x + ox, y, z + oz) for d, (ox, oz) in OUT.items()}
        if blk.endswith("_wall"):
            con = {d: ("low" if (full(v) or (v or "").split("[")[0].endswith(("_wall", "fence_gate", "bars", "pane")))
                       else "none") for d, v in nb.items()}
            straight = (con["north"] == con["south"] == "low" and con["east"] == con["west"] == "none") or \
                       (con["east"] == con["west"] == "low" and con["north"] == con["south"] == "none")
            above = w.get(x, y + 1, z)
            up = "false" if straight and (above in (None, "air")) else "true"
            w.set(x, y, z, f"{blk}[north={con['north']},south={con['south']},east={con['east']},west={con['west']},up={up}]")
        elif blk.endswith("_fence"):
            con = {d: ("true" if (full(v) or (v or "").split("[")[0].endswith(("_fence", "fence_gate"))) else "false")
                   for d, v in nb.items()}
            w.set(x, y, z, f"{blk}[" + ",".join(f"{d}={c}" for d, c in con.items()) + "]")


# the cave system under the summit (castle_cave.json: flood fill of the cave air below the surface, from
# bridge.region): the castle's footings would close its mouths on the cliff into dark rooms, so it is filled
CAVE = [tuple(p) for p in json.loads((Path(__file__).parent / "castle_cave.json").read_text())
        if 244 <= p[0] <= 292 and -286 <= p[2] <= -228]   # only under the castle's own footprint
CAVE += [(296, 104, -279), (296, 105, -279), (296, 104, -278), (296, 105, -278)]   # a dark nook in the cliff below


# ---------------------------------------------------------------- build
def build():
    b = Build("castle")
    w = W(b)
    terraces(w)
    grand_stair(w)
    curtain(w)
    towers(w)
    gatehouse(w)
    keep(w)
    walk_doors(w)
    wall_lamps(w)
    bailey(w)
    garden(w)
    east_terraces(w)
    terrace_stairs(w)
    approach(w)
    for x, y, z, f in DOOR_FRONTS + [(263, 125, -267, "south"), (262, 125, -267, "south")]:
        w.set(x, y + 1, z, "air") if w.get(x, y + 1, z) not in ("air", None) and "stairs" not in w.get(x, y + 1, z) else None
        w.set(x, y + 2, z, "air")
        if w.get(x, y, z) in ("grass_block", "farmland[moisture=7]"):
            w.set(x, y, z, "dirt_path")
    for x, y, z in CAVE:      # the cave under the summit, filled (see CAVE)
        if w.get(x, y, z) is None:
            w.set(x, y, z, "stone")
    w.set(296, 105, -280, "lantern[hanging=false]")   # a lamp in the cliff gully below the NE tower
    for x, z in ((256, -285),):   # a lamp post on the plateau behind the keep (lights the nook under the bartizan)
        g = ground(x, z)
        w.fill(x, g + 1, z, x, g + 2, z, "dark_oak_fence")
        w.set(x, g + 3, z, "lantern[hanging=false]")
    for x, z in ((275, -266), (275, -270)):
        w.fill(x, 122, z, x, 122, z, "dark_oak_fence")
        w.set(x, 123, z, "lantern[hanging=false]")
    connect(w)
    return b


def grand_stair(w):
    """From the bailey (121) up to the garden (125): a 5-wide flight in the retaining wall, with cheeks
    and lamp posts."""
    for x in range(261, 266):
        for k in range(4):
            z = -253 + k
            y = 124 - k
            w.set(x, y, z, stair("north"))
            w.fill(x, 120, z, x, y - 1, z, brick)
            w.air(x, y + 1, z, x, y + 4, z)
        w.set(x, 125, -254, "stone_bricks")
        w.set(x, 126, -254, "air")
    for x in (260, 266):
        for k in range(4):
            z = -253 + k
            w.fill(x, 120, z, x, 125 - k, z, brick)
            w.set(x, 126 - k, z, "stone_brick_slab[type=bottom]") if False else None
        w.fill(x, 125, -254, x, 127, -254, brick)
        w.set(x, 128, -254, "lantern[hanging=false]")


def terrace_stairs(w):
    """A short flight wherever a terrace edge is chosen: found from the level map at fixed rows."""
    for z in (-270, -258, -246):
        for x in range(EAST_X - 1, CX1):
            a, c = level(x, z), level(x + 1, z)
            if a is None or c is None or c >= a:
                continue
            steps = a - c
            for zz in (z, z + 1):
                for k in range(steps):
                    xx = x + k
                    yy = a - k
                    if k == 0:
                        w.set(xx, yy, zz, stair("west"))
                        w.set(xx, yy + 1, zz, "air")
                    else:
                        w.set(xx, yy, zz, stair("west"))
                        w.fill(xx, c, zz, xx, yy - 1, zz, brick)
                        w.air(xx, yy + 1, zz, xx, yy + 3, zz)
            break


if __name__ == "__main__":
    for z in range(CZ0, CZ1 + 1, 2):
        print(z, "".join({125: "A", 121: "b", 117: "c"}.get(level(x, z), "?") for x in range(CX0, CX1 + 1)))
    b = build()
    print(len(b.blocks), b.bounds())
