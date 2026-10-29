"""What the in-game architect may build, checked by the tools (mc preview) rather than trusted to the agent,
and shared with the scenario suite so the guard and its eval can't disagree."""

import math

from .. import blocks
from ..parts import FACE_STEP
from ..placement import bounds

RADIUS = 32        # without a selection, a build stays this close to where the player stood
MAX_SIDE = 48      # ... and this wide
MAX_HEIGHT = 64
GAP = 3            # blocks between the player and the near side of a build put "in front of" them


def build_box(cells):
    """The build's own box: its blocks, not the air of the trees and hill cleared for it."""
    own = [p for p, b in cells.items() if not blocks.is_air(b)]
    return [list(v) for v in bounds(own or cells)]


def ahead(ctx, frame, at):
    """The --at that puts this build GAP blocks in front of the player, centred on them across their view."""
    (x0, _, z0), (x1, _, z1) = frame
    px, pz = math.floor(ctx["pos"][0]), math.floor(ctx["pos"][2])
    dx, dz = FACE_STEP.get(ctx.get("facing"), (0, 1))
    if dz:  # facing south or north: slide along z so the near side is GAP away, centre on x
        sx = px - (x0 + x1) // 2
        sz = (pz + GAP - z0) if dz > 0 else (pz - GAP - z1)
    else:
        sz = pz - (z0 + z1) // 2
        sx = (px + GAP - x0) if dx > 0 else (px - GAP - x1)
    return at[0] + sx, at[1] + sz


def limits(ctx, frame, at=None):
    """None if the build may go there, else why not (and, when it covers the player, the --at to use)."""
    (x0, y0, z0), (x1, y1, z1) = frame
    if x1 - x0 + 1 > MAX_SIDE or z1 - z0 + 1 > MAX_SIDE or y1 - y0 + 1 > MAX_HEIGHT:
        return f"too big: {x1 - x0 + 1}x{y1 - y0 + 1}x{z1 - z0 + 1} (max {MAX_SIDE} wide, {MAX_HEIGHT} tall)"
    pos = ctx.get("pos")
    if not pos or ctx.get("selection"):
        return None
    if max(abs(v - pos[0]) for v in (x0, x1)) > RADIUS or max(abs(v - pos[2]) for v in (z0, z1)) > RADIUS:
        return f"too far from {ctx.get('player')} (at {pos[0]},{pos[2]}): keep it within {RADIUS} blocks of them"
    px, pz = math.floor(pos[0]), math.floor(pos[2])
    if x0 - 1 <= px <= x1 + 1 and z0 - 1 <= pz <= z1 + 1:
        hint = f": use --at {','.join(map(str, ahead(ctx, frame, at)))}" if at else ""
        return (f"the build covers where {ctx.get('player')} stands ({px},{pz}); put it in front of them "
                f"(they face {ctx.get('facing', 'south')}){hint}")
    return None
