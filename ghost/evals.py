"""The ghost's evals (docs/ghost/design.md, Evals). Each suite has its own grading rules:

  guarantees  the bridge's promises, by code: a repeated key changes nothing; a forged, expired,
              too-small or over-cap grant is refused (deterministic; must be 100%)
  listening   the candidate filter on labelled chat: did it reply when it should, stay quiet when it
              shouldn't (both rates; each message k times, a case passes only if all k agree: pass^k)
  scenarios   simulated players end to end, graded on what the store and the world say afterwards
  chaos       kill a process mid-task; grade: nothing lost, nothing done twice, time to recover

Run: .venv/bin/python -m ghost eval <suite> [--k N]
"""

import copy
import time

from . import bridge, tools

SPOT = (230, 250, -300)   # a sky block in the commons, far from everything


def _place(key=None, grant=None, block="minecraft:glass"):
    body = {"origin": list(SPOT), "size": [1, 1, 1], "palette": [None, block], "rle": [1, 1], "label": "eval",
            "history": False}
    if key:
        body["key"] = key
    if grant:
        body["grant"] = grant
    return bridge.call("/place", body)


def _refused(fn):
    try:
        fn()
        return False, "accepted"
    except bridge.BridgeError as e:
        return "HTTP 400" in str(e), str(e).split(": ", 1)[-1][:90]


def guarantees():
    run = f"eval{int(time.time())}"
    x, y, z = SPOT
    ok_grant = tools.grant(run, "world", SPOT, SPOT, 1)
    checks = []
    first = _place(f"{run}-a", tools.grant(run + "-a", "world", SPOT, SPOT, 5))
    again = _place(f"{run}-a", tools.grant(run + "-a", "world", SPOT, SPOT, 5))
    checks.append(("a repeated key changes nothing", again.get("repeat") is True and again["id"] == first["id"],
                   f"first {first.get('id')}, again {again}"))
    forged = copy.deepcopy(ok_grant)
    forged["max_blocks"] = 1000
    checks.append(("a grant with a changed cap is refused (signature)", *_refused(lambda: _place(grant=forged))))
    expired = tools.grant(run, "world", SPOT, SPOT, 1, seconds=-5)
    checks.append(("an expired grant is refused", *_refused(lambda: _place(grant=expired))))
    small = tools.grant(run + "-s", "world", (x + 1, y, z), (x + 2, y, z), 5)
    checks.append(("a build outside the granted box is refused", *_refused(lambda: _place(grant=small))))
    capped = tools.grant(run + "-c", "world", SPOT, SPOT, 1)
    _place(grant=capped)
    checks.append(("a grant's block cap is enforced across calls", *_refused(lambda: _place(grant=capped))))
    other = tools.grant(run, "world_nether", SPOT, SPOT, 1)
    checks.append(("a grant for another world is refused", *_refused(lambda: _place(grant=other))))
    _place(block="minecraft:air")
    return checks


LISTENING = [  # (message, near a ghost?, is it for the ghost?)
    ("ghost can you follow me", False, True),
    ("hey ghost what is this build", False, True),
    ("where did the ghost go", False, True),
    ("this ghost town is so empty lol", False, False),
    ("he totally ghosted me yesterday", False, False),
    ("did you see that ghost movie", False, False),
    ("come here", True, True),
    ("can you build me a little bench", True, True),
    ("brb dinner", True, False),
    ("anyone want to trade diamonds?", True, False),
    ("lol nice house sam", True, False),
    ("wait for me", True, True),
]


def listening(k=3):
    from .core import FILTER_SCHEMA, FILTER_SYSTEM
    from . import model
    from concurrent.futures import ThreadPoolExecutor

    def judge(case):
        text, near, _ = case
        prompt = f'The message: "{text}".' + (" They're standing next to the lakeside ghost." if near else "")
        return bool(model.ask("filter", FILTER_SYSTEM, prompt, FILTER_SCHEMA).get("for_ghost"))

    with ThreadPoolExecutor(6) as pool:
        answers = list(pool.map(judge, [c for c in LISTENING for _ in range(k)]))
    out = []
    for i, (text, near, want) in enumerate(LISTENING):
        got = answers[i * k:(i + 1) * k]
        out.append((f"{'near' if near else 'far '} {text!r} -> {'reply' if want else 'quiet'}",
                    all(g == want for g in got), f"answers {got}"))
    replied = [c for c, (_, _, w) in zip(out, LISTENING) if w]
    quiet = [c for c, (_, _, w) in zip(out, LISTENING) if not w]
    print(f"replied when it should: {sum(c[1] for c in replied)}/{len(replied)}; "
          f"quiet when it should: {sum(c[1] for c in quiet)}/{len(quiet)} (pass^{k})")
    return out


def report(name, checks):
    print(f"\n{name}:")
    for desc, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {desc}  ({detail})")
    n = sum(1 for _, ok, _ in checks if ok)
    print(f"{n}/{len(checks)} pass")
    return n == len(checks)


def _scenarios(a):
    from .evals_scenarios import scenarios
    return scenarios(a.only)


def _chaos(a):
    from .evals_scenarios import chaos
    return chaos()


SUITES = {"guarantees": lambda a: guarantees(), "listening": lambda a: listening(a.k), "scenarios": _scenarios,
          "chaos": _chaos}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="ghost eval")
    ap.add_argument("suite", choices=sorted(SUITES))
    ap.add_argument("--k", type=int, default=3, help="listening: runs per message (pass^k)")
    ap.add_argument("--only", nargs="*", help="scenarios: just these (follow, guest, injection, build_and_undo, ...)")
    a = ap.parse_args(argv)
    return 0 if report(a.suite, SUITES[a.suite](a)) else 1
