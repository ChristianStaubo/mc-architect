"""The ghost plugin's routes, over MCBridge's bridge (same token)."""

import sys

from . import config

sys.path.insert(0, str(config.ROOT))
from architect.bridge import BridgeError, call  # noqa: E402,F401


def inbox(wait=25):
    return call("/ghost/inbox", {"wait": wait}, timeout=wait + 15)["events"]


def ack(ids):
    return call("/ghost/inbox/ack", {"ids": list(ids)})


def post(kind, text, context):
    """A simulated player's event (evals): the same path a real one takes."""
    return call("/ghost/inbox/post", {"kind": kind, "text": text, "context": context})["id"]


def say(ghost, player, text, buttons=()):
    return call("/ghost/say", {"ghost": ghost, "player": player, "text": text, "buttons": [list(b) for b in buttons]})


def body(ghost, action, **kw):
    return call("/ghost/body", {"ghost": ghost, "action": action, **kw})


def bodies():
    return call("/ghost/bodies", {})["bodies"]


def houses(houses=None, members=None):
    b = {}
    if houses is not None:
        b["houses"] = houses
    if members is not None:
        b["members"] = members
    return call("/ghost/houses", b)


def menu(player):
    return call("/ghost/menu", {"player": player})


def status():
    return call("/ghost/status", {})
