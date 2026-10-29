# Build rubric (the critic's half of the judge)

The critic scores a build from its contact sheet (`mc shots`) and the brief, never from the builder's
reasoning. Each criterion is 1–10; 5 is "fine, unremarkable", 8 is "a good player build you'd show a
friend", 10 is "the best builds on community sites". Calibrated against the user's own ratings
(`evals/ratings.jsonl`); when the critic and the user disagree, the user is right and this file changes.

| Criterion | What earns a high score | What costs points |
|---|---|---|
| brief | Everything the brief asks for is there and recognisable (a tavern reads as a tavern). | Missing parts of the brief; the wrong kind of building. |
| shape | An interesting silhouette: varied heights, wings, dormers, a roof that isn't one flat slab. | A plain box; a roof that's just a lid. |
| depth | Walls have relief: frames, beams, pillars, inset windows, overhangs, trim, 1-block offsets. | Flat walls of one block type. |
| palette | 3–5 materials that suit the style, used consistently, with texture variation (e.g. stone + cobble + andesite). | One material everywhere, or clashing colours. |
| proportion | Doors, windows, floors and roof at believable sizes for a player; roof pitch suits the footprint. | Squat or stretched; tiny windows on a huge wall; 2-block ceilings everywhere. |
| detail | Purposeful small things: lanterns, flower boxes, fences, barrels, signage, chimney, path to the door. | Bare, or clutter without purpose. |
| site | Sits on the land: follows the slope, a path in, foundation that looks deliberate, no scars. | Floating, a cobblestone cliff of foundation, carved terrain left raw. |
| interior | Rooms are usable and furnished for their purpose, lit, with headroom. | Empty shells, cramped rooms, furniture blocking paths. |

**overall** is not the average: it is the critic's honest answer to "how good is this build for its
brief?" (1–10), informed by the criteria. A single serious problem (no interior in a tavern) caps it.

## Output (write it as JSON to the path you are given)
```json
{
  "task": "tavern-slope",
  "scores": {"brief": 6, "shape": 4, "depth": 3, "palette": 6, "proportion": 5, "detail": 4, "site": 5, "interior": 5},
  "overall": 5,
  "summary": "one sentence a player would say looking at it",
  "problems": ["the three most important fixes, most important first, each concrete (where, what to do)"],
  "strengths": ["what to keep"]
}
```
