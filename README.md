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

## Use
```bash
./mc.py place cottage --dry-run     # render a plan without touching the world
./mc.py place cottage --near <you>  # build it next to you, on the ground
./mc.py undo                        # take it back
./mc.py site 0,0                    # what's the terrain there
./mc.py render 0,100,0 20,130,20    # picture of any region
```
Pictures land in `local/renders/`. `./mc.py -h` lists everything.

## Layout
- `plans/`: things to build. A plan is a Python file whose `build()` returns a `Build`.
- `architect/`: the toolkit. `build.py` (grids, payloads), `parts.py` (walls, windows, doors, roofs),
  `render.py` (isometric and top-down pictures, standard library only), `bridge.py` (the API client).
- `mc.py`: the CLI, the one tool the agent uses.
- `plugin/`: the bridge (Java, Paper + WorldEdit APIs): read regions and heightmaps, place and undo
  through WorldEdit, run commands. JSON over HTTP with a token in `server/plugins/MCBridge/token`.
- `docker/`, `compose.yaml`: the server image. Non-root, no Linux capabilities, nothing downloaded at start.
- `config/server.properties`: our server settings, merged into Paper's own file on every start.

## Dependencies
`deps.lock.json` pins every download to an official source (Adoptium, PaperMC, Modrinth's EngineHub
maintainers) and a hash. `python3 scripts/deps.py lock` moves to the newest releases that are
**at least 7 days old** (the same rule as pnpm's `minimumReleaseAge`). The Docker base image is a dated
Debian release pinned by digest. Jars, Java, worlds and tokens are never committed.
