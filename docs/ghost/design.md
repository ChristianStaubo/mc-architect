# The ghost: design

Status: milestones 1-2 built and evaluated (see README.md for what runs and how it differs). The ghost is optional: its own Paper plugin (`ghost-plugin/`, depends on
MCBridge) and its own services, added to a server only if wanted.

The ghost is an AI that lives on the server. Players chat with it; it builds, guides and looks after
things, within what their house and role allow. Each house has its own ghost; a neutral **server spirit**
greets new players and does the jobs that belong to no house. Every ghost is a face over one shared
engine: one store, one policy engine, one worker pool, one bridge.

## Principles
1. **The tools decide what's allowed, never a prompt.** Every tool call passes the policy engine; the model
   can ask for anything and still only do what the requester and the ghost are both allowed to do.
2. **Stored first, done after.** Every event, task, approval and effect is written to the store before
   anything happens, so a crash at any point resumes instead of repeating or losing work.
3. **Every world change happens once, and can be undone.** Mutating bridge calls carry an idempotency key;
   the undo entry is journalled before the blocks change.
4. **Untrusted text never steers an action by itself.** Chat, signs, books and names are data. Text from
   signs and books is read by a tool-less reader; player names reach the planner as ids.
5. **Cheap first.** Code handles what code can (greetings, "follow me", filtering); a small model routes;
   big models only build.
6. **Everything is measured.** One audit row per tool call, one trace per task, and an eval for each of
   these principles.

## The shape

```
 Minecraft (Paper plugin)                         the ghost (Python)
 ─────────────────────────                        ──────────────────────────────────────────────
 chat, /ghost, joins, signs ──► inbox ──► sources ──► fast filter (code) ──► threads
                                                                       │ subscribed? ──► its worker
 ghost body (entity)                                                   └ new ──► house ghost (router)
 houses, zones, roles                                                               │ dispatch
 last-line policy check                                                             ▼
 keyed bridge (/place ...) ◄──── tool layer: policy · budget · lease · key · audit ◄── workers
 chat ◄────────────────────────── outbox ◄── replies (only the router talks to players)
                                       store (SQLite): events, threads, tasks, approvals,
                                       budgets, leases, memory, audit, outbox, workflows
 watchdog: heartbeats + progress ──► pause / escalate / restart          ops room: reads the store
```

### Listening (decided)
The ghost isn't always running; it wakes on events. Every chat message gets one of three treatments:

| Treatment | Which messages | What happens |
|---|---|---|
| **Explicit** | `/ghost ...`, chat starting with "ghost" or "@ghost", clicks on its buttons | always handled; `/ghost stop` and buttons never wait on a model |
| **Candidate** | chat that mentions "ghost" anywhere; chat from a player near the ghost's body | a small model decides whether it's for the ghost ("this ghost town is empty" isn't) |
| **Ignored** | everything else | never sent to a model |

The checks for who a message is addressed to are code; working out what it means is always a model's
job. Candidates that arrive while a router is busy are batched into its next turn. Each house can turn
the nearby-chat check off (privacy). Eval: did it reply when it should, and stay quiet when it should
(both rates, on mixed chat from simulated players).

### The router's memory (decided)
A house ghost isn't one never-ending model session. Its memory is the store (events, threads, tasks,
house notes); each wake is a fresh model call with context built by code: the new event, that player's
recent thread, open tasks by id, the house summary, plus tools to read anything else by id. A crash
loses nothing, players' contexts stay apart, and any wake can be replayed. Compaction is ours: a nightly
summary written from the log, the raw log always kept. Eval: does it remember what you asked yesterday?

