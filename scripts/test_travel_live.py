"""Live test of /sethome, /home, the cooldown and the /tpa refusals, run as an online player through the
bridge's /as (as if they typed it): python3 scripts/test_travel_live.py PLAYER. It overwrites that
player's home with where they stand, and leaves them there. Accepting a /tpa needs two people."""
import sys, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from architect import bridge

if len(sys.argv) != 2:
    sys.exit("usage: python3 scripts/test_travel_live.py <player who is online>")
P = sys.argv[1]


def pos():
    return next(p['pos'] for p in bridge.status()['players'] if p['name'] == P)


def near(a, b, d=1.5):
    return all(abs(x - y) <= d for x, y in zip(a, b))


def run(cmd):
    return bridge.as_player(P, cmd)


start = pos()
results = []
run("sethome")
bridge.command(f"tp {P} 290 99 -229"); time.sleep(1)
results.append(("tp away", not near(pos(), start, 5)))
time.sleep(10.5)  # the cooldown applies to plugin teleports only, but start clean
run("home"); time.sleep(1.5)
results.append(("home brings you back", near(pos(), start)))
bridge.command(f"tp {P} 290 99 -229"); time.sleep(1)
run("home"); time.sleep(1.5)
results.append(("cooldown holds a second /home", near(pos(), (290.5, 99, -228.5), 2)))
time.sleep(10)
run("home"); time.sleep(1.5)
results.append(("home works after the cooldown", near(pos(), start)))
for c in (f"tpa {P}", "tpa NobodyOnline", "tpahere NobodyOnline", "tpaccept", "tpdeny", "tpa"):
    r = run(c)
    results.append((f"{c} answered without error", r.get("ok", False)))
for name, ok in results:
    print(("ok   " if ok else "FAIL ") + name)
print("final position", [round(v, 1) for v in pos()], "start", [round(v, 1) for v in start])
