# mc-architect

A harness that lets Claude Code build things in Minecraft by itself (towns, cathedrals, landscapes) and
get better at it through evals. It builds on a local Paper test server (Docker) through our own bridge
plugin and WorldEdit, sees the results as rendered pictures, and never needs the game's UI.

## Setup (macOS with Docker Desktop; Linux works the same)
```bash
python3 scripts/deps.py stage linux-aarch64   # Java 25, Paper, WorldEdit: pinned, every hash checked (linux-x64 on Intel)
docker compose build
scripts/build-plugin.sh                       # compiles the bridge plugin inside the image
```
Accept the [Minecraft EULA](https://aka.ms/MinecraftEULA) yourself: put `eula=true` in `server/eula.txt`.
Add yourself to `server/whitelist.json` and `server/ops.json` (or `./mc.py cmd "whitelist add <name>"`
once it runs), then:
```bash
docker compose up -d
./mc.py doctor
```
Join in Minecraft 26.3 at `localhost`. Both ports listen on 127.0.0.1 only.

## What it can do
- **Build from a plan** on real terrain: foundations follow the slope, hills inside the footprint are
  cleared, trees that touch the build go whole, blocks are checked against the server before placing.
  Every edit snapshots what it replaced, so undo works after restarts.
- **Judge a build**: `mc audit` (floating blocks, doors, beds, sealed rooms, dark floors where mobs
  spawn) and contact sheets (four corners, top-down, floor plans, close-up facades) for a critic agent.
- **Improve by evals**: builder agents (`mc-builder`) build a fixed task suite (`evals/tasks/`), a
  separate critic scores the pictures (`evals/RUBRIC.md`), the scoreboard tracks runs (`mc eval report`).
- **Plan and build towns** on natural terrain: a planner agent lays out roads and plots, roads follow
  the land and bridge water, plots are terraced, builders work in parallel (`mc town ...`, `docs/town.md`).
- **Redstone**: contraptions as parts with live tests (a hidden 2x2 piston door with an inside lever).
- **Blueprints** before building (`mc blueprint`), and a flight recorder after: a trace of every bridge
  request, automatic incidents for failures (`mc incidents`, `mc incident ID replay`), friction reports.

## Use
```bash
./mc.py site --task cottage-meadow  # the terrain of a plot: height grid, water, slope, map
./mc.py place cottage --dry-run     # preview a plan on the real terrain, audited, nothing placed
./mc.py place cottage --near <you>  # build it next to you, on the ground
./mc.py audit && ./mc.py shots      # judge it
./mc.py undo                        # take it back
```
Pictures land in `local/renders/`. `./mc.py -h` lists everything. Claude Code: start from `CLAUDE.md`
and the skills in `.claude/skills/` (`mc-build`, `mc-improve`).

## Layout
- `mc.py`: the CLI, the one tool the agents use.
- `architect/`: the toolkit. `blocks` (what a block string means), `build` and `parts` (plans and the
  parts they're made of), `placement` (putting a plan on the land), `terrain` (roads, terraces,
  bridges), `town` (layouts), `redstone`, `audit` (the judge), `render` (pictures, standard library
  only), `edits` (undo), `evals`, and the recorder: `journal`, `trace`, `incidents`. `bridge` talks to
  the server.
- `plans/`: example plans (`parts_sampler.py` uses every part). `towns/`: town briefs, layouts, plans.
- `evals/`: tasks, rubrics, ratings. `STYLE.md`: the house style. `docs/`: the workflow and the town plan.
- `.claude/`: agents (builder, critic, planner, town critic) and skills.
- `plugin/`: the bridge (Java, Paper + WorldEdit): read regions, place and undo through WorldEdit, flip
  levers, write signs, run commands. JSON over HTTP on 127.0.0.1 with a token.
- `docker/`, `compose.yaml`: the server image. Non-root, no Linux capabilities, nothing downloaded at start.
- `config/server.properties`: our server settings, merged into Paper's own file on every start.
- `tests/`: `python3 -m unittest discover tests`; `scripts/test_door_live.py` tests the door on the server.

## Dependencies
`deps.lock.json` pins every download to an official source (Adoptium, PaperMC, Modrinth's EngineHub
maintainers) and a hash. `python3 scripts/deps.py lock` moves to the newest releases that are
**at least 7 days old** (the same rule as pnpm's `minimumReleaseAge`). The Docker base image is a dated
Debian release pinned by digest. Jars, Java, worlds and tokens are never committed.
