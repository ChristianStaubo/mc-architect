# The city harness: many agents building one city

A test of routing and multi-agent orchestration, separate from the ghosts: Kingsreach, a capital of
113 plots (about ten times Riverford), planned and built by over 200 agent runs in parallel on Temporal.
Code: `ghost/city/`. Run: `.venv/bin/python -m ghost city start|status|workers NAME`.

## The shape
```
CityWorkflow (orchestrator: decides order and concurrency, does no work itself)
  plan_macro        1 macro planner (Opus): districts + avenues          -> districts.json, layout roads
  plan_district x10 district planners (Sonnet) at once, each in its box  -> districts/<id>.json
  merge_and_check   merge, check; each district fixes only its own failures (up to 2 rounds)
  lay_ground        roads and terraces, by code, each once
  PlotWorkflow xN   a sliding window of N child workflows (N changeable while it runs):
      build_plot      builder agent (Sonnet): plan, place, audit, look, revise
      check_plot      audit + "did every edit stay inside the plot" (code)
      judge_plot      critic agent scores the contact sheet (1-10)
      (one fix round) when the audit fails or the score is under 6: the builder resumes its session
```
- **Boundaries by tools, not prompts:** each agent's Write/Edit are scoped to its own file (a district's
  plot file, a builder's plan); the critic can only read; Bash only `./mc.py` and never undo, cmd or the
  ghost. `city_agents` records every run's minutes, cost and refused tool calls.
- **Durable:** a worker restart retries the agents that were running (a fresh plot attempt first takes back
  what the interrupted one placed); a stopped run resumes, skipping finished plots. An orchestrator bug
  (fixed mid-run) was replayed from Temporal's history without redoing the plots already finished.

## Kingsreach, the first run (2026-11-06/07)
| | |
|---|---|
| plots | 113 built, 0 flawed, 0 edits outside their plot |
| agent runs | 363: 1 macro planner, 16 district planner runs (10 + 6 repairs), 178 builder runs, 168 critic runs |
| agent time | 340 agent-minutes in about 70 minutes of building (15 min planning, pilot 20 min, city 32 min at 6 then 12 builders, finish 3 min) |
| cost | about $56 equivalent (builders $46, critics $6, planners $5) |
| quality | critic mean 5.8/10; 51 plots took a fix round, first score 4.9 -> 5.8 |
| refused tool calls | 337, all Bash outside `./mc.py` (python, cat, ls, cd ... && ./mc.py); no attempt to write outside an agent's own files |

## What it showed
- **Parallel works; the plan is the weak link.** Builders are fast (1.5-3 min a building) and stay in their
  plots, but the macro plan used under half the site, on a grid, and the craftsmen's quarter rings an empty
  field. Planning has no judge: next is a plan critic scoring the map, with the macro planner revising.
- **Most plots are the same few kinds of house.** Designing a few variants per district and placing them by
  code would cut most of the builder time and cost.
- **Tool gaps the agents hit:** a way to list plots and read layouts without Python (most refusals), and
  `mc town shots` on a city larger than the bridge's 4M-block region limit.
- **Harness bugs found by running it:** argument order for `mc town`, `workflow.wait` returning lists,
  long critic answers cut before parsing, interrupted runs left "live" in the records. All fixed.
