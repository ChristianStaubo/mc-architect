"""python -m ghost <command>: the ghost's processes and evals.

  core | worker | watchdog     run one process (in the foreground)
  run                          all three, restarted if one dies (Ctrl-C stops them)
  status                       heartbeats, open tasks, today's budgets, recent audit
  eval <suite> [--k N]         guarantees | listening | scenarios | chaos  (see ghost/evals.py)
  city start NAME [--plan-only] [--districts a,b] [--max-plots N] [--concurrency N] [--run ID]
  city workers NAME --run ID --concurrency N   change how many builders a running build uses
  city decide NAME --run ID --key K --answer TEXT   answer a blocked worker's DECISION NEEDED
  city status NAME [--run ID]  the city harness (docs/ghost/city.md): plan, fan out, build in parallel
  migrate                      apply ghost/schema.sql
"""

import sys


def _die_with_parent():
    """A supervised child (GHOST_SUPERVISED=1) exits when its supervisor is gone, so a crashed supervisor
    never leaves orphans running beside the next one (macOS has no parent-death signal)."""
    import os
    import threading
    import time
    parent = os.getppid()

    def watch():
        while os.getppid() == parent:
            time.sleep(2)
        os._exit(0)
    threading.Thread(target=watch, daemon=True).start()


def main(argv):
    import os
    if os.environ.get("GHOST_SUPERVISED"):
        _die_with_parent()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "core":
        from .core import main as m
        return m()
    if cmd == "worker":
        import asyncio
        from .worker import main as m
        return asyncio.run(m())
    if cmd == "watchdog":
        from .watchdog import main as m
        return m()
    if cmd == "run":
        from .watchdog import supervise
        return supervise()
    if cmd == "status":
        from .watchdog import status
        return status()
    if cmd == "eval":
        from .evals import main as m
        return m(rest)
    if cmd == "city":
        from .city.cli import main as m
        return m(rest)
    if cmd == "migrate":
        from . import db
        db.migrate()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
