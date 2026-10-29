"""When the tools fall short: gaps, stuck reports, friction, incidents (the flight recorder)."""

import json
import os
import subprocess
import sys

from .. import incidents, journal
from .common import ROOT


def cmd_incidents(a):
    rows = incidents.listing()
    if not a.all:
        rows = [r for r in rows if r["kind"] in ("crash", "bridge")] or rows[-10:]
    for r in rows[-30:]:
        print(f"{r['id']:<40} {r['kind']:<8} {r['run'] or '-':<24} {r['error'].splitlines()[0][:90]}")
    print(f"{len(incidents.listing())} incidents kept (newest {incidents.KEEP}); --all shows refusals and errors too")


def cmd_incident(a):
    d = incidents.get(a.id)
    info = json.loads((d / "incident.json").read_text())
    if a.action == "replay":
        argv = info["argv"]
        changes_world = argv[0] == "place" or argv[:1] == ["town"] and argv[1] in ("road", "terrace", "tidy")
        if not changes_world and argv[0] not in ("blueprint", "site", "audit", "shots", "render", "status", "edits", "town"):
            raise SystemExit(f"won't replay '{argv[0]}' (it changes the world); run it yourself")
        if changes_world and "--dry-run" not in argv:
            argv = argv + ["--dry-run"]
        env = dict(os.environ, MC_RUN_ID=info["run"] or "")
        print(f"replaying (dry): mc {' '.join(argv)}")
        return subprocess.run([sys.executable, str(ROOT / "mc.py"), *argv], env=env).returncode
    print(f"{info['id']}  [{info['kind']}]  run {info['run'] or '-'}  {info['t']}")
    print(f"command: mc {' '.join(info['argv'])}")
    print(f"error: {info['error']}")
    if info.get("stack"):
        print("stack (last lines):\n  " + "\n  ".join(info["stack"].strip().splitlines()[-6:]))
    print("\nlast bridge requests:")
    for l in [json.loads(x) for x in (d / "trace.jsonl").read_text().splitlines() if x.strip()][-8:]:
        print(f"  {l['t'][11:]} {l['path']:<11} {l['status']:>4} {l['ms']:>5}ms {json.dumps(l['req'])[:70]}"
              + (f"  ERROR {l['error'][:60]}" if l.get("error") else ""))
    print("\nlast mc commands:")
    for l in [json.loads(x) for x in (d / "journal.jsonl").read_text().splitlines() if x.strip()][-8:]:
        print(f"  {l['t'][11:]} {l['run'] or '-':<22} {l['cmd']:<8} {' '.join(l['argv'])[:50]:<50} {'ok' if l['ok'] else 'FAIL'}")
    log = (d / "server.log").read_text().splitlines() if (d / "server.log").exists() else []
    bad = [x for x in log if any(k in x for k in ("ERROR", "WARN", "Exception"))]
    print(f"\nserver log: {len(log)} lines kept, {len(bad)} warnings/errors" + ("".join("\n  " + x[:140] for x in bad[-4:])))
    print(f"\nfiles: {d}" + ("  (plan.py = the plan as it was)" if (d / "plan.py").exists() else ""))
    print(f"replay it (dry): mc incident {info['id']} replay")


def cmd_gap(a):
    fid = journal.stuck(a.text, kind="gap")
    print(f"gap {fid} noted. Carry on; the fixer turns gaps into tools.")


def cmd_stuck(a):
    fid = journal.stuck(a.text)
    print(f"friction {fid} saved. STOP now and report it: the fixer takes it from here.")


def cmd_friction(a):
    if a.action == "resolve":
        r = journal.resolve(a.id, a.fix, a.cause, a.repeat_of)
        print(f"resolved {r['id']} ({r['cause']}): {r['fix']}")
    elif a.action == "stats":
        rs = journal.reports(include_resolved=True)
        by = {}
        for r in rs:
            k = r.get("cause", "open")
            by[k] = by.get(k, 0) + 1
        builds = sum(1 for e in journal.entries() if e["cmd"] == "place" and "--dry-run" not in e["argv"] and e["ok"])
        print(f"{len(rs)} friction reports ({sum(r['status'] == 'open' for r in rs)} open), "
              f"{builds} builds placed: {builds / max(1, len(rs)):.1f} builds per friction report")
        print("by cause: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: -kv[1])))
        print(f"repeats (a fix that didn't hold): {sum(1 for r in rs if r.get('repeat_of'))}")
        kinds = {}
        for r in rs:
            k = r.get("kind", "stuck")
            kinds[k] = kinds.get(k, 0) + 1
        print("by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
        crashes = [i for i in incidents.listing() if i["kind"] in ("crash", "bridge")]
        print(f"incidents: {len(incidents.listing())} kept, {len(crashes)} crashes/bridge failures")
    else:
        for r in journal.reports(include_resolved=a.all):
            print(f"{r['id']}  [{r['status']}] {r.get('kind', 'stuck'):<8} run {r['run'] or '-'}: {r['report'][:140]}")


def register(sub):
    g = sub.add_parser("gap")
    g.add_argument("text")
    g.set_defaults(fn=cmd_gap)
    sub.add_parser("incidents")
    sub.choices["incidents"].add_argument("--all", action="store_true")
    sub.choices["incidents"].set_defaults(fn=cmd_incidents)
    ic = sub.add_parser("incident")
    ic.add_argument("id")
    ic.add_argument("action", nargs="?", choices=["show", "replay"], default="show")
    ic.set_defaults(fn=cmd_incident)
    st = sub.add_parser("stuck")
    st.add_argument("text")
    st.set_defaults(fn=cmd_stuck)
    f = sub.add_parser("friction")
    f.add_argument("action", nargs="?", choices=["list", "resolve", "stats"], default="list")
    f.add_argument("id", nargs="?")
    f.add_argument("fix", nargs="?")
    f.add_argument("--cause")
    f.add_argument("--repeat-of")
    f.add_argument("--all", action="store_true")
    f.set_defaults(fn=cmd_friction)
