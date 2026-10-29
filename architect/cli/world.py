"""The server: doctor, status, restart, console commands."""

import json
import subprocess
import sys
import time

from .. import bridge, edits
from .common import ROOT


def cmd_doctor(_):
    ok = True
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", "mc-architect"],
                       capture_output=True, text=True)
    state = r.stdout.strip() or "missing (is Docker Desktop running?)"
    print(f"container: {state}")
    ok &= state == "running"
    try:
        s = bridge.status()
        print(f"bridge: ok, Minecraft {s['minecraft']}, TPS {s['tps']:.1f}, "
              f"{len(s['players'])} online, {len(edits.listing())} live edits")
    except bridge.BridgeError as e:
        print(f"bridge: {e}")
        ok = False
    if not ok:
        print("fix: open -a Docker; docker compose up -d  (plugin: scripts/build-plugin.sh, then mc restart)")
    return 0 if ok else 1


def cmd_status(_):
    print(json.dumps(bridge.status(), indent=2))


def cmd_restart(_):
    """Restart the container (the world saves first) and wait for the bridge."""
    subprocess.run(["docker", "compose", "up", "-d", "--force-recreate"], cwd=ROOT, check=True)
    for _ in range(60):
        time.sleep(2)
        try:
            bridge.status()
            print("server up")
            return 0
        except bridge.BridgeError:
            pass
    sys.exit("server did not come back in 2 minutes: docker logs mc-architect")


def cmd_cmd(a):
    first = a.command.lstrip("/").split()[0].lower() if a.command.strip() else ""
    if first in ("stop", "restart", "reload", "rl"):
        # Paper's /restart only stops the server here (no restart script); /reload breaks plugins.
        sys.exit(f"refused: '{first}' from inside the game. Use: mc restart")
    r = bridge.command(a.command)
    print("\n".join(r["output"]) or ("ok" if r["ok"] else "failed"))
    return 0 if r["ok"] else 1


def register(sub):
    for n, fn in (("doctor", cmd_doctor), ("status", cmd_status), ("restart", cmd_restart)):
        sub.add_parser(n).set_defaults(fn=fn)
    c = sub.add_parser("cmd")
    c.add_argument("command")
    c.set_defaults(fn=cmd_cmd)
