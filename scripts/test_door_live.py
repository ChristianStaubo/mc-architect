"""Live test of the 2x2 piston door on scratch ground (needs the running server; forceloads its chunks,
since redstone only runs in ticking chunks). python3 scripts/test_door_live.py -> PASS / FAIL"""
import sys, time; sys.path.insert(0, '.')
from architect import bridge, edits, redstone
O = (330, 66, 330)
bridge.command("forceload add 320 320 345 345")
b, info = redstone.piston_door_2x2()
cells = {(O[0] + x, O[1] + y, O[2] + z): v for (x, y, z), v in b.blocks.items()}
for e0 in [e for e in edits.listing() if e["label"] == "test-door"]:
    edits.undo(e0["id"])
e = edits.place(cells, "test-door")
xs, ys, zs = zip(*cells)
bridge.call("/kick", {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]})
lever = [O[i] + info["lever"][i] for i in range(3)]
lo = (O[0] - 1, O[1] - 1, O[2] - 1); hi = (O[0] + 1, O[1] + 2, O[2] + 2)
def state():
    time.sleep(1.0)
    return redstone.door_state(bridge.region(lo, hi), info, O)[0]
inside = [O[i] + info["inside_lever"][i] for i in range(3)]
got = [state()]
for on in (True, False, True, False):  # the outside lever
    bridge.call("/use", {"pos": lever, "on": on}); got.append(state())
for on in (True, False):  # the inside lever
    bridge.call("/use", {"pos": inside, "on": on}); got.append(state())
bridge.call("/use", {"pos": lever, "on": True}); got.append(state())   # both: open, and stays open
bridge.call("/use", {"pos": inside, "on": True}); got.append(state())
bridge.call("/use", {"pos": lever, "on": False}); got.append(state())  # inside still on: open
bridge.call("/use", {"pos": inside, "on": False}); got.append(state())  # both off: closed
want = ["closed", "open", "closed", "open", "closed", "open", "closed", "open", "open", "open", "closed"]
print(e["id"], got)
print("PASS" if got == want else f"FAIL (wanted {want})")
