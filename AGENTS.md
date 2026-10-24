# AGENTS.md: how to work in this repo

## Loop rule
- Read `memory.md` FIRST every task. Update it LAST (summarize, prune stale lines). Keep it short.

## Context discipline
- Edit only the files the task needs; `memory.md` has the file map.
- `python -m slabwatch --help` must always work: heavy imports (torch, tabpfn, psycopg, temporalio, playwright) go
  inside functions.
- Workflow code in `slabwatch/workflows.py` must stay deterministic: no I/O, no `datetime.now()`, no randomness.
  Put I/O in activities.

## Run discipline
- Secrets only in `.env` (git-ignored). Add every new key to `.env.example` and to `doctor`.
- A missing key must raise `config.MissingKey` (clear message), never a traceback.
- Render must not install torch or local `tabpfn` (`requirements.txt` is the Render list).

## Honesty rules (contest entry)
- Never write a number into README/docs/post unless `scripts/` or `slabwatch/evaluate.py` produced it under `results/`.
- Don't claim a feature works until it ran end to end. Label unfinished things "TO VERIFY" or "soon".
- Gemma must refuse rather than guess. Don't loosen `MIN_CONFIDENCE` or validation to make a demo look better.
- The decision layer is plain code. Messages are calm and say what they assumed.

## Commits
- Conventional Commits: `feat|fix|docs|chore|test(scope): summary`. Never put secrets or reference numbers in messages.

## Stop conditions
- Ask before new heavy dependencies, paid credits beyond free tiers, or loosening the leakage test.
