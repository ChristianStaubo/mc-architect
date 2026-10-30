# The lake town (next capability)

> Working notes, kept for history. The plan for the lakeside town on our own test world. For how things work now, see `docs/`.

Goal: one town built from scratch that **works with the natural terrain**: a lake, water builds,
buildings on a mountainside, roads that follow the land. No flattened plain.

## Site: the twin lakes, x 256..399, z -272..-129
Found by scanning 1024 x 1024 blocks around spawn for windows with 12-35% water, 25+ blocks of relief
and mostly grass (`local/world-1024.json`, sketch `local/renders/town-plan-sketch.png`).
- A ridge in the west at y 120-127 falling ~60 blocks east to two lakes at y 62.
- A low peninsula (y 62-68) between the lakes, joined by a strait; a bench of flat land to the south.

| # | District | Where | Terrain | What goes there |
|---|---|---|---|---|
| 1 | Keep | summit, x 258..282, z -270..-246 | y 120-127 | a keep or temple: the landmark you see from the lakes |
| 2 | Upper quarter | x 270..300, z -236..-204 | y 95-118, steep | larger houses on terraces, retaining walls |
| 3 | Slope houses | x 292..318, z -200..-160 | y 70-95 | cottages stepped down the hill along the road |
| 4 | Market | the peninsula, x 328..352, z -206..-170 | y 62-68 | square with stalls and a well, tavern, church |
| 5 | Harbour | east shore, x 352..372 | water | piers, boathouses, a lighthouse |
| 6 | North shore | x 310..328, z -232..-214 | shore | fishing huts on posts |
| 7 | Fields | south bench, x 300..340, z -156..-132 | y 64-70 | farms, a windmill, a barn |
Main road: switchbacks from the keep down the ridge to the market, a **bridge over the southern lake**,
branches to the harbour and the fields.

## How we build it (the harness grows a level)
1. **Town planner agent** (Opus): reads the site (`mc site` over the whole area, a slope map) and writes
   `towns/<name>/layout.json`: roads (polylines with widths), plots (footprint, floor level, district,
   building type and size, which way the door faces the road), landmarks, one style palette. Rendered as
   a map for the user to approve before anything is built.
2. **New tools**:
   - roads and paths that follow the terrain (grade at most 1 block per 2, steps or switchbacks where
     steeper, gravel/path/cobble mix, edges, lamps);
   - terraces and retaining walls (cut and fill per plot, so a house sits on a level pad with a stone
     wall on the low side instead of a cobblestone cliff);
   - bridges (span water between two road ends, arches or posts);
   - `mc town` commands: plan, show, build-plot, status.
3. **Builders in parallel**, one per plot, briefed from the layout (type, size, door side, floor level,
   palette, neighbours). Existing building types become parametrised plans so a street varies instead
   of repeating.
4. **Judging at two levels**: each building gets the audit and the critic; a **town critic** judges the
   whole town from above and from street level (does it read as one place, roads connected, variety
   without chaos, does it follow the land). New audit checks: every door reaches a road; no road steeper
   than its grade; no building over water without posts.
5. **Evals**: a town scoreboard (town critic score, % plots passing, connectivity) next to the building
   suite, so improvements to the planner are measured like everything else.

Start small: one street from the market to the harbour (6-8 buildings, a bridge), then grow up the hill.

## Later
- **Enhance a real village**: `/locate structure` finds generated villages; the planner reads the
  existing buildings (region scan) and either upgrades them in place (same footprint, better build) or
  adds new buildings and roads around them.
- **Redstone**: plans can already place redstone (block states); what's missing is a way to *test* a
  contraption: a bridge endpoint to flip levers/buttons and read back lamp/piston/door states after N
  ticks, so the audit can check "the door opens when the button is pressed". Then evals for contraptions
  (piston doors, item sorters, farms).
