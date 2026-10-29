# Evals v2: design and how it works

The eval system that tells us whether the harness (tools, parts, skills, prompts, models) builds better
Minecraft than it did yesterday, and stops us shipping a change that makes it worse. v1 was a one-off
benchmark run by hand from a chat; this is the version we can run headless, repeat, compare and trust.

Sources: Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
(Jan 2026); fm26-manager's `docs/agent-workflow.md` and `docs/audit-2033-08.md`; our own r1, r2 and
town1 runs.

## 1. Goals and non-goals

**Goals**
- Answer "did this change help, hurt, or do nothing?" with numbers that survive noise.
- Catch regressions in seconds, before every push.
- Measure the builder (model + harness) on what players see, graded mostly by code, partly by
  calibrated judges, and ultimately by the user's own taste.
- Run without a human or a chat: one command, any time, from a script or a schedule.
- Grow from real failures: every friction report and incident can become a task.

**Non-goals (for now)**
- Public benchmarking or comparing against other systems.
- Statistical rigour beyond what changes our decisions (bootstrap intervals, not papers).
- Grading in-game "feel" from a live client (pictures and code checks only; the user rates in-game).

## 2. Where v1 falls short

| v1 | Problem | v2 |
|---|---|---|
| 5 tasks, 1 trial each | Agents are non-deterministic; r1 → r2 (+1.0) may be noise | 3 trials per task, rates with intervals |
| One holistic Opus critic | Uncalibrated, unmeasured variance, no "can't tell" | Code graders first; per-dimension judges with an escape hatch; judge variance measured |
| Musts: door, interior | Most requirements are checkable but left to the critic | A catalogue of code graders per task |
| Runs launched by hand from chat | Not reproducible, schedulable or CI-able; transcripts lost | `mc eval run` launches headless builders (`claude -p`), saves everything |
| Shared live world, "please don't read r1" | Leakage and drift between trials | Each trial on a reset plot, its own workspace, read access limited |
| No versions on results | Can't attribute a change | Every run stamped: commit, models, prompt and skill hashes |
| r2 changed tools *and* process | Confounded | One change per comparison run |
| No regression suite | Things that worked can silently break | A regression suite that must stay at 100% |
| One aggregate human rating | No real calibration | Per-build blind ratings on a rating page; critic–human agreement tracked |

## 3. Vocabulary (Anthropic's, applied here)
- **Task**: one brief on one plot with its graders (e.g. `tavern-slope`).
- **Trial**: one builder attempt at a task, from a clean plot to a final edit.
- **Grader**: one check. *Code graders* read the world (via the bridge) and the journal; *judges* are
  model graders reading the contact sheet; the *human* rates on the rating page.
- **Transcript**: the builder's full session (stream-json from `claude -p`) plus our journal and trace.
- **Outcome**: the blocks in the world after the trial, never what the builder says it built.
- **Suite**: a set of tasks run together (`regression`, `capability`, later `town`, `redstone`).
- **Run**: one execution of a suite at one version of everything, with a manifest.

## 4. Suites

