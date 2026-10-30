"""Headless Claude Code, the one way this harness starts it (eval builders, judges, the in-game architect):
`dontAsk` permissions (the user's default mode approves anything), and none of the user's MCP servers,
skills or slash commands: loading 19 MCP servers cost ~5 s of startup, and their tool definitions rode
along on every model call (docs/notes/architect-build-log.md, speed)."""

import json

LEAN = ["--strict-mcp-config", "--mcp-config", '{"mcpServers": {}}', "--disable-slash-commands"]
MC_TOOLS = ["Bash(./mc.py *)", "Read", "Write", "Edit", "Glob", "Grep"]
ENDS = {"success": "done", "error_max_budget_usd": "budget"}


def command(prompt, model, tools, budget, agent=None, settings=None, deny=(), resume=None, stream=True):
    cmd = ["claude", "-p", prompt, "--model", model, *LEAN, "--permission-mode", "dontAsk",
           "--max-budget-usd", str(budget), "--allowedTools", *tools]
    cmd += ["--output-format", "stream-json", "--verbose"] if stream else ["--output-format", "json"]
    if agent:
        cmd += ["--agent", agent]
    if settings:
        cmd += ["--settings", str(settings)]
    if deny:
        cmd += ["--disallowedTools", *deny]
    if resume:
        cmd += ["--resume", resume]
    return cmd


def result_of(lines):
    """The last `result` event of a stream-json transcript (cost, turns, why it ended)."""
    last = {}
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            last = ev
    return last


def end_of(result):
    """done, budget, or the raw subtype (error if there was no result at all)."""
    return ENDS.get(result.get("subtype"), result.get("subtype") or "error")
