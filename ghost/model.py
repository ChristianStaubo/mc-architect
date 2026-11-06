"""The one model interface (docs/ghost/design.md, Models). Today: headless Claude Code on the owner's
subscription; later the API (any provider) behind the same ask(). Every call becomes a trace row.

ask() is for the small, quick judgments (the candidate filter, the routers): no tools, no session, a
JSON schema for the answer. Workers run the full mc-architect agent instead (ghost/activities.py)."""

import hashlib
import json
import os
import subprocess
import time
import uuid

from . import db

LEAN = ["--strict-mcp-config", "--mcp-config", '{"mcpServers": {}}', "--disable-slash-commands",
        "--no-session-persistence", "--tools", ""]
MODELS = {"filter": "haiku", "router": "haiku", "worker": "sonnet"}


class ModelError(RuntimeError):
    pass


def _prompt_hash(system):
    h = hashlib.sha256(system.encode()).hexdigest()[:16]
    db.run("INSERT INTO prompts (hash, body) VALUES (%s, %s) ON CONFLICT DO NOTHING", h, system)
    return h


def ask(role, system, prompt, schema, task_id=None, trace_id=None, timeout=90):
    """The model's answer as a dict matching `schema`. Raises ModelError (after recording the trace)."""
    model = os.environ.get(f"GHOST_MODEL_{role.upper()}", MODELS[role])
    trace_id = trace_id or uuid.uuid4().hex
    cmd = ["claude", "-p", prompt, "--model", model, "--system-prompt", system, *LEAN,
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
