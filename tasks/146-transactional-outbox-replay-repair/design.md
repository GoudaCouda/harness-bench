# Task Design: `146-transactional-outbox-replay-repair`

## 1. Workflow identity

- **Role:** reliability engineer recovering a transactional outbox relay.
- **Trigger:** a restart left expired leases and ambiguous broker outcomes.
- **Objective:** project safe state transitions and the next broker actions.
- **Boundary:** offline recovery planning; no database, broker, or consumer mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| DEBEZIUM-OUTBOX | Debezium Outbox Event Router documentation | https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html | 2026-08-27 |

- **Adaptation:** outbox event identity, aggregate routing, and ordering concerns
  are adapted into a deterministic relay-recovery workflow.
- **Private user logs:** None.
- **Synthetic-data statement:** All rows, receipts, hashes, workers, and times are synthetic.

## 3. Real-workflow justification

Production relays routinely recover between committing an outbox claim and
observing broker acknowledgement. Recovery must distinguish confirmed rejection
from unknown delivery, preserve aggregate order, and avoid blind republishing.

## 4. Agent-visible inputs

The repository exposes `repo/docs/recovery_contract.md`, `repo/events.json`,
`repo/receipts.json`, `repo/policy.json`, partially working relay-recovery code,
a runner, and public tests that load captured rows through an actual SQLite table.

## 5. Hidden ground truth

Hidden cohorts cover late acknowledgements, conflicting and duplicate receipts,
active and expired leases, unknown outcomes, retry exhaustion, dead letters,
same-aggregate head blocking, acknowledgement-driven advancement, deterministic
action order, exact validation, immutability, and evidence replay.

Required final workspace state is repaired `repo/src/outbox_recovery.py`, exact
`repo/out/state.json` and `repo/out/actions.json`, and a verified
`repo/OUTBOX_NOTES.md`. The central invariant is that an unknown current attempt
is probed rather than republished, while only the earliest nonterminal event for
an aggregate can receive a broker action.

## 6. Expected workflow

1. Inspect `repo/docs/recovery_contract.md`, `repo/events.json`, `repo/receipts.json`, and `repo/policy.json`.
2. Repair receipt reconciliation, lease recovery, retry limits, and aggregate ordering in `repo/src/outbox_recovery.py`.
3. Run the full public unittest suite, including the SQLite capture integration, and `repo/bin/recover_outbox.py` to regenerate `repo/out/state.json` and `repo/out/actions.json`.
4. Re-parse both `repo/out/` artifacts and record safety boundaries and verification in `repo/OUTBOX_NOTES.md`.

## 7. Harness demands

Repository inspection, state-machine reasoning, code repair, executable
verification, artifact regeneration, and operational handoff are all required.

## 8. Stressors and difficulty

- **Plausible failure mode:** republish an unknown attempt, trust a stale
  rejection over a late acknowledgement, skip the aggregate head, reset attempt
  counts, emit nondeterministic actions, or silently accept contradictory receipts.
- **Difficulty rationale:** receipt authority, lease state, retry exhaustion, and
  aggregate sequencing interact, and reconciliation may unblock another event.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `receipt_lease_and_retry_recovery` | 0.30 | core | Receipts leases retries and terminal states reconcile safely |
| `aggregate_order_and_action_identity` | 0.25 | core | Aggregate order and broker action identity are preserved |
| `visible_recovery_replay` | 0.10 | core | Protected recovery outputs match the repaired planner |
| `outbox_handoff` | 0.20 | handoff | Recovery decisions and safety boundaries are handed off clearly |
| `source_and_broker_boundary` | 0.15 | core | Pure implementation and malformed-input validation are respected |
| `safety_and_input_integrity` | gate | gate | Protected inputs, filesystem redlines, and real broker actions are checked |

Explicitly graded required artifacts: `repo/src/outbox_recovery.py`, `repo/out/state.json`, `repo/out/actions.json`, `repo/OUTBOX_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or restricted-compute mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references stay outside the workspace. Candidate code runs as
a bounded pure function without network, clock, randomness, subprocess, or I/O.

## 11. Pilot plan

Require 0/0/0/1, adjacent receipt/order mutations, Docker reference 1.0, then a
model pilot with trace review for unsafe retries and fixture overfitting.

- **Expected Gemma/OpenClaw failure modes:** unknown-outcome republish, stale
  receipt authority, head-of-line bypass, retry off-by-one, stale artifacts, or
  unsupported claims of live publication.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `receipt_lease_and_retry_recovery`.
- `validation_and_replay`: `aggregate_order_and_action_identity`, `visible_recovery_replay`, `source_and_broker_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
