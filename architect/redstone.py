"""Redstone contraptions as parts, each with a test that drives it the way a player would (bridge /use)
and checks the result (bridge /region). A contraption isn't done until its test passes on the server.

Local coordinates for doors: the door's plane is x = 0, outside is +x, inside (the tunnel) is -x; the
doorway is z = 0..1, y = 0..1 (floor at y = -1). Everything a part doesn't set is `rock`."""

from .build import Build

DUST = "redstone_wire[east=side,west=side,north=side,south=side,power=0]"


def piston_door_2x2(rock="stone", door="stone", tunnel_depth=6, face_x=1):
    """A hidden 2x2 piston door in a rock face, with a lever on the face to the door's north (-z) side.
    Closed: two door blocks per side are pushed into the doorway by sticky pistons (powered by redstone
    torches). The lever powers the torches' blocks, the torches go out, the pistons retract and pull the
    door blocks into the rock: the doorway opens onto a tunnel. The doorway sits one block back from the
    face (x = face_x) so the rock on either side hides the piston heads.

    Returns (build, info): info has the lever position, the doorway cells and the tunnel cells."""
    b = Build("piston-door-2x2")
    # the rock mass the mechanism is buried in
    b.fill(-tunnel_depth - 2, -4, -7, face_x, 5, 6, rock)
    # doorway niche in the face, the door plane and the tunnel behind
    for y in (0, 1):
        for z in (0, 1):
            b.set(face_x, y, z, "air")
            b.set(0, y, z, "air")  # placed open: the torches close it once it's kicked
            for x in range(-tunnel_depth, 0):
                b.set(x, y, z, "air")
    # pistons beside the doorway, each with its door block on its face (retracted = open)
    for y in (0, 1):
        b.set(0, y, -2, "sticky_piston[extended=false,facing=south]")
        b.set(0, y, 3, "sticky_piston[extended=false,facing=north]")
        b.set(0, y, -1, door)
        b.set(0, y, 2, door)
    # torches: one under each bottom piston (standing on a control block); one behind each top piston,
    # on the side of a control block further back. Not above the top pistons: Java pistons also count as
    # powered when the space above them is next to power (quasi-connectivity), so a torch's control block
    # there held the top row shut when the lever turned the torch off (found by the test).
    b.set(0, -1, -2, "redstone_torch[lit=true]")
    b.set(0, -1, 3, "redstone_torch[lit=true]")
    for z in (-2, 3):
        b.set(-1, 1, z, "redstone_wall_torch[facing=east,lit=true]")  # on control block (-2, 1, z)
        b.set(-1, 2, z, "air")  # nothing solid over the torch: it would be powered and feed the wire
        b.set(-2, 3, z, "air")  # room for the wire to step down onto the control block
        b.set(-2, 2, z, DUST)   # on top of the control block: powering it puts the torch out
    # bottom line under the doorway: its ends point into the bottom torches' control blocks
    for z in (-1, 0, 1, 2):
        b.set(0, -2, z, DUST)
    # top line over the tunnel roof, between the two step-downs
    for z in (-1, 0, 1, 2):
        b.set(-2, 3, z, DUST)
    # the lever on the face, north of the door, and the wire from it
    lever = (face_x + 1, 1, -4)
    b.set(face_x, 1, -4, rock)
    b.set(*lever, "lever[face=wall,facing=east,powered=false]")
    b.set(0, 1, -4, DUST)
    # down to the bottom line: steps with air above each lower dust, then under the tunnel floor
    for (x, y, z) in ((-1, 0, -4), (-2, -1, -4), (-3, -2, -4)):
        b.set(x, y, z, DUST)
        b.set(x, y + 1, z, "air")
    for z in (-3, -2, -1, 0):
        b.set(-3, -2, z, DUST)
    for x in (-2, -1):
        b.set(x, -2, 0, DUST)
    # up to the top line: two steps, west, then along the tunnel roof to join it in the middle
    b.set(0, 2, -4, "air")
    b.set(0, 2, -5, DUST)
    b.set(0, 3, -5, "air")
    for (x, z) in ((-1, -5), (-2, -5), (-3, -5), (-3, -4), (-3, -3), (-3, -2), (-3, -1), (-3, 0)):
        b.set(x, 3, z, DUST)
    info = {"lever": lever, "doorway": [(0, y, z) for y in (0, 1) for z in (0, 1)],
            "tunnel": [(-1, y, z) for y in (0, 1) for z in (0, 1)]}
    return b, info


def door_state(cells, info, origin):
    """'closed' if all doorway cells are solid, 'open' if all are air, else 'jammed' (with the cells)."""
    ox, oy, oz = origin
    got = [cells.get((ox + x, oy + y, oz + z), "?") for x, y, z in info["doorway"]]
    air = [g.replace("minecraft:", "").startswith("air") for g in got]
    if all(air):
        return "open", got
    if not any(air):
        return "closed", got
    return "jammed", got
