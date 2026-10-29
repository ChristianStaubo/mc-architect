"""The in-game architect: the daemon (architect serve), and the tools its agent talks and shows designs with
(say, preview). docs/in-game-architect.md."""

import json
import math
import os
import sys

from .. import bridge
from ..assistant import daemon, sessions
from ..build import payload
from ..placement import bounds
from .build import place_args, resolve, show_on_terrain
from .common import ints

RADIUS = 32        # without a selection, a build stays this close to where the player stood
MAX_SIDE = 48      # ... and this wide
MAX_HEIGHT = 64


def player_of(a):
    p = a.for_ or os.environ.get("MC_PLAYER")
    if not p:
        sys.exit("refused: whose preview? --for PLAYER (or MC_PLAYER)")
    return p


AHEAD = {"south": (0, 1), "north": (0, -1), "east": (1, 0), "west": (-1, 0)}


def limits(player, box, cells):
    """Refuse a build outside what the player asked for (their selection, or near where they stood) or one
    that would swallow them: without a selection it goes in front of them, never on their spot."""
    ctx = sessions.get(player).get("context") or {}
    (x0, y0, z0), (x1, y1, z1) = box
    if x1 - x0 + 1 > MAX_SIDE or z1 - z0 + 1 > MAX_SIDE or y1 - y0 + 1 > MAX_HEIGHT:
        return f"too big: {x1 - x0 + 1}x{y1 - y0 + 1}x{z1 - z0 + 1} (max {MAX_SIDE} wide, {MAX_HEIGHT} tall)"
    pos = ctx.get("pos")
    if pos and not ctx.get("selection"):
        far = max(abs(x - pos[0]) for x in (x0, x1)), max(abs(z - pos[2]) for z in (z0, z1))
        if max(far) > RADIUS:
            return f"too far from {player} (at {pos[0]},{pos[2]}): keep the build within {RADIUS} blocks of them"
        px, pz = math.floor(pos[0]), math.floor(pos[2])
        foot = {(x, z) for (x, _, z), b in cells.items() if b != "air" and not str(b).endswith(":air")}
        if any((px + dx, pz + dz) in foot for dx in (-1, 0, 1) for dz in (-1, 0, 1)):
            dx, dz = AHEAD.get(ctx.get("facing"), (0, 1))
            return (f"the build covers where {player} stands ({px},{pz}). Put it in front of them: they face "
                    f"{ctx.get('facing', 'south')}, so its nearest side should be about 3 blocks that way, "
                    f"at {px + 3 * dx},{pz + 3 * dz} (move --at, not the design)")
    return None


def cmd_preview(a):
    player = player_of(a)
    sel = (sessions.get(player).get("context") or {}).get("selection")
    if sel and not a.within:  # the player's WorldEdit selection is the area
        a.within = f"{sel['min'][0]},{sel['min'][2]},{sel['max'][0]},{sel['max'][2]}"
    build, t, at, cells, y0 = resolve(a)
    box = [list(v) for v in bounds(cells)]
    why = limits(player, box, cells)
    if why:
        sys.exit(f"refused: {why}")
    r = show_on_terrain(build, at, y0, cells)
    shown = bridge.preview(player, payload(cells, label=build.name))
    args = ["--at", f"{at[0]},{at[1]}", "--y", str(y0), "--foundation", a.foundation]
    args += ["--no-clear"] * a.no_clear + ["--keep-trees"] * a.keep_trees + (["--within", a.within] if a.within else [])
    sessions.set_pending(player, a.plan, args, box, shown["blocks"])
    print(f"previewed for {player}: {shown['blocks']} blocks, box {box[0]}..{box[1]}, "
          f"{'on their screen now' if shown['shown'] else 'they are not online: it shows when they are'}. "
          f"audit {r['fails']} fail. Tell them with mc say; they answer /arc yes, /arc no, or ask for changes.")


def cmd_say(a):
    buttons = [b.split("=", 1) for b in a.button]
    r = bridge.say(a.player, a.text, a.tone, buttons)
    print("said" if r["delivered"] else f"{a.player} isn't online: not delivered")


def cmd_architect(a):
    if a.action == "serve":
        daemon.serve(model=a.model, log=lambda m: print(m, flush=True))
    elif a.action == "status":
        print(json.dumps(sessions._read(), indent=1) if a.all else daemon.status())
    elif a.action == "ask":  # a virtual player asks (tests, evals)
        ctx = {"player": a.as_, "world": "world", "pos": ints(a.at), "facing": a.facing, "selection": None}
        if a.selection:
            v = ints(a.selection)
            ctx["selection"] = {"min": v[:3], "max": v[3:]}
        kind = a.text if a.text in ("yes", "no", "undo", "cancel", "status") else "request"
        print(f"posted event {bridge.post_event(ctx, '' if kind != 'request' else a.text, kind)}")


def register(sub):
    pv = sub.add_parser("preview", help="show a plan to one player as ghost blocks (the architect's yes/no step)")
    place_args(pv)
    pv.add_argument("--for", dest="for_", help="the player (default: MC_PLAYER)")
    pv.set_defaults(fn=cmd_preview)
    sy = sub.add_parser("say", help="a line in a player's chat from the architect")
    sy.add_argument("player")
    sy.add_argument("text")
    sy.add_argument("--tone", default="info", choices=["info", "done", "warn", "thinking"])
    sy.add_argument("--button", action="append", default=[], help='LABEL=/command, e.g. "Build it=/arc yes"')
    sy.set_defaults(fn=cmd_say)
    ar = sub.add_parser("architect", help="the in-game architect's daemon")
    ar.add_argument("action", choices=["serve", "status", "ask"])
    ar.add_argument("text", nargs="?", help="ask: what the virtual player says")
    ar.add_argument("--as", dest="as_", default="virtual_vera")
    ar.add_argument("--at", default="300,90,-233", help="ask: X,Y,Z where the virtual player stands")
    ar.add_argument("--facing", default="south")
    ar.add_argument("--selection", help="ask: X0,Y0,Z0,X1,Y1,Z1")
    ar.add_argument("--model", default="sonnet")
    ar.add_argument("--all", action="store_true", help="status: every player's full state")
    ar.set_defaults(fn=cmd_architect)
