"""The gate's exit code: skipped server checks are a failure, not a silent green. No server needed."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from architect import regression
from architect.cli.evals import cmd_eval


def record(failed=0, skipped=0, offline=False):
    return {"manifest": {"commit": "abc1234", "dirty": False, "minecraft": "1", "paper_build": 1, "worldedit": "1"},
            "checks": [], "offline": offline, "passed": 5, "failed": failed, "skipped": skipped}


def gate(rec, offline=False):
    out = io.StringIO()
    with mock.patch.object(regression, "run", return_value=rec), redirect_stdout(out):
        code = cmd_eval(SimpleNamespace(action="gate", offline=offline))
    return code, out.getvalue()


class GateExit(unittest.TestCase):
    def test_skipped_server_checks_fail(self):
        code, out = gate(record(skipped=3))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: 3 checks skipped", out)

    def test_all_ran_and_passed(self):
        self.assertEqual(gate(record())[0], 0)

    def test_offline_passes(self):
        self.assertEqual(gate(record(offline=True), offline=True)[0], 0)

    def test_failed_check_fails(self):
        self.assertEqual(gate(record(failed=1))[0], 1)


class KitsInGate(unittest.TestCase):
    def test_every_kit_has_an_offline_row(self):
        kits = {p.stem for p in regression.ROOT.joinpath("kits").glob("*.py")
                if not p.name.startswith("_")}
        rows = {name for group, name, needs_server, _ in regression.checks(offline=True) if group == "kits"}
        self.assertTrue(kits)
        self.assertEqual(rows, kits)

    def test_a_broken_kit_fails_with_its_first_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp) / "broken.py"
            kit.write_text("def build(w, d, door, kind, seed):\n    raise RuntimeError('no walls')\n")
            with mock.patch("architect.cli.common.out_path", return_value=Path(tmp) / "sheet.png"):
                ok, detail = regression.check_kit(kit)()
        self.assertFalse(ok)
        self.assertTrue(detail.startswith("0/4 clean; house seed 1: error:"), detail)
        self.assertIn("no walls", detail)


if __name__ == "__main__":
    unittest.main()
