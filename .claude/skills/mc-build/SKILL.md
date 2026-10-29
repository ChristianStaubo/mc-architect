---
name: mc-build
description: Build something in Minecraft on the mc-architect test server — read the site, write a plan with the architect parts, preview, place on the ground, audit, look at the shots, revise. Use for any build request or eval task. For improving the harness itself, use mc-improve.
---

# Building

You build through `./mc.py` (repo root) and Python plans. Never the game UI.
Read `STYLE.md` first: those are the user's rules for what a good build is.

## The loop
1. **Site.** `./mc.py site X,Z W,D` → read the map PNG. Note the ground range, slope direction
   (brighter = higher), water and trees. Decide where the door faces and how the build meets the slope.
2. **Plan.** A Python file whose `build()` returns an `architect.build.Build` in local coordinates:
   x east, z south, y up, **y 0 = the ground floor**. Use the parts (below); plain `b.set` / `b.fill`
   for anything they don't cover. Keep sizes as named constants at the top so revisions are one edit.
3. **Preview.** `./mc.py place PLAN --dry-run --task T` → Read the PNG (two opposite corners).
   It also checks the build fits the plot. Fix what looks wrong *before* placing.
4. **Place.** `./mc.py place PLAN --at X,Z --task T` (X,Z = where local 0,0 goes).
   Options: `--foundation BLOCK|none` (none for posts over water), `--y Y` (fix the floor height),
   `--no-clear` (keep terrain in the box, e.g. to build into a hill yourself).
5. **Audit.** `./mc.py audit` — any FAIL must be fixed (floating, door, bed, sealed, dark).
6. **Look.** `./mc.py shots` → Read the sheet: 4 corners, top-down, floor plan. Judge it against
   the brief and STYLE.md like a picky player would.
7. **Revise.** `./mc.py undo`, edit the plan, place again. Two or three rounds is normal; stop when
   the audit is clean and you'd show it to a friend, or when the budget is near.

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
