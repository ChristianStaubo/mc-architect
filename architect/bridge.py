"""Client for the MCBridge plugin (plugin/src): JSON over HTTP on 127.0.0.1, bearer token."""

import http.client
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "server" / "plugins" / "MCBridge" / "token"
URL = "http://127.0.0.1:8765"


class BridgeError(Exception):
    pass


def call(path, body=None, timeout=180):
    if not TOKEN_FILE.exists():
        raise BridgeError(f"no bridge token at {TOKEN_FILE}: is the server running with the plugin?")
    req = urllib.request.Request(
        URL + path, data=json.dumps(body or {}).encode(), method="POST",
        headers={"Authorization": "Bearer " + TOKEN_FILE.read_text().strip(),
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("error", "")
        except Exception:
            msg = ""
        raise BridgeError(f"{path}: HTTP {e.code} {msg}") from None
    except urllib.error.URLError as e:
        raise BridgeError(f"bridge not reachable ({e.reason}): docker compose up -d") from None
    except (http.client.HTTPException, ConnectionError) as e:
        # Docker's port forwarder accepts, then drops, while the server is still starting.
        raise BridgeError(f"bridge not ready ({type(e).__name__}): is the server still starting?") from None


def status():
    return call("/status")


def command(cmd):
    return call("/command", {"command": cmd})


def region(lo, hi, world=None):
    """Blocks in the inclusive box lo..hi, decoded to a dict {(x, y, z): block-data string}."""
    r = call("/region", {"min": list(lo), "max": list(hi), **({"world": world} if world else {})})
    cells = rle_decode(r["rle"])
    (x0, y0, z0), (w, h, d) = r["min"], r["size"]
    out, i = {}, 0
    for y in range(h):
        for z in range(d):
            for x in range(w):
                out[(x0 + x, y0 + y, z0 + z)] = r["palette"][cells[i]]
                i += 1
    return out


def heightmap(lo_xz, hi_xz, world=None):
    """{(x, z): (top_y, top_block)} for the inclusive area; top_y is the highest solid non-leaf block."""
    r = call("/heightmap", {"min": list(lo_xz), "max": list(hi_xz), **({"world": world} if world else {})})
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


def rle_decode(rle):
    out = []
    for k in range(0, len(rle), 2):
        out.extend([rle[k]] * rle[k + 1])
    return out
