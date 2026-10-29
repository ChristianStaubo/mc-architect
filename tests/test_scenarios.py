"""The scenario suite's checks on made-up observations (no server, no model)."""

import unittest

from architect import scenarios


def obs(**kw):
    base = {"pending": None, "pending_before": None, "preview": False, "new_edits": [], "new_edit_records": [],
            "pos": [0, 70, 0], "selection": None, "said": [], "claude": None, "claude_before": None,
            "cmds": [], "minutes": 1.0, "end": "done", "site_changed": 0}
    return base | kw


def pending(lo, hi):
    return {"box": [list(lo), list(hi)]}


class CheckTest(unittest.TestCase):
    def test_near(self):
        o = obs(pending=pending((3, 70, 2), (8, 75, 7)))
        self.assertTrue(scenarios.check("near", 3, o)[0])
        self.assertFalse(scenarios.check("near", 2, o)[0])

    def test_inside_selection(self):
        sel = {"min": [0, 60, 0], "max": [10, 90, 10]}
        self.assertTrue(scenarios.check("inside_selection", True, obs(pending=pending((1, 70, 1), (9, 80, 9)), selection=sel))[0])
        self.assertFalse(scenarios.check("inside_selection", True, obs(pending=pending((1, 70, 1), (11, 80, 9)), selection=sel))[0])

    def test_taller_and_resumed(self):
        o = obs(pending=pending((0, 70, 0), (5, 83, 5)), pending_before=pending((0, 70, 0), (5, 80, 5)),
                claude="s1", claude_before="s1")
        self.assertTrue(scenarios.check("taller", 3, o)[0])
        self.assertFalse(scenarios.check("taller", 4, o)[0])
        self.assertTrue(scenarios.check("resumed", True, o)[0])
        self.assertFalse(scenarios.check("resumed", True, o | {"claude": "s2"})[0])

    def test_matches_preview(self):
        before = pending((0, 70, 0), (5, 80, 5))
        placed = [{"id": "e1", "min": [0, 70, 0], "max": [5, 80, 5]}]
        self.assertTrue(scenarios.check("matches_preview", True, obs(pending_before=before, new_edit_records=placed))[0])
        self.assertFalse(scenarios.check("matches_preview", True, obs(pending_before=before, new_edit_records=[]))[0])

    def test_tools_before(self):
        self.assertTrue(scenarios.check("tools_before", ["site", "preview"], obs(cmds=["site", "preview", "say"]))[0])
        self.assertFalse(scenarios.check("tools_before", ["site", "preview"], obs(cmds=["preview", "site"]))[0])
        self.assertFalse(scenarios.check("tools_before", ["site", "preview"], obs(cmds=["say"]))[0])

    def test_within_limits(self):
        self.assertTrue(scenarios.check("within_limits", True, obs())[0])  # declined: fine
        self.assertFalse(scenarios.check("within_limits", True, obs(pending=pending((0, 70, 0), (60, 80, 5))))[0])

    def test_unknown_expectation_fails(self):
        self.assertFalse(scenarios.check("telepathy", True, obs())[0])


if __name__ == "__main__":
    unittest.main()
