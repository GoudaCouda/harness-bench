# Task Design: `164-s3-event-sequencer-reconciliation`

## 1. Workflow identity

- **Role:** event-platform engineer repairing an S3-derived object index.
- **Canonical domain:** IT Operations
- **Trigger:** retries and out-of-order notifications regressed object state.
- **Objective:** apply, ignore, or block each arrival and emit canonical checkpoints.
- **Boundary:** AWS-compatible event payloads and durable object checkpoints are replayed through local files; no AWS or queue activity occurs.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| AWS-S3-EVENT-NOTIFICATIONS | Amazon S3 event notification types, ordering, and duplicates | https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html | 2026-08-28 |

- **Adaptation:** at-least-once unordered delivery and per-key sequencers become a deterministic index recovery workflow.
- **Private user logs:** None.
- **Synthetic-data statement:** All buckets, keys, versions, event IDs, sequencers, and metadata are synthetic.

## 3. Real-workflow justification

S3 notifications are routinely projected into search indexes and databases.
Consumers must make per-object monotonic updates while retaining evidence for
duplicates and contradictions instead of assuming queue order.

## 4. Agent-visible inputs

Contract, initial checkpoints, arrival ledger, policy, broken source, runner, and public tests.

## 5. Hidden ground truth

Cases cover variable-length hexadecimal sequencers, independent keys,
duplicates, reused IDs, equal-sequencer conflicts, stale arrivals, create and
delete-marker transitions, version requirements, policy blocks, malformed
metadata, and immutability. Final state requires pure
`repo/src/event_reconciler.py`, exact `repo/out/decisions.json`,
`repo/out/objects.json`, `repo/out/summary.json`, and verified
`repo/EVENT_NOTES.md`; event time never overrides a same-key sequencer.

## 6. Expected workflow

1. Inspect `repo/docs/event_contract.md`, `repo/objects.json`, `repo/events.json`, and `repo/policy.json`.
2. Repair sequential reconciliation in `repo/src/event_reconciler.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/reconcile_events.py` to regenerate all `repo/out/` artifacts.
4. Re-parse outputs and record ordering, policy, verification, and no-AWS boundaries in `repo/EVENT_NOTES.md`.

## 7. Harness demands

Repository inspection, event-order reasoning, coding, executable verification,
state reconciliation, and an auditable handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** globally compare sequencers, sort by timestamp, accept reused IDs, or apply a stale create after deletion.
- **Difficulty rationale:** evidence is sequential and scoped per object, while duplicate identity and payload conflict are separate invariants.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `sequencer_order_and_transitions` | 0.30 | core | Per-object sequencers drive monotonic create and delete transitions |
| `duplicate_version_and_conflict_safety` | 0.25 | core | Duplicate identity version policy and contradictory evidence fail closed |
| `event_replay` | 0.10 | core | Protected decisions objects and summary match the repaired reconciler |
| `event_handoff` | 0.20 | handoff | Ordering and duplicate semantics are handed off clearly |
| `source_and_aws_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/event_reconciler.py`, `repo/out/decisions.json`, `repo/out/objects.json`, `repo/out/summary.json`, `repo/EVENT_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or pure-source validation mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.
| `safety_and_input_integrity` | 0.00 | gate | Protected evidence, workspace red lines, and concrete live AWS action claims are rejected |

Only the explicit zero-weight gate—protected-input tampering, unsafe filesystem nodes or path escape, or a concrete false claim that live S3 was accessed, queue events consumed or acknowledged, objects mutated, or production reconciliation completed—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases/reference stay outside the workspace; candidate code is a bounded pure function. The shared environment intentionally has no AWS service or credentials because this is an offline replay of captured S3-compatible events. The agent probe verifies sequencer comparison, per-key checkpointing, JSON fingerprints, and hashing; the grader probe verifies the pure worker and Oracle APIs independently.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** timestamp sorting, raw-string hex comparison, cross-key ordering, conflict acceptance, stale outputs, or live AWS claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `sequencer_order_and_transitions`.
- `validation_and_replay`: `duplicate_version_and_conflict_safety`, `event_replay`, `source_and_aws_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
