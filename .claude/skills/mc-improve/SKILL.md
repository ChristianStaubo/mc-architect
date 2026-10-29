---
name: mc-improve
description: Run the mc-architect improvement loop — run the eval suite with builder agents, judge every build (audit + critic), read friction, fix the owning layer (parts, CLI, bridge, audit, style rules), leave a test, re-run, commit. Use for "keep improving", "run the evals", "work on the builder", or a scheduled improvement run. Only stops for the user when stuck or for taste/deploy decisions.
---

# The improvement loop (you are the fixer and the supervisor)

The method is `docs/agent-workflow.md` (from fm26-manager). In short: builders build, judges judge,
you fix the tools, the scoreboard says whether it worked. The user is paged only when you are stuck.

## One round
1. **Health.** `./mc.py doctor` (Docker Desktop: `open -a Docker`; server: `docker compose up -d`).
   `./mc.py eval gate` (the regression suite: unit tests, every part, plans, block names, place + undo,
   the door test, incident replays) must be 100% before and after every fix.
2. **Run.** `./mc.py eval run [--tasks a,b] [--trials 3] --label "<what changed>"` (docs/evals.md §7):
   it resets each site, runs a headless Sonnet builder per trial with the tools fenced in, grades it
   with the task's code graders and has Opus judges score its sheet. Never build for the builders.
3. **Check.** `./mc.py eval check <task> [--plan P]` grades one plan on a reset site (a reference by
   default), e.g. to see whether a grader is fair.
4. **Report.** `./mc.py eval report <run> [--vs <older run>]`: pass@k, pass^k, quality with intervals,
   failing graders, flags. Look at the sheets (`local/evals/<run>/<task>/<trial>/sheet.png`) and read
   a few transcripts yourself too: graders and judges can be wrong.
5. **Ratings.** Now and then, `python3 scripts/rating_page.py <run>` makes a rating page for the user to
   calibrate the judges against (docs/evals.md §10).
6. **Fix.** Read every friction report (`./mc.py friction`: stuck stops, gaps, auto-filed crashes),
   every incident (`./mc.py incidents`, then `./mc.py incident ID`: the error and stack, the last bridge
   requests and commands, the plan as it was, the server log; `replay` reruns it dry) and each builder's
   report (file any gap it mentions that isn't already friction: `MC_RUN_ID=<run> ./mc.py gap "..."`,
   then it's kind "gap"). Reproduce with replay before fixing; replay again after. For each problem,
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
