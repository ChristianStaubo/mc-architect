"""The judge's hard half: checks on the blocks actually in the world, each one something a player
would notice. fail = the build is broken; warn = worth a look. Pure functions over a region dict
{(x, y, z): block-data string}, so tests can feed them hand-made grids."""

from collections import deque

DIRS = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
N6 = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]

PASSABLE = ("air", "short_grass", "tall_grass", "fern", "flower", "dandelion", "poppy", "tulip", "orchid",
            "allium", "bluet", "oxeye", "cornflower", "lily_of_the_valley", "dead_bush", "torch", "sign",
            "banner", "carpet", "button", "lever", "pressure_plate", "rail", "redstone_wire", "vine",
            "sugar_cane", "leaf_litter", "bush", "firefly", "moss_carpet", "ladder", "scaffolding")
# Light passes through these (everything else is treated as a full opaque block).
TRANSPARENT = PASSABLE + ("glass", "pane", "leaves", "stairs", "slab", "fence", "wall", "door", "trapdoor",
                          "lantern", "bed", "chest", "iron_bars", "ladder", "chain", "campfire", "candle",
                          "flower_pot", "head", "skull", "anvil", "bell", "end_rod", "lectern",
                          "enchanting_table", "brewing_stand", "cauldron", "hopper", "scaffolding", "water")
LIGHT = {"sea_lantern": 15, "glowstone": 15, "shroomlight": 15, "jack_o_lantern": 15, "froglight": 15,
         "beacon": 15, "lava": 15, "soul_lantern": 10, "lantern": 15, "soul_torch": 10, "soul_wall_torch": 10,
         "torch": 14, "end_rod": 14, "campfire": 15, "redstone_lamp": 15, "candle": 3}
NEEDS_LIT = ("campfire", "redstone_lamp", "candle")
# A mob can't spawn standing on these.
NO_SPAWN_FLOOR = ("glass", "pane", "leaves", "slab[type=bottom", "stairs", "fence", "wall", "carpet",
                  "bed", "chest", "barrier", "bedrock", "farmland", "dirt_path")


def parse(block):
    name, _, rest = block.replace("minecraft:", "").partition("[")
    props = dict(p.split("=", 1) for p in rest.rstrip("]").split(",") if "=" in p)
    return name, props


def name(block):
    return parse(block)[0]


def is_air(b):
    return b is None or name(b) in ("air", "cave_air", "void_air")


def passable(b):
    if b is None:
        return True
    n = name(b)
    return n in ("air", "cave_air", "void_air") or any(k in n for k in PASSABLE if k != "air")


def transparent(b):
    if b is None:
        return True
    n = name(b)
    return passable(b) or any(k in n for k in TRANSPARENT)


def emits(b):
    n, props = parse(b)
    for k, level in LIGHT.items():
        if k in n:
            if any(x in n for x in NEEDS_LIT) and props.get("lit") != "true":
                return 0
            if "candle" in n:
                return 3 * int(props.get("candles", "1"))
            return level
    return 0


def is_door(b):
    return b is not None and name(b).endswith("_door")


def standable(cells, p):
    """A mob or player fits here: two passable blocks over a solid one."""
    x, y, z = p
    below = cells.get((x, y - 1, z))
    return (passable(cells.get(p)) and not is_door(cells.get(p)) and passable(cells.get((x, y + 1, z)))
            and below is not None and not passable(below) and not is_door(below))


def flood(cells, starts, ok):
    seen = set(starts)
    q = deque(starts)
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in N6:
            n = (x + dx, y + dy, z + dz)
            if n in cells and n not in seen and ok(cells[n]):
                seen.add(n)
                q.append(n)
    return seen


