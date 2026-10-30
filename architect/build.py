"""A build: a sparse grid of blocks in local coordinates (y = 0 is the ground floor), plus the payload
the bridge's /place takes. Block names are Minecraft block-data strings ("oak_stairs[facing=north]");
the "minecraft:" prefix is optional."""

import importlib.util
from collections import Counter
from pathlib import Path

from .blocks import name


def _states(block):
    """Python's True/False written into block states (lakeside: spruce_fence[north=False]) become the
    lowercase the server wants."""
    if "[" in block and ("=True" in block or "=False" in block):
        block = block.replace("=True", "=true").replace("=False", "=false")
    return block


class Build:
    def __init__(self, name="build"):
        self.name = name
        self.blocks = {}
        self.entities = []  # (x, y, z, type): summoned after the blocks are placed (boats, armour stands)
        self.signs = []     # (x, y, z, [lines], side): text written into signs after placing

    def entity(self, x, y, z, kind):
        self.entities.append((x, y, z, kind))

    def sign(self, x, y, z, block, lines, side="front"):
        """A sign block with up to 4 lines of text (e.g. a tavern's name)."""
        self.set(x, y, z, block)
        self.signs.append((x, y, z, list(lines)[:4], side))

    def set(self, x, y, z, block):
        self.blocks[(x, y, z)] = _states(block)

    def get(self, x, y, z):
        return self.blocks.get((x, y, z))

    def fill(self, x1, y1, z1, x2, y2, z2, block):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.blocks[(x, y, z)] = _states(block)

    def bounds(self):
        xs, ys, zs = zip(*self.blocks)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def footprint(self):
        return {(x, z) for (x, y, z) in self.blocks}

    def counts(self):
        return dict(Counter(name(b) for b in self.blocks.values()).most_common())


def payload(cells, label="build"):
    """{(x, y, z): block or None} in world coordinates -> the /place body. Cells not listed are left alone."""
    xs, ys, zs = zip(*cells)
    lo = (min(xs), min(ys), min(zs))
    size = (max(xs) - lo[0] + 1, max(ys) - lo[1] + 1, max(zs) - lo[2] + 1)
    palette, index, rle = [None], {None: 0}, []
    value, count = -1, 0
    for y in range(lo[1], lo[1] + size[1]):
        for z in range(lo[2], lo[2] + size[2]):
            for x in range(lo[0], lo[0] + size[0]):
                b = cells.get((x, y, z))
                if b is not None and b not in index:
                    index[b] = len(palette)
                    palette.append(b)
                v = index[b]
                if v == value:
                    count += 1
                else:
                    if count:
                        rle += [value, count]
                    value, count = v, 1
    rle += [value, count]
    return {"origin": list(lo), "size": list(size), "palette": palette, "rle": rle, "label": label}


def load(path):
    """Run a plan file's build(); its optional PLACE (the `mc place` arguments a reference plan goes on
    its task's plot with) rides along as build.place_args."""
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    b = mod.build()
    b.place_args = getattr(mod, "PLACE", [])
    return b


def centre(v):
    """A coordinate for a summon or entity selector: a whole block's centre (12 -> "12.5"), or as given
    when the plan already chose a spot inside the block (6.25 stays "6.25")."""
    return f"{v}.5" if isinstance(v, int) else f"{v:g}"
