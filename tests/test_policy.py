"""Where and how big an /arc preview may be (architect/assistant/policy.py), with no town on disk."""

import unittest
from unittest import mock

from architect.assistant import policy


def ctx(pos=(0.5, 64, 0.5), facing="south", selection=None, target=None):
    return {"player": "Steve", "pos": list(pos), "facing": facing, "selection": selection, "target": target}


class LimitsTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(policy, "occupied", return_value=[])  # it reads towns/ and local/
        self.occupied = p.start()
        self.addCleanup(p.stop)

    def test_a_small_build_near_the_player_is_allowed(self):
        self.assertIsNone(policy.limits(ctx(), ((3, 64, 3), (10, 70, 10))))

    def test_too_big_is_refused(self):
        why = policy.limits(ctx(), ((0, 64, 0), (policy.MAX_SIDE, 70, 10)))
        self.assertIn("too big", why)
        why = policy.limits(ctx(), ((3, 0, 3), (10, policy.MAX_HEIGHT, 10)))
        self.assertIn("too big", why)

    def test_too_far_from_the_player_is_refused(self):
        why = policy.limits(ctx(), ((100, 64, 0), (110, 70, 10)))
        self.assertIn("too far from them", why)

    def test_inside_a_selection_any_distance_is_allowed(self):
        sel = {"min": [100, 60, 100], "max": [130, 80, 130]}
        self.assertIsNone(policy.limits(ctx(selection=sel), ((105, 64, 105), (125, 70, 125))))

    def test_a_build_over_the_player_is_refused_with_a_spot_ahead(self):
        why = policy.limits(ctx(), ((-3, 64, -3), (3, 70, 3)), at=(0, 0))
        self.assertIn("covers where Steve stands", why)
        self.assertIn("--at", why)

    def test_a_taken_spot_is_refused(self):
        self.occupied.return_value = ["the tavern"]
        self.assertIn("taken", policy.limits(ctx(), ((3, 64, 3), (10, 70, 10))))


class AnchorTest(unittest.TestCase):
    def test_a_selection_wins_over_the_spot_ahead(self):
        sel = {"min": [10, 60, 20], "max": [20, 70, 30]}
        a = policy.anchor(ctx(selection=sel, target={"pos": [5, 64, 5]}))
        self.assertIsNone(a["spot"])
        self.assertEqual(a["what"], "their selection")
        self.assertEqual(a["site"][:2], (15, 25))

    def test_the_crosshair_then_in_front(self):
        self.assertEqual(policy.anchor(ctx(target={"pos": [5, 64, 7]}))["spot"], (5, 7))
        a = policy.anchor(ctx(pos=(2.5, 64, 3.5), facing="south"))
        self.assertEqual((a["spot"], a["what"]), ((2, 3), "them"))
        self.assertGreater(a["site"][1], 3)  # the ground read is ahead of them


if __name__ == "__main__":
    unittest.main()
