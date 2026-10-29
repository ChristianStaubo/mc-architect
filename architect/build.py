"""A build: a sparse grid of blocks in local coordinates (y = 0 is the ground floor), plus the payload
the bridge's /place takes. Block names are Minecraft block-data strings ("oak_stairs[facing=north]");
the "minecraft:" prefix is optional."""

AIR = "air"


class Build:
    def __init__(self, name="build"):
        self.name = name
        self.blocks = {}

    def set(self, x, y, z, block):
        self.blocks[(x, y, z)] = block

    def get(self, x, y, z):
        return self.blocks.get((x, y, z))

    def fill(self, x1, y1, z1, x2, y2, z2, block):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.blocks[(x, y, z)] = block

    def bounds(self):
        xs, ys, zs = zip(*self.blocks)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def footprint(self):
        return {(x, z) for (x, y, z) in self.blocks}

    def counts(self):
        out = {}
        for b in self.blocks.values():
            k = b.split("[")[0]
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))


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
