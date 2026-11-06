"""python -m ghost <command>: the ghost's processes and evals.

  core | worker | watchdog     run one process (in the foreground)
  run                          all three, restarted if one dies (Ctrl-C stops them)
  status                       heartbeats, open tasks, today's budgets, recent audit
  eval <suite> [--k N]         guarantees | listening | scenarios | chaos  (see ghost/evals.py)
  migrate                      apply ghost/schema.sql
"""

import sys


def main(argv):
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
    if cmd == "migrate":
        from . import db
        db.migrate()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
