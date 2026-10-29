"""The audit must catch what a player would: run with `python3 -m unittest` from the repo root."""

import unittest

from architect import terrain
from architect.audit import audit
from architect.build import Build
from architect.parts import door, floor, walls


def world(build, ground_y=0, size=14):
    """A flat world: stone up to ground_y, air above, with the build's blocks placed at y = ground_y + 1."""
    cells = {}
    for x in range(-3, size):
        for z in range(-3, size):
            for y in range(ground_y - 3, ground_y + 12):
                cells[(x, y, z)] = "stone" if y <= ground_y else "air"
    for (x, y, z), b in build.blocks.items():
        cells[(x, y + ground_y + 1, z)] = b
    lo = tuple(min(p[i] for p in build.blocks) for i in range(3))
    hi = tuple(max(p[i] for p in build.blocks) for i in range(3))
    box = ((lo[0], lo[1] + ground_y + 1, lo[2]), (hi[0], hi[1] + ground_y + 1, hi[2]))
    return cells, box


def hut(lit=True, with_door=True, roof=True):
    b = Build("hut")
    floor(b, 0, 0, 6, 6, 0, "oak_planks")
    walls(b, 0, 0, 6, 6, 1, 3, "stone_bricks")
    if roof:
        floor(b, 0, 0, 6, 6, 4, "oak_planks")
    if with_door:
        door(b, 3, 1, 6, "south")
    if lit:
        b.set(3, 1, 3, "lantern[hanging=false]")
    return b


def failed(r):
    return {c["check"] for c in r["checks"] if c["level"] == "fail"}


class AuditTest(unittest.TestCase):
    def test_good_hut_passes(self):
        r = audit(*world(hut()))
        self.assertEqual(failed(r), set())
        self.assertEqual(r["stats"]["doors"], 1)
        self.assertGreater(r["stats"]["indoor_floor"], 10)

    def test_dark_hut_fails(self):
        self.assertIn("dark", failed(audit(*world(hut(lit=False)))))

    def test_no_door_is_sealed(self):
        self.assertIn("sealed", failed(audit(*world(hut(with_door=False)))))

    def test_floating_block(self):
        b = hut()
        b.set(3, 8, 3, "oak_planks")  # hangs in the air above the roof
        self.assertIn("floating", failed(audit(*world(b))))

    def test_blocked_door(self):
        b = hut()
        b.fill(3, 1, 7, 3, 2, 7, "stone")  # a wall right outside the door
        self.assertIn("door", failed(audit(*world(b))))

    def test_open_roof_warns_no_interior(self):
        r = audit(*world(hut(roof=False)))
        self.assertIn("interior", {c["check"] for c in r["checks"]})

    def test_tower_open_to_its_roof_is_still_indoors(self):
        # r1 watchtower: the stairwell opens onto the roof platform, so the room connects to the sky.
        # It must count as indoors (no false "nowhere enclosed" warning) and its floor must be checked
        # for light (a dark tower floor is a mob spawner).
        b = hut(lit=False)
        b.set(1, 4, 1, "air")  # the hatch up to the roof
        r = audit(*world(b))
        self.assertNotIn("interior", {c["check"] for c in r["checks"]})
        self.assertIn("dark", failed(r))

    def test_market_stall_is_not_indoors(self):
        # an awning on posts, open on three sides: no room, so no dark-floor failure under it
        b = Build("stall")
        floor(b, 0, 0, 4, 2, 0, "stone_bricks")
        for x, z in ((0, 0), (4, 0), (0, 2), (4, 2)):
            b.fill(x, 1, z, x, 2, z, "oak_fence")
        floor(b, 0, 0, 4, 2, 3, "red_wool")
        self.assertNotIn("dark", failed(audit(*world(b))))

    def test_step_behind_a_door_is_not_a_block(self):
        # lakeside lighthouse: a stair right inside the door was reported as blocking it
        b = hut()
        b.set(3, 1, 5, "oak_stairs[facing=north,half=bottom,shape=straight]")
        self.assertNotIn("door", failed(audit(*world(b))))

    def test_ladder_reaches_a_loft(self):
        # lakeside inn: a loft reached only by a ladder was reported as sealed
        b = hut()
        floor(b, 1, 1, 5, 5, 3, "oak_planks")
        b.fill(1, 1, 1, 1, 3, 1, "ladder[facing=east]")
        floor(b, 0, 0, 6, 6, 5, "oak_planks")
        walls(b, 0, 0, 6, 6, 4, 4, "stone_bricks")
        b.set(3, 4, 3, "lantern[hanging=false]")
        self.assertNotIn("sealed", failed(audit(*world(b))))

    def test_stepped_awning_is_not_floating(self):
        # rows stepping down and out touch only along an edge: held up in the game (sampler awning)
        b = hut()
        for x in range(1, 6):
            b.set(x, 3, -1, "red_wool")
            b.set(x, 2, -2, "white_wool")
        self.assertNotIn("floating", failed(audit(*world(b))))

    def test_corner_touch_still_floats(self):
        b = hut()
        b.set(-1, 6, -1, "red_wool")  # touches the roof's corner only
        self.assertIn("floating", failed(audit(*world(b))))

    def test_half_bed(self):
        b = hut()
        b.set(1, 1, 1, "red_bed[facing=north,part=head]")
        self.assertIn("bed", failed(audit(*world(b))))


class TerraceTest(unittest.TestCase):
    def test_terrace_leaves_water_alone(self):
        # town1: the boathouse terrace filled its half of the bay with dirt
        cols = {(x, z): ((62, "water") if x >= 3 else (64, "grass_block")) for x in range(-2, 8) for z in range(-2, 4)}
        cells = terrain.terrace(0, 0, 5, 2, 65, cols, margin=0)
        self.assertFalse(any(x >= 3 for (x, y, z) in cells if (x, z) in cols and cols[(x, z)][1] == "water"))


if __name__ == "__main__":
    unittest.main()
