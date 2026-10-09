# Task Design: `242-cron-next-fire-repair`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** build engineer repairing a mill cron helper
- **Trigger:** a Monday-or-the-1st job skipped a valid day
- **Objective:** repair next-fire on a 30-day clock with Vixie DOM/DOW OR
- **Irreversible boundary:** no mill dispatch or production crontab install is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| CELERY-TASK-STATES | Celery task states | https://docs.celeryq.dev/en/stable/userguide/tasks.html#states | 2026-09-11 | Grounds scheduled work that must compute the next run |
| TEMPORAL-WORKFLOWS | Temporal workflow documentation | https://docs.temporal.io/workflows | 2026-09-11 | Motivates an explicit next-fire rather than wall-clock waiting |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A 30-day mill clock makes cron next-fire executable without datetime or DST.

## 3. Real-workflow justification

Vixie cron ORs DOM and DOW when both are restricted. Implementations that AND them skip valid days.

## 4. Agent-visible inputs

`repo/docs/cron_contract.md` is the highest authority. `repo/job.json` is the protected mill job. Public tests live in `repo/tests/test_public.py`.

## 5. Hidden ground truth

Hidden cases cover star fields, midnight, Monday 06:00, and DOM/DOW OR. The evaluator audits and executes `next_fire` in a restricted worker.

The required final workspace state is `repo/src/cron.py`.
The durable record keeps a stable key for each decision in `repo/src/cron.py`.

## 6. Expected workflow

1. Read the contract and job.json.
2. Run the public unittest.
3. Implement next_fire and re-run tests.
4. Write next_fire.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `011-calendar-scheduling-conflict` | time reasoning | 011 finds a meeting slot; 242 computes cron next-fire on a synthetic clock |
| `239-dag-priority-scheduler-repair` | repository code repair | 239 orders a DAG; 242 walks a cron field machine |

1. Read the protected inputs and record their state before editing `repo/src/cron.py`.
2. Apply the published rule to the key fields that determine `repo/src/cron.py`.
3. Write `repo/src/cron.py` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires repairing code, running tests, emitting a snapshot, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** exclusive after, 30-day months, DOM/DOW OR
- **Difficulty:** hard; AND-ing DOM and DOW passes the public Monday test but fails hidden OR cases
- **Plausible failure mode:** include the after minute, or treat 31-day Gregorian months

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`function_behavior` (0.50 core) runs hidden cases. `visible_snapshot` (0.30 core) checks next_fire.json. `verification_handoff` (0.20 optional) checks notes.

### Adjacent examples

- **Nearest valid:** after Jan 1 00:00, `0 6 * * 1` fires day 2 06:00.
- **Nearest wrong 1:** AND semantics skip the 15th that is not a Monday.
- **Nearest wrong 2:** returning the after stamp itself.

`repo/src/cron.py` is a required final artifact checked by the hidden evaluator.
`repo/next_fire.json` is a required final artifact checked by the hidden evaluator.
`repo/IMPLEMENTATION_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

Hidden OR cases are not in the public tests. Candidate source is AST-audited.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect AND semantics for DOM/DOW.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
