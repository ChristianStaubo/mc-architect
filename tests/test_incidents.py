"""A failing mc command must leave an incident with what's needed to reproduce it (no server needed:
the plan fails to load before any bridge call)."""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "local" / "runs" / "incidents"
FRICTION = ROOT / "local" / "runs" / "friction"


class IncidentTest(unittest.TestCase):
    def test_crash_saves_an_incident_and_files_friction(self):
        plan = ROOT / "local" / "tmp" / "broken_for_test.py"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("def build(:\n")
        before = set(os.listdir(INC)) if INC.exists() else set()
        env = dict(os.environ, MC_RUN_ID="test:incident-unit")
        r = subprocess.run([sys.executable, str(ROOT / "mc.py"), "place", str(plan), "--at", "0,0", "--dry-run"],
                           capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0)
        new = set(os.listdir(INC)) - before
        try:
            self.assertEqual(len(new), 1)
            d = INC / new.pop()
            info = json.loads((d / "incident.json").read_text())
            self.assertEqual(info["kind"], "crash")
            self.assertIn("SyntaxError", info["error"])
            self.assertTrue((d / "plan.py").exists())
            self.assertTrue((d / "journal.jsonl").exists())
            filed = [p for p in FRICTION.glob("f*.json") if json.loads(p.read_text()).get("incident") == d.name]
            self.assertEqual(len(filed), 1)
        finally:
            for p in FRICTION.glob("f*.json"):
                if json.loads(p.read_text()).get("run") == "test:incident-unit":
                    p.unlink()
            for x in INC.glob("*"):
                if x.is_dir() and json.loads((x / "incident.json").read_text()).get("run") == "test:incident-unit":
                    shutil.rmtree(x)
            plan.unlink()


if __name__ == "__main__":
    unittest.main()