def audit(cells, box):
    """cells: a region around the build (a margin of terrain included); box: (min, max) of the edit."""
    (x0, y0, z0), (x1, y1, z1) = box
    in_box = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 <= p[2] <= z1  # noqa: E731
    lo = tuple(min(p[i] for p in cells) for i in range(3))
    hi = tuple(max(p[i] for p in cells) for i in range(3))
    edge = lambda p: any(p[i] in (lo[i], hi[i]) for i in range(3))  # noqa: E731
    checks = []

    def add(check, level, msg, at=()):
        checks.append({"check": check, "level": level, "msg": msg, "count": len(at),
                       "at": [list(p) for p in sorted(at)[:5]]})

    # 1. floating: every non-air block must connect (through other blocks) to the ground below the box
    ground = [p for p, b in cells.items() if p[1] == lo[1] and not is_air(b)]
    held = flood(cells, ground, lambda b: not is_air(b))
    floating = [p for p, b in cells.items() if in_box(p) and not is_air(b) and p not in held]
    if floating:
        add("floating", "fail", f"{len(floating)} blocks float, connected to nothing on the ground", floating)

    # 2. doors: both halves, and a way through on both sides
    for p, b in cells.items():
        if not in_box(p) or not is_door(b):
            continue
        n, props = parse(b)
        if props.get("half") != "lower":
            continue
        up = cells.get((p[0], p[1] + 1, p[2]))
        if not is_door(up) or parse(up)[1].get("half") != "upper":
            add("door", "fail", f"door at {p} has no upper half", [p])
            continue
        d = DIRS[props["facing"]]
        for side, sign in (("outside", 1), ("inside", -1)):
            c = (p[0] + sign * d[0], p[1], p[2] + sign * d[2])
            here, above = cells.get(c), cells.get((c[0], c[1] + 1, c[2]))
            step = here is not None and ("stairs" in here or "slab[type=bottom" in here)  # a step up is fine
            if not ((passable(here) or step) and passable(above)):
                add("door", "fail", f"door at {p} is blocked on its {side} ({cells.get(c)})", [p])

    # 3. beds: head and foot together
    for p, b in cells.items():
        n, props = parse(b)
        if in_box(p) and n.endswith("_bed") and props.get("part") == "head":
            d = DIRS[props["facing"]]
            foot = cells.get((p[0] - d[0], p[1], p[2] - d[2]))
            if not foot or not name(foot).endswith("_bed") or parse(foot)[1].get("part") != "foot":
                add("bed", "fail", f"bed at {p} is missing its foot", [p])

    # 4. rooms. Indoor = a standing spot reachable (through doors) with a roof somewhere above it and a
    # wall or door in all four directions: a tower with an open stairwell to its roof is indoors, a porch
    # or a market stall is not. Reachable not at all = sealed.
    outside = flood(cells, [p for p, b in cells.items() if edge(p) and passable(b)], passable)
    doors = [p for p, b in cells.items() if is_door(b)]
    through = flood(cells, list(outside) + doors, lambda b: passable(b) or is_door(b))

    def covered(p):
        return any(not passable(cells.get((p[0], y, p[2]))) for y in range(p[1] + 2, y1 + 1))

    def walled(p):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, z = p[0] + dx, p[2] + dz
            while x0 <= x <= x1 and z0 <= z <= z1 and passable(cells.get((x, p[1], z))) \
                    and not is_door(cells.get((x, p[1], z))):
                x, z = x + dx, z + dz
            if not (x0 <= x <= x1 and z0 <= z <= z1):
                return False
        return True

    stand_inside = [p for p in through if in_box(p) and standable(cells, p) and covered(p) and walled(p)]
    sealed = [p for p, b in cells.items()
              if in_box(p) and passable(b) and p not in through and standable(cells, p)]
    if sealed:
        add("sealed", "fail", f"{len(sealed)} standing spots in rooms nobody can get into", sealed)
    if doors and not stand_inside:
        add("interior", "warn", "the doors lead nowhere enclosed: a hole in the roof or walls, or no room")

    # 5. light: no dark floor indoors (block light 0 = monsters spawn there, even in daylight)
    light = {}
    q = deque()
    for p, b in cells.items():
        e = emits(b)
        if e:
            light[p] = e
            q.append(p)
    while q:
        p = q.popleft()
        for dx, dy, dz in N6:
            n = (p[0] + dx, p[1] + dy, p[2] + dz)
            if n in cells and transparent(cells[n]) and light.get(n, 0) < light[p] - 1:
                light[n] = light[p] - 1
                q.append(n)
    dark = [p for p in stand_inside if light.get(p, 0) == 0
            and not any(k in cells[(p[0], p[1] - 1, p[2])] for k in NO_SPAWN_FLOOR)]
    if dark:
        add("dark", "fail", f"{len(dark)} indoor floor spots at light 0: mobs can spawn inside", dark)

    # 6. glass panes that connect to nothing
    loose = []
    for p, b in cells.items():
        n, props = parse(b)
        if in_box(p) and n.endswith("pane"):
            for side, d in DIRS.items():
                if props.get(side) == "true" and is_air(cells.get((p[0] + d[0], p[1], p[2] + d[2]))):
                    loose.append(p)
                    break
    if loose:
        add("pane", "warn", f"{len(loose)} glass panes connect to empty air", loose)

    fails = sum(c["level"] == "fail" for c in checks)
    warns = sum(c["level"] == "warn" for c in checks)
    return {"checks": checks, "fails": fails, "warns": warns,
            "stats": {"blocks": sum(1 for p, b in cells.items() if in_box(p) and not is_air(b)),
                      "indoor_floor": len(stand_inside), "doors": sum(1 for p in doors if in_box(p)) // 2,
                      # storeys: levels with a real floor (4+ standing spots), not every stair step
                      "indoor_levels": sorted(y for y in {p[1] for p in stand_inside}
                                              if sum(1 for p in stand_inside if p[1] == y) >= 4)}}