### Layers
| Layer | Does | Doesn't |
|---|---|---|
| **Sources** | Turn plugin events (chat, `/ghost`, join, sign placed) and timers into stored triggers with ids | Decide anything |
| **Fast filter** | Code rules: is the ghost addressed? which house? rate limit? simple command (follow, come, stop)? | Call a model |
| **Threads** | Group a player's conversation; follow-ups go straight to the worker that owns it | — |
| **House ghost (router)** | One long-lived, small-model session per house: talks to players, keeps continuity, dispatches tasks | Build, run tools that change the world |
| **Server spirit** | Same as a house ghost, but for no house: onboarding, town crier, guardian, house cup judge | Act inside a house's zone without that house |
| **Workers** | One isolated session per task (design a build, plan a mega-build phase, write the digest) | Talk to players |
| **Tool layer** | The only way to touch the world: checks policy, reserves budget, takes area leases, adds an idempotency key, writes the audit row, calls the bridge | Trust anything the model says about who is asking |
| **Body** | Where the ghost is and what it does visibly: `go_to`, `follow`, `look_at`, `say`, `emote`, `build_animated` | — |
| **Watchdog** | Outside the main loop: liveness (heartbeats) and progress (repeated or no-op actions, unchanged world) | Live in the same process it watches |

## The body (decided)
A mannequin (the player-shaped entity from 1.21.9; to confirm on 26.3) with a ghost skin: glowing,
floating, a faint particle trail, its head turning toward whoever is talking. Each house ghost glows in its
house colour; the spirit is white. It glides a little each tick toward its target (no pathfinding, through
walls) and everyone online sees it. Fallback if the mannequin isn't there: a figure of display entities.
A real player (Mineflayer) comes later behind the same body interface.

## Who may do what (the policy model)
- **Principals:** `Player` (with a `House` and a role: owner, head, member, guest), `Ghost` (one per
  house), `Spirit`, `Worker` (acting for one task).
