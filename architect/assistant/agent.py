"""One architect request: a headless Claude session (the mc-architect agent) with the player's words and
context, fenced to the mc tools like the eval builders. Follow-ups resume the same session."""

import json
import os
import subprocess
import threading
import time

from .sessions import DIR, ROOT

TOOLS = ["Bash(./mc.py *)", "Read", "Write", "Edit", "Glob", "Grep"]
# Only the player's /arc yes and /arc undo change the world (the daemon runs them), never the agent.
# (Deny rules go in a settings file: a --disallowedTools pattern turned off all of Bash.)
DENIED = [f"Bash(./mc.py {c}:*)" for c in ("place", "undo", "cmd", "restart", "eval", "town")]


def settings():
    p = DIR / "agent-settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"permissions": {"deny": DENIED}}))
    return p
TIMEOUT = 15 * 60


def prompt(player, text, ctx, plan, resume):
    return "\n".join([
        f'{player} says (in game, via /arc): "{text}"',
        f"What the game told us about them: {json.dumps(ctx)}",
        f"Your plan file: {plan}",
        "This continues your conversation with them: change the design you previewed, preview it again."
        if resume else "A new request.",
        "Follow .claude/agents/mc-architect.md. You are headless: nobody answers questions except through "
        "mc say, and your final message is only a log line for us.",
    ])


class Run:
    """A running request; cancel() stops it."""

    def __init__(self, player, text, ctx, plan, run_id, model, resume=None, budget=3.0, transcript=None):
        cmd = ["claude", "-p", prompt(player, text, ctx, plan, bool(resume)), "--agent", "mc-architect",
               "--model", model, "--permission-mode", "dontAsk", "--output-format", "stream-json", "--verbose",
               "--max-budget-usd", str(budget), "--settings", str(settings()), "--allowedTools", *TOOLS]
        if resume:
            cmd += ["--resume", resume]
        env = {**os.environ, "MC_RUN_ID": run_id, "MC_PLAYER": player}
        self.started = time.time()
        self.transcript = transcript
        self.cancelled = False
        self.proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.timer = threading.Timer(TIMEOUT, self.cancel)
        self.timer.start()

    def cancel(self):
        self.cancelled = True
        self.proc.kill()

    def wait(self):
        """{session_id, result, cost, end, tools}: what the agent did."""
        result, session, tools = {}, None, []
        log = open(self.transcript, "w") if self.transcript else None
        for line in self.proc.stdout:
            if log:
                log.write(line)
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            session = ev.get("session_id") or session
            if ev.get("type") == "assistant":
                for c in ev["message"]["content"]:
                    if c.get("type") == "tool_use":
                        tools.append((c["name"], (c["input"].get("command") or c["input"].get("file_path") or "")[:200]))
            elif ev.get("type") == "result":
                result = ev
        self.proc.wait()
        self.timer.cancel()
        if log:
            log.close()
        end = "cancelled" if self.cancelled else {"success": "done"}.get(result.get("subtype"), result.get("subtype") or "error")
        return {"session_id": session, "result": (result.get("result") or "")[-2000:], "end": end,
                "api_usd": result.get("total_cost_usd"), "tools": tools,
                "minutes": round((time.time() - self.started) / 60, 1),
                "stderr": self.proc.stderr.read()[-500:] if end == "error" else ""}
