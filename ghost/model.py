"""The one model interface (docs/ghost/design.md, Models). Today: headless Claude Code on the owner's
subscription; later the API (any provider) behind the same ask(). Every call becomes a trace row.

ask() is for the small, quick judgments (the candidate filter, the routers): no tools, no session, a
JSON schema for the answer. Workers run the full mc-architect agent instead (ghost/activities.py)."""

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid

from . import config, db

sys.path.insert(0, str(config.ROOT))
from architect import claude  # noqa: E402

LEAN = [*claude.LEAN, "--no-session-persistence", "--tools", ""]
MODELS = {"filter": "haiku", "router": "haiku", "worker": "sonnet"}
_stored = set()


def name(role):
    """The model for a job: GHOST_MODEL_<ROLE> overrides the default."""
    return os.environ.get(f"GHOST_MODEL_{role.upper()}", MODELS[role])


class ModelError(RuntimeError):
    pass


def _prompt_hash(system):
    h = hashlib.sha256(system.encode()).hexdigest()[:16]
    if h not in _stored:
        db.run("INSERT INTO prompts (hash, body) VALUES (%s, %s) ON CONFLICT DO NOTHING", h, system)
        _stored.add(h)
    return h


def ask(role, system, prompt, schema, task_id=None, trace_id=None, timeout=90, notes=None):
    """The model's answer as a dict matching `schema`. Raises ModelError (after recording the trace).
    notes: a file the model may keep with Read / Edit / Write (its memory); every other path is denied."""
    model = name(role)
    trace_id = trace_id or uuid.uuid4().hex
    lean = LEAN if not notes else [x for x in LEAN if x not in ("--tools", "")] + [
        "--tools", "Read,Edit,Write", "--permission-mode", "dontAsk", "--add-dir", str(notes.parent),
        "--allowedTools", *(f"{t}(/{notes})" for t in ("Read", "Edit", "Write"))]
    cmd = ["claude", "-p", prompt, "--model", model, "--system-prompt", system, *lean,
           "--json-schema", json.dumps(schema), "--output-format", "json"]
    t0 = time.time()
    out, ok, answer = "", False, None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd="/tmp")
        out = r.stdout
        d = json.loads(out) if out.strip() else {}
        answer = d.get("structured_output")
        ok = answer is not None and not d.get("is_error")
        if not ok:
            out = out or r.stderr
    except (subprocess.TimeoutExpired, ValueError) as e:
        out = f"{type(e).__name__}: {e}"
    ms = int((time.time() - t0) * 1000)
    db.run("INSERT INTO traces (trace_id, span_id, task_id, role, model, prompt_hash, input, output, ms, ok) "
           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", trace_id, uuid.uuid4().hex[:16], task_id, role, model,
           _prompt_hash(system), prompt, json.dumps(answer) if ok else out[-4000:], ms, ok)
    if not ok:
        raise ModelError(f"{role} model call failed: {out[-300:]}")
    return answer
