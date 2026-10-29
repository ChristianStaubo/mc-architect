"""Lighthouse on the point: a round white-and-red banded tower (radius 3) on the north end of the land,
spiral stair round a central column up to a glazed lantern room with a sea-lantern lamp, a gallery deck
with iron railings on a corbel, and a cone cap. A small gabled keeper's room joins its south side; door
east to the land, a rowing boat moored in the shallows. Local (0,0) = world (-289, 448)."""
from architect.build import Build
from architect.parts import cone_roof, door, gable_roof, round_tower, spiral_stairs, window

PLACE = ["--at", "-289,448", "--y", "63"]

CX, CZ = 4, 4        # tower centre
R = 3                # tower radius
TOP = 20             # gallery / lantern-room floor
WHITE, RED = "white_concrete", "red_concrete"
ROOF = "red_nether_brick_stairs"
BASE = "stone_bricks"


def ring(r, cx=CX, cz=CZ):
    out = []
    for x in range(cx - r - 1, cx + r + 2):
        for z in range(cz - r - 1, cz + r + 2):
            d = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
            if r - 0.5 <= d < r + 0.5:
                out.append((x, z))
    return out


def disk(r, cx=CX, cz=CZ):
    return [(x, z) for x in range(cx - r - 1, cx + r + 2) for z in range(cz - r - 1, cz + r + 2)
            if ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5 < r + 0.5]


def toward(x, z, cx=CX, cz=CZ):
    dx, dz = cx - x, cz - z
    return ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")


def connect(b, kinds=("iron_bars",)):
    """Set the side connections of bars/fences to whatever solid or same-kind block is next to them."""
    for (x, y, z), blk in list(b.blocks.items()):
        n = blk.split("[")[0]
        if n not in kinds:
            continue
        st = []
        for side, (dx, dz) in (("north", (0, -1)), ("south", (0, 1)), ("east", (1, 0)), ("west", (-1, 0))):
            o = b.blocks.get((x + dx, y, z + dz), "air")
            on = o.split("[")[0]
            ok = on == n or not (on == "air" or "stairs" in on or "slab" in on or "lantern" in on or "door" in on)
            st.append(f"{side}={'true' if ok else 'false'}")
        b.set(x, y, z, f"{n}[{','.join(st)},waterlogged=false]")