- **Resources:** zones (a house's area, the commons, protected areas), budgets, memory, the board.
- **Actions:** `Say`, `Move`, `Preview`, `Build`, `Demolish`, `Undo`, `ApproveBuild`, `SpendBudget`,
  `ReadMemory`, `WriteMemory`, `PostCommission`.
- **The rule:** a worker may do an action only if the **requesting player** may, **and** the ghost it
  works for may, **and** the task's grant covers it (zone, block cap, expiry). The requester comes from
  the authenticated event (the player's UUID), never from model arguments.
- **Tiers:**

| Tier | Examples | Gate |
|---|---|---|
| Free | chat, follow, look, preview | anyone in the house |
| Asker's yes | place a build, undo their own build | the asker, as `/arc yes` today |
| Head's yes | big builds, terrain changes, spending past the daily allowance | the house head |
| Other house's yes | anything in their zone | that house's head |
| Owner only | protected zones, mega-builds, policy changes | the server owner |
| Never | op, whitelist, server commands, other players' inventories | nobody |

- **Approvals** are durable waits with an expiry, bound to a hash of the plan (the plan can't change after
  the yes), with a summary written by code (box, block count, palette, preview), not by the model.
- **Engine (decided: Cedar, behind one `authorize(who, action, what, context)`):** policy files in
  `policies/`, evaluated in Python by the tool layer and again in the plugin as a last-line check on world
  edits. Every action asks it (say, move, preview, build, undo, memory, budget, approve); thinking doesn't.
  Facts come from the store and the game, never from the model: the requester from the event, block
  counts counted by code, approvals from the approvals table. Each decision is audited with the ids of
  the rules that decided it.
- **Signed grants:** an approved build gets a short-lived signed grant (task, zone box, max blocks,
  expiry); the plugin checks it before placing anything. The model never sees the signing key, so even a
  hijacked worker can't build outside what was approved.

## Houses in the world (decided for now)
- **Two houses to start**, each with one hardcoded zone (a rectangle, full height) next to the other,
  in a config file. Everything outside the zones is the commons. Later: players `/claim` land with a
  limited number of claim slots.
- **Postgres holds houses, roles and zones**; the plugin keeps a copy, refreshed through the bridge on
  change, so its last-line check never waits on the database.
- **Roles:** the owner is set in config; the owner appoints heads (`/house head <player>`); a player is a
  member of the house they picked; anyone who hasn't picked is a guest.
- **House picker:** on first join a chest-style menu with a coloured banner per house (name, colour, one
  line); a click confirms. After that only the owner can move someone. Chat buttons as a fallback.

## Processes (decided)
| Service | Does |
|---|---|
| `minecraft` | Paper plus the plugin (body, houses, picker, bridge, last-line policy check) |
| `postgres` | all state, ours and Temporal's |
| `temporal`, `temporal-ui` | durable workflows and their web view |
| `ghost-core` | listener, fast filter, threads, router wakes, outbox sender |
| `ghost-worker` | the Temporal worker: workflows and their activities (model calls, bridge calls); can run several |
| `watchdog` | heartbeats and progress; pauses, escalates, restarts; outside what it watches |
| `ops` | the ops room, through a read-only database user |

Locally, `ghost-core`'s model calls and `ghost-worker` run on the host, because `claude -p` uses the
owner's Claude login; hosted, they'd run in Docker with an API key. The model interface hides this.

## Models (decided for now)
Behind one model interface: today `claude -p` on the subscription, later the API (any provider).
Candidate filter and routers: Haiku. Workers: Sonnet (Opus for `big`). Evals will find how cheap each
job can go. Until we're on the API, house budgets count requests and blocks, not dollars. The instant
commands and buttons skip the model, and the router acknowledges before handing off, since a `claude -p`
call takes seconds to start.

## Durability
- **Store (decided: Postgres, in Docker):** one Postgres for our tables and Temporal's (separate
  databases), the same locally and hosted. We use transactions (a change and its outbox message commit
  together), `LISTEN/NOTIFY` (the outbox wakes instantly), `SKIP LOCKED` (queues) and JSON columns. SQLite
  would cope with our load; Temporal is what needs a networked database in production.
- **Hosting (decided):** one small VPS running the compose file (Minecraft, Postgres, Temporal, the
  ghost), deployed by a GitHub Action that runs the evals first. Pay-per-use hosts price an always-on
  6 GB Minecraft server at ten times a VPS.
- **Workflows (decided: Temporal, self-hosted, open source):** a build or commission is a workflow whose
  id is the task id; model calls, chunk placements and audits are activities (retried, so the bridge's
  idempotency keys make repeats harmless). Approvals are signals, expiry is a timer, the ops room and
  `/ghost status` use queries, mega-build phases are child workflows, very long builds continue-as-new.
  Workflow code does no I/O. The listener and the routers' quick wakes stay plain code over the store.
- **Outbox:** chat replies and board posts are written in the same transaction as the state change and
  sent by a separate loop, so nothing is said twice or lost.
- **Idempotent bridge:** every mutating call carries `task:phase:chunk`; a repeat returns the stored
  result. Undo entries are written `pending` before placing and marked `applied` after.
- **Area leases:** `leases(area, holder, expires_at)`; a worker must hold the lease for a chunk to build
  in it, so two workers can't undo each other's work.
- **Budgets:** reserve before a call, settle after; running out pauses the workflow and asks for
  approval, it doesn't crash.
- **Restart:** each resumed worker gets a note to check the world before repeating anything outside.

## Context and memory
- **Inline what's needed now, spill the rest:** the event, the player's house and role, the ground where
  they're looking, recent thread messages; long things are cut with an id to read the rest.
- **Recall by id:** tasks, builds (edit ids), threads and memories have ids that link to each other.
- **Memory:** rows keyed `(house, player, scope)`; a ghost reads only its house's memory; the spirit
  reads none of a house's private memory. Nightly consolidation, retention limits, and "forget me".
- **Compaction:** each router keeps a rolling summary plus the raw log on disk (a summary can be redone
  from the log; the log is never thrown away by the summary).

## Observability
- **Audit row per tool call:** time, trace id, task, ghost, worker, requester, action, resource, policy
  decision and the rules that decided it, approval id, whether untrusted text was in context, budget
  before/after, result, undo handle. Ids, not memory content, so deleting memories keeps the record.
- **Traces (decided: in Postgres):** a row per model call (prompt, reply, tokens, time) with
  OpenTelemetry-style trace and span ids, so they can be exported to Grafana or Langfuse later. Repeated
  prompt parts are stored once by hash; full text kept 30 days, the small facts forever; the table is
  partitioned by day; trace rows are written in batches off the reply path. Audit rows are written before
  the action, since they're part of the safety guarantee. Any decision can be replayed.
- **Temporal's web UI** shows every workflow, step, retry and failure.
- **Uptime:** an outside check on the game port and a health endpoint, alerting when it's down.
- **Ops room:** a page reading the store: who's using it, p50/p95 latency, cost per active player-hour,
  refusals, approvals, errors, watchdog state.

## Evals (one per principle)
Simulated players (a small model with a goal and a personality) send events through the bridge's
virtual-player route; grading is by code on the end state (world, store, conversation); each case runs k
times and reports pass^k; chaos tests kill containers mid-build. Each suite gets its own grading rules
(to be written).

| Eval | How | Pass |
|---|---|---|
| Capability | simulated players (an LLM playing a player) with goals; graded on the final world state; k runs each | pass^k on the core tasks |
| Policy | paired cases: allowed vs not, same wording otherwise | 0 harmful world changes; wrongful refusals under a target |
| Injection gauntlet | signs, books, chat, names; static cases, then an attacker model, then live players | 0 harmful world changes |
| Isolation | a canary memory planted in one house | never appears in another house's context |
| Chaos | seeded bridge faults; kill the daemon, the server, the network mid-build | 0 lost, 0 half-done, 0 double-charged; p95 recovery under 60 s |
| Load | a stream of chat with ~7% real requests from many simulated players | p50/p95 reply and task times; cost per player-hour |
| Judge | the house cup judge against your own ratings | agreement measured; pairwise, order-swapped |

## Folder structure
```
ghost/                    the agent system (Python), next to architect/ (the building toolkit it uses)
  store/                  SQLite schema, migrations, the step log / workflows, the outbox
  sources/                bridge inbox, timers → triggers
  filter.py               the fast path
  threads.py
  router/                 house ghosts and the spirit (personas, dispatch, replies)
  workers/                task kinds: build, commission, mega-build phase, digest
  tools/                  the tool layer (every world-touching call), idempotency, leases, budgets
  policy/                 the engine wrapper, approvals, grants
  memory/                 memory store, consolidation, retention, forget-me
  body/                   the body interface; the plugin ghost entity; later a real player
  watchdog/               liveness and progress
  obs/                    audit, traces, metrics, the ops room
  evals/                  simulated players, gauntlet, chaos, load, judge calibration
policies/                 Cedar schema and policies, shared by Python and the plugin
plugin/src/dev/mcarchitect/
  ghost/                  the ghost body entity, /ghost, events to the inbox
  houses/                 houses, zones, roles, the house picker on first join
  policy/                 the last-line check on world edits
docs/ghost/               this design and the ones that follow
```
`architect/assistant/` (today's `/arc` daemon) becomes the first worker kind and is retired once the
ghost covers it.

## Milestones
1. **Foundations:** the store, the tool layer with audit and idempotency keys, the keyed bridge, Cedar
   with houses and roles, the house picker. Eval: policy pairs.
2. **The ghost appears:** body entity, one house ghost and the spirit as routers, today's architect as
   the first worker. Eval: capability with simulated players.
3. **Approvals, budgets, the board:** durable waits, reserve/settle, commissions as workflows.
4. **Durability:** workflows resumed after a crash, leases, the watchdog. Eval: chaos.
5. **Living server:** town crier, guardian (record-only first), memory and forget-me. Eval: isolation.
6. **Show:** the injection gauntlet, the ops room. Eval: gauntlet. (The house cup is deferred.)
7. **Hosted:** staging and live on the VPS; evals as the release gate.
8. **Model ladder:** routing by task, canaries.

## Open questions
- How workers call the model: Claude Code headless (today) or our own loop on the Claude API (one activity per model call)?
- Does a router per house lose too much when a player talks to two houses?
- How do resumed workflows behave when the code changes during a three-hour build?
- Cost per active player-hour target.
