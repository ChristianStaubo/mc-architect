"""The in-game architect: the daemon (architect serve), and the tools its agent talks and shows designs with
(say, preview). docs/in-game-architect.md."""

import json
import os
import sys

from .. import bridge
from ..assistant import daemon, policy, sessions
from ..build import payload
from ..placement import bounds
from .build import place_args, resolve, show_on_terrain
from .common import ints


def player_of(a):
    p = a.for_ or os.environ.get("MC_PLAYER")
    if not p:
        sys.exit("refused: whose preview? --for PLAYER (or MC_PLAYER)")
    return p


def cmd_preview(a):
    player = player_of(a)
    ctx = {"player": player, **(sessions.get(player).get("context") or {})}
    sel = ctx.get("selection")
    if sel and not a.within:  # the player's WorldEdit selection is the area
        a.within = f"{sel['min'][0]},{sel['min'][2]},{sel['max'][0]},{sel['max'][2]}"
    build, t, at, cells, y0 = resolve(a)
    box, frame = [list(v) for v in bounds(cells)], policy.build_box(cells)
    why = policy.limits(ctx, frame, at)
    if why:
        sys.exit(f"refused: {why}")
    r = show_on_terrain(build, at, y0, cells)
    shown = bridge.preview(player, payload(cells, label=build.name) | {"frame": frame})
    args = ["--at", f"{at[0]},{at[1]}", "--y", str(y0), "--foundation", a.foundation]
    args += ["--no-clear"] * a.no_clear + ["--keep-trees"] * a.keep_trees + (["--within", a.within] if a.within else [])
    sessions.set_pending(player, a.plan, args, box, frame, shown["blocks"])
    print(f"previewed for {player}: the build is {frame[0]}..{frame[1]} ({shown['blocks']} blocks changed), "
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
        print(json.dumps(sessions.all_players(), indent=1) if a.all else daemon.status())
    elif a.action == "ask":  # a virtual player asks (tests, evals)
        ctx = {"player": a.as_, "world": "world", "pos": ints(a.at), "facing": a.facing, "selection": None}
        if a.selection:
            v = ints(a.selection)
            ctx["selection"] = {"min": v[:3], "max": v[3:]}
        kind = a.text if a.text in daemon.HANDLERS else "request"
        print(f"posted event {bridge.post_event(ctx, '' if kind != 'request' else a.text, kind)}")


BENCH = ["a small stone well with a little wooden roof", "a wooden bench with a lamp post next to it",
         "a small cosy cottage with a chimney"]


def cmd_bench(a):
    """The same requests, one after another, as virtual players on the scenario sites: how long until the
    preview, until they're told, and in all."""
    from .. import scenarios, sites
    scs = [s for s in scenarios.scenarios() if s["id"] in ("well-here", "change-it", "cancel")]
    told = []
    for text, sc in zip(BENCH, scs):
        name = f"bench-{sc['id']}"
        sessions.forget(name)
        sites.reset(scenarios.site_id(sc))
        daemon.handle({"player": name, "kind": "request", "text": text, "context": scenarios.context(sc, name)},
                      a.model, lambda m: None)
        scenarios.wait(name)
        r = json.loads((sessions.workspace(name) / "runs" / f"{sessions.get(name)['requests']}.json").read_text())
        told.append(r["to_say_s"])
        bridge.preview_clear(name)
        sites.reset(scenarios.site_id(sc))
        print(f"  {text[:40]:<40} preview {r['to_preview_s']}s, told {r['to_say_s']}s, all {round(r['minutes'] * 60)}s, "
              f"{len(r['tools'])} tool calls", flush=True)
    told = sorted(t for t in told if t is not None)
    print(f"told after {told} s (median {told[len(told) // 2] if told else '-'})")


def register(sub):
    sub.add_parser("bench", help="time the architect on three fixed requests").set_defaults(fn=cmd_bench, model="sonnet")
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
