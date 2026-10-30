# Evals

How we know a change made the builders better, not just different. Three suites, from fast to slow.

| Suite | Command | What it checks | Time |
|---|---|---|---|
| Regression gate | `./mc.py eval gate` | the toolkit still works | ~1 min |
| Build quality | `./mc.py eval run` | how well agents build | ~10-20 min |
| Architect behaviour | `./mc.py eval scenarios` | the in-game architect does the right thing | ~5 min |

## Regression gate
Everything that works must keep working: the unit tests, every building part and example plan audited in
a flat test world, block names checked against the server, place and undo restoring a plot exactly, the
redstone door tested live, and every build task's reference solution passing its own checks. It must be
100%. `./mc.py eval gate --offline` runs the half that needs no server (the pre-push hook uses it).

## Build quality
Fifteen tasks in `evals/tasks/`: a cottage on a meadow, a tavern on a slope, a covered bridge over a
river, a lighthouse on a point, a forest cabin that keeps the trees, and more. Each task is a brief, a plot
and its checks:

```json
{"id": "tight-cottage", "brief": "A tiny cottage that makes the most of a cramped 9 by 11 plot...",
 "plot": {"min": [-472, -48], "max": [-464, -38]},
 "graders": [{"code": "inside_plot"}, {"code": "door_reaches_outside"}, {"code": "contains", "any": ["*_bed"]},
             {"judge": "rubric", "dimensions": ["brief", "shape", "depth", "palette", "detail", "interior"]}]}
```

Each trial:
1. The plot is put back exactly as it was (`evals/sites/`), and the world is held still.
2. A builder agent works on it headless, limited to the `mc` tools.
3. **Code graders** decide pass or fail: can you walk to every door and storey, does it stay in its plot,
   is it over the water, are the trees still standing... (`architect/graders.py`).
4. **Judges** score the contact sheet 1-10 against `evals/RUBRIC.md`, three dimensions each.

`./mc.py eval report RUN` shows, per task, how many trials passed (pass@3 and pass^3), quality with a 90%
interval, cost and time. `--vs OLD_RUN` compares two runs task by task. Every task has a reference
solution (`evals/reference/`) that passes its checks, so a failing task means the builder, not the test.

## Architect behaviour
Nine scripted conversations in `evals/scenarios/`, played by virtual players on their own plots: build
here, build in my selection, change it, too big, not a build, unclear, cancel, yes with nothing waiting,
undo with nothing built. Checks are code: did it preview before placing, place exactly what it previewed,
stay where asked, and leave the ground exactly as it was after undo.

## Notes
- Agent runs use the Claude Code CLI on your subscription. Dollar figures in reports are API-equivalent
  usage, not charges.
- Results land in `local/evals/`; run summaries are committed to `evals/results/`.
- To add a task: write `evals/tasks/<id>.json`, capture its site (`architect/sites.py`), and add a
  reference plan that passes `./mc.py eval check <id>`.
- Design history and past runs: `docs/notes/evals-design.md`.
