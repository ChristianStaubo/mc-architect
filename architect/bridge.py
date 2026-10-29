"""Client for the MCBridge plugin (plugin/src): JSON over HTTP on 127.0.0.1, bearer token."""

import http.client
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import trace

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "server" / "plugins" / "MCBridge" / "token"
URL = "http://127.0.0.1:8765"


class BridgeError(Exception):
    pass


def call(path, body=None, timeout=180):
    t0 = time.time()
    status, err, size = 0, None, 0
    try:
        out, size = _call(path, body, timeout)
        status = 200
        return out
    except BridgeError as e:
        status, err = getattr(e, "status", -1), e
        raise
    finally:
        trace.record(path, body, int((time.time() - t0) * 1000), status, err, size)


def _call(path, body, timeout):
    if not TOKEN_FILE.exists():
        raise BridgeError(f"no bridge token at {TOKEN_FILE}: is the server running with the plugin?")
    req = urllib.request.Request(
        URL + path, data=json.dumps(body or {}).encode(), method="POST",
        headers={"Authorization": "Bearer " + TOKEN_FILE.read_text().strip(),
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw), len(raw)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("error", "")
        except Exception:
            msg = ""
        err = BridgeError(f"{path}: HTTP {e.code} {msg}")
        err.status = e.code
        raise err from None
    except urllib.error.URLError as e:
        raise BridgeError(f"bridge not reachable ({e.reason}): docker compose up -d") from None
    except (http.client.HTTPException, ConnectionError) as e:
        # Docker's port forwarder accepts, then drops, while the server is still starting.
        raise BridgeError(f"bridge not ready ({type(e).__name__}): is the server still starting?") from None


def status():
    return call("/status")


def command(cmd):
    return call("/command", {"command": cmd})


def as_player(player, cmd):
    """Run a command as if `player` typed it (replies go to their chat)."""
    return call("/as", {"player": player, "command": cmd})


def region(lo, hi):
    """Blocks in the inclusive box lo..hi as {(x, y, z): block-data string}."""
    return decode(call("/region", {"min": list(lo), "max": list(hi)}))


def decode(r):
    """A /region response (min, size, palette, rle in y, z, x order) as {(x, y, z): block}."""
    (x0, y0, z0), (w, _, d) = r["min"], r["size"]
    out, i = {}, 0
    for k in range(0, len(r["rle"]), 2):
        b = r["palette"][r["rle"][k]]
        for _ in range(r["rle"][k + 1]):
            y, rest = divmod(i, w * d)
            z, x = divmod(rest, w)
            out[(x0 + x, y0 + y, z0 + z)] = b
            i += 1
    return out


def heightmap(lo_xz, hi_xz):
    """{(x, z): (top_y, top_block)} for the inclusive area; top_y is the highest solid non-leaf block."""
    r = call("/heightmap", {"min": list(lo_xz), "max": list(hi_xz)})
    (x0, z0), (x1, z1) = r["min"], r["max"]
    out, i = {}, 0
    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            out[(x, z)] = (r["heights"][i], r["palette"][r["tops"][i]])
            i += 1
    return out


def place(payload):
    return call("/place", payload, timeout=600)


def undo(edit_id=None):
    return call("/undo", {"id": edit_id} if edit_id else {})


def history():
    return call("/history")["edits"]



# ---- the in-game architect (docs/in-game-architect.md) ----

def inbox(wait=25):
    """Events from /arc (and virtual players): waits up to `wait` seconds for one."""
    return call("/inbox", {"wait": wait}, timeout=wait + 15)["events"]


def ack(ids):
    return call("/inbox/ack", {"ids": list(ids)})


def post_event(context, text="", kind="request"):
    """An /arc event from a virtual player (context: player, pos, facing, ... as Context.java makes them)."""
    return call("/inbox/post", {"context": context, "text": text, "kind": kind})["id"]


def say(player, text, tone="info", buttons=()):
    """A line in the player's chat from the architect; buttons: [(label, command), ...]."""
    return call("/say", {"player": player, "text": text, "tone": tone, "buttons": [list(b) for b in buttons]})


def preview(player, body):
    """Show a /place body to one player only, as ghost blocks."""
    return call("/preview", {**body, "player": player})


def preview_clear(player):
    return call("/preview/clear", {"player": player})


def preview_get(player):
    return call("/preview/get", {"player": player})
