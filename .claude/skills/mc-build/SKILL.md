---
name: mc-build
description: Build something in Minecraft on the mc-architect test server — read the site, write a plan with the architect parts, preview, place on the ground, audit, look at the shots, revise. Use for any build request or eval task. For improving the harness itself, use mc-improve.
---

# Building

You build through `./mc.py` (repo root) and Python plans. Never the game UI.
Read `STYLE.md` first: those are the user's rules for what a good build is.

## The loop
1. **Site.** `./mc.py site --task T` (or `X,Z W,D`): the plot's height grid (rows north→south, `~` =
   water), which side is highest, and a map PNG. Decide where the door faces, how the build meets the
   slope (step it, terrace it, a basement on the low side) and where the path comes in.
2. **Plan.** A Python file whose `build()` returns an `architect.build.Build` in local coordinates:
   x east, z south, y up, **y 0 = the ground floor**. Use the parts (below); plain `b.set` / `b.fill`
   for anything they don't cover. Keep sizes as named constants at the top so revisions are one edit.
3. **Preview.** `./mc.py place PLAN --task T --dry-run` → Read the PNG: your build drawn on the real
   terrain (two opposite corners), exactly as place would leave it, **and audited** (floating blocks,
   sealed rooms, dark floors show here, before you place). Block names are checked against the server
   (a typo is refused with the closest real names). Without `--at` the build is centred in the plot;
   the output prints the `--at` it used. Re-previewing over your own earlier build is fine: heights
   come from the terrain before your edits. Fix what looks wrong *before* placing.
4. **Place.** `./mc.py place PLAN --task T [--at X,Z]` (X,Z = where local 0,0 goes).
   Options: `--foundation BLOCK|none` (none for posts over water), `--y Y` (fix the floor height),
   `--no-clear` (keep terrain in the box), `--keep-trees` (by default trees touching the build go).
   Clearing only happens from y 0 up: anything below (posts, a basement) is exactly what you write.
5. **Audit.** `./mc.py audit` — any FAIL must be fixed (floating, door, bed, sealed, dark).
6. **Look.** `./mc.py shots` → Read the sheet: 4 corners, top-down, and a floor plan per storey (the
   critic sees exactly this sheet: if the stairs or a room aren't visible there, they don't count).
7. **Self-critique, then revise (required).** Before your second placement, write down the three
   biggest problems against `evals/RUBRIC.md` and the checklist below, as a strict critic would. Fix
   them: `./mc.py undo`, edit the plan, place, audit, shots. At least two rounds; three is normal. Use
   your budget: a first placement is a draft. Stop when the audit is clean and the checklist holds.

## Checklist (what every r1 critic marked down)
- [ ] Not a box: the footprint or roofline is broken (L, wing, porch, dormer, cross gable, turret, overhang).
- [ ] Walls have depth: frame posts, beam bands, inset windows, a base band (`timber_frame` helps).
- [ ] The site is used: steps/terrace/basement on a slope, no raw cut edges, a path to every door.
- [ ] Lived-in outside: at least three purposeful details (lanterns by the door, flower boxes, fence,
      barrels, woodpile, garden, sign).
- [ ] Every part of the brief is visible from the outside or the floor plan (a critic only sees pictures).
- [ ] Rooms are furnished for their use, lit, with stairs you can see on the floor plan.

## Parts (`architect/parts.py`)
| Part | Does |
|---|---|
| `floor(b, x1, z1, x2, z2, y, block)` | a filled layer |
| `walls(b, x1, z1, x2, z2, y1, y2, block, corner=None)` | hollow rectangle of walls, optional corner posts |
| `clear_inside(b, x1, z1, x2, z2, y1, y2)` | air inside the walls (clears hills from the room) |
| `window(b, x, y, z, along="x"/"z", width, height, pane)` | glass panes with connections set |
| `door(b, x, y, z, facing, wood)` | both door halves; facing = direction you walk out |
| `gable_roof(b, x1, z1, x2, z2, y, stair, gable, ridge="x"/"z", overhang=1)` | pitched stair roof, gable ends filled |
| `light(b, x, y, z, block)` | a light source |
| `timber_frame(b, x1, z1, x2, z2, y1, y2, fill, post, beam, every=4)` | walls with posts every N and beam bands top and bottom |
| `straight_stairs(b, x, y, z, direction, steps, stair, width=1, support=None)` | a flight up toward `direction`; clears headroom (cuts the stairwell); returns the top landing |
| `spiral_stairs(b, x1, z1, x2, z2, y1, y2, stair, landing)` | stairs climbing around the inside of a shaft (towers), landings at corners |
| `posts(b, [(x, z), ...], y_top, y_bottom, block)` | stilts, piers, dock posts (over water: `--foundation none`) |
| `stamp(b, piece, x, y, z, turns=0)` | copy another Build in, turned 0–3 quarter turns (facings and connections turn too): repeated stalls, houses, towers |
| `dormer(b, x, y, z, facing, roof_stair, wall, width=3)` | a gabled dormer window out of a roof slope; call after the roof |
Beams: pass the bare log name (`dark_oak_log`); parts set `[axis=...]` themselves.
`plans/cottage.py` is a worked example.

## Block states (the bridge places exactly what you write)
- Stairs: `oak_stairs[facing=north,half=bottom]` — facing is the tall back side.
- Logs: `oak_log[axis=y]` (x/z for beams). Slabs: `[type=bottom|top|double]`.
- Doors, beds: always both halves (`door()` does doors; beds: `part=head` + `part=foot`, foot behind the head).
- Panes, fences, walls: set connections (`east=true` ...) or use `window()`.
- Ladders/wall torches/signs need `facing` away from the block they hang on.

## When the tools fall short
If a part you need doesn't exist and would take more than ~20 lines to fake, a command fails twice,
or something contradicts this skill: `./mc.py stuck "<goal> | <what you tried> | <what happened>"`
and stop. A clean early stop is worth more than a clever workaround: the fixer turns it into a tool.
