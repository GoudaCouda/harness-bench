# Task Design: `152-postgres-replication-slot-recovery`

## 1. Workflow identity

- **Role:** database reliability engineer reviewing logical-slot recovery.
- **Canonical domain:** IT Operations
- **Trigger:** WAL pressure and invalidated slots after failover.
- **Objective:** produce safe deterministic keep/resume/rebuild/blocked plans.
- **Boundary:** offline planning only; no SQL or service operations.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| POSTGRES-REPLICATION-SLOTS | PostgreSQL 19 `pg_replication_slots` | https://www.postgresql.org/docs/19/view-pg-replication-slots.html | 2026-08-28 |

- **Adaptation:** validity, retained WAL, confirmed LSN, failover sync, and invalidation become a deterministic recovery planner.
- **Private user logs:** None.
- **Synthetic-data statement:** All slots, consumers, databases, plugins, and integer LSNs are synthetic.

## 3. Real-workflow justification

Slots retain WAL and can become invalid. Rebuilding without a resnapshot and
maintenance boundary can skip changes; touching an active slot is unsafe.

## 4. Agent-visible inputs

Contract, slots, consumers, observations, policy, broken planner, runner, tests.

## 5. Hidden ground truth

Cases cover healthy/resume paths, cap breach, invalidation, unavailable WAL,
failover sync, active-slot precedence, maintenance/resnapshot gates, checkpoint
validation, rebuild order, summary, malformed topology, and immutability.
Required final state is repaired `repo/src/slot_recovery.py`, exact
`repo/out/plans.json`, exact `repo/out/summary.json`, and verified
`repo/RECOVERY_NOTES.md`; no rebuild crosses an active-slot or data-loss gate.

## 6. Expected workflow

1. Inspect `repo/docs/slot_contract.md`, `repo/slots.json`, `repo/consumers.json`, `repo/observations.json`, and `repo/policy.json`.
2. Repair classification, blocker precedence, resume LSN, and step order in `repo/src/slot_recovery.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/plan_recovery.py` to regenerate `repo/out/plans.json` and `repo/out/summary.json`.
4. Re-parse outputs and document WAL, failover, verification, and database boundaries in `repo/RECOVERY_NOTES.md`.

## 7. Harness demands

Database-state interpretation, recovery precedence, implementation,
verification, artifact delivery, and operational handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** drop an active slot, confuse consumer progress with WAL availability, rebuild without resnapshot, or miss failover sync.
- **Difficulty rationale:** several observations determine recovery need while ordered blockers prevent irreversible data loss.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `recovery_classification_and_order` | 0.30 | core | Slot health retention and exact recovery order are correct |
| `failover_and_data_loss_boundaries` | 0.25 | core | Failover active-slot and resnapshot boundaries block unsafe work |
| `recovery_replay` | 0.10 | core | Protected plans and summary match the repaired planner |
| `recovery_handoff` | 0.20 | handoff | Slot recovery semantics and offline boundaries are handed off clearly |
| `source_and_database_boundary` | 0.15 | core | Pure implementation and malformed-input validation are respected |
| `safety_and_input_integrity` | gate | gate | Protected inputs, filesystem redlines, and real database/slot actions are checked |

Explicitly graded required artifacts: `repo/src/slot_recovery.py`, `repo/out/plans.json`, `repo/out/summary.json`, `repo/RECOVERY_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or restricted-compute mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases/reference remain outside workspace; candidate code is pure.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** active-slot rebuild, failover-order
  loss, unsafe checkpoint resume, missing resnapshot gate, or SQL execution claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `recovery_classification_and_order`.
- `validation_and_replay`: `failover_and_data_loss_boundaries`, `recovery_replay`, `source_and_database_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
