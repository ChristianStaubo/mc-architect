"""Where the ghost's settings live: houses and zones (config/ghost/houses.json), the database, secrets."""

import json
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOUSES_FILE = ROOT / "config" / "ghost" / "houses.json"
POLICY_DIR = ROOT / "policies"
LOCAL = ROOT / "local" / "ghost"
GRANT_KEY = ROOT / "server" / "plugins" / "MCBridge" / "grant-key"  # written by the plugin; models never read it
TEMPORAL = os.environ.get("GHOST_TEMPORAL", "127.0.0.1:7233")
TASK_QUEUE = "ghost-builds"


@lru_cache
def db_password():
    """The local database password: generated once into local/ghost/db-password (gitignored)."""
    f = LOCAL / "db-password"
    if not f.exists():
        LOCAL.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(24))
        f.chmod(0o600)
    return f.read_text().strip()


def dsn(user="ghost", db="ghost_app"):
    if os.environ.get("GHOST_DSN"):
        return os.environ["GHOST_DSN"]
    return f"postgresql://{user}:{db_password()}@127.0.0.1:5433/{db}"


@dataclass(frozen=True)
class Zone:
    id: str
    house: str | None       # None: the commons
    protected: bool
    box: tuple | None       # (x0, z0, x1, z1)

    def contains(self, x, z):
        x0, z0, x1, z1 = self.box
        return x0 <= x <= x1 and z0 <= z <= z1


COMMONS = Zone("commons", None, False, None)


@lru_cache
def houses():
    return json.loads(HOUSES_FILE.read_text())


def house(hid):
    return next((h for h in houses()["houses"] if h["id"] == hid), None)


def style(hid):
    """A house's building style, in words, from its town (towns/<town>/town.json and layout.json)."""
    h = house(hid)
    if not h:
        return ""
    town = ROOT / "towns" / h.get("town", hid)
    t = json.loads((town / "town.json").read_text()) if (town / "town.json").exists() else {}
    pal = json.loads((town / "layout.json").read_text()).get("palette", {}) if (town / "layout.json").exists() else {}
    blocks = ", ".join(f"{k} {v}" for k, v in pal.items() if k != "notes")
    return f"{h['name']}: {t.get('style') or pal.get('notes', '')}" + (f" (palette: {blocks})" if blocks else "")


def zone_of(ctx):
    """The zone a player's context puts them in."""
    pos = ctx.get("pos") or [0, 0, 0]
    return zone_at(pos[0], pos[2])


def zones():
    """Protected zones first: they win where they overlap a house's zone."""
    out = [Zone(p["id"], p.get("house"), True, tuple(p["box"])) for p in houses().get("protected", [])]
    for h in houses()["houses"]:
        out += [Zone(z["id"], h["id"], False, tuple(z["box"])) for z in h["zones"]]
    return out


def home_column(hid):
    """The middle of a house's first zone (its body's home), as (x, z)."""
    x0, z0, x1, z1 = house(hid)["zones"][0]["box"]
    return (x0 + x1) // 2, (z0 + z1) // 2


def zone_at(x, z):
    return next((zn for zn in zones() if zn.contains(x, z)), COMMONS)


def zones_touching(box):
    """Every zone a build's footprint (x0, z0, x1, z1) touches, the commons included if any of it is outside."""
    x0, z0, x1, z1 = box
    hit = [zn for zn in zones() if not (zn.box[2] < x0 or zn.box[0] > x1 or zn.box[3] < z0 or zn.box[1] > z1)]
    corners = [(x0, z0), (x0, z1), (x1, z0), (x1, z1)]
    if any(zone_at(cx, cz) is COMMONS for cx, cz in corners) or not hit:
        hit.append(COMMONS)
    return hit
