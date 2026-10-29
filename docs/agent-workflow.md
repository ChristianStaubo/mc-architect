# How this harness gets better (the workflow)

Adapted from fm26-manager's `docs/agent-workflow.md` (the full version, with the FM examples:
`~/coding/games/fm26-manager/docs/agent-workflow.md`). Goal: Claude builds great things in Minecraft
**by itself**, and earns autonomy one capability at a time.

## 1. The outcome, as a scoreboard
"Build cool stuff" isn't measurable; this is:
- **Objective:** the critic's `overall` score (1–10) on a fixed eval suite (`evals/tasks/`), calibrated
  against the user's own ratings.
- **Constraints that stop gaming it:** the audit passes (nothing floating, doors work, rooms reachable,
  lit, beds whole); the brief's musts are there; the build stays in its plot; calls within budget.

## 2. The loop: builder → judge → fixer
```
builder (Sonnet) ── builds via mc ──► audit (code) + critic (model, pictures only)
      ▲                                         │
      │                     all clear ──► keep, score it
      │                     fixable    ──► builder revises (inner loop)
      │                     tool gap   ──► mc stuck → friction
      └── fixer (main session) fixes the owning layer, adds a test, re-runs the evals ◄──┘
                            taste call ──► the user sets a rule (STYLE.md)
```
- **Builder:** works through one CLI, stops early and cleanly when the tools fall short.
- **Judge:** never the actor. The audit is deterministic (`architect/audit.py`, tested); the critic is
  a separate model that sees only the contact sheet and the brief (`evals/RUBRIC.md`).
- **Fixer:** reads friction and the scoreboard, fixes the layer that owns the problem (part, CLI,
  bridge, audit, rubric, style rule), leaves a test, re-runs the evals. Skill: `mc-improve`.

## 3. Measuring the loop itself
- Every `mc` call is journaled (`local/runs/commands.jsonl`) with its run id: calls per build,
  failed calls, dry runs, undos. Fewer calls for the same quality = better tools.
- **Builds per stop** (`mc friction stats`) is our "miles per disengagement": it should rise.
- Friction by cause separates missing parts (expected, shrinks) from bugs and confusing tools.

## 4. Rules come from failures
Write style rules and audit checks from builds that went wrong, not from imagination. When the user
corrects a build ("rule: ..."), find the principle, add it to `STYLE.md` with a date, and where it can
be checked, a check + test. Ratings the user gives go in `evals/ratings.jsonl`; when the critic and the
user disagree, the rubric changes.

## 5. Safety rails
- Builds happen on the local test server; every change goes through `place` and can be undone
  (snapshots survive restarts). The friends' server only gets builds the user approves.
- Preview (`--dry-run`) before placing; read every picture after.
- Builders can't edit repo code; only the fixer changes tools, with tests.
