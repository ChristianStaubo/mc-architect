"""Who is in which house, with which role. The store is the truth; the plugin gets a copy."""

from . import bridge, config, db
from .policy import Who


def who(player):
    """The requester as the policy engine sees them: from the members table and config, never from a model."""
    name = player.lower()
    row = db.one("SELECT house, role FROM members WHERE player = %s", name)
    if name == config.houses()["owner"].lower():
        return Who("player", name, "owner", row and row["house"])
    if not row or not row["house"]:
        return Who("player", name, "guest")
    return Who("player", name, row["role"], row["house"])


def join(player, uuid, house):
    if not config.house(house):
        raise ValueError(f"no house {house}")
    role = "owner" if player.lower() == config.houses()["owner"].lower() else "member"
    db.run("INSERT INTO members (player, uuid, house, role) VALUES (%s, %s, %s, %s) "
           "ON CONFLICT (player) DO UPDATE SET house = EXCLUDED.house, uuid = EXCLUDED.uuid, "
           "role = CASE WHEN members.role IN ('head', 'owner') THEN members.role ELSE EXCLUDED.role END, updated_at = now()",
           player.lower(), uuid, house, role)


def head_of(house):
    row = db.one("SELECT player FROM members WHERE house = %s AND role = 'head' ORDER BY updated_at LIMIT 1", house)
    return row and row["player"]


def approver(house):
    """Who approves for a house: its head, or the owner while it has none."""
    return head_of(house) or config.houses()["owner"].lower()


def ghost_of(who):
    """A player's own ghost: their house's, or the spirit."""
    return who.house or "spirit"


def answering(who, ctx):
    """The ghost that answers what they say: the one they're standing next to (another house's, for a
    visitor), else the one they're mid-conversation with, else their own."""
    for g in (ctx.get("near_ghost"), ctx.get("talking_to")):
        if g and (config.house(g) or g == "spirit"):
            return g
    return ghost_of(who)


def sync():
    """Send the houses and members to the plugin (on start and after every change)."""
    hs = [{"id": h["id"], "name": h["name"], "color": h["color"], "motto": h.get("motto", "")}
          for h in config.houses()["houses"]]
    ms = {r["player"]: {"house": r["house"], "role": r["role"]} for r in db.all("SELECT player, house, role FROM members")}
    owner = config.houses()["owner"].lower()
    ms.setdefault(owner, {"house": None, "role": "owner"})["role"] = "owner"
    return bridge.houses(hs, ms)
