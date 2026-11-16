"""Judges never raise: a malformed reply or a timeout costs the dimensions ("unknown"), not the trial."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from architect import judges

DIMS = ["shape", "depth", "proportion"]


class Parse(unittest.TestCase):
    def test_json_inside_prose(self):
        text = 'Here you go: {"shape": {"score": 7, "evidence": "clear silhouette"}, "depth": {"score": 5}} done.'
        out = judges._parse(text, DIMS)
        self.assertEqual(out["shape"], {"score": 7, "evidence": "clear silhouette"})
        self.assertEqual(out["depth"]["score"], 5)
        self.assertEqual(out["proportion"]["score"], "unknown")

    def test_braces_that_are_not_json(self):
        out = judges._parse("the roof {looks} fine, the walls {do not}", DIMS)
        self.assertEqual({d: v["score"] for d, v in out.items()}, dict.fromkeys(DIMS, "unknown"))

    def test_json_list(self):  # the braces span both objects: not one JSON object, so nothing is trusted
        out = judges._parse('[{"shape": {"score": 7}}, {"depth": {"score": 6}}]', DIMS)
        self.assertEqual({d: v["score"] for d, v in out.items()}, dict.fromkeys(DIMS, "unknown"))

    def test_one_object_in_a_list_is_read(self):
        self.assertEqual(judges._parse('[{"shape": {"score": 7}}]', DIMS)["shape"]["score"], 7)

    def test_score_out_of_range(self):
        out = judges._parse('{"shape": {"score": 11}, "depth": {"score": 0}, "proportion": 4}', DIMS)
        self.assertEqual(out["shape"]["score"], "unknown")
        self.assertEqual(out["depth"]["score"], "unknown")
        self.assertEqual(out["proportion"]["score"], 4)

    def test_no_text(self):
        self.assertEqual(judges._parse(None, DIMS)["shape"]["score"], "unknown")


class JudgeGroup(unittest.TestCase):
    def test_timeout_is_unknown_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.png"
            sheet.write_bytes(b"png")
            boom = subprocess.TimeoutExpired(cmd="claude", timeout=600)
            with mock.patch.object(judges.subprocess, "run", side_effect=boom):
                scores, cost = judges.judge_group({"brief": "a cottage"}, DIMS, sheet, "sonnet")
        self.assertEqual(cost, 0.0)
        self.assertEqual({d: v["score"] for d, v in scores.items()}, dict.fromkeys(DIMS, "unknown"))
        self.assertEqual(scores["shape"]["evidence"], "judge timed out")


if __name__ == "__main__":
    unittest.main()
