"""authorize(): the one question every action asks (docs/ghost/design.md, "Who may do what").

Cedar decides, from policies/ghost.cedar. Facts come from the store and the game: who the requester is
(the event's player), their role and house (the members table), the zone (config), block counts (code).
A worker acting for someone needs both: the requester may, and the ghost may (`both`).
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

import cedarpy

from . import config


@dataclass(frozen=True)
class Who:
    kind: str                 # player | ghost | spirit
    id: str                   # player name, house id (a ghost), or "spirit"
    role: str = "guest"       # players: owner | head | member | guest
    house: str | None = None  # players: the house they picked; ghosts: theirs

    @staticmethod
    def ghost(house):
        return Who("ghost", house, house=house)


SPIRIT = Who("spirit", "spirit")


@dataclass
class Decision:
    allowed: bool
    rules: list = field(default_factory=list)   # the @ids of the policies that decided
    errors: list = field(default_factory=list)
    who: str = ""

    def reason(self):
        return ", ".join(self.rules) or ("no rule allows it" if not self.allowed else "")


@lru_cache
def _policies():
    text = (config.POLICY_DIR / "ghost.cedar").read_text()
    ids = re.findall(r'@id\("([^"]+)"\)', text)
    return text, ids


def _uid(t, i):
    return {"__entity": {"type": t, "id": i}}


def _entities(principal, resource):
    ents = {}

    def add(t, i, attrs, parents=()):
        ents[(t, i)] = {"uid": _uid(t, i), "attrs": attrs, "parents": list(parents)}

    for h in config.houses()["houses"]:
        add("House", h["id"], {"name": h["name"]})
    if principal.kind == "player":
        attrs = {"role": principal.role}
        if principal.house:
            attrs["house"] = _uid("House", principal.house)
        add("Player", principal.id, attrs, [_uid("House", principal.house)] if principal.house else [])
    elif principal.kind == "ghost":
        add("Ghost", principal.id, {"house": _uid("House", principal.house)})
    else:
        add("Spirit", principal.id, {})
    if isinstance(resource, config.Zone):
        attrs = {"protected": resource.protected}
        if resource.house:
            attrs["house"] = _uid("House", resource.house)
        add("Zone", resource.id, attrs)
    else:  # a memory: ("memory", id, owner name)
        _, mid, owner = resource
        add("Player", owner, {"role": "member"}) if (("Player", owner) not in ents) else None
        add("Memory", mid, {"owner": _uid("Player", owner)})
    return list(ents.values())


def _ref(who):
    return f'{ {"player": "Player", "ghost": "Ghost", "spirit": "Spirit"}[who.kind]}::"{who.id}"'


def authorize(who, action, resource, context=None):
    """May `who` do `action` (Say, Move, Preview, Build, Demolish, Undo, ApproveBuild, ReadMemory) to
    `resource` (a config.Zone, or ("memory", id, owner))?"""
    text, ids = _policies()
    res = (f'Zone::"{resource.id}"' if isinstance(resource, config.Zone) else f'Memory::"{resource[1]}"')
    r = cedarpy.is_authorized({"principal": _ref(who), "action": f'Action::"{action}"', "resource": res,
                               "context": context or {}}, text, _entities(who, resource))
    rules = [ids[int(p[len("policy"):])] if p.startswith("policy") else p for p in r.diagnostics.reasons]
    return Decision(r.allowed, rules, list(r.diagnostics.errors), who=f"{who.kind}:{who.id}")


def both(requester, ghost, action, resource, context=None):
    """A worker acting for `requester` on behalf of `ghost`: both must be allowed (no confused deputy)."""
    a = authorize(requester, action, resource, context)
    if not a.allowed:
        return a
    b = authorize(ghost, action, resource, context)
    return Decision(b.allowed, a.rules + b.rules, a.errors + b.errors, who=b.who if not b.allowed else a.who)


def build_context(blocks, head_approved=False, zone_head_approved=False):
    return {"blocks": int(blocks), "head_approved": bool(head_approved), "zone_head_approved": bool(zone_head_approved)}


def validate():
    """Policy errors against the schema (empty = fine). Run in tests and before deploying policy changes."""
    text, _ = _policies()
    schema = (config.POLICY_DIR / "ghost.cedarschema").read_text()
    r = cedarpy.validate_policies(text, schema)
    return [] if r.validation_passed else [str(e) for e in r.errors]
