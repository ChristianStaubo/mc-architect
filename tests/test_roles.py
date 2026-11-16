"""The headless agents' fences: what mc.py refuses to the in-game architect (MC_ROLE=architect) and to eval
builders (MC_ROLE=builder), before any bridge call (no server needed), and the mc cmd stop/reload check."""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from architect.cli.world import refused_command

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "local" / "runs" / "incidents"


def mc(*argv, **env):
    """Run mc.py with extra env; remove any incident it leaves. (returncode, stderr)"""
    before = set(os.listdir(INC)) if INC.exists() else set()
    e = {k: v for k, v in os.environ.items() if k not in ("MC_ROLE", "MC_PLAYER", "MC_GHOST")}
    e.update(MC_RUN_ID="test:roles", **env)
    try:
        r = subprocess.run([sys.executable, str(ROOT / "mc.py"), *argv], capture_output=True, text=True, env=e,
                           timeout=60)
    finally:
        for x in (set(os.listdir(INC)) if INC.exists() else set()) - before:
            p = INC / x
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    return r.returncode, r.stderr


class RoleTest(unittest.TestCase):
    def refused(self, argv, **env):
        code, err = mc(*argv, **env)
        self.assertNotEqual(code, 0, err)
        self.assertIn("refused", err)

    def test_architect_cannot_answer_for_a_player(self):
        self.refused(["architect", "ask", "yes", "--as", "bob", "--at", "0,64,0"], MC_ROLE="architect", MC_PLAYER="bob")

    def test_architect_cannot_bench(self):
        self.refused(["bench"], MC_ROLE="architect", MC_PLAYER="bob")

    def test_architect_previews_only_for_its_player(self):
        self.refused(["preview", "x.py", "--for", "alice"], MC_ROLE="architect", MC_PLAYER="bob")

    def test_builder_cannot_check_the_reference(self):
        self.refused(["eval", "check", "tight-cottage"], MC_ROLE="builder")

    def test_builder_cannot_run_server_commands(self):
        self.refused(["cmd", "list"], MC_ROLE="builder")

    def test_builder_cannot_run_the_gate(self):
        self.refused(["eval", "gate", "--offline"], MC_ROLE="builder")

    def test_architect_may_name_its_own_player(self):
        # gets past the role check (then fails on the missing plan, not on the fence)
        code, err = mc("preview", "local/tmp/no_such_plan_for_roles.py", "--for", "BOB", MC_ROLE="architect",
                       MC_PLAYER="bob")
        self.assertNotIn("previews for the player who asked", err)


class CmdRefusalTest(unittest.TestCase):
    def test_refused(self):
        for text in ["stop", "/stop", " /stop", "minecraft:stop", "BUKKIT:reload", "execute as @a run stop", "rl",
                     "restart", "/minecraft:reload"]:
            with self.subTest(text=text):
                self.assertIsNotNone(refused_command(text))

    def test_allowed(self):
        for text in ["say stop the music", "list", "time set day", "whitelist add stopper", "",
                     "execute as @a run say stop"]:
            with self.subTest(text=text):
                self.assertIsNone(refused_command(text))


if __name__ == "__main__":
    unittest.main()
