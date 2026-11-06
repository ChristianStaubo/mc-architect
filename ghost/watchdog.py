"""The watchdog: outside the main loop, it checks liveness (heartbeats) and progress (tasks that stopped
moving, designs going round in circles) and steps in (docs/ghost/flows.md, flows 3 and 6).

`supervise()` (python -m ghost run) also starts ghost-core and a ghost-worker and restarts either one
when it dies or its heartbeat goes stale: the crash-recovery path chaos tests exercise."""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time

from . import config, db, outbox, tasks

STALE_S = 30
STUCK = {"designing": 25 * 60, "building": 15 * 60, "new": 5 * 60}   # seconds without progress
REPEATS = 6   # the same tool call this many times in a row: going round in circles
LOOP_CALLS = 40   # a task making more audited calls than this in 5 minutes is looping


def check(log=print):
    """One pass. Returns a list of findings (also logged)."""
    found = []
    db.run("DELETE FROM heartbeats WHERE process LIKE 'ghost-worker-%%' AND now() - at > interval '10 minutes'")
    for b in db.all("SELECT process, extract(epoch FROM now() - at)::int AS age FROM heartbeats"):
        if b["age"] > STALE_S and b["age"] < 3600:
            found.append(f"{b['process']}: no heartbeat for {b['age']} s")
    for t in db.all("SELECT id, state, player, ghost, extract(epoch FROM now() - updated_at)::int AS age FROM tasks "
                    "WHERE state = ANY(%s)", list(STUCK)):
        if t["age"] > STUCK[t["state"]]:
            found.append(f"task {t['id']} {t['state']} for {t['age'] // 60} min")
            stuck(t, f"stopped moving while {t['state']}")
        elif t["state"] == "designing" and circling(t["id"]):
            found.append(f"task {t['id']}: the design keeps repeating the same step")
            stuck(t, "kept repeating the same step")
    for t in db.all("SELECT a.task_id AS id, count(*) AS n, t.state, t.player, t.ghost FROM audit a JOIN tasks t ON t.id = a.task_id "
                    "WHERE a.at > now() - interval '5 minutes' AND t.state = ANY(%s) "
                    "GROUP BY a.task_id, t.state, t.player, t.ghost HAVING count(*) > %s", list(tasks.OPEN), LOOP_CALLS):
        found.append(f"task {t['id']}: {t['n']} tool calls in 5 minutes (looping)")
        stuck(t, "was looping")
    for f in found:
        log(f"watchdog: {f}")
    db.heartbeat("watchdog", findings=found)
    return found


def circling(task_id):
    """The newest design transcript's last tool calls all the same? (Reads only its tail.)"""
    files = sorted((config.ROOT / "local" / "ghost-tasks" / str(task_id)).glob("design-*.jsonl"),
                   key=lambda f: int(f.stem.split("-")[1]))
    if not files:
        return False
    with open(files[-1], "rb") as f:
        f.seek(max(0, f.seek(0, 2) - 64_000))
        tail = f.read().decode(errors="replace").splitlines()[1:]
    calls = []
    for line in tail:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            calls += [json.dumps([c["name"], c["input"]], sort_keys=True)
                      for c in ev["message"]["content"] if c.get("type") == "tool_use"]
    last = calls[-REPEATS:]
    return len(last) == REPEATS and len(set(last)) == 1


def stuck(t, why):
    """Stop the workflow, close the task, tell the player (the graded response's last step; budgets are the
    hard backstop)."""
    from temporalio.client import Client

    async def cancel():
        c = await Client.connect(config.TEMPORAL)
        try:
            await c.get_workflow_handle(f"build-{t['id']}").terminate(reason=f"watchdog: {why}")
        except Exception:  # noqa: BLE001 (already gone)
            pass
    asyncio.run(cancel())
    if tasks.move(t["id"], "failed", watchdog=why):  # (not if it finished meanwhile)
        outbox.say(t["ghost"], t["player"], "I got stuck on that one, sorry. Want to try asking a simpler way?")


def main():
    print("watchdog watching", flush=True)
    while True:
        try:
            check()
        except Exception as e:  # noqa: BLE001
            print(f"watchdog: {e}", flush=True)
        time.sleep(10)


PROCS = {"ghost-core": ["core"], "ghost-worker": ["worker"]}


