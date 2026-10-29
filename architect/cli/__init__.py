"""The `mc` command line, one module per command group. Each module's register(sub) adds its subcommands
and points them at their functions (set_defaults(fn=...)); main() parses, runs, and records every call in
the journal (and an incident on a failure)."""

import argparse
import sys
import time

from .. import bridge, incidents, journal
from . import assistant, build, evals, look, recorder, town, world
from .common import Parser

GROUPS = [world, build, look, recorder, town, evals, assistant]


def main(doc):
    p = Parser(prog="mc", description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for g in GROUPS:
        g.register(sub)
    a = p.parse_args()
    if a.cmd == "eval" and a.action == "report" and a.task and not a.run:
        a.run = a.task  # `mc eval report RUN`
    t0 = time.time()
    code, err, kind, exc = 0, None, None, None
    try:
        code = a.fn(a) or 0
    except bridge.BridgeError as e:
        # 4xx = the request was wrong (too big, unknown block): the caller's error, not the bridge's
        code, err, exc = 1, f"error: {e}", e
        kind = "error" if 400 <= getattr(e, "status", 0) < 500 else "bridge"
    except SystemExit as e:
        code, err = (e.code if isinstance(e.code, int) else 1), (e.code if isinstance(e.code, str) else None)
        if err:
            kind = "refused" if err.startswith("refused") else "error"
    except Exception as e:  # a tool bug: record it with everything around it, then show it
        code, err, kind, exc = 1, repr(e), "crash", e
    argv = sys.argv[1:]
    journal.log(a.cmd, argv[1:], int((time.time() - t0) * 1000), code == 0, err)
    # Judges failing (audit, town show: exit 2) are the system working, not incidents.
    if kind and a.cmd not in ("incidents", "incident"):
        iid = incidents.save(a.cmd, argv, kind, err, exc)
        err = f"{err}\n(incident {iid}: mc incident {iid})"
    if kind == "crash":
        import traceback
        traceback.print_exception(exc)
    if err:
        print(err, file=sys.stderr)
    sys.exit(code)

