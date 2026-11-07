"""Kits: mc kit sample KIT — a kit's variants built offline, checked and drawn on one sheet."""

from pathlib import Path

from .. import kits
from .common import ints, out_path


def cmd_kit(a):
    path = Path(a.kit)
    if not path.exists():
        path = Path("kits") / f"{a.kit.removesuffix('.py')}.py"
    sizes = [tuple(ints(s.replace("x", ","))) for s in a.sizes.split()] if a.sizes else None
    rows, sheet = kits.sample(path, a.n, sizes, a.kinds.split(",") if a.kinds else None,
                              out_path(f"kit-{path.stem}"), a.town)
    bad = sum(bool(r["problems"]) for r in rows)
    for r in rows:
        ok = "ok  " if not r["problems"] else "FAIL"
        print(f"{ok} {r['kind']:<14} {r['w']}x{r['d']} door {r['door']:<5} seed {r['seed']:<3} "
              f"{r.get('blocks', 0):>5} blocks {r.get('ms', 0):>4} ms")
        for p in r["problems"]:
            print(f"       {p}")
    print(f"{len(rows) - bad}/{len(rows)} clean. sheet (in order, {2 if rows and rows[0]['kind'] == 'bridge' else 4} a row): {sheet}")
    return 2 if bad else 0


def register(sub):
    k = sub.add_parser("kit", help="sample a kit (kits/README.md): variants built offline, checked, drawn on one sheet")
    k.add_argument("action", choices=["sample"])
    k.add_argument("kit", help="kits/NAME.py or NAME")
    k.add_argument("--n", type=int, default=8)
    k.add_argument("--sizes", help='e.g. "9x9 12x14"')
    k.add_argument("--town", help="sample exactly the plots of this town the kit builds (their sizes, doors, kinds, seeds)")
    k.add_argument("--kinds", help="comma-separated (default: the kit's KINDS)")
    k.set_defaults(fn=cmd_kit)