def supervise():
    """Run core and a worker; restart one that exits or stops beating. Ctrl-C stops everything."""
    db.migrate()
    logs = config.ROOT / "local" / "tmp"
    logs.mkdir(parents=True, exist_ok=True)
    kids = {}

    def start(name):
        out = open(logs / f"{name}.log", "a")
        kids[name] = (subprocess.Popen([sys.executable, "-m", "ghost", *PROCS[name]], cwd=config.ROOT,
                                       stdout=out, stderr=subprocess.STDOUT,
                                       env={**os.environ, "GHOST_SUPERVISED": "1"}), time.time())
        print(f"started {name} (pid {kids[name][0].pid})", flush=True)

    def stop(*_):  # SIGTERM too, so the children never outlive the supervisor
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    for n in PROCS:
        start(n)
    try:
        while True:
            try:
                supervise_once(kids, start)
            except Exception as e:  # noqa: BLE001 (the database or Docker away: keep the children, retry)
                print(f"supervisor: {e}; retrying", flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        for p, _ in kids.values():
            p.send_signal(signal.SIGTERM)
        for p, _ in kids.values():
            p.wait(10)


def supervise_once(kids, start):
    """Restart a child that exited or stopped beating; then run the watchdog's checks."""
    for name, (p, since) in list(kids.items()):
        beat = db.one("SELECT extract(epoch FROM now() - at)::int AS age FROM heartbeats WHERE process = %s",
                      f"{name}-{p.pid}" if name == "ghost-worker" else name)
        stale = beat and beat["age"] > STALE_S and time.time() - since > STALE_S
        if p.poll() is not None or stale:
            print(f"{name} {'exited ' + str(p.returncode) if p.poll() is not None else 'stopped beating'}; restarting",
                  flush=True)
            if p.poll() is None:
                p.kill()
            db.run("DELETE FROM heartbeats WHERE process = %s", f"{name}-{p.pid}")  # it's gone, not late
            start(name)
    check()


def health():
    """0 healthy, 1 a process is late (restart it), 2 the store or a core process is gone, 3 stopped on purpose."""
    if (config.LOCAL / "STOPPED").exists():
        return 3
    try:
        beats = {b["process"]: b["age"] for b in db.all("SELECT process, extract(epoch FROM now() - at)::int AS age "
                                                        "FROM heartbeats WHERE now() - at < interval '10 minutes'")}
    except Exception:  # noqa: BLE001
        return 2
    core_ok = beats.get("ghost-core", 999) < STALE_S
    worker_ok = any(a < STALE_S for p, a in beats.items() if p.startswith("ghost-worker-"))
    return 0 if core_ok and worker_ok else 1 if beats else 2


def status():
    code = health()
    print(f"health: {['ok', 'a process is late', 'down', 'stopped on purpose'][code]} ({code})")
    print("heartbeats:")
    for b in db.all("SELECT process, extract(epoch FROM now() - at)::int AS age, detail FROM heartbeats ORDER BY process"):
        print(f"  {b['process']:<22} {b['age']:>6} s ago")
    print("open tasks:")
    for t in db.all("SELECT id, player, ghost, state, request FROM tasks WHERE state = ANY(%s) ORDER BY id",
                    list(tasks.OPEN)):
        print(f"  #{t['id']} {t['player']} ({t['ghost']}) {t['state']}: {t['request'][:60]}")
    print("today:")
    for r in db.all("SELECT house, kind, sum(amount) AS n FROM budget WHERE day = current_date AND state <> 'released' "
                    "GROUP BY house, kind ORDER BY 1, 2"):
        print(f"  {r['house']}: {r['n']} {r['kind']}")
    print("recent decisions:")
    for a in db.all("SELECT at, requester, action, resource, decision, rules, result FROM audit ORDER BY id DESC LIMIT 8"):
        print(f"  {a['at']:%H:%M:%S} {a['requester']:<16} {a['action']:<12} {a['resource']:<16} {a['decision']:<5} "
              f"{','.join(a['rules'])} {a['result'] or ''}")
    unsent = db.one("SELECT count(*) AS n FROM outbox WHERE sent_at IS NULL AND tries >= 5")["n"]
    if unsent:
        print(f"{unsent} messages could not be delivered (5 tries)")
    return code
