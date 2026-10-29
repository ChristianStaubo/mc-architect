"""Incidents: when an mc command fails, everything needed to see why and to reproduce it, saved at once
(local/runs/incidents/<id>/), the way fm26's flight recorder does:
  incident.json   the command (argv, run, cwd), the kind, the error and its stack
  trace.jsonl     the last 20 bridge requests (this run's, else everyone's)
  journal.jsonl   the last 20 mc commands
  plan.py         the plan file as it was when it failed (if the command named one)
  server.log      the last 80 lines of the server's log
  edits.json      the last 5 live edits
Kept: the newest 50. A crash or a bridge failure also files friction, so the fixer sees it."""

import json
import shutil
import subprocess
import time
import traceback
from pathlib import Path

from . import journal, trace

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "local" / "runs" / "incidents"
KEEP = 50
KINDS = ("crash", "bridge", "refused", "error")


def plan_path(argv):
    """The plan file a command used, if any (place / blueprint take a name or a path)."""
    if len(argv) < 2 or argv[0] not in ("place", "blueprint"):
        return None
    p = Path(argv[1])
    if not p.exists():
        p = ROOT / "plans" / f"{argv[1].removesuffix('.py')}.py"
    return p if p.exists() else None


def save(cmd, argv, kind, error, exc=None):
    DIR.mkdir(parents=True, exist_ok=True)
    iid = time.strftime("i%Y%m%d-%H%M%S") + f"-{cmd}"
    d = DIR / iid
    n = 1
    while d.exists():
        d = DIR / f"{iid}-{n}"
        n += 1
    d.mkdir()
    run = journal.run_id()
    info = {"id": d.name, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "run": run, "cmd": cmd, "argv": argv,
            "kind": kind, "error": str(error)[:2000],
            "stack": "".join(traceback.format_exception(exc)) if exc else None}
    (d / "incident.json").write_text(json.dumps(info, indent=2))
    lines = trace.tail(20, run) if run and trace.tail(1, run) else trace.tail(20)
    (d / "trace.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines))
    (d / "journal.jsonl").write_text("".join(json.dumps(l) + "\n" for l in journal.entries()[-20:]))
    p = plan_path(argv)
    if p:
        shutil.copyfile(p, d / "plan.py")
    try:
        r = subprocess.run(["docker", "logs", "--tail", "80", "mc-architect"], capture_output=True, text=True, timeout=10)
        (d / "server.log").write_text(r.stdout + r.stderr)
    except Exception as e:  # the server being down is itself worth recording
        (d / "server.log").write_text(f"(no server log: {e})")
    try:
        from . import edits
        (d / "edits.json").write_text(json.dumps(edits.listing()[-5:], indent=2))
    except Exception:
        pass
    if kind in ("crash", "bridge"):
        journal.stuck(f"auto: {kind} in mc {' '.join(argv)[:120]} | {str(error)[:300]} | incident {d.name}",
                      kind="incident", incident=d.name)
    prune()
    return d.name


def listing():
    if not DIR.exists():
        return []
    return [json.loads((d / "incident.json").read_text()) for d in sorted(DIR.iterdir())
            if (d / "incident.json").exists()]


def get(iid):
    d = DIR / iid
    if not (d / "incident.json").exists():
        matches = [x for x in DIR.iterdir() if x.name.startswith(iid)] if DIR.exists() else []
        if len(matches) != 1:
            raise SystemExit(f"no incident {iid}")
        d = matches[0]
    return d


def prune():
    ds = sorted(x for x in DIR.iterdir() if x.is_dir())
    for d in ds[:-KEEP]:
        shutil.rmtree(d, ignore_errors=True)
