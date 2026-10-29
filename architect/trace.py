"""The bridge trace: one line per request to the bridge (local/runs/trace/<day>.jsonl): what was asked,
how big, how long, what came back. Every tool and script talks to the server through architect.bridge,
so nothing slips past (the command journal only sees mc commands). Kept 30 days."""

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "local" / "runs" / "trace"
KEEP_DAYS = 30


def summarise(path, body):
    """The request in a few fields, never the whole payload (a place can be megabytes)."""
    if not body:
        return {}
    out = {}
    for k in ("min", "max", "origin", "size", "pos", "on", "label", "command", "id", "world"):
        if k in body:
            out[k] = body[k]
    if "palette" in body:
        out["palette"] = len(body["palette"])
    if "blocks" in body:
        out["blocks"] = len(body["blocks"])
    return out


def record(path, body, ms, status, error=None, resp_bytes=0):
    DIR.mkdir(parents=True, exist_ok=True)
    line = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "run": os.environ.get("MC_RUN_ID", ""), "pid": os.getpid(),
            "path": path, "req": summarise(path, body), "ms": ms, "status": status, "bytes": resp_bytes}
    if error:
        line["error"] = str(error)[:400]
    with open(DIR / f"{time.strftime('%Y-%m-%d')}.jsonl", "a") as f:
        f.write(json.dumps(line) + "\n")


def tail(n=20, run=None):
    """The last n trace lines (of a run, if given), newest last."""
    out = []
    for p in sorted(DIR.glob("*.jsonl"), reverse=True):
        lines = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        if run:
            lines = [l for l in lines if l.get("run") == run]
        out = lines + out
        if len(out) >= n:
            break
    return out[-n:]


def prune():
    cutoff = time.time() - KEEP_DAYS * 86400
    for p in DIR.glob("*.jsonl"):
        if p.stat().st_mtime < cutoff:
            p.unlink()
