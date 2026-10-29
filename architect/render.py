"""Pictures of blocks without a game client: an isometric view and a top-down map, written as PNGs with
the standard library only. Colours come from block names (a rough palette, not textures), which is
enough for the agent and the judge to see shape, proportion and materials."""

import struct
import zlib

# First matching substring wins; order specific before general.
COLORS = [
    ("water", (52, 92, 196)), ("lava", (220, 100, 20)), ("glass_pane", (190, 220, 235)),
    ("glass", (200, 228, 240)), ("grass_block", (95, 159, 53)), ("dirt_path", (148, 122, 65)),
    ("podzol", (90, 63, 28)), ("mud", (60, 57, 60)), ("dirt", (134, 96, 67)),
    ("red_sand", (190, 102, 33)), ("sandstone", (216, 203, 155)), ("sand", (219, 207, 163)),
    ("gravel", (131, 127, 126)), ("snow", (240, 248, 248)), ("ice", (145, 183, 253)),
    ("leaves", (60, 110, 40)), ("cherry", (226, 178, 172)), ("dark_oak", (66, 43, 20)),
    ("spruce", (114, 84, 48)), ("birch", (196, 176, 118)), ("jungle", (160, 115, 80)),
    ("acacia", (168, 90, 50)), ("mangrove", (117, 54, 48)), ("bamboo", (194, 173, 80)),
    ("crimson", (101, 48, 70)), ("warped", (43, 104, 99)), ("oak_log", (109, 85, 50)),
    ("oak", (162, 130, 78)), ("deepslate", (80, 80, 82)), ("cobblestone", (122, 122, 122)),
    ("mossy", (100, 118, 80)), ("stone_brick", (122, 121, 122)), ("bricks", (150, 97, 83)),
    ("brick", (150, 97, 83)), ("andesite", (136, 136, 137)), ("diorite", (188, 188, 189)),
    ("granite", (149, 103, 85)), ("tuff", (108, 109, 102)), ("calcite", (223, 224, 220)),
    ("blackstone", (42, 36, 41)), ("basalt", (80, 81, 86)), ("quartz", (235, 229, 222)),
    ("terracotta", (152, 94, 67)), ("white", (234, 236, 236)), ("black", (25, 25, 29)),
    ("red", (160, 39, 34)), ("blue", (53, 57, 157)), ("yellow", (248, 197, 39)),
    ("green", (84, 109, 27)), ("lantern", (250, 200, 90)), ("torch", (250, 200, 90)),
    ("coal", (40, 40, 40)), ("iron", (200, 200, 200)), ("copper", (192, 107, 79)),
    ("stone", (125, 125, 125)), ("log", (109, 85, 50)), ("planks", (162, 130, 78)),
]
# Not drawn, and they don't hide what's behind them.
SKIP = ("short_grass", "tall_grass", "fern", "flower", "dandelion", "poppy", "tulip", "orchid",
        "allium", "azure_bluet", "oxeye", "cornflower", "lily_of_the_valley", "dead_bush", "seagrass",
        "kelp", "vine", "bush", "sugar_cane", "moss_carpet", "leaf_litter", "firefly")


def block_name(block):
    return block.split("[")[0].replace("minecraft:", "")


def color(block):
    name = block_name(block)
    for key, rgb in COLORS:
        if key in name:
            return rgb
    h = zlib.crc32(name.encode())
    return (90 + h % 120, 90 + (h >> 8) % 120, 90 + (h >> 16) % 120)


def skipped(block):
    name = block_name(block)
    return name in ("air", "cave_air", "void_air") or any(s in name for s in SKIP)


def shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


def write_png(path, width, height, pixels):
    """pixels: bytearray of RGB, row-major."""
    raw = b"".join(b"\x00" + bytes(pixels[y * width * 3:(y + 1) * width * 3]) for y in range(height))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))


def _sprite(t):
    """Pixel offsets of one isometric block, tile size t: the top rhombus, the left (+z) and right (+x)
    faces. The block is 2t wide and 2t tall; (0, 0) is its top-left corner."""
    top, left, right = [], [], []
    for py in range(2 * t):
        for px in range(2 * t):
            cx = abs(px + 0.5 - t)  # distance from the block's vertical centre line
            edge = t - cx / 2  # the top rhombus's lower edge: lowest in the middle
            if py < t and cx <= t - 2 * abs(py + 0.5 - t / 2) + 1:
                top.append((px, py))
            elif edge - 0.5 <= py < edge - 0.5 + t:  # below it: two parallelograms
                (left if px < t else right).append((px, py))
    return top, left, right


def iso(cells, path, tile=8, background=(205, 222, 235)):
    """Isometric picture of {(x, y, z): block}, viewed from the south-east (+x, +z) and above."""
    solid = {p: b for p, b in cells.items() if not skipped(b)}
    if not solid:
        raise ValueError("nothing to draw")
    xs, ys, zs = zip(*solid)
    x0, z0, y1 = min(xs), min(zs), max(ys)
    sx = lambda x, z: (x - x0 - (z - z0)) * tile  # noqa: E731
    sy = lambda x, y, z: ((x - x0) + (z - z0)) * tile // 2 + (y1 - y) * tile  # noqa: E731
    pts = [(sx(x, z), sy(x, y, z)) for x, y, z in solid]
    minx, miny = min(p[0] for p in pts), min(p[1] for p in pts)
    width = max(p[0] for p in pts) - minx + 2 * tile
    height = max(p[1] for p in pts) - miny + 2 * tile
    pad = tile * 2
    width, height = width + 2 * pad, height + 2 * pad
    px = bytearray(bytes(background) * (width * height))
    top, left, right = _sprite(tile)
    order = sorted(solid, key=lambda p: (p[0] + p[2], p[1], p[0]))
    for (x, y, z) in order:
        b = solid[(x, y, z)]
        c = color(b)
        ox, oy = sx(x, z) - minx + pad, sy(x, y, z) - miny + pad
        faces = []
        if (x, y + 1, z) not in solid:
            faces.append((top, shade(c, 1.0)))
        if (x, y, z + 1) not in solid:
            faces.append((left, shade(c, 0.78)))
        if (x + 1, y, z) not in solid:
            faces.append((right, shade(c, 0.6)))
        for pixels, rgb in faces:
            for dx, dy in pixels:
                i = ((oy + dy) * width + ox + dx) * 3
                px[i:i + 3] = bytes(rgb)
    write_png(path, width, height, px)
    return width, height


def top_down(columns, path, scale=4):
    """Map of {(x, z): (top_y, top_block)}: colour by block, brightness by height, north up."""
    xs, zs = zip(*columns)
    x0, z0 = min(xs), min(zs)
    w, d = max(xs) - x0 + 1, max(zs) - z0 + 1
    ys = [v[0] for v in columns.values()]
    lo, hi = min(ys), max(ys)
    px = bytearray(w * scale * d * scale * 3)
    for (x, z), (y, b) in columns.items():
        f = 0.7 + 0.5 * ((y - lo) / (hi - lo) if hi > lo else 0.5)
        # a little hill-shading: darker when the column to the north is higher
        north = columns.get((x, z - 1))
        if north and north[0] > y:
            f *= 0.85
        rgb = bytes(shade(color(b), f))
        for dz in range(scale):
            row = ((z - z0) * scale + dz) * w * scale
            for dx in range(scale):
                i = (row + (x - x0) * scale + dx) * 3
                px[i:i + 3] = rgb
    write_png(path, w * scale, d * scale, px)
    return w * scale, d * scale
