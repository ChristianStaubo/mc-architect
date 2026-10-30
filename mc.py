#!/usr/bin/env python3
"""mc: the command line for the Minecraft server (and the one tool its agents use).

Build
  mc site --task T | --plot TOWN/P | X,Z [W,D]
                                    terrain of a plot (or centred on X,Z): heights grid, water, slope, map
  mc place PLAN [--at X,Z | --near PLAYER] [--task T | --plot TOWN/P | --within X0,Z0,X1,Z1] [--dry-run]
             [--foundation BLOCK|none] [--y Y] [--no-clear] [--keep-trees]
                                    build a plan (plans/NAME or a .py path) on the ground there:
                                    local (0,0,0) at X,Z, y 0 one above the median ground; foundation
                                    fills down to the terrain, the hill inside the box is cleared,
                                    trees touching the build removed. With --task and no --at the
                                    build is centred in the plot. --dry-run previews on the real terrain
  mc undo [EDIT]                    undo the latest edit, or EDIT (e.g. e12); survives restarts
  mc edits                          live edits (id, label, task, box)
Look and judge
  mc shots [EDIT]                   contact sheet: 4 corner views, top-down, floor plan (critic input)
  mc render X1,Y1,Z1 X2,Y2,Z2 [--view se|sw|nw|ne] [--surface [N]]
                                    isometric picture of any region (--surface: no underground)
  mc audit [EDIT] [--friction]      hard checks (floating, doors, beds, sealed rooms, dark floors, panes)
                                    exit 2 on a fail; --friction files a friction report for it
  mc blueprint PLAN --at X,Z [--y Y] [--no-clear] [--foundation F] [--face west]
                                    the approval sheet: site + footprint, design x-ray, face before/after,
                                    floor plans, and the audit of the result. Places nothing.
When the tools fall short
  mc gap "<what was missing or awkward>"   note a tool gap and carry on (the fixer turns it into a tool)
  mc stuck "<goal> | <what you tried> | <what happened>"   save a friction report, then STOP
  mc incidents [--all] | incident ID [replay]   failures saved automatically: error, stack, last bridge
                                    requests and commands, the plan as it was, the server log; replay = dry rerun
  mc friction [--all] | resolve ID "<fix>" --cause C | stats
The in-game architect (docs/architect.md)
  mc architect serve | status       the daemon that answers /arc in game; what it's doing
  mc architect ask "TEXT" --as NAME --at X,Y,Z [--facing F] [--selection ...]   a virtual player asks
  mc preview PLAN --for PLAYER [place options]   show a plan to one player only, as ghost blocks
  mc say PLAYER "TEXT" [--button "Label=/command"]   a line in their chat from the architect
  mc bench                          time the architect on three fixed requests
Evals (docs/evals.md)
  mc eval gate [--offline]          the regression suite: must be 100%; exit 1 on a failure
  mc eval run [--tasks a,b] [--trials 3] | report [RUN] [--vs OLD] | judge RUN   build quality
  mc eval check TASK [--plan P]     grade a plan on a task's freshly reset site
  mc eval scenarios [--tasks ...]   the architect's scripted conversations
  mc eval list | brief TASK --run R | reset TASK
Towns (towns/NAME/town.json + layout.json)
  mc town site NAME                 the area's height grid, slope classes, terrain and slope maps
  mc town show NAME                 check the layout (plots, roads, doors, water, earthworks) + map; exit 2 on a fail
  mc town road NAME ROAD [--dry-run]       build a road (follows the land, bridges over water)
  mc town terrace NAME PLOT [--dry-run]    level a plot at its floor_y with retaining walls
  mc town brief NAME PLOT           a builder's brief for a plot; build it with place --plot NAME/PLOT
  mc town shots NAME                the whole town from four corners and above (the town critic's input)
  mc town tidy NAME [--dry-run]     remove whole trees touching plots and roads (never inside plots)
  mc town status NAME               what's built
Server
  mc doctor | status | restart | cmd "<command>"  (cmd refuses stop/restart/reload)

Every call is logged to local/runs/commands.jsonl and every bridge request to local/runs/trace/ (with
MC_RUN_ID); a failure saves an incident in local/runs/incidents/. Pictures: local/renders/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from architect.cli import main  # noqa: E402

if __name__ == "__main__":
    main(__doc__)