def build():
    b = Build("lighthouse")

    # ---- keeper's room (south of the tower), built first so the tower cuts through its north end
    KX1, KZ1, KX2, KZ2 = 3, 7, 7, 13
    b.fill(KX1, -1, KZ1, KX2, -1, KZ2, BASE)
    b.fill(KX1 + 1, 0, KZ1 + 1, KX2 - 1, 0, KZ2 - 1, "spruce_planks")
    for x in range(KX1, KX2 + 1):
        for z in range(KZ1, KZ2 + 1):
            if x in (KX1, KX2) or z in (KZ1, KZ2):
                b.set(x, 0, z, BASE)
                b.set(x, 1, z, "mossy_stone_bricks" if (x + z) % 4 == 0 else BASE)
                b.fill(x, 2, z, x, 3, z, "white_concrete" if (x * 3 + z) % 5 else "calcite")
                b.set(x, 4, z, "spruce_log[axis=x]" if z in (KZ1, KZ2) else "spruce_log[axis=z]")
    for (x, z) in ((KX1, KZ2), (KX2, KZ2), (KX2, KZ1), (KX1, KZ1)):
        b.fill(x, 1, z, x, 4, z, "spruce_log[axis=y]")
    b.fill(KX2, 1, 10, KX2, 3, 10, "air")
    b.fill(KX1 + 1, 1, KZ1 + 1, KX2 - 1, 4, KZ2 - 1, "air")
    gable_roof(b, KX1, KZ1, KX2, KZ2, 4, ROOF, "red_terracotta", ridge="z", overhang=1, end_overhang=1)
    for (x, y, z) in list(b.blocks):
        if z < KZ1:
            del b.blocks[(x, y, z)]
    # door east to the land, windows, shutters
    door(b, KX2, 1, 10, facing="east", wood="spruce")
    b.set(KX2 + 1, 3, 9, "lantern[hanging=false]") if False else None
    b.set(KX2, 3, 10, "spruce_planks")
    window(b, KX1, 2, 9, along="z", width=2, height=1)
    window(b, KX1, 2, 9, along="z", width=2, height=1)
    for z in (9, 10):
        b.set(KX1, 2, z, f"glass_pane[east=false,north={'false' if z == 9 else 'true'},south={'true' if z == 9 else 'false'},west=false]")
    b.set(KX1, 3, 9, "glass_pane[east=false,north=false,south=true,west=false]")
    b.set(KX1, 3, 10, "glass_pane[east=false,north=true,south=false,west=false]")
    for z in (8, 11):
        b.set(KX1 - 1, 2, z, "spruce_trapdoor[facing=west,half=bottom,open=true]")
        b.set(KX1 - 1, 3, z, "spruce_trapdoor[facing=west,half=bottom,open=true]")
    window(b, 5, 2, KZ2, along="x", height=2)
    b.set(KX2, 2, 12, "glass_pane[east=false,north=true,south=true,west=false]")
    # furniture
    b.set(4, 1, 12, "red_bed[facing=south,part=head,occupied=false]")
    b.set(4, 1, 11, "red_bed[facing=south,part=foot,occupied=false]")
    b.set(6, 1, 12, "chest[facing=north,type=single,waterlogged=false]")
    b.set(6, 1, 8, "barrel[facing=up,open=false]")
    b.set(6, 2, 8, "lantern[hanging=false]")
    b.set(4, 3, 9, "spruce_trapdoor[facing=east,half=top,open=false]") if False else None
    b.set(5, 1, 12, "crafting_table")
    b.set(4, 4, 10, "air")
    b.set(5, 6, 10, "lantern[hanging=true]") if False else None
    b.set(5, 1, 9, "white_carpet") if False else None
    b.set(5, 0, 10, "spruce_planks")
    b.set(5, 1, 10, "red_carpet")
    b.set(5, 1, 11, "red_carpet")

    # ---- the tower
    for (x, z) in disk(R):
        b.set(x, -1, z, BASE)
        b.set(x, 0, z, BASE)
    round_tower(b, CX, CZ, 1, TOP - 1, R, WHITE)
    for (x, z) in ring(R):
        for y in range(1, TOP):
            if y <= 2:
                blk = "mossy_stone_bricks" if (x + z + y) % 3 == 0 else BASE
            elif 7 <= y <= 9 or 14 <= y <= 16:
                blk = RED
            else:
                blk = "calcite" if (x * 5 + y * 3 + z) % 7 == 0 else WHITE
            b.set(x, y, z, blk)
    # rocky skirt in the shallows round the base
    for (x, z) in ring(R + 1):
        if x <= 2 or z <= 1:
            b.set(x, -1, z, ("cobblestone", "mossy_cobblestone", "stone", "andesite")[(x * 7 + z * 3) % 4])
            if (x + z) % 3 == 0:
                b.set(x, 0, z, ("mossy_cobblestone", "cobblestone")[(x + z) % 2])
    # arch into the keeper's room
    b.fill(CX, 1, 7, CX, 2, 7, "air")
    b.set(CX, 3, 7, "stone_brick_stairs[facing=north,half=top,shape=straight]") if False else None
    # central column, spiral stair round it
    b.fill(CX, 1, CZ, CX, TOP - 1, CZ, BASE)
    for (x, z) in disk(R):  # gallery / lantern floor
        b.set(x, TOP, z, "polished_andesite")
    spiral_stairs(b, CX - 1, CZ - 1, CX + 1, CZ + 1, 1, TOP, "stone_brick_stairs", "polished_andesite", start=5)
    # inside lights (torches on the outer wall, in the gap round the stair)
    for (x, z, y, f) in ((2, 4, 2, "east"), (6, 4, 5, "west"), (4, 2, 9, "south"), (2, 4, 12, "east"),
                         (6, 4, 15, "west"), (4, 2, 18, "south"), (6, 4, 1, "west")):
        b.set(x, y, z, f"wall_torch[facing={f}]")
    # slit windows up the tower
    for (x, z, y, al) in ((4, 1, 4, "x"), (7, 4, 8, "z"), (1, 4, 10, "z"), (4, 1, 13, "x"), (7, 4, 17, "z"),
                          (1, 4, 17, "z"), (4, 7, 11, "x")):
        window(b, x, y, z, along=al, height=2)

    # ---- corbel, gallery deck, railing
    for (x, z) in ring(R + 1):
        b.set(x, TOP - 1, z, f"{ROOF}[facing={toward(x, z)},half=top,shape=straight]")
        b.set(x, TOP, z, "polished_andesite")
        b.set(x, TOP + 1, z, "iron_bars")
    # lantern room: glass ring, door to the gallery, the lamp
    cone_roof(b, CX, CZ, TOP + 4, 2, ROOF, top="red_nether_bricks")
    for (x, z) in ring(2):
        b.fill(x, TOP + 1, z, x, TOP + 4, z, "glass")
    for (x, z) in ((2, 2), (6, 2), (2, 6), (6, 6)):  # dark posts at the gallery corners
        b.set(x, TOP + 1, z, "polished_andesite")
    door(b, CX, TOP + 1, CZ - 2, facing="north", wood="spruce")
    b.fill(CX, TOP + 1, CZ, CX, TOP + 3, CZ, "sea_lantern")
    b.set(CX, TOP + 6, CZ, "lantern[hanging=true]")
    b.set(CX, TOP + 8, CZ, "lightning_rod[facing=up,powered=false,waterlogged=false]")
    connect(b)

    # ---- outside: path, crates, boat
    for z in range(8, 16):
        b.set(8, 0, z, "gravel" if z % 3 else "cobblestone")
    b.set(8, 0, 10, "stone_bricks")
    b.set(8, 1, 12, "barrel[facing=up,open=false]")
    b.set(8, 1, 13, "barrel[facing=up,open=false]")
    b.set(8, 2, 13, "lantern[hanging=false]")
    b.set(8, 1, 8, "spruce_fence")
    b.set(8, 2, 8, "lantern[hanging=false]")
    b.entity(0, 0, 11, "oak_boat")
    return b