### 4.1 Regression (code only, deterministic, ~1-3 min, must be 100%)
Things that already work and must keep working. No model in the loop except where noted.
- **Parts**: every part in `architect/parts.py` builds a small reference plan that passes the audit
  (today's `plans/parts_sampler.py`, split per part), previewed with `place --dry-run`.
- **Placement**: place a reference plan on each eval plot, check foundation/clearing/trees, undo, and
  check the plot is restored block for block (`edits` snapshot round trip).
- **Audit**: `tests/` (already 15 tests) plus a recorded fixture per audit check that ever misfired.
- **Redstone**: `scripts/test_door_live.py` (both levers), and every future contraption's live test.
- **Replays**: every resolved incident (`local/runs/incidents/`) whose cause was a tool bug, replayed dry;
  it must now pass. (fm26's lesson: a fixed failure without a replayable fixture comes back.)
- **Reference builds**: each capability task's reference plan placed and graded; it must pass its own
  code graders (proves the task and the graders work: Anthropic's "0% everywhere means a broken task").
Gate: `mc eval gate` runs this suite; a git pre-push hook calls it (opt-in, see §11).

### 4.2 Capability (builders, 3 trials per task, ~1-2 h per full run)
Things we want to get better at. Expected to start well below the ceiling.
- The 5 v1 tasks, rewritten in the v2 format (§5).
- New tasks from what went wrong (friction report → task): a building on a steep plot (split levels), a
  bridge over a ravine, a stall row that must not be symmetric, an interior-heavy build (library), a
  build that must NOT touch neighbouring trees or water (a "should not" case), a tight plot (the
  overhang problem), a tower whose stairs must reach every floor.
- Target size: 15-20 tasks in the first version, growing toward 30-50 (Anthropic: 20-50 from real failures).
- Each task tagged with difficulty (1-3) and kind (`should` / `should-not`).
- **Graduation**: a task whose code graders pass in all trials (pass^3 = 100%) for 3 consecutive runs
  moves to regression (its reference + a frozen best trial plan). **Saturation**: when the suite mean
  passes 80%, add harder tasks.

### 4.3 Later suites
- **town**: a planner + builders task on a fixed site with town-level graders (roads connected, every
  door reaches a road, no plot overlaps, earthworks bounds) and the town judge.
- **redstone**: contraption tasks graded entirely by live tests (press → expected state after N ticks).

## 5. Task format v2

```json
{
  "id": "tavern-slope",
  "suite": "capability",
  "kind": "should",
  "difficulty": 2,
  "brief": "A two-storey tavern set into a grassy hillside: ...",
  "style": "medieval timber frame",
  "plot": {"min": [-224, 208], "max": [-201, 231]},
  "budget": {"calls": 45, "minutes": 25, "usd": 3.0},
  "graders": [
    {"code": "audit_clean"},
    {"code": "storeys", "min": 2},
    {"code": "stairs_reach_every_storey"},
    {"code": "door_reaches_outside"},
    {"code": "indoor_floor", "min": 30},
    {"code": "lit_indoors"},
    {"code": "contains", "any": ["oak_sign", "spruce_sign", "*_banner", "*_wall_sign"]},
    {"code": "floor_levels", "min": 2},
    {"code": "inside_plot"},
    {"judge": "rubric", "dimensions": ["brief", "shape", "depth", "palette", "proportion", "detail", "site", "interior"]}
  ],
  "pass": "all code graders pass",
  "reference": "evals/reference/tavern-slope.py"
}
```

### 5.1 Code grader catalogue (`architect/graders.py`, pure functions over the region, like the audit)
| Grader | Checks |
|---|---|
| `audit_clean` | no audit FAIL |
| `inside_plot` | every changed block within the plot (from the edit's box and the snapshot diff) |
| `untouched_outside` | nothing outside the plot changed (diff against the pre-trial snapshot): the "should not" check |
| `storeys` | count of storeys (the audit's indoor levels with 4+ floor spots) |
| `stairs_reach_every_storey` | a walkable path (stairs, ladders) connects every storey (flood with step-up rules) |
| `door_reaches_outside` | from every door, open air at ground level is reachable |
| `height` | top of the build ≥ N above its floor |
| `over_water` | ≥ N blocks of the build stand over water (posts/deck) |
| `indoor_floor`, `lit_indoors` | from the audit's stats |
| `contains` / `contains_not` | block names present / absent (glob patterns) |
| `floor_levels` | people stand at ≥ N different heights on and in the build (split levels, terraces) |
| `water_untouched` | no water block changed |
| `keeps_trees` | a share of the plot's logs still standing |
| `light_near_top` | a light source in the top N blocks (lighthouse, watchtower) |
| `not_symmetric` | the build isn't mirror-symmetric (for the market task) |
| `materials` | 3-5 main materials (STYLE.md palette rule) |
| `road_reached` | (town) the door is within 4 blocks of a road |
| `redstone` | (redstone) drive inputs, read outputs, compare to the expected table |
Each returns `{"pass": bool, "value": ..., "detail": "..."}` so failures explain themselves.

### 5.2 Reference solutions
Each capability task gets a reference plan (`evals/reference/<task>.py`), written once by a strong model
and reviewed: it must pass all the task's code graders. It proves the task is solvable and the graders
are fair, and it's the regression check for the graders themselves.

## 6. Trial isolation
- **Plot reset**: before a trial, the plot is restored to its pristine snapshot
  (`evals/sites/<task>.json.gz`, captured once from the seeded world, committed small or regenerated).
  Not "undo the last run's edits": a full restore, so drift and leftovers can't leak in.
- **World state**: on the test server, `gamerule advance_time false`, `advance_weather false`, time fixed
  at noon, `random_tick_speed 0` during runs (no grass spread, leaf decay or crop growth between snapshot
  and grading), peaceful (already). Set by `mc eval run`, restored after. (26.3's rule names, checked on
  the server; the old camelCase names make the bridge return HTTP 500, which the bridge should report as
  400.)
- **Workspace**: each trial gets `local/evals/<run>/<task>/<trial>/` for its plan and its transcript;
  the builder's `MC_RUN_ID` is `<run>:<task>:<trial>`; `place --task` refuses other plots (already).
- **Read limits**: builders run headless with `--allowedTools` limited to Bash(./mc.py *), Read, Write,
  Edit, Glob, Grep, and a settings file denying `Read(local/evals/**)` and `Read(local/plans/**)` except
  their own workspace. Leakage becomes impossible, not just discouraged.
- **Concurrency**: tasks have separate plots, so trials of different tasks run in parallel (cap 5); the
  3 trials of one task run one after another on the reset plot.
- **Server**: one server per run; a crashed server marks the affected trials `error` (not `fail`) and
  they're retried once.

## 7. The runner: `mc eval run`

```
mc eval run --suite capability [--tasks a,b] [--trials 3] [--model claude-sonnet-...]
            [--judge-model claude-opus-...] [--label "dormer_on part"]
mc eval gate                  # regression suite, exit 1 on any failure
mc eval report [RUN] [--vs RUN]
mc eval rate                  # open the blind rating page for the newest run
```
Per trial:
1. Reset the plot (§6), set world rules.
2. Launch the builder: `claude -p "<task prompt>" --agent mc-builder --model <pinned>
   --output-format stream-json --verbose --max-budget-usd <budget> --allowedTools ... --settings
   <read-deny settings>`, cwd = the repo, a wall-clock timeout = the budget's minutes. Save the
   stream-json as the transcript (it also carries the token counts and cost).
3. When it ends (done, stuck, budget, timeout), take the trial's last live edit as the outcome.
4. Run code graders on the outcome; make the contact sheet; run judges (§8).
5. Write `trial.json` (§9) and leave the plot built until the next trial resets it (so the user can
   look at the latest).
Headless means it can run on a schedule (nightly) or before a release, and the main session only reads
the report.

## 8. Grading

**Order**: code graders first. A trial passes when every code grader passes (that's the pass/fail behind
pass@k and pass^k). Judges score quality on top; they never decide pass/fail.

**Judges** (model graders, Anthropic's practices):
- One isolated judge per rubric dimension (8 small calls instead of one holistic one), each seeing only
  the brief, its dimension's rubric text with anchored examples (what a 3, 5, 8 look like), and the
  contact sheet. Structured output: `{"score": 1-10 | "unknown", "evidence": "..."}`.
- `unknown` is allowed (a facade the sheet doesn't show); unknown dimensions are excluded, not zeroed.
- **Quality** = mean of the known dimension scores. (Anthropic also suggests a holistic overall; we keep
  one "overall" judge as a ninth dimension so we can compare with v1.)
- **Judge variance**: each judge runs twice on the same sheet at temperature default; the run reports the
  judges' own spread. If two runs of the same judge disagree by > 1.5 on average, the rubric text for that
  dimension is too vague: fix it before trusting comparisons.
- The judge model differs from the builder model where possible (builder Sonnet, judge Opus), and its id
  and the rubric file hash are in the manifest.

## 9. Results and reporting

**Layout**
```
local/evals/<run>/manifest.json           # version stamp (below)
local/evals/<run>/<task>/<trial>/         # plan.py, transcript.jsonl, sheet.png, trial.json
evals/results/<run>.json                  # committed summary: per task and overall (small)
```
**Manifest**: run id, suite, label, start/end, git commit (+ dirty flag), builder model id, judge model
id, hashes of: `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `STYLE.md`, `evals/RUBRIC.md`, the task
files, `architect/parts.py`; Paper/WorldEdit versions; trials per task.

**trial.json**: task, trial, outcome edit, each grader's result, judge scores (with unknowns and both
repeats), pass, quality, calls, failed calls, audit fails during the trial, gaps/stucks filed, tokens in
and out, cost, wall time, end reason (done / stuck / budget / timeout / error).

**Report** (`mc eval report RUN [--vs OLD]`):
- Per task: pass rate over trials, **pass@3** (any trial passed) and **pass^3** (all passed), quality
  mean ± bootstrap 90% interval, tokens, cost, minutes, calls.
- Overall: mean pass^3, mean quality ± interval, total cost and time, stops per trial.
- **Comparison**: paired by task (same tasks in both runs), the difference in quality and pass rate with
  a bootstrap interval; a change "helped" only if the interval clears 0. Grader-level diffs show *what*
  changed ("stairs_reach_every_storey 2/5 → 5/5").
- Flags: tasks at 0% in all trials (broken task?), tasks at 100% three runs running (graduate),
  suite mean > 80% (add harder tasks), judge disagreement > 1.5 (vague rubric).

## 10. Calibration with the user
- **Rating page**: an Artifact page (with a shared database) showing the newest run's contact sheets
  blind (no task names, no scores, shuffled, including some reference builds), a 1-10 rating and an
  optional note each. Ratings land in `evals/ratings.jsonl` per build, with the run and trial.
- **Agreement**: Spearman correlation and mean bias between the judges' quality and the user's ratings,
  per dimension where the user also says why. Target: correlation ≥ 0.7, |bias| ≤ 1.
- **Updates**: when they diverge, the rubric changes (anchored examples from the user's own ratings),
  logged with a date in `evals/RUBRIC.md`; the next run measures agreement again.
- **Cadence**: ~10-15 ratings after a run when the user has five minutes; not every run.

## 11. Gating and cadence
- `mc eval gate` (regression) before every push: a `pre-push` hook, opt-in via `scripts/install-hooks.sh`.
- Capability run: on demand per change (with `--label`), and nightly while we're iterating (scheduled
  task), each change measured on its own run (one change at a time; §2).
- Towns and redstone suites: when those capabilities are being worked on.

## 12. Cost and time (estimates to check on the first run)
Builders and judges run `claude -p` on the user's claude.ai subscription (no API key), so nothing is
billed per run. The dollar figures in reports (`api_usd`) are the CLI's API-price estimate of the
tokens used: a measure of how much of the subscription's usage a run takes, and a cap per trial
(`--max-budget-usd`), not a charge.
- Builder trial: ~70-120k tokens, ~1-4 min (r2/town1 builders). 15 tasks × 3 trials ≈ 45 trials ≈ 4-5M
  tokens, ~30-60 min wall with 5 in parallel.
- Judges: 9 dimensions × 2 repeats × 45 trials ≈ 800 small calls with one image each.
- Regression suite: no model calls, 1-3 minutes.
The report prints actual cost per run so we can trim (fewer trials on stable tasks, judges once).

## 13. Rollout
1. **Regression suite + gate** (fast win, no models): parts, placement round trip, audit fixtures,
   door test, incident replays. **Done 2026-10-29**: `architect/regression.py`, `mc eval gate`
   (15 checks, ~15 s, 100%); the pre-push hook runs its offline half (no world changes while someone
   plays) and warns.
2. **Task format v2 + code graders + reference plans.** Done 2026-10-29 for 15 tasks (the 5 v1 tasks
   plus 10 on new sites: steep slope, river crossing, tight plot, pond, point, hilltop, forest...).
   `architect/graders.py` (19 graders, unit tests in `tests/test_graders.py`), pristine sites in
   `evals/sites/` (`architect/sites.py`: capture once, reset before every trial), `mc eval check TASK
   [--plan P]` (reset, place, grade). Every reference passes its graders and the gate checks them
   (group "graders"). Lessons: a reset must retire the task's old edits (placement read them as
   ground), doors must count as walkable, and the world must hold still (no random ticks) between a reset
   and the grading; unstable wild mushrooms were dropped from the site snapshots.
3. **Runner**: `mc eval run [--tasks a,b] [--trials 3]` (`architect/trials.py`).
4. **Judges** (`architect/judges.py`: three judges per trial, three dimensions each, `unknown`
   allowed, trial 1 of each task judged twice) and **report** (`architect/scoreboard.py`, `mc eval
   report RUN [--vs OLD]`; the summary is committed to `evals/results/<run>.json`).
5. **Rating page** (`scripts/rating_page.py`) + calibration.
6. **Grow the capability suite** to 20 tasks from friction; first real A/B: one change, two runs.
7. Town and redstone suites.

## 14. Decisions (the user, 2026-10-29)
1. **Trials per task**: 3.
2. **Builder model for evals**: Sonnet pinned; Opus evaluated occasionally.
3. **Pre-push gate**: warn only, for now.
4. **Rating page**: an Artifact page for blind ratings is fine.
5. **Cadence**: capability runs on demand (no nightly runs for now).

## 15. Runs

### c1029-1705: first v2 capability run (15 tasks x 3, Sonnet builders, Opus judges)
- **Pass**: 80% of trials; pass@3 100% of tasks, pass^3 60%. Quality 5.22 (90% CI 5.12-5.33); the
  judges' self-spread is 0.26, so the rubric is specific enough to compare runs.
- **Failures are real** (checked by hand): chapel and tavern doors 3 blocks up a plinth with no steps,
  pond posts in the water the brief said to leave, a forest cabin that cut most of the grove.
- **Builders stop at the minimum**: ~11 mc calls of 30-50 allowed, ~1 minute, two placements (the
  agent's "done" bar), no critique round; the cottage builder copied `plans/cottage.py`. Quality sits
  below r2 (6.0), which had a critic and a fixer in the loop. The next harness change to A/B: a
  self-critique round against the rubric before stopping, and a done bar on quality, not placements.
- **Isolation hole, fixed**: the user's default permission mode (auto) let builders run any Bash
  (cat, grep, python3). No transcript touched the answers (checked), but trials now run with
  `--permission-mode dontAsk` (verified: `./mc.py` runs, `cat evals/reference/...` and Read are refused).
- **Usage**: ~$0.17 of API-equivalent usage per builder trial, ~$0.80 per judged trial (judges are
  most of the $44); 45 trials in ~10 minutes of wall time at 5 in parallel.
