"""What a block-data string means: its name, its properties, and the categories the rest of the code
asks about (air, water, tree, plant). One place, cached: a region has millions of cells but only tens
of distinct block strings, and the renderer, the audit, terrain and placement all ask the same questions."""

from functools import lru_cache

AIR = frozenset(("air", "cave_air", "void_air"))
# Small plants you walk through and see past (not drawn, don't block a path or the light).
PLANTS = ("short_grass", "tall_grass", "fern", "flower", "dandelion", "poppy", "tulip", "orchid", "allium",
          "bluet", "oxeye", "cornflower", "lily_of_the_valley", "dead_bush", "seagrass", "kelp", "vine",
          "bush", "sugar_cane", "moss_carpet", "leaf_litter", "firefly")
TREE = ("_log", "_leaves", "vine", "bee_nest", "_wood")


@lru_cache(maxsize=4096)
def parse(block):
    """("oak_stairs", {"facing": "north", ...}) from "minecraft:oak_stairs[facing=north,...]"."""
    name, _, rest = block.replace("minecraft:", "").partition("[")
    props = dict(p.split("=", 1) for p in rest.rstrip("]").split(",") if "=" in p)
    return name, props


def name(block):
    return parse(block)[0]


def is_air(block):
    return block is None or name(block) in AIR


@lru_cache(maxsize=4096)
def is_plant(block):
    n = name(block)
    return any(k in n for k in PLANTS)


def is_water(block):
    return name(block) == "water"


@lru_cache(maxsize=4096)
def is_tree(block):
    n = name(block)
    return any(k in n for k in TREE)
