# mc-architect: instructions for Claude

You build things in Minecraft for the user and their friends: houses now, towns, cathedrals and
landscapes next. Work on the local test server; the friends' server only gets builds the user approves.

## Start here
1. `./mc.py doctor`: container, server and bridge up? (`docker compose up -d` if not; `./mc.py restart`.)
2. `./mc.py -h`: the only tool. Never drive the game UI.
3. The method for growing this into an autonomous builder (scoreboard, player → judge → fixer, evals):
   `~/coding/games/fm26-manager/docs/agent-workflow.md`.

## How a build goes
1. Look at the site: `./mc.py site X,Z` (heights, surface, a top-down map). Read the picture.
2. Write a plan in `plans/` with the parts in `architect/parts.py`; add a part when a plan needs one
   (a part is reusable; a plan is one building).
3. `./mc.py place PLAN --dry-run` and look at the preview before touching the world.
4. `./mc.py place PLAN --at X,Z` (or `--near <player>`); look at the render it prints.
5. Wrong? `./mc.py undo`, fix the plan, place again.

## Rules
- Look at every render you produce (Read the PNG). An output line only proves the call ran.
- Every change goes through `place` so it can be undone. Undo history lives in memory: a restart
  forgets it, so undo before restarting if you might need to.
- `mc cmd` refuses stop/restart/reload: use `./mc.py restart`.
- Block states matter: set connections (panes, fences), door halves and bed parts explicitly; the bridge
  places exactly what you send.
- Keep worlds, renders, tokens and downloaded jars out of git. Dependencies only through `scripts/deps.py`
  (official sources, hash-checked, at least 7 days old).
- Plugin change: `scripts/build-plugin.sh`, then `./mc.py restart`.
