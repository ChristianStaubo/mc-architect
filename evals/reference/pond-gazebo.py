"""Garden gazebo by the pond: an octagonal oak gazebo on a raised stone-brick plinth on the pond's east
bank, eight stripped-oak posts with arched stair brackets under a dark-oak cone roof and finial, benches
on its north and east sides, a hanging lantern. A low oak jetty runs west from its open side out over
the water (no posts in the pond: the deck sits one block above the water and is carried by the bank),
with fence rails, lantern posts and a bench at the end. Flower beds ring the plinth; a gravel path leads
in from the south. Local (0,0) = world (264, 224); local y 0 = world 63 (the bank; water is at 62)."""
from architect.build import Build
from architect.parts import cone_roof

PLACE = ["--at", "264,224", "--y", "63"]

CX, CZ = 15, 12          # gazebo centre (world 279, 236)
POST_TOP = 5
ROOF_Y = 6
FLOWERS = ["poppy", "dandelion", "azure_bluet", "cornflower", "oxeye_daisy", "allium", "lily_of_the_valley"]
STONE = ["stone_bricks", "stone_bricks", "mossy_stone_bricks", "stone_bricks", "cracked_stone_bricks"]


def edge(cells):
    s = set(cells)
    return [(x, z) for (x, z) in cells if any((x + dx, z + dz) not in s for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]


def toward(x, z):
    dx, dz = CX - x, CZ - z
    return ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")


def connect(b, kinds=("oak_fence",)):
    """Fence connections to neighbouring fences and solid blocks."""
    for (x, y, z), blk in list(b.blocks.items()):
        n = blk.split("[")[0]
        if n not in kinds:
            continue
        st = []
        for side, (dx, dz) in (("east", (1, 0)), ("north", (0, -1)), ("south", (0, 1)), ("west", (-1, 0))):
            o = b.blocks.get((x + dx, y, z + dz), "air").split("[")[0]
            ok = o == n or not (o == "air" or any(k in o for k in ("stairs", "slab", "lantern", "door", "poppy",
                                                                      "dandelion", "bluet", "cornflower", "daisy",
                                                                      "allium", "lily", "bush", "leaves")))
            st.append(f"{side}={'true' if ok else 'false'}")
        b.set(x, y, z, f"{n}[{','.join(st)},waterlogged=false]")


def build():
    b = Build("pond-gazebo")
    o3 = [(CX + dx, CZ + dz) for dx in range(-3, 4) for dz in range(-3, 4) if abs(dx) + abs(dz) <= 5]
    o4 = [(CX + dx, CZ + dz) for dx in range(-4, 5) for dz in range(-4, 5) if abs(dx) + abs(dz) <= 6]
    rim = edge(o3)                                  # the gazebo's perimeter (posts, benches, rails)
    bed = [p for p in o4 if p not in set(o3)]       # the ring around the plinth
    west_in = {(CX - 4, CZ + d) for d in (-1, 0, 1)}
    south_in = {(CX + d, CZ + 4) for d in (-1, 0, 1)}

    # ---- plinth: stone-brick base at ground level, raised oak floor with a stone curb
    for i, (x, z) in enumerate(o4):
        b.set(x, 0, z, STONE[(x * 3 + z * 7) % len(STONE)] if (x, z) in set(o3) or (x, z) in west_in | south_in
              else "grass_block")
    for (x, z) in o3:
        b.set(x, 1, z, "stone_bricks" if (x, z) in set(rim) else "oak_planks")
    b.set(CX, 1, CZ, "chiseled_stone_bricks")
    for (x, z) in bed:
        if (x, z) in west_in | south_in:
            b.set(x, 1, z, f"stone_brick_stairs[facing={toward(x, z)},half=bottom,shape=straight]")
        elif (x * 5 + z * 3) % 4 == 0:
            b.set(x, 1, z, "azalea" if (x + z) % 3 == 0 else "bush")
        else:
            b.set(x, 1, z, FLOWERS[(x * 7 + z * 11) % len(FLOWERS)])

    # ---- posts at the eight octagon corners, arched brackets between them
    corners = [(x, z) for (x, z) in rim if abs(x - CX) + abs(z - CZ) == 5]
    for (x, z) in corners:
        b.fill(x, 2, z, x, POST_TOP, z, "stripped_oak_log[axis=y]")
    for (x, z) in rim:
        if (x, z) in corners:
            continue
        out = {"east": "west", "west": "east", "north": "south", "south": "north"}[toward(x, z)]
        b.set(x, POST_TOP, z, f"oak_stairs[facing={toward(x, z)},half=top,shape=straight]")
        dx, dz = x - CX, z - CZ
        side = "N" if dz == -3 else "S" if dz == 3 else "W" if dx == -3 else "E"
        if side in "NE":   # benches, backs to the outside: you sit facing the pond and the centre
            b.set(x, 2, z, f"oak_stairs[facing={out},half=bottom,shape=straight]")
        # W (jetty) and S (path) sides stay open
    # ---- roof: dark oak cone with an overhang, a finial on top
    cone_roof(b, CX, CZ, ROOF_Y, 3, "dark_oak_stairs", top="dark_oak_planks")
    b.set(CX, ROOF_Y + 5, CZ, "oak_fence")
    b.set(CX, ROOF_Y + 6, CZ, "lantern[hanging=false]")
    # an open vault under the cone: a fence drop from the apex to a hanging lantern
    b.fill(CX, POST_TOP, CZ, CX, ROOF_Y + 3, CZ, "oak_fence")
    b.set(CX, POST_TOP - 1, CZ, "lantern[hanging=true]")

    # ---- jetty: oak deck one block above the water, log rims, rails, lantern posts, bench at the end
    JX1, JX2 = 6, CX - 5
    for x in range(JX1, JX2 + 1):
        b.set(x, 0, CZ - 1, "stripped_oak_log[axis=x]")
        b.set(x, 0, CZ, "oak_planks")
        b.set(x, 0, CZ + 1, "stripped_oak_log[axis=x]")
        b.set(x, 1, CZ - 1, "oak_fence")
        b.set(x, 1, CZ + 1, "oak_fence")
    b.set(JX1 - 1, 0, CZ, "oak_slab[type=bottom]")            # a low step at the tip
    for z in (CZ - 1, CZ + 1):
        b.set(JX1, 1, z, "stripped_oak_log[axis=y]")
        b.set(JX1, 2, z, "lantern[hanging=false]")
        b.set(JX2, 1, z, "stripped_oak_log[axis=y]")
        b.set(JX2, 2, z, "lantern[hanging=false]")
    b.set(JX1 + 1, 1, CZ, "oak_stairs[facing=east,half=bottom,shape=straight]")  # bench looking out over the pond

    # ---- gravel path from the south entrance to the plot edge, lamp post beside it
    for z in range(CZ + 5, 20):
        for x in (CX - 1, CX, CX + 1):
            b.set(x, 0, z, "gravel" if (x + z) % 3 else "coarse_dirt")
    b.set(CX + 2, 1, CZ + 6, "stripped_oak_log[axis=y]")
    b.set(CX + 2, 2, CZ + 6, "oak_fence")
    b.set(CX + 2, 3, CZ + 6, "lantern[hanging=false]")
    connect(b)
    return b
