"""Pictures of blocks without a game client: an isometric view and a top-down map, written as PNGs with
the standard library only. Colours come from block names (a rough palette, not textures), which is
enough for the agent and the judge to see shape, proportion and materials."""

import struct
import zlib
from functools import lru_cache

from .blocks import is_air, is_plant
from .blocks import name as block_name  # noqa: F401  (re-exported: render.block_name)

# First matching substring wins; order specific before general.
# The 16 dye colours (wool, carpet, concrete, banners, beds, stained glass...), two-word ones before the
# words they contain: orange wool drew green and light blue drew blue (Riverford's awnings).
DYES = [(f"{d}_", rgb) for d, rgb in (
    ("light_blue", (58, 175, 217)), ("light_gray", (142, 142, 134)), ("white", (234, 236, 236)),
    ("orange", (240, 118, 19)), ("magenta", (189, 68, 179)), ("yellow", (248, 197, 39)), ("lime", (112, 185, 25)),
    ("pink", (237, 141, 172)), ("gray", (62, 68, 71)), ("cyan", (21, 137, 145)), ("purple", (121, 42, 172)),
    ("blue", (53, 57, 157)), ("brown", (114, 71, 40)), ("green", (84, 109, 27)), ("red", (160, 39, 34)),
    ("black", (20, 21, 25)))]
COLORS = [
    # copper's ages first: "weathered_copper" contains "red_" and drew red
    ("oxidized", (82, 162, 132)), ("weathered", (108, 153, 110)), ("exposed", (161, 125, 103)),
    ("water", (52, 92, 196)), ("lava", (220, 100, 20)), ("glass_pane", (190, 220, 235)),
    ("glass", (200, 228, 240)), ("grass_block", (95, 159, 53)), ("dirt_path", (148, 122, 65)),
    ("podzol", (90, 63, 28)), ("mud_brick", (137, 103, 79)), ("packed_mud", (142, 106, 79)), ("mud", (60, 57, 60)), ("dirt", (134, 96, 67)),
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
    ("blackstone", (42, 36, 41)), ("redstone_wire", (190, 25, 20)), ("redstone_torch", (255, 60, 30)),
    ("redstone_wall_torch", (255, 60, 30)), ("redstone_lamp", (230, 170, 70)), ("redstone_block", (170, 20, 10)), ("basalt", (80, 81, 86)), ("quartz", (235, 229, 222)),
    # coloured terracotta before the bare word: 'white_terracotta' drew dark brown, and both lakeside
    # critics read the town's plaster as brown (map colours from the game)
    ("white_terracotta", (209, 178, 161)), ("light_gray_terracotta", (135, 107, 98)),
    ("gray_terracotta", (57, 42, 35)), ("orange_terracotta", (161, 83, 37)), ("yellow_terracotta", (186, 133, 35)),
    ("red_terracotta", (143, 61, 46)), ("brown_terracotta", (77, 51, 35)), ("cyan_terracotta", (86, 91, 91)),
    ("terracotta", (152, 94, 67)), ("white_concrete", (207, 213, 214)), ("smooth_quartz", (235, 229, 222)), *DYES, ("sticky_piston", (120, 170, 80)), ("piston_head", (170, 140, 95)), ("piston", (170, 140, 95)),
    ("lever", (90, 70, 50)), ("observer", (90, 90, 95)), ("repeater", (160, 60, 50)), ("lantern", (250, 200, 90)), ("torch", (250, 200, 90)),
    ("coal", (40, 40, 40)), ("iron", (200, 200, 200)), ("copper", (192, 107, 79)),
    ("stone", (125, 125, 125)), ("log", (109, 85, 50)), ("planks", (162, 130, 78)),
]
@lru_cache(maxsize=4096)
def color(block):
    name = block_name(block)
    for key, rgb in COLORS:
        if key in name:
            return rgb
    h = zlib.crc32(name.encode())
    return (90 + h % 120, 90 + (h >> 8) % 120, 90 + (h >> 16) % 120)


def skipped(block):
    """Not drawn, and doesn't hide what's behind it: air and small plants."""
    return is_air(block) or is_plant(block)


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


ROTATIONS = {"se": 0, "sw": 1, "nw": 2, "ne": 3}  # the corner the camera looks from


def _rotate(p, k):
    x, y, z = p
    for _ in range(k):
        x, z = z, -x
    return x, y, z


