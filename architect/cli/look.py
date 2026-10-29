"""Looking and judging: audit, contact sheets, renders of any region."""



from .. import bridge, journal, render
from .. import audit as auditing
from .common import out_path, ints, latest_edit, run_audit, shots


def cmd_audit(a):
    e = latest_edit(a.id)
    r = run_audit(e)
    st = r["stats"]
    print(auditing.report(r, f"audit {e['id']} ({e['label']}): ",
                          f"; {st['blocks']} blocks, {st['doors']} doors, {st['indoor_floor']} indoor floor spots"))
    if r["fails"] and a.friction:
        fid = journal.stuck(f"audit {e['id']} failed: " + "; ".join(c["msg"] for c in r["checks"] if c["level"] == "fail"))
        print(f"friction filed: {fid}")
    return 2 if r["fails"] else 0


def cmd_shots(a):
    e = latest_edit(a.id)
    path, levels = shots(e)
    print(f"{path}\nlayout, left to right, top to bottom: views from the SE, SW, NW and NE corners; "
          f"top-down (north up); floor plans (north up) at y {', '.join(map(str, levels))}; then the facades "
          f"straight on, close up: south, east, north, west")


def cmd_render(a):
    lo, hi = ints(a.lo), ints(a.hi)
    lo, hi = [min(p) for p in zip(lo, hi)], [max(p) for p in zip(lo, hi)]
    cells = bridge.region(lo, hi)
    if a.surface:  # only the top few blocks of the land: what you'd see walking around, no cross-section
        cols = bridge.heightmap((lo[0], lo[2]), (hi[0], hi[2]))
        cells = {p: b for p, b in cells.items() if p[1] >= cols[(p[0], p[2])][0] - a.surface}
    path = out_path(f"region-{a.view}")
    w, h, _ = render.iso(cells, path, tile=a.tile, view=a.view)
    print(f"{path} ({w}x{h})")


def register(sub):
    x = sub.add_parser("shots")
    x.add_argument("id", nargs="?")
    x.set_defaults(fn=cmd_shots)
    x = sub.add_parser("audit")
    x.add_argument("id", nargs="?")
    x.add_argument("--friction", action="store_true")
    x.set_defaults(fn=cmd_audit)
    r = sub.add_parser("render")
    r.add_argument("lo")
    r.add_argument("hi")
    r.add_argument("--tile", type=int, default=8)
    r.add_argument("--view", default="se", choices=list(render.ROTATIONS))
    r.add_argument("--surface", type=int, nargs="?", const=3, default=0,
                   help="keep only the top N blocks of the land (default 3): no underground cross-section")
    r.set_defaults(fn=cmd_render)
