"""Build the blind rating page (docs/evals.md §10) for a capability run.

    python3 scripts/rating_page.py RUN [--refs N] [--per-task N]

Picks the run's contact sheets plus a few reference builds, shuffles them under anonymous ids, writes
local/rate/<batch>/index.html with the sheets beside it, and the key (anonymous id -> run, task, trial)
to local/rate/<batch>/key.json, which never leaves this machine. The page stores ratings in its own
database; `python3 scripts/rating_page.py --pull BATCH ratings.json` joins a dump of it with the key
into evals/ratings.jsonl."""

import argparse
import html
import json
import random
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from architect import evals, judges, scoreboard, trials  # noqa: E402

OUT = ROOT / "local" / "rate"
TEMPLATE = Path(__file__).with_name("rating_page.html")


def build(run, refs, per_task):
    recs = [r for r in trials.trial_records(run) if r.get("sheet") and Path(r["sheet"]).exists()]
    recs = [r for rs in scoreboard.by_task(recs).values() for r in random.sample(rs, min(per_task, len(rs)))]
    items = [{"run": run, "task": r["task"], "trial": r["trial"], "sheet": r["sheet"]} for r in recs]
    ref_sheets = sorted(evals.REFERENCES.glob("*.png"))
    for p in random.sample(ref_sheets, min(refs, len(ref_sheets))):
        items.append({"run": "reference", "task": p.stem, "trial": 0, "sheet": str(p)})
    random.shuffle(items)
    batch = time.strftime("b%m%d-%H%M")
    d = OUT / batch
    (d / "sheets").mkdir(parents=True, exist_ok=True)
    key, cards = {}, []
    for n, it in enumerate(items, 1):
        aid = f"{batch}-{n:02d}"
        shutil.copy(it["sheet"], d / "sheets" / f"{aid}.png")
        key[aid] = {k: it[k] for k in ("run", "task", "trial")}
        brief = evals.task(it["task"])["brief"] if it["task"] in evals.tasks() else ""
        cards.append({"id": aid, "img": f"sheets/{aid}.png", "brief": brief})
    (d / "key.json").write_text(json.dumps(key, indent=1))
    write_page(d, batch, cards, LEDE_BLIND)
    print(f"{len(cards)} builds in {d}/index.html (key: {d}/key.json)")
    return d


def reveal(batch):
    """Rewrite a batch's page with what each build is and the judges' scores beside it. Not blind any
    more: the key is marked revealed, and ratings pulled from then on carry blind: false."""
    d = OUT / batch
    key = json.loads((d / "key.json").read_text())
    cards = []
    for aid, k in sorted(key.items()):
        if k["run"] == "reference":  # references have no trial record: judge their sheet now
            scores, _ = judges.judge(evals.task(k["task"]), evals.REFERENCES / f"{k['task']}.png", "opus")
            j, label = {"scores": scores, "quality": judges.quality(scores)}, "hand-made reference"
        else:
            j = json.loads((trials.trial_path(k["run"], k["task"], k["trial"]) / "trial.json").read_text())
            label = f"builder, trial {k['trial']}"
        scores = j.get("scores") or {}
        cards.append({"id": aid, "img": f"sheets/{aid}.png", "brief": evals.task(k["task"])["brief"],
                      "judge": {"task": k["task"], "label": label, "quality": j.get("quality"),
                                "scores": {dim: v["score"] for dim, v in scores.items()},
                                "why": scores.get("overall", {}).get("evidence", "")}})
        k["revealed"] = True
    (d / "key.json").write_text(json.dumps(key, indent=1))
    write_page(d, batch, cards, LEDE_REVEALED)
    print(f"{len(cards)} builds with judge scores in {d}/index.html")


LEDE_BLIND = ("Each sheet shows one build from four corners, from above, its floor plans and its four faces. "
              "Score it 1 to 10 for its brief: 5 is fine but unremarkable, 8 is a build you'd show a friend. A "
              "short note on why helps the judges learn. Builder and model are hidden on purpose.")
LEDE_REVEALED = ("Each sheet shows one build from four corners, from above, its floor plans and its four faces, "
                 "with what the AI judges scored it. Give your own 1 to 10 for its brief (5 is fine but "
                 "unremarkable, 8 is a build you'd show a friend), and say why where you disagree with the judges.")


def write_page(d, batch, cards, lede):
    page = (TEMPLATE.read_text().replace("__BATCH__", batch).replace("__LEDE__", lede)
            .replace("__CARDS__", html.escape(json.dumps(cards), quote=False)))
    (d / "index.html").write_text(page)


def pull(batch, dump):
    """dump: the page's `ratings` collection as JSON ({doc id: {score, note, at}} or a list of docs)."""
    key = json.loads((OUT / batch / "key.json").read_text())
    rows = json.loads(Path(dump).read_text())
    if isinstance(rows, list):
        rows = {r.get("id") or r.get("doc_id"): r.get("data", r) for r in rows}
    out = ROOT / "evals" / "ratings.jsonl"
    n = 0
    with open(out, "a") as f:
        for aid, r in rows.items():
            if aid in key and isinstance(r.get("score"), (int, float)):
                k = key[aid]
                f.write(json.dumps({"run": k["run"], "task": k["task"], "trial": k["trial"], "rating": r["score"],
                                    "note": r.get("note", ""), "blind": not k.get("revealed"), "batch": batch,
                                    "at": r.get("at")}) + "\n")
                n += 1
    print(f"{n} ratings appended to {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run", nargs="?")
    p.add_argument("--refs", type=int, default=3)
    p.add_argument("--per-task", type=int, default=1, help="trials per task to rate (10-15 builds is a sitting)")
    p.add_argument("--pull", nargs=2, metavar=("BATCH", "DUMP"))
    p.add_argument("--reveal", metavar="BATCH", help="show what each build is and the judges' scores")
    a = p.parse_args()
    if a.pull:
        pull(*a.pull)
    elif a.reveal:
        reveal(a.reveal)
    else:
        build(a.run, a.refs, a.per_task)