def iso(cells, path=None, tile=8, background=(205, 222, 235), view="se"):
    """Isometric picture of {(x, y, z): block} seen from above and the `view` corner. Returns
    (width, height, pixels) and writes a PNG if `path` is given."""
    k = ROTATIONS[view]
    solid = {_rotate(p, k): b for p, b in cells.items() if not skipped(b)}
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
    if path:
        write_png(path, width, height, px)
    return width, height, px


def plan(cells, y, path=None, scale=10, background=(250, 250, 245)):
    """Floor plan: the layer at height y seen from above (walls, doors, furniture), with the floor
    below it shown faded. North up."""
    xs = [p[0] for p in cells]
    zs = [p[2] for p in cells]
    x0, z0, w, d = min(xs), min(zs), max(xs) - min(xs) + 1, max(zs) - min(zs) + 1
    px = bytearray(bytes(background) * (w * scale * d * scale))
    for x in range(x0, x0 + w):
        for z in range(z0, z0 + d):
            b, under = cells.get((x, y, z)), cells.get((x, y - 1, z))
            if b and not skipped(b):
                rgb = color(b)
            elif under and not skipped(under):
                rgb = tuple(int(c * 0.35 + 255 * 0.65) for c in color(under))
            else:
                continue
            for dz in range(scale):
                row = ((z - z0) * scale + dz) * w * scale
                for dx in range(scale):
                    edge = dx == 0 or dz == 0
                    i = (row + (x - x0) * scale + dx) * 3
                    px[i:i + 3] = bytes(shade(rgb, 0.85) if edge else rgb)
    if path:
        write_png(path, w * scale, d * scale, px)
    return w * scale, d * scale, px


def sheet(images, path, columns=3, gap=12, background=(255, 255, 255)):
    """Lay (width, height, pixels) images out in a grid, one PNG."""
    cw = max(i[0] for i in images) + gap
    ch = max(i[1] for i in images) + gap
    rows = (len(images) + columns - 1) // columns
    W, H = cw * min(columns, len(images)) + gap, ch * rows + gap
    out = bytearray(bytes(background) * (W * H))
    for n, (w, h, px) in enumerate(images):
        ox = gap + (n % columns) * cw
        oy = gap + (n // columns) * ch
        for y in range(h):
            dst = ((oy + y) * W + ox) * 3
            out[dst:dst + w * 3] = px[y * w * 3:(y + 1) * w * 3]
    write_png(path, W, H, out)
    return W, H


def top_down(columns, path=None, scale=4):
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
    if path:
        write_png(path, w * scale, d * scale, px)
    return w * scale, d * scale, px


LOOK = {"west": (0, -1), "east": (0, 1), "north": (2, -1), "south": (2, 1)}


def elevation(cells, look="west", path=None, scale=16, skip=(), background=(244, 241, 232)):
    """A flat, straight-on drawing of a face, like an architect's elevation: looking `look`, each cell
    shows the first visible block along the view, darker the further back it is. `skip` (block names)
    makes those see-through: skip the rock to get a section through a mechanism. Up is up."""
    axis, sign = LOOK[look]  # 0 = x, 2 = z; the view runs along this axis in direction `sign`
    other = 2 if axis == 0 else 0
    vis = {p: b for p, b in cells.items() if not skipped(b) and block_name(b) not in skip}
    if not vis:
        raise ValueError("nothing to draw")
    us = [p[other] for p in vis]
    ys = [p[1] for p in vis]
    ds = [p[axis] for p in vis]
    u0, u1, y0, y1, d0, d1 = min(us), max(us), min(ys), max(ys), min(ds), max(ds)
    # looking west (-x) you see north (-z) on your right: flip the horizontal so the drawing isn't mirrored
    flip = (look in ("west", "south"))
    w, h = (u1 - u0 + 1) * scale, (y1 - y0 + 1) * scale
    px = bytearray(bytes(background) * (w * h))
    first = {}
    front = d1 if sign < 0 else d0  # the plane nearest the viewer
    for (p, b) in vis.items():
        key = (p[other], p[1])
        dist = abs(p[axis] - front)
        if key not in first or dist < first[key][0]:
            first[key] = (dist, b)
    for (u, y), (dist, b) in first.items():
        f = max(0.45, 1.0 - 0.07 * dist)
        rgb = bytes(shade(color(b), f))
        cu = (u1 - u) if flip else (u - u0)
        for dy in range(scale):
            row = ((y1 - y) * scale + dy) * w
            for dx in range(scale):
                edge = dx == 0 or dy == 0
                i = (row + cu * scale + dx) * 3
                px[i:i + 3] = bytes(shade(color(b), f * 0.82)) if edge else rgb
    if path:
        write_png(path, w, h, px)
    return w, h, px
