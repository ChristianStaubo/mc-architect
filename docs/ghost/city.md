# The city harness: many agents building one city

A test of routing and multi-agent orchestration, separate from the ghosts: Kingsreach, a capital of
113 plots (about ten times Riverford), planned and built by over 200 agent runs in parallel on Temporal.
Code: `ghost/city/`. Run: `.venv/bin/python -m ghost city start|status|workers|decide NAME`.

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
- **Escalation, not guessing:** a planner that can't go on without a decision that isn't its to make (removing
  something built, leaving its box) changes nothing and ends with `DECISION NEEDED: question || option || ...`.
  The orchestrator stores it (`city_decisions`), shows it in `city status`, and waits on an `answer` signal
  while the other districts carry on; `ghost city decide NAME --run R --key K --answer TEXT` resumes that
  planner's session with the answer. Removing a built plot is only allowed after such an answer: its blocks
  are taken back and the plot marked `removed`; a planner that drops one without asking fails.
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

## Infill: filling the hollow districts (2026-11-07)
The first plan left the district middles empty. An infill run gives each hollow district's planner its
coverage and the size of the hole, keeps every built plot, and adds lanes, a centrepiece and new plots.

| run | what | result |
|---|---|---|
| kr1-infill | northgate, harbour, riverside, craftsmen | 26 plots in about 8 min, critic mean 5.6; craftsmen added nothing: its middle is ringed by built plots and the river, so no lane fits, and the planner's question had nowhere to go |
| kr1-craftsmen | craftsmen again, through the escalation path | the planner asked (east lane out of its box / remove a west plot / move a row plot); answered "remove one west plot, a T of lanes, a smiths' green"; it removed `craftsmen_smithy_hill`, laid 3 lanes and 13 plots in 9 min; critic mean 5.9; $5.40 |

Share of each district's box that is plots or streets:

| district | before | after |
|---|---|---|
| northgate | 38% | 69% |
| harbour | 30% | 57% |
| riverside | 55% | 67% |
| craftsmen | 35% | 64% |

Found by running it: removing a plot took minutes of undo with no heartbeat, so Temporal timed the step out
and retried it; the retry read the already-edited district file, saw nothing removed, and left the terrace
and the record behind. Fixed: heartbeats during the undo, and "what was removed" comes from the built layout,
not the file. (The terrace stayed: the new lane runs over it.)

## What it showed
- **Parallel works; the plan is the weak link.** Builders are fast (1.5-3 min a building) and stay in their
  plots, but the macro plan used under half the site, on a grid, and the craftsmen's quarter rings an empty
  field. Planning has no judge: next is a plan critic scoring the map, with the macro planner revising.
- **Most plots are the same few kinds of house.** Designing a few variants per district and placing them by
  code would cut most of the builder time and cost.
- **Tool gaps the agents hit:** a way to list plots and read layouts without Python (most refusals), and
  `mc town shots` on a city larger than the bridge's 4M-block region limit. Fixed with `mc town plots`,
  `mc town check --district D` and one line in every prompt (Bash only starts with `./mc.py`): in the craftsmen
  rerun the cd/sed/python refusals went to zero; the 24 left were builders trying `./mc.py undo` (now told to
  re-place instead) and the critic reading single renders.
- **A blocked worker needs somewhere to send its question.** Before the escalation path, the craftsmen
  planner's question ended up in a log and the district silently got nothing.
- **Harness bugs found by running it:** argument order for `mc town`, `workflow.wait` returning lists,
  long critic answers cut before parsing, interrupted runs left "live" in the records. All fixed.

## Kits: agents design once, code builds many (2026-11-07)
Measuring Kingsreach showed where the time went: placing a house through WorldEdit takes under a
second, the `mc` commands about 3 s, but each house had its own Sonnet session writing and revising
a plan (1.4 min, ~19 turns, ~10k output tokens), and a third of all agent time went to critic and
fix rounds that moved scores less than a point. So a kit (`kits/README.md`) is one parametric design,
`build(w, d, door, kind, seed)`, that fills a plot exactly. An agent writes it once, checking it with
`mc kit sample` (every instance built offline, checked and drawn on one sheet). One critic scores the
kit from that sheet, and code stamps it on every plot (`mc place KIT --plot`).
`KitTownWorkflow` (`ghost/city/kitwork.py`, `python -m ghost city kits NAME`) runs kit authors in
parallel, then a critic per kit with one fix round, then the ground and bridges by code, then the
stamping, then the plot critic on a sample of 6.

## The Kingsway (kw1)
A 3.2 km highway from Kingsreach to Riverford: `scripts/survey.py` reads the corridor (2,900 x 560
blocks, 65 s), `architect/route.py` routes it by A* (grades, high ground, few straight crossings) and
`scripts/kingsway.py` lays it out by code: 54 road pieces, 2 bridges, 4 waystation hamlets (31 plots).

| | Kingsreach (agent per house) | Kingsway (kits) |
|---|---|---|
| design | 363 agent runs, ~$62 | 2 kit authors (Opus) + 4 kit critic runs: 27 min, ~$11 |
| building | ~70 min for 151 plots | roads and terraces 24 s; 2 bridges < 1 s; **31 buildings 15 s** |
| quality (critic, sampled) | 5.8 | 5.2 (kits 6/10; "the kinds look too alike") |

The cost no longer grows with the number of buildings. Quality is a little lower, and fixing it in
the kit fixes every building at once. Bugs found by running it: a `waterlogged=false` lantern read as
water put a bridge 20 blocks high; a space in a building's name hid the contact sheets from the critic.
("$" is Claude Code's API-equivalent estimate; the runs used the subscription.)

## The Kingsway Express
`scripts/express.py`, by code with no agents: an underground blue-ice boat line under the Kingsway, two
2-wide lanes at y 28 in a deepslate shell, legs that run straight through six stations (platforms,
bubble-column elevators up and down, a ladder, a hut on free ground). 3.6 km and ~150k blocks placed
in about 6 s, every lane block checked in-world. First built with 1-wide lanes, which take no boat (a
boat is ~1.4 wide). Rebuilding it showed the real limit of `edits.undo`: it restores a whole box
snapshot, so it refuses when any later edit's box overlaps, and a long L-shaped tunnel's box overlaps
everything. The fix belongs in `edits.py` (restore only the edit's own cells).
