# The architect

Ask for a build from inside Minecraft, see it before it exists, then keep it or don't.

```
you        /arc a stone well with a little roof, right here
architect  On it: a stone well with a little roof
architect  A stone-brick well with a spruce roof and a lantern.   [Build it] [No thanks]
you        /arc make the roof taller
architect  Done: the roof is two blocks taller.                   [Build it] [No thanks]
you        /arc yes
architect  Built it.                                              [Undo]
```

| Command | What happens |
|---|---|
| `/arc <idea>` | a new design, or a change to the one you're looking at |
| `/arc yes` | builds exactly what the preview showed |
| `/arc no` | drops the preview |
| `/arc undo` | takes your last build back, block for block |
| `/arc cancel`, `/arc status` | stop it; ask what it's doing |
| `/arc big <idea>` | the same, with a stronger (slower) model for large builds |

## What you see
- **A preview only you can see.** The blocks are sent to your screen alone; the world, and every other
  player, sees nothing until you say yes.
- **A glowing frame** around the build, visible through walls and from far away, and a bar at the top of
  your screen while a preview is waiting.
- **It builds where you mean.** Without a selection, the build goes a few blocks in front of you, facing
  you. With a WorldEdit selection, it fills the selection.

## How it works
```
Minecraft                          your machine
  /arc ... ──► plugin inbox ─────► ./mc.py architect serve
                                     ├─ yes / no / undo: answered at once, no AI
                                     └─ a request: a Claude agent designs it with the
                                        building toolkit, previews it, and tells you
  your screen ◄── preview, chat ◄────┘
```
- The plugin (`plugin/.../architect/`) turns `/arc` into an event with where you stand, which way you
  face, the ground and your selection.
- The daemon (`architect/assistant/`) answers yes, no and undo itself. A request starts a headless
  Claude Code session (`.claude/agents/mc-architect.md`); a follow-up continues the same conversation.
- The agent writes a small Python plan with the parts in `architect/parts.py` and runs `mc preview`. It
  never places anything: `/arc yes` does, with exactly the plan and position it previewed.
- A first preview takes about ten seconds; yes and undo are instant.

## Limits
The tools enforce these, not the agent's good manners:
- Without a selection: at most 48 blocks wide and 64 tall, within 32 blocks of you, and never on the
  spot you're standing.
- The agent can only preview and talk. Placing, undoing and console commands are refused to it.
- Two requests run at a time; the rest wait their turn. Operators only for now (`mcbridge.architect`).

## Running and testing
```bash
./mc.py architect serve      # leave it running while people play
./mc.py architect status     # who it's working for, previews waiting, recent builds
./mc.py eval scenarios       # scripted conversations, checked by code (see evals.md)
./mc.py bench                # how long three fixed requests take
```
It runs on your Claude subscription through the Claude Code CLI. Each request's transcript is saved in
`local/assistant/<player>/runs/`.
