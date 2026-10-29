# mc-architect: instructions for Claude

You build things in Minecraft for the user and their friends (houses now; towns, cathedrals and
landscapes next) and you improve the harness that does it. Work on the local test server; the friends'
server only gets builds the user approves.

## Start here
1. `./mc.py doctor`: Docker, server and bridge up? (`open -a Docker`, `docker compose up -d`.)
2. Building something → skill **mc-build** (and `STYLE.md`). Improving the harness, running evals,
   "keep going" → skill **mc-improve** (and `docs/agent-workflow.md`).
3. `./mc.py -h`: the only tool. Never drive the game UI.

## Layout
- `mc.py`: the CLI (its commands live in `architect/cli/`, one module per group). `architect/`: build grids,
  parts, renders, audit, edits (undo), journal, evals; `architect/assistant/`: the in-game architect's daemon.
- `plans/`: reusable plans (examples). Builders' plans for evals: `local/plans/<run>/`.
- `evals/tasks/`: the eval suite (v2: graders per task), `evals/sites/` their pristine plots, `evals/reference/`
  a passing plan per task (builders must never read these); `evals/RUBRIC.md`: the critic's rubric. `STYLE.md`: the house style.
- `.claude/agents/`: `mc-builder` (Sonnet, builds a task), `mc-critic` (scores from pictures), `mc-architect`
  (answers players' `/arc` in game: preview and talk, never place; docs/in-game-architect.md).
- `evals/scenarios/`: scripted `/arc` conversations checked by code (`mc eval scenarios`).
- `plugin/`: the Paper plugin (Java), one package per feature: `bridge/` (the agent's API), `travel/`
  (homes, /tpa), `architect/` (/arc, inbox, previews); a new feature implements `core/Feature`. `docker/`, `compose.yaml`: the server. `tests/`: `python3 -m unittest discover tests`.
- `local/` (gitignored): renders, edits + snapshots, notes, eval results, and the flight recorder:
  `runs/commands.jsonl` (every mc command), `runs/trace/` (every bridge request), `runs/incidents/`
  (a failure's error, stack, recent requests and commands, plan copy, server log), `runs/friction/`.

## Rules
- Read every PNG you produce. An output line only proves the call ran.
- Every change goes through `place` (snapshots, undo survives restarts). `mc cmd` refuses
  stop/restart/reload: use `./mc.py restart`.
- Block states matter: set connections, door halves and bed parts explicitly.
- Plugin change: `scripts/build-plugin.sh`, then `./mc.py restart`.
- Dependencies only through `scripts/deps.py` (official sources, hash-checked, at least 7 days old).
- `./mc.py eval gate` (regression, docs/evals.md) passes before a commit; a new part gets a reference
  plan in `architect/regression.py`. `scripts/install-hooks.sh` adds a warn-only pre-push check.
- Commits: small, no attribution lines, never push without the user.
