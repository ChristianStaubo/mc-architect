"""The code graders on small hand-made worlds."""

import unittest

from architect import graders

GROUND = 0


def world(w=12, d=12, h=6):
    """A flat grass world, air above."""
    cells = {}
    for x in range(w):
        for z in range(d):
            cells[(x, GROUND, z)] = "minecraft:grass_block"
            for y in range(1, h):
                cells[(x, y, z)] = "minecraft:air"
    return cells


def outcome(after, before, plot=((0, 0), (11, 11))):
    return graders.Outcome(after, before, plot)


class WalkTest(unittest.TestCase):
    def hut(self, door=True):
        before = world()
        after = dict(before)
        for x in range(3, 8):
            for z in range(3, 8):
                for y in (1, 2, 3):
                    if x in (3, 7) or z in (3, 7):
                        after[(x, y, z)] = "minecraft:stone_bricks"
                after[(x, 4, z)] = "minecraft:stone_bricks"
        if door:
            after[(5, 1, 3)] = "minecraft:oak_door[half=lower,facing=north]"
            after[(5, 2, 3)] = "minecraft:oak_door[half=upper,facing=north]"
        return outcome(after, before)

    def test_door_reached(self):
        r = graders.door_reaches_outside(self.hut())
        self.assertTrue(r["pass"], r)

    def test_walk_goes_through_doors(self):
        self.assertIn((5, 1, 5), self.hut().walk())

    def test_sealed_room_not_walkable(self):
        self.assertNotIn((5, 1, 5), self.hut(door=False).walk())

    def test_step_needs_headroom(self):
        before = world()
        after = dict(before)
        after[(5, 1, 5)] = "minecraft:stone"      # a one-block step...
        after[(4, 2, 5)] = "minecraft:stone"      # ...with a ceiling over the approach
        after[(4, 3, 5)] = "minecraft:stone"
        o = outcome(after, before)
        self.assertIn((5, 2, 5), o.walk())       # reachable from the other sides


class GraderTest(unittest.TestCase):
    def test_keeps_trees(self):
        before = world()
        for y in (1, 2, 3):
            before[(2, y, 2)] = "minecraft:oak_log[axis=y]"
            before[(8, y, 8)] = "minecraft:oak_log[axis=y]"
        after = dict(before)
        for y in (1, 2, 3):
            after[(8, y, 8)] = "minecraft:air"
        after[(5, 1, 5)] = "minecraft:stone"
        r = graders.keeps_trees(outcome(after, before), min_share=0.6)
        self.assertFalse(r["pass"])
        self.assertEqual(r["value"], 0.5)

    def test_inside_plot(self):
        before = world()
        after = dict(before)
        after[(11, 1, 11)] = "minecraft:stone"
        self.assertFalse(graders.inside_plot(outcome(after, before, plot=((0, 0), (10, 10))))["pass"])

    def test_material_families(self):
        self.assertEqual(graders.family("spruce_stairs"), graders.family("spruce_planks"))
        self.assertEqual(graders.family("stone_brick_slab"), graders.family("stone_bricks"))
        self.assertNotEqual(graders.family("spruce_log"), graders.family("spruce_planks"))

    def test_height_from_ground(self):
        before = world(h=12)
        after = dict(before)
        for y in range(1, 11):
            after[(5, y, 5)] = "minecraft:stone"
        r = graders.height(outcome(after, before), min=10)
        self.assertTrue(r["pass"], r)

    def test_crashing_grader_fails(self):
        task = {"graders": [{"code": "contains", "nope": 1}]}
        r = graders.run(task, outcome(world(), world()))
        self.assertFalse(r[0]["pass"])


if __name__ == "__main__":
    unittest.main()
