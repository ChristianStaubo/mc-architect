"""Riverford north gate, e tower (see gate_tower_common.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_tower_common import tower  # noqa: E402


def build():
    return tower(True)
