# Task Design: `053-event-time-window-reconciliation`

## 1. Workflow identity

- **Role:** data engineer repairing a streaming backfill reconciler.
- **Trigger:** ingestion-time grouping and retries corrupt window state.
- **Objective:** restore event-time, watermark, lateness, and revision semantics.
- **Boundary:** no live replay, source-offset commit, or deployment is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| BEAM-MODEL-EVENT-TIME | Apache Beam programming guide, event time and watermarks | https://beam.apache.org/documentation/programming-guide/#event-time-and-watermarks | 2026-08-27 |
| FLINK-EVENT-TIME | Apache Flink event-time documentation | https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/ | 2026-08-27 |

- **Adaptation:** event-time windows, watermarks, allowed lateness, and trigger updates become an offline state reconciliation with explicit replay ownership and revisions.
- **Private user logs:** None; events, keys, timestamps, and checkpoints are synthetic.

## 3. Real-workflow justification

Streaming jobs routinely receive delayed events and replay source offsets after
recovery. A plausible local repair must preserve idempotency and finalized state,
not merely recompute a spreadsheet aggregate from one batch.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/window_contract.md` | authoritative state-transition contract |
| `repo/src/window_reconciler.py` | broken implementation |
| `repo/window_cases.json` | visible prior-state incidents |
| `repo/tests/test_public.py` | public event-time/finality regressions |

## 5. Hidden ground truth

Independent cohorts cover exact duplicate and conflicting replay IDs, event-time
ordering, one-revision-per-run updates, pending windows, exact finality, new late
drops, final-window replays, negative timestamps, malformed prior ownership, and
input immutability.
They run the agent-visible `repo/src/window_reconciler.py`. Required final state
includes that repaired source, exact `repo/window_report.json`, and a grounded
`repo/REPAIR_NOTES.md` handoff.

## 6. Expected workflow

1. Inspect `repo/docs/window_contract.md` and the prior-window state schema.
2. Run `repo/tests/test_public.py` against `repo/src/window_reconciler.py`.
3. Repair event-time reconciliation and validation in `repo/src/window_reconciler.py`.
4. Generate `repo/window_report.json` from `repo/window_cases.json` in case order.
5. Record verification and atomic checkpoint risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

The task requires repository inspection, local execution, stateful reasoning,
exact JSON production, verification, and live-system restraint.

## 8. Stressors and difficulty

- **Plausible failure mode:** use ingest time, increment once per event, classify
  equality incorrectly, drop a final replay, or mutate prior state.
- **Difficulty rationale:** accepted, pending, late, and replayed records depend
  jointly on prior ownership, event-time window, watermark, and finality.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `event_time_dedup_and_revision` | 0.35 | core | Event-time assignment, replay identity, and revisions remain stable |
| `watermark_lateness_and_finality` | 0.25 | core | Watermark, lateness, pending, and final boundaries are exact |
| `visible_window_report` | 0.05 | core | Visible streaming incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Reconciliation behavior and operational risk are handed off |
| `source_and_workspace_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/window_reconciler.py`, `repo/window_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and reference outputs are excluded. Candidate code is evaluated
in a bounded pure worker with only task-whitelisted `copy` and `collections`;
I/O, network, processes, private attributes, and dynamic calls remain
unavailable. Grading is read-only and network-disabled.

## 11. Pilot plan

Require deterministic reference/empty/untouched checks plus malformed-input behavior scored by affected blocks and Docker isolation, then run a
fresh Gemma + OpenClaw trial and inspect state-transition failures.

- **Expected Gemma/OpenClaw failure modes:** finality equality, prior replay handling, revision
  over-increment, negative-window arithmetic, report drift, or shallow notes.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and a real model pilot are required instead.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `event_time_dedup_and_revision`.
- `validation_and_replay`: `watermark_lateness_and_finality`, `visible_window_report`, `source_and_workspace_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
