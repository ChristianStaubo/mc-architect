# The in-game architect: design

Players build *with* the architect from inside Minecraft. You stand somewhere and type
`/arc a little bakery here, facing the road`; the architect answers in chat, shows you a ghost of the
build that only you can see, and places it when you say yes. `/arc undo` takes it back.

Status (2026-10-30): built, the scenario suite passes, and tried in the real game (Claude drove it: `/arc`
as the owner through the bridge's `/as`, the camera moved with `/tp`, screenshots of the game window with
`screencapture -l <window id>`). The ghost preview shows on the player's screen only, survives walking
650 blocks away and back, updates on a change, and yes / undo build and restore the ground exactly.

## Running it
```
./mc.py architect serve          # the daemon: leave it running while people play (Ctrl-C stops it)
./mc.py architect status         # who it's working for, previews waiting, builds
./mc.py architect ask "a small well" --as someone --at X,Y,Z --facing south   # a virtual player asks
./mc.py eval scenarios [--tasks well-here,change-it]                        # the behaviour suite
```
In game: `/arc <idea>`, then `/arc yes`, `/arc no`, `/arc undo`, `/arc cancel`, `/arc status`. Operators
only for now (permission `mcbridge.architect`). Each request's transcript and summary are in
`local/assistant/<player>/runs/`.

