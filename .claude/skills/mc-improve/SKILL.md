---
name: mc-improve
description: Run the mc-architect improvement loop — run the eval suite with builder agents, judge every build (audit + critic), read friction, fix the owning layer (parts, CLI, bridge, audit, style rules), leave a test, re-run, commit. Use for "keep improving", "run the evals", "work on the builder", or a scheduled improvement run. Only stops for the user when stuck or for taste/deploy decisions.
---

# The improvement loop (you are the fixer and the supervisor)

The method is `docs/agent-workflow.md` (from fm26-manager). In short: builders build, judges judge,
you fix the tools, the scoreboard says whether it worked. The user is paged only when you are stuck.

## One round
1. **Health.** `./mc.py doctor` (Docker Desktop: `open -a Docker`; server: `docker compose up -d`).
   `python3 -m unittest discover tests` must pass.
2. **Run id.** Next free `rN` (`./mc.py eval report` lists runs). Reset plots: `./mc.py eval reset <task>`
   for every task you will run.
3. **Build.** For each task (`./mc.py eval list`), spawn an `mc-builder` agent (Sonnet) with:
   the task id, the run id, and "follow .claude/agents/mc-builder.md". Plots are separate, so run
   builders in parallel (up to 5). Never build for them.
4. **Judge.** For each finished task: `./mc.py shots <edit>` (the builder's last edit for that task:
   `./mc.py edits`), then spawn an `mc-critic` agent with the brief (`./mc.py eval brief`), the sheet
   path, and `local/evals/<run>/<task>.critique.json` as its output path. Then
   `./mc.py eval record <task> --run <run> --critique <that path>`.
5. **Scoreboard.** `./mc.py eval report <run>` and `./mc.py eval report` (all runs). Look at the
   sheets yourself too: the critic can be wrong.
6. **Fix.** Read every friction report (`./mc.py friction`) and builder report. For each problem,
   fix the **owning layer**, smallest change that removes the class of problem:
   | Symptom | Layer |
   |---|---|
   | builder faked something by hand, or stalled on geometry | a new part in `architect/parts.py` (+ the table in mc-build) |
   | a command was confusing, failed, or took many calls | `mc.py` / the skill text |
   | the world did something the bridge didn't report | `plugin/` (then `scripts/build-plugin.sh`, `./mc.py restart`) |
   | a broken build passed the audit | a new check in `architect/audit.py` + a test in `tests/` |
   | the critic and your own eyes disagree | `evals/RUBRIC.md` / `.claude/agents/mc-critic.md` |
   | the same taste mistake in several builds | a rule in `STYLE.md` (dated) |
   Leave a test that would have caught it when the layer is code. Resolve the friction:
   `./mc.py friction resolve <id> "<fix, commit>" --cause <cause>`.
7. **Commit.** Small commits straight to main, no attribution lines, never push without the user.
8. **Next round** with the same tasks to measure the fix. Keep a short log in `local/notes/loop.md`:
   run, scores, what changed, what you expect next time.

## Scoreboard (what "better" means)
- **Objective:** mean critic `overall` of passing builds (`quality`).
- **Constraints:** pass rate (audit clean + brief's musts) never drops; calls per task and failed
  calls trend down; builds per stop (`./mc.py friction stats`) trends up.
- A change that raises quality but breaks a constraint is not an improvement; revert it.

## When to ask the user (otherwise decide, write down why, keep going)
- Taste calls the rubric can't settle (two good directions), or the critic and your eyes keep disagreeing:
  ask for a rating; log it to `evals/ratings.jsonl` and recalibrate the rubric.
- Anything on a server other than the local test server; deleting worlds; spending beyond what they set.
- You're stuck on the same failure after two fixes.
