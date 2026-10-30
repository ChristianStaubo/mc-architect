"""Model judges (docs/notes/evals-design.md §8): quality scores for a trial's contact sheet, never pass/fail.

Three small judges per trial, each with a few rubric dimensions, instead of one holistic critic: each
sees only the brief, its dimensions' rubric rows and the picture, and may answer "unknown" when the
picture can't show it. Some trials are judged twice so the run can report how much the judges disagree
with themselves."""

import json
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import claude

ROOT = Path(__file__).resolve().parent.parent
RUBRIC = ROOT / "evals" / "RUBRIC.md"
GROUPS = [("brief", "site", "interior"), ("shape", "depth", "proportion"), ("palette", "detail", "overall")]
OVERALL = ("How good is this build for its brief, honestly (not the average of the others)? A single serious "
           "problem (no interior in a tavern, floating) caps it.")
NO_TOOLS = ["Bash", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "Agent", "NotebookEdit"]


def rows():
    """{dimension: (what earns a high score, what costs points)} from the rubric's table."""
    out = {}
    for line in RUBRIC.read_text().splitlines():
        m = re.match(r"^\| (\w+) \| (.+?) \| (.+?) \|$", line)
        if m and m.group(1) != "Criterion":
            out[m.group(1)] = (m.group(2), m.group(3))
    return out


def prompt(task, dims, image):
    r = rows()
    lines = [
        "You are judging a Minecraft build from its contact sheet: corner views from the SE, SW, NW and NE, "
        "a top-down view, floor plans per storey, then the facades straight on.",
        f"Its brief: {task['brief']}",
        f"Its style: {task.get('style', '-')}",
        "",
        "Score only these dimensions, each 1-10: 5 is fine but unremarkable, 8 a good player build you'd show "
        "a friend, 10 the best builds on community sites. Use the whole scale; most builds are 4-7.",
    ]
    for d in dims:
        if d == "overall":
            lines.append(f"- overall: {OVERALL}")
        else:
            hi, lo = r[d]
            lines.append(f"- {d}: high = {hi} Low = {lo}")
    lines += [
        "",
        f"Read the image {image} (your only input; read nothing else). If the pictures can't show a dimension, "
        "answer \"unknown\" for it rather than guessing.",
        "Reply with only a JSON object, no prose around it: "
        + json.dumps({d: {"score": "1-10 or \"unknown\"", "evidence": "what in the picture decides it"} for d in dims}),
    ]
    return "\n".join(lines)


def _parse(text, dims):
    m = re.search(r"\{.*\}", text or "", re.S)
    data = json.loads(m.group(0)) if m else {}
    out = {}
    for d in dims:
        v = data.get(d, {})
        s = v.get("score") if isinstance(v, dict) else v
        out[d] = {"score": s if isinstance(s, (int, float)) and 1 <= s <= 10 else "unknown",
                  "evidence": v.get("evidence", "") if isinstance(v, dict) else ""}
    return out


def judge_group(task, dims, sheet, model):
    """One judge, in an empty directory with a copy of the sheet (no repo context, no other files)."""
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "sheet.png"
        shutil.copy(sheet, img)
        cmd = claude.command(prompt(task, dims, img), model, ["Read"], 1.0, deny=NO_TOOLS, stream=False)
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=600)
    try:
        res = json.loads(p.stdout)
    except ValueError:
        return {d: {"score": "unknown", "evidence": f"judge failed: {p.stderr[-200:]}"} for d in dims}, 0.0
    return _parse(res.get("result"), dims), res.get("total_cost_usd") or 0.0


def judge(task, sheet, model):
    """All dimensions the task asks for: {dimension: {score, evidence}}, and the judges' cost."""
    wanted = next((g["dimensions"] for g in task.get("graders", []) if g.get("judge") == "rubric"), [])
    groups = [dims for dims in ([d for d in g if d in wanted or d == "overall"] for g in GROUPS) if dims]
    with ThreadPoolExecutor(len(groups)) as ex:  # the three judges are independent
        results = list(ex.map(lambda dims: judge_group(task, dims, sheet, model), groups))
    scores = {d: v for s, _ in results for d, v in s.items()}
    return scores, sum(c for _, c in results)


def quality(scores):
    """Mean of the known dimension scores (overall kept apart, as in v1)."""
    known = [v["score"] for d, v in scores.items() if d != "overall" and v["score"] != "unknown"]
    return round(sum(known) / len(known), 2) if known else None
