"""Simulated players for the ghost's evals: their events go through the plugin's inbox, the same path a
real player's take, and we read the outcome from the store (docs/ghost/design.md, Evals)."""

import time

from . import bridge, db
from .config import ROOT  # noqa: F401 (evals use sim.ROOT)


class Player:
    def __init__(self, name, pos, facing="north", target=None):
        self.name, self.pos, self.facing, self.target = name.lower(), list(pos), facing, target

    def ctx(self, addressed="explicit", near=None):
        return {"player": self.name, "uuid": f"sim-{self.name}", "world": "world", "pos": self.pos,
                "facing": self.facing, "addressed": addressed, "near_ghost": near,
                "target": {"pos": self.target, "block": "minecraft:grass_block"} if self.target else None}

    def chat(self, text, addressed="explicit", near=None):
        """addressed: what the plugin's code checks decided (explicit / candidate)."""
        return bridge.post("chat", text, self.ctx(addressed, near))

    def command(self, text):
        return bridge.post("command", text, self.ctx())

    def click(self, text):
        return bridge.post("button", text, self.ctx())

    def pick(self, house):
        return bridge.post("pick_house", house, self.ctx())

    def join(self):
        return bridge.post("join", "", self.ctx())


def said_to(player, since_id=0):
    """What the ghosts said to this player after outbox id `since_id`."""
    return db.all("SELECT id, ghost, text, buttons, sent_at FROM outbox WHERE player = %s AND id > %s ORDER BY id",
                  player.lower(), since_id)


def last_outbox_id():
    r = db.one("SELECT coalesce(max(id), 0) AS n FROM outbox")
    return r["n"]


def wait_for(pred, timeout=60, every=1.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(every)
    return None
