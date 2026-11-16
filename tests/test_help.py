"""`./mc.py -h` is the agents' only manual: every subcommand (and every town action) the parser knows must
appear in mc.py's docstring. A new command without a help line fails here."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from architect.cli import GROUPS  # noqa: E402
from architect.cli.common import Parser  # noqa: E402

# Registered commands left out of the help on purpose (none yet).
INTERNAL = set()


def doc():
    return ast.get_docstring(ast.parse((ROOT / "mc.py").read_text()))


def parser():
    p = Parser(prog="mc")
    sub = p.add_subparsers(dest="cmd", required=True)
    for g in GROUPS:
        g.register(sub)
    return sub


def documented(text):
    """Names the help shows as commands: `mc NAME`, and alternatives on the same line (`mc doctor | status`)."""
    names = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("mc "):
            for part in line[3:].split(" | "):
                if part.split():
                    names.add(part.split()[0])
    return names


class HelpTest(unittest.TestCase):
    def test_every_command_is_in_the_help(self):
        missing = set(parser().choices) - documented(doc()) - INTERNAL
        self.assertFalse(missing, f"not in mc.py's help: {sorted(missing)}")

    def test_every_town_action_is_in_the_help(self):
        town = parser().choices["town"]
        action = next(a for a in town._actions if a.dest == "action")
        missing = [n for n in action.choices if f"mc town {n} " not in doc()]
        self.assertFalse(missing, f"town actions not in mc.py's help: {missing}")


if __name__ == "__main__":
    unittest.main()
