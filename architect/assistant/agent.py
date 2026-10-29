"""One architect request: a headless Claude session (the mc-architect agent) with the player's words and
context, fenced to the mc tools like the eval builders. Follow-ups resume the same session."""

import datetime as dt
import json
import os
import subprocess
import threading
import time

from .sessions import DIR, ROOT

TOOLS = ["Bash(./mc.py *)", "Read", "Write", "Edit", "Glob", "Grep"]
# The architect needs no MCP servers; loading the user's (19 of them) cost ~5 s of startup and their tool
# definitions rode along on every model call (docs/in-game-architect.md, speed).
NO_MCP = ["--strict-mcp-config", "--mcp-config", '{"mcpServers": {}}']
LEAN = os.environ.get("MC_ARC_LEAN", "1") != "0"  # "0": the old way (all MCP servers, nothing pre-read), for A/B timing
TEMPLATE = """from architect.build import Build
from architect.parts import walls, floor, gable_roof, door, window, light  # ...whatever you use

def build():
    b = Build("well")              # local coords: y 0 = ground floor, x/z from 0
    floor(b, 0, 0, 4, 4, 0, "cobblestone")
    b.set(2, 1, 2, "water")        # single blocks; b.fill(x1, y1, z1, x2, y2, z2, block) for boxes
    return b"""
# Only the player's /arc yes and /arc undo change the world (the daemon runs them), never the agent.
# (Deny rules go in a settings file: a --disallowedTools pattern turned off all of Bash.)
DENIED = [f"Bash(./mc.py {c}:*)" for c in ("place", "undo", "cmd", "restart", "eval", "town")]


def settings():
    p = DIR / "agent-settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"permissions": {"deny": DENIED}}))
    return p
TIMEOUT = 15 * 60


def prompt(player, text, ctx, plan, resume, site=""):
    from ..parts import cheatsheet
    lines = [
        f'{player} says (in game, via /arc): "{text}"',
        f"What the game told us about them: {json.dumps(ctx)}",
        f"Your plan file: {plan}",
    ]
    if not LEAN:
        lines.append("A new request." if not resume else "This continues your conversation with them.")
    elif resume:
        lines.append("This continues your conversation with them: change the design you previewed, preview it again.")
    else:
        lines += ["A new request.",
                  f"The ground in front of them (already read for you, so skip mc site unless you build elsewhere):\n{site}",
                  f"The parts (architect/parts.py; no need to read it):\n{cheatsheet()}",
                  f"A plan looks like this:\n{TEMPLATE}"]
    lines.append("Follow .claude/agents/mc-architect.md. You are headless: nobody answers questions except through "
                 "mc say. End with one short line for our log, nothing more.")
    return "\n".join(lines)


class Run:
    """A running request; cancel() stops it."""

    def __init__(self, player, text, ctx, plan, run_id, model, resume=None, budget=3.0, transcript=None, site=""):
        cmd = ["claude", "-p", prompt(player, text, ctx, plan, bool(resume), site), "--agent", "mc-architect",
               *(NO_MCP if LEAN else []),
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

    def _drain(self, log):
        for line in self.proc.stdout:
            if log:
                log.write(line)
        self.proc.wait()
        if log:
            log.close()

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
                break  # the answer is in: the process takes seconds more to exit, don't hold the player up
        if result:
            threading.Thread(target=self._drain, args=(log,), daemon=True).start()
            log = None
        else:
            self.proc.wait()
        self.timer.cancel()
        if log:
            log.close()
        end = "cancelled" if self.cancelled else {"success": "done"}.get(result.get("subtype"), result.get("subtype") or "error")
        return {"session_id": session, "started": dt.datetime.fromtimestamp(self.started).isoformat(timespec="seconds"), "result": (result.get("result") or "")[-2000:], "end": end,
                "api_usd": result.get("total_cost_usd"), "tools": tools,
                "minutes": round((time.time() - self.started) / 60, 1),
                "stderr": self.proc.stderr.read()[-500:] if end == "error" else ""}
