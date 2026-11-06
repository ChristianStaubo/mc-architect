# The ghost

An optional agent system for the server: each house has a ghost you can talk to in chat; it follows
you, and designs builds that you preview before anything changes. A neutral server spirit greets new
players. Design: [design.md](design.md). Flows: [flows.md](flows.md).

## Run it
```bash
python3 scripts/pydeps.py install                               # .venv, pinned and hash-checked
scripts/build-plugin.sh                                         # mc-bridge.jar + ghost.jar
docker compose -f compose.yaml -f compose.ghost.yaml up -d      # the server (with the ghost plugin), Postgres, Temporal
.venv/bin/python -m ghost run                                   # ghost-core + ghost-worker + the watchdog
```
Without `compose.ghost.yaml` the server runs exactly as before, with no ghost plugin and no ghost services.
Temporal's UI is on http://localhost:8233 (every build is a workflow you can watch).
`.venv/bin/python -m ghost status` shows heartbeats, open tasks, today's budgets and recent decisions.
The model calls use the Claude Code CLI on your subscription (`claude -p`), so the ghost's processes
run on the host, not in Docker.

## In game
| You | The ghost |
|---|---|
| first join | a menu: pick Lakeside or Riverford |
| `ghost, follow me` / `/ghost come here` | its body floats after you (house-coloured, glowing) |
| `ghost, build a bench here` | "On it", then a preview only you see, with [Build it] [No thanks] |
| `ghost, make it taller` | a new design, previewed again |
| [Build it] | checked against the rules; built, or it asks whoever's yes is needed |
| `/ghost stop` | stops at once, no AI involved |
| `/ghost status` | your last request and your house's budget today |

Chat that mentions "ghost", or that you say next to its body, is checked by a small model ("is this for
the ghost?"). Everything else in chat never leaves the server.

## The rules (policies/ghost.cedar)
- Small builds (up to 2,000 blocks) in your own house's land or the commons; bigger ones (up to 20,000)
  need your house head's yes; another house's land needs *their* head's yes, and their ghost builds it.
- Guests (no house yet) can talk, not build. Protected places (Lakeside's market) need the owner.
- Never on top of what's there: a town's plots, walls and roads, or another build (`no-building-over-builds`,
  for everyone, the owner too). The preview step refuses those spots, so the architect picks clear ground.
- Saying yes in words gets the [Build it] button back: building always takes the click.
- A worker acts only if the asker *and* the ghost are both allowed. Who's asking comes from the game,
  block counts from code, approvals from the store; never from the model.
- Each house gets 40 requests and 60,000 blocks a day (until it runs on the API, then dollars).

## Evals
`.venv/bin/python -m ghost eval <suite>`; each suite has its own grading:

| Suite | Grading | Result (2026-11-06) |
|---|---|---|
| policy pairs (`.venv/bin/python -m unittest tests.test_ghost_policy`) | 22 allowed/denied pairs, schema check, requester-and-ghost | all pass |
| `guarantees` | the bridge, by code: repeated key, forged / expired / out-of-box / over-cap / wrong-world grant | 6/6 |
| `listening` | the candidate filter on labelled chat, pass^3 | replied 6/6, stayed quiet 6/6 |
| `scenarios` | simulated players on each house's testing ground (never in the towns), graded on the store and the world: follow, guest, injection, build + undo, a second build on the same spot, cross-house approval | 16/16 |
| `chaos` | kill a process mid-task: nothing lost, nothing twice, time to recover | 3/3; recovery: design 45 s, build 26 s, core 61 s |

What went wrong in the first in-game test, and what changed: the scenario spots were inside Lakeside's inn and
Riverford's fisher's house, and three test benches stayed there (undone; tests now build on testing grounds far
from the towns); nothing stopped a build landing on an existing one (now a policy rule and a preview check);
"use this design" was read as yes (building now takes the click); undo in another house's land was checked
against the wrong ghost.

What the evals caught while building it: an approval loop (approved yet still denied, so it asked again,
~700 times; now stopped in the workflow, in the message, and by the watchdog); the other house's ghost
not doing its half of a cross-house build; an event stored but never answered when ghost-core died
mid-way (now resumed on redelivery); a body that vanished when its chunk unloaded.

## Where the build differs from the design
- **The plugin's last-line check is the signed grant**, not a second Cedar engine in Java: the plugin
  places nothing a grant doesn't cover (box, block cap, expiry), and grants are minted only after Cedar
  allowed the build.
- **Follow-ups**: buttons go straight to the build's workflow; free text still goes through the router,
  which knows the open design (it decides change, accept or cancel).
- **The watchdog** checks heartbeats, tasks that stop moving, designs repeating the same step, and tasks
  making too many calls; it stops the workflow and tells the player. It doesn't yet escalate to a
  stronger model first.
- **Trace rows** are written as each model call finishes (not batched yet).
- Not built yet: memory beyond the thread, the town crier, the guardian, the ops room page, mega-builds,
  the spirit's body.
