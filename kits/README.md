# Kits: one design, many buildings

A kit is a Python file whose `build(...)` returns an `architect.build.Build` sized to the plot it's
given. An agent writes the kit once; code stamps it on every plot of its kind in about a second each.
Kingsreach built every house with its own agent: about 1.5 agent-minutes and $0.25 a house, plus a
critic and usually a fix round. A kit spends that effort once for a whole district or road.

## Buildings: `build(w, d, door="south", kind="house", seed=0)`
- Local coordinates as in any plan: x east, z south, y up, **y 0 = the ground floor** (the floor block).
  Fill **exactly** x 0..w-1, z 0..d-1. Nothing outside, including roof overhangs, steps and porches.
- `door` is the side facing the road (`north`/`south`/`east`/`west`). The main door faces that way,
  and the doorway can be reached: the floor is at y 0 and outside ground is at y -1, so put a step
  (stair or slab) at y 0 in front of the door, inside the plot.
- `kind` is one of the kit's `KINDS` list (e.g. `["inn", "stable", "house"]`). Each kind must read as
  itself from outside: an inn's sign and a bigger hall, a stable's open stalls and hay.
- `seed` gives variety: use `random.Random(seed)` to choose roof type, wings and porches, materials
  from the palette, and details. The same seed always builds the same building.
- Use the parts in `architect/parts.py` (see the mc-build skill's table). Keep it to one file.

## Bridges: `KIND = "bridge"`, `build(length, width, rise, depth, ramp_a, ramp_b, seed)`
- x 0..length-1 runs across the water, z 0..width-1 across the road (the way across is the middle,
  z = width // 2). **y 0 = the water's surface block.** The bed is at y -depth - 1. Piers go down to it.
- You walk at `y = rise` (the deck block is at rise - 1) except on the ramps. The first `ramp_a`
  blocks climb from rise - ramp_a at x 0, one per block, and the last `ramp_b` blocks fall the same way.
  Those ends sit on the banks.
- Keep the way across open: 2 blocks of headroom along the middle of the deck. Parapets go on the
  edges (z 0 and z width-1).

## Checking a kit
`./mc.py kit sample kits/NAME.py --town TOWN` builds exactly the plots the kit will build
(offline, nothing placed). It checks each one for fit, door side and step, and the audit on a flat pad
(floating, sealed rooms, dark floors, beds). Then it draws them all on one sheet: Read it. Without
`--town`, it samples a spread of sizes, doors and kinds. Bridge kits are sampled over six typical
crossings. The command exits with 0 only when every instance is clean.

Placing: `./mc.py place kits/NAME.py --plot TOWN/PLOT` (the plot's size, door, kind and a seed from its
id are passed in), and `./mc.py town bridge TOWN ID` for a crossing.