## What it feels like
```
you    /arc a stone well with a little roof, right here
arc    On it: sketching a well for the spot you're on (grass, flat).
arc    Here's a preview, only you can see it. /arc yes to build, /arc no, or tell me what to change.
you    /arc make the roof spruce and a bit taller
arc    Updated the preview: spruce roof, one block taller.
you    /arc yes
arc    Built (edit e270). /arc undo takes it back.
```
- `/arc <anything>`: a request or a change to the current one (the conversation continues).
- `/arc yes` / `/arc no`: place the preview / drop it. No model needed: instant.
- `/arc undo`: take back your last architect build. Instant.
- `/arc status`, `/arc cancel`: what it's doing; stop it.
- Context it gets for free: where you stand and face, your WorldEdit selection (if any: "build it
  here" means *there*), the ground under you, nearby builds and town plots, the biome.

## How it works
```
 Minecraft (Paper)                           Your machine (or the host later)
 ┌──────────────────────────────┐            ┌──────────────────────────────────────┐
 │ /arc ... ──► ArchitectCommand │            │ mc architect serve   (the daemon)     │
 │                 │             │  /inbox    │   reads events, one job per player    │
 │                 ▼             │ ◄────────► │   yes/no/undo: handled directly       │
 │              Inbox (queue)    │  (bridge,  │   requests: claude -p --agent         │
 │                               │   private) │     mc-architect (resumes the chat)   │
 │ Preview: fake blocks sent     │ ◄───────── │        │ uses mc commands:            │
 │ to that player only           │  /preview  │        ▼                              │
 │ chat replies                  │ ◄───────── │   mc say / mc preview / mc place ...  │
 └──────────────────────────────┘  /say      └──────────────────────────────────────┘
```
- **Events, not polling the chat**: the plugin queues each `/arc` as an event with the player's context;
  the daemon long-polls `/inbox`. Events survive a slow agent; nothing is lost if the daemon restarts
  mid-job (it picks up unhandled events).
- **Previews are client-side fake blocks** (Paper's `sendBlockChanges`): exact, cheap (no entities), and
  only the asking player sees them. They look exactly like real blocks, so a preview is also marked: a
  glowing light-blue wireframe round the build (12 vanilla block-display rods, glowing, seen through
  walls, visible only to that player, never saved) and a line above the hotbar ("Preview: ... /arc yes"). The world doesn't change until "yes". A preview is redrawn when the
  player comes back into range and cleared on "no", on timeout, or on a new preview.
- **"yes" is deterministic**: the daemon keeps the pending preview (plan file + placement args) and runs
  the same `mc place` the preview was drawn from, so what you saw is exactly what you get.
- **Conversation**: one Claude session per player per request (`--resume`), so "make it taller" knows
  what "it" is. A new request after yes/no starts fresh.
- **The agent** (`.claude/agents/mc-architect.md`): quick and chatty in-game, always previews before
  placing, never places without a yes, stays inside the player's selection or a sensible radius, and
  says what it's doing. Same fenced tools as eval builders (`dontAsk`, `./mc.py` only).

## Safety and fairness
- Permission `mcbridge.architect` (you at first; friends later, per name).
- One job per player, a few at a time server-wide; `/arc cancel` stops one.
- Limits: a maximum build volume; no building over someone else's build or a town plot unless it's
  yours; undo only your own builds.
- Every placement is a normal edit (snapshot, undo, journal), tagged with the player.

## Evals for it (the agent-behaviour suite)
Scripted conversations, checked by code: fast, exact and cheap compared with judging looks.
```json
{"id": "well-here", "player": {"at": [120, 70, 40], "facing": "south"},
 "steps": [
   {"say": "a stone well with a little roof, right here",
    "expect": {"tools_in_order": ["site|look", "preview"], "no_place": true, "preview_near_player": 6}},
   {"say": "yes", "expect": {"placed": true, "matches_preview": true, "inside_radius": 12}},
   {"say": "undo", "expect": {"world_restored": true}}]}
```
- Graders over the tool trace (the journal already records every `mc` call with the run id) and the
  world: previewed before placing, placed where asked, never outside the selection, undo restores
  exactly, replies sent, no stray edits, within time.
- Runs headless with a *virtual player* (an event posted to the inbox with a made-up position), so it
  doesn't need anyone online; a few live checks use a real player through the bridge's `/as`.

## Folder structure (after the change)
```
plugin/src/dev/mcarchitect/
  MCBridgePlugin.java          main: turns features on, nothing else
  core/                        shared by every feature
    Feature.java               interface: enable(plugin), disable(); a feature owns its commands
    Chat.java                  message styles (info, warn, clickable buttons)
    Json.java                  small JSON helpers
  bridge/                      the private HTTP API the agent uses
    HttpBridge.java            server, token, routing
    WorldRoutes.java           /region /heightmap /place /undo /history /blocks /validate
    PlayerRoutes.java          /status /command /as /use /kick /sign /say
  travel/
    Travel.java                /sethome /home /tpa /tpahere /tpaccept /tpdeny
  architect/                   the in-game architect (new)
    ArcCommand.java            /arc and its subcommands, tab completion
    Inbox.java                 event queue + /inbox (long-poll) and /inbox/ack
    Preview.java               fake-block previews per player, redraw, clear
    Context.java               position, facing, WorldEdit selection, ground, biome

architect/                     Python: the agent's toolkit (unchanged modules stay)
  cli/                         mc.py split by command group, one file each (mc.py becomes ~30 lines)
    build.py                   place, undo, edits, blueprint, shots, render, audit, site
    town.py                    town ...
    evals.py                   eval gate|check|run|judge|report
    world.py                   status, cmd, restart, doctor
    recorder.py                gap, stuck, friction, incidents
    assistant.py               architect serve|status|ask, say, preview   (new)
  assistant/                   the in-game architect's daemon (new)
    daemon.py                  the serve loop: inbox -> handlers
    sessions.py                per-player state: claude session, pending preview, last build
    handlers.py                yes / no / undo / cancel (no model), requests (the agent)
    agent.py                   claude -p wrapper, prompt with the player's context
  scenarios.py                 the agent-behaviour eval suite (new)
  ...                          build, parts, placement, terrain, town, graders, trials, ...

.claude/agents/mc-architect.md the in-game agent
evals/scenarios/*.json         scripted conversations for the suite
docs/in-game-architect.md      this file
```
Adding a command later = a new folder under `plugin/.../<feature>/` with a `Feature`, its entries in
`plugin.yml`, and (if the agent needs it) a file in `architect/cli/`.

## Plan (steps 0-4 done 2026-10-30)
0. **Restructure, no behaviour change**: plugin into `core/ bridge/ travel/`; `mc.py` into
   `architect/cli/`. The gate (30/30) must still pass, plus a live travel test.
1. **Plugin**: `/arc`, the inbox, player context (with WorldEdit selection), `/say`, fake-block previews.
2. **Daemon**: `mc architect serve`; yes/no/undo/cancel without a model; requests to the agent with
   session resume; progress messages in chat.
3. **Agent**: `mc-architect.md`, `mc preview` and `mc say`, the "preview first, never place unasked" rules.
4. **Scenario evals**: 8-10 conversations (here, in my selection, change it, undo, cancel, refuse a
   too-big request, someone else's plot), graders, `mc eval scenarios`.
5. **Try it together in game**, fix what feels off, then friends' permission.

## Decisions (defaults unless the owner says otherwise)
- Command: `/arc` (alias `/architect`); an `@architect` chat mention can come later.
- Who: only the owner at first.
- Model: Sonnet for requests (speed); Opus available for big ones (`/arc big ...`).
- The daemon runs on this Mac next to the server for now; on the host after deployment.

## What building it taught us
- A `--disallowedTools` pattern switched off all of Bash in headless runs; deny rules belong in a settings
  file (`Bash(./mc.py place:*)`).
- Under `dontAsk`, an agent that writes files with a shell heredoc is refused and may simply stop: both
  agents now say Bash runs only `./mc.py`, files go through Write/Edit.
- The scenario runner must count a queued request as busy, or it grades steps that never ran.
- In game, "right here" put the well on the player's spot: `mc preview` now refuses (without a selection)
  a build covering where the player stands, and says which way to move it.
- Testing a real client without the owner: Codex's computer use can't target the game (a bare Java window
  is not an "app" to it), but `screencapture -x -o -l <window id>` captures the game window in the
  background, and the bridge's `/as` and `/tp` drive the player. Minecraft must have "pause on lost
  focus" off (F3+P), or its menu covers the view.
- "Three blocks taller" came out +2 (walls +3, roof lower) until the agent was told to compare the
  preview's box before saying it's done: the suite caught it.
