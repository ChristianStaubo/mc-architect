# Roadmap

Where this is going, so we don't forget. Dates are when the goal was set; the plan under each is a
first sketch, to be redone when we start it.

## Goals (the user, 2026-10-29)

### 1. A full city
Not a village: districts, a road network with a hierarchy, landmarks, walls or gates, a harbour, parks,
built across real terrain. Builds on the lakeside town (`towns/lakeside`, `docs/town.md`).
- Planner scales from 8 plots to 100+: districts first, then streets, then plots; a city-level critic.
- Builders in waves (a district at a time) with the eval suite guarding quality.
- Variety at scale: parametrised building types (`stamp`, palettes per district) so streets don't repeat.
- Infrastructure parts: city walls, gates, aqueducts, canals, big bridges, plazas, parks.

### 2. Terraforming
Shape the land itself: flatten or raise a district's base, carve rivers and canals, raise hills,
smooth cliffs into terraces, plant forests and fields, make beaches. Today we have roads, terraces
and tree clearing (`architect/terrain.py`).
- Terrain operations as parts with previews and undo: `raise`, `lower`, `smooth`, `carve_river`,
  `plant_forest`, `beach`, with blending into the untouched land around them.
- Natural-looking results: noise, varied blocks (grass, coarse dirt, gravel, moss), no straight edges.
- A terrain judge (does it look natural? does water flow sensibly?) and code checks (no floating
  terrain, water contained, slopes walkable).

### 3. Players: /tp without creative
Friends play in survival on the real server and can travel between places without being operators.
**Done 2026-10-29 (first cut):** `/sethome`, `/home`, `/tpa`, `/tpahere`, `/tpaccept`, `/tpdeny` for
every player, in our own plugin (`plugin/src/.../Travel.java`, nothing installed; homes in
`plugins/MCBridge/homes.json`, requests expire after a minute, 10 s cooldown). Live test:
`scripts/test_travel_live.py`. Still to check with two people: accepting and denying a /tpa. Warps
were left out for now (the user's call).
- Named warps (the market, the hall, the lighthouse...) that any player can use: `/warp <name>` or
  `/tp`-like commands granted by permission, not op. Options: our own small plugin command in MCBridge
  (warps stored in a file, `mc warp add|remove|list` for us), or a well-known plugin (EssentialsX's
  /warp, LuckPerms for permissions), checked under the dependency rules (official source, hashes,
  7 days).
- Survival by default, creative only for the owner; the agent's building keeps going through the bridge.
- Safety: rate limits, no warps into the redstone mechanisms, spawn protection where needed.

### 4. Host the server
Run it somewhere friends can join any time. **Plan: docs/hosting.md** (2026-10-29: one 8 GB VPS, live +
staging containers, Tailscale for the bridge, restic backups, ~$9-12/month).
- Our own Docker image (already built from pinned, hash-checked files) on a small VPS or home box.
- Public game port only; the bridge stays private (SSH tunnel or a VPN), never on the internet.
- Backups (world snapshots off-machine on a schedule), whitelist, monitoring, updates under the
  7-day rule, a restore drill.
- The agent works on a staging copy and pushes approved builds to the live world.

## Near term
0. **The in-game architect** (docs/in-game-architect.md): built 2026-10-30 (`/arc`, ghost previews,
   yes/no/undo/cancel, the daemon, `mc eval scenarios` 9/9). Left: the owner tries it in game, then
   friends' permission and an `@architect` chat mention.
1. ~~Evals v2 (docs/evals.md)~~: done 2026-10-29 (first run c1029-1705: 80% pass, quality 5.22).
2. ~~Survival travel (/sethome, /home, /tpa)~~: done 2026-10-29; the two-player accept/deny check is left.
3. **Deploy (postponed; after the in-game architect), following docs/hosting.md:**
   - the owner picks the host (OVH VPS-2 recommended), backup storage (B2 or R2) and the whitelist, and
     creates those accounts plus Tailscale;
   - we build and test locally first: live + staging compose, `mc` per server, backup/restore scripts,
     `mc promote`, the server setup checklist;
   - then set up the VPS, restore the current world onto it, run a restore drill, invite friends.
4. Then: terraforming parts and warps, in the order the projects need them.

## Feature ideas (proposed 2026-10-30, not scheduled)
- **Better builders**: a critique round before "done" (`mc critique`: the judges' notes on its own
  sheet), the done bar on quality not placements; the castle's tool gaps (steep spires, walls that
  follow a slope, terraces, spiral-stair landings, choosing blueprint floors, an audit that ignores
  natural caves); room kits (bedroom, kitchen, tavern bar, library, throne room); palettes with
  texture variation. Each change A/B tested with `mc eval run --vs`.
- **Terraforming** (goal 2): raise, lower, smooth, carve a river, plant a forest, make a beach, with
  previews, undo and naturalness checks.
- **From town to city** (goal 1): district, road and plot planning; builders by district; a city critic;
  walls, gates, plazas, harbour, aqueducts. Lakeside and the castle become the old town.
- **Redstone kits**: piston doors, elevators, hidden stairs, farms, sorters, each tested live by
  driving inputs and reading outputs.
- **Warps** (`/warp market`): skipped for now in favour of homes and /tpa; easy to add to travel/.
