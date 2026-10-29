"""Every new part once (friction fixes): chimney, shutters, flower box, outside stair, roofs that meet,
dormer_on, round tower + cone roof, awning, dock with a boat, a sign with text."""
from architect.build import Build
from architect import parts

def build():
    b = Build("sampler")
    parts.floor(b, 0, 0, 10, 6, 0, "stone_bricks")
    parts.timber_frame(b, 0, 0, 10, 6, 1, 4, "white_terracotta", post="dark_oak_log[axis=y]", beam="dark_oak_log")
    parts.clear_inside(b, 0, 0, 10, 6, 1, 8)
    parts.door(b, 5, 1, 6, "south")
    parts.window(b, 2, 2, 6, "x", width=2)
    parts.shutters(b, 2, 2, 6, "x", 2, 1, "south")
    parts.flower_box(b, 2, 2, 6, "x", 2, "south")
    main = parts.gable_roof(b, 0, 0, 10, 6, 5, "dark_oak_stairs", "white_terracotta", ridge="x")
    parts.dormer_on(b, main, 7, "back", "white_terracotta")
    parts.chimney(b, 1, 1, 5, 10, width=1)
    parts.light(b, 3, 1, 3)
    parts.light(b, 8, 1, 3)
    parts.outside_stair(b, 11, 1, 1, "south", 4, side="east")
    b.sign(6, 2, 7, "spruce_wall_sign[facing=south]", ["The Sampler", "est. today"])
    parts.round_tower(b, 16, 3, 0, 8, 2, "stone_bricks")
    parts.floor(b, 15, 2, 17, 4, 0, "spruce_planks")
    parts.cone_roof(b, 16, 3, 9, 2, "dark_oak_stairs")
    parts.door(b, 16, 1, 5, "south")
    parts.light(b, 16, 1, 3)
    parts.awning(b, 0, 4, 0, 4, "north")
    parts.dock(b, 20, 0, 28, 2, 0, -3)
    return b
