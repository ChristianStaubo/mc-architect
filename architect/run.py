"""Running the mc CLI as a subprocess (daemon jobs, eval checks, regression), the one way: from the repo
root, with the caller's MC_RUN_ID / MC_PLAYER so the journal files it under the right run."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def mc(*argv, timeout=None, **env):
    """(ok, output) of `mc.py argv...`; env: extra environment variables (MC_RUN_ID=..., MC_PLAYER=...)."""
    r = subprocess.run([sys.executable, str(ROOT / "mc.py"), *map(str, argv)], cwd=ROOT, capture_output=True,
                       text=True, timeout=timeout, env={**os.environ, **env})
    return r.returncode == 0, (r.stdout + r.stderr).strip()
