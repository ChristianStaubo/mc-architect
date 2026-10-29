"""The flight recorder: one line per mc command (local/runs/commands.jsonl) and friction reports, the
builder's clean "I'm stuck" stops (local/runs/friction/). Decides nothing; the fixer reads it."""

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "local" / "runs"
JOURNAL = RUNS / "commands.jsonl"
FRICTION = RUNS / "friction"
CAUSES = ("missing-part", "cli", "bridge", "judge", "taste", "terrain", "render", "brief", "bug")


def run_id():
    return os.environ.get("MC_RUN_ID", "")


def log(cmd, argv, ms, ok, error=None, extra=None):
    RUNS.mkdir(parents=True, exist_ok=True)
    line = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "run": run_id(), "cmd": cmd, "argv": argv,
            "ms": ms, "ok": ok}
    if error:
        line["error"] = str(error)[:500]
    if extra:
        line.update(extra)
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(line) + "\n")


def entries(run=None):
    if not JOURNAL.exists():
        return []
    out = [json.loads(l) for l in JOURNAL.read_text().splitlines() if l.strip()]
    return [e for e in out if run is None or e.get("run") == run]


def stuck(text, kind="stuck", **extra):
    """Save what the builder was doing when the tools fell short. kind: stuck (it stopped), gap (a tool
    was missing or awkward and it carried on), incident (filed automatically on a crash), report (a gap
    the fixer copied from a builder's final report)."""
    FRICTION.mkdir(parents=True, exist_ok=True)
    fid = time.strftime("f%Y%m%d-%H%M%S")
    n = 1
    while (FRICTION / f"{fid}.json").exists():
        fid = time.strftime("f%Y%m%d-%H%M%S") + f"-{n}"
        n += 1
    report = {"id": fid, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "run": run_id(), "report": text, "kind": kind,
              "recent": entries(run_id() or None)[-15:], "status": "open", **extra}
    (FRICTION / f"{fid}.json").write_text(json.dumps(report, indent=2))
    return fid


def reports(include_resolved=False):
    if not FRICTION.exists():
        return []
    out = [json.loads(p.read_text()) for p in sorted(FRICTION.glob("f*.json"))]
    return [r for r in out if include_resolved or r["status"] == "open"]


def resolve(fid, fix, cause, repeat_of=None):
    if cause not in CAUSES:
        raise SystemExit(f"cause must be one of: {', '.join(CAUSES)}")
    p = FRICTION / f"{fid}.json"
    r = json.loads(p.read_text())
    r.update(status="resolved", fix=fix, cause=cause, resolved=time.strftime("%Y-%m-%dT%H:%M:%S"))
    if repeat_of:
        r["repeat_of"] = repeat_of
    p.write_text(json.dumps(r, indent=2))
    return r
