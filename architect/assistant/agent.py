"""One architect request: a headless Claude session (the mc-architect agent) with the player's words and
context, fenced to the mc tools like the eval builders. Follow-ups resume the same session."""

import json
import os
import subprocess
import threading
import time

from .. import claude
from ..parts import cheatsheet
from .sessions import ROOT

# Only the player's /arc yes and /arc undo change the world (the daemon runs them), never the agent: the deny
# rules (a settings file; a --disallowedTools pattern turned off all of Bash) and mc.py's own role check.
SETTINGS = ROOT / ".claude" / "architect-settings.json"
TIMEOUT = 15 * 60
TEMPLATE = """from architect.build import Build
from architect.parts import walls, floor, gable_roof, door, window, light  # ...whatever you use

def build():
    b = Build("well")              # local coords: y 0 = ground floor, x/z from 0
    floor(b, 0, 0, 4, 4, 0, "cobblestone")
    b.set(2, 1, 2, "water")        # single blocks; b.fill(x1, y1, z1, x2, y2, z2, block) for boxes
    return b"""


def prompt(player, text, ctx, plan, resume, site=""):
    """The same reference first (parts, template: cached across requests), then this request."""
    if resume:
        lines = ["This continues your conversation with them: change the design you previewed, preview it again."]
    else:
        lines = [f"The parts (architect/parts.py; no need to read it):\n{cheatsheet()}",
                 f"A plan looks like this:\n{TEMPLATE}",
                 "A new request.",
                 f"The ground in front of them (already read for you, so skip mc site unless you build elsewhere):\n{site}"]
    lines += [f'{player} says (in game, via /arc): "{text}"',
              f"What the game told us about them: {json.dumps(ctx)}",
              f"Your plan file: {plan}",
              "Follow .claude/agents/mc-architect.md. You are headless: nobody answers questions except through "
              "mc say. End with one short line for our log, nothing more."]
    return "\n".join(lines)


class Run:
    """A running request; cancel() stops it. t0: when the player's wait began (all timings count from it)."""

    def __init__(self, player, text, ctx, plan, run_id, model, t0, resume=None, budget=3.0, transcript=None, site=""):
        cmd = claude.command(prompt(player, text, ctx, plan, bool(resume), site), model, claude.MC_TOOLS, budget,
                             agent="mc-architect", settings=SETTINGS, resume=resume)
        env = {**os.environ, "MC_RUN_ID": run_id, "MC_PLAYER": player, "MC_ROLE": "architect"}
        self.t0, self.transcript, self.cancelled = t0, transcript, False
        self.stderr = open(transcript.with_suffix(".stderr"), "w") if transcript else subprocess.DEVNULL
        self.proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=self.stderr, text=True)
        self.timer = threading.Timer(TIMEOUT, self.cancel)
        self.timer.start()

    def cancel(self):
        self.cancelled = True
        self.proc.kill()

    def _drain(self, log):
        """The rest of the transcript, until the process exits."""
        for line in self.proc.stdout:
            if log:
                log.write(line)
        self.proc.wait()
        for f in (log, self.stderr):
            if hasattr(f, "close"):
                f.close()

    def wait(self):
        """{session_id, result, end, api_usd, tools, minutes}: what the agent did. Returns as soon as its
        answer arrives; the process takes seconds more to exit and finishes in the background."""
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
                break
        threading.Thread(target=self._drain, args=(log,), daemon=True).start() if result else self._drain(log)
        self.timer.cancel()
        return {"session_id": session, "result": (result.get("result") or "")[-2000:],
                "end": "cancelled" if self.cancelled else claude.end_of(result),
                "api_usd": result.get("total_cost_usd"), "tools": tools,
                "minutes": round((time.time() - self.t0) / 60, 1)}
