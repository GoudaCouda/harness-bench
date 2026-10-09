# Task Design: `077-sqlite-migration-transaction-recovery`

## 1. Workflow identity

- **Role:** application engineer recovering an interrupted SQLite schema migration.
- **Trigger:** BUSY and connection-loss outcomes were retried without transaction-state reconciliation.
- **Objective:** produce a phase-correct, ledger-idempotent recovery plan.
- **Boundary:** no captured, non-fixture, or production database/deployment action;
  tests may apply the plan to a disposable local SQLite database under the test
  temporary directory.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| SQLITE-TRANSACTION | SQLite transaction documentation | https://sqlite.org/lang_transaction.html | 2026-08-27 |
| SQLITE-BUSY | SQLite result and error codes | https://sqlite.org/rescode.html#busy | 2026-08-27 |
| SQLITE-STEP | SQLite statement evaluation guidance | https://sqlite.org/c3ref/step.html | 2026-08-27 |

- **Adaptation:** documented transaction and BUSY behavior becomes a deterministic
  recovery state machine with a clean-apply plan replayed against disposable SQLite.
- **Private user logs:** None.
- **Synthetic-data statement:** Schemas, IDs, checksums, SQL strings, and failure observations are synthetic.

## 3. Real-workflow justification

Migration runners must distinguish contention before a transaction, during a
statement, and at COMMIT. Blind statement resumption breaks atomicity, while
blind replay after connection loss can duplicate an already committed change.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/migration_contract.md` | authoritative state-machine contract |
| `repo/src/migration_recovery.py` | broken planner |
| `repo/migration_cases.json` | visible incidents |
| `repo/tests/test_public.py` | public regressions |
| `repo/tests/test_sqlite_integration.py` | real disposable SQLite transaction replay |

## 5. Hidden ground truth

Hidden cohorts extend the agent-visible `repo/migration_cases.json` and
`repo/docs/migration_contract.md` with clean apply, BUSY at
begin/statement/commit, interrupted connections, unknown commits,
already-applied ledger rows, checksum and version divergence, duplicate ledger
IDs, transaction-control injection, malformed types and observations,
immutable evidence, and external-action restraint. Required final state includes
repaired `repo/src/migration_recovery.py`, exact `repo/recovery_plan.json`, and
verified `repo/REPAIR_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/migration_contract.md`, `repo/migration_cases.json`, and `repo/tests/test_public.py`.
2. Validate migration identity, statements, ledger, and observation in `repo/src/migration_recovery.py`.
3. Select rollback/full retry, commit-only retry, probe, apply, or no-op in `plan_migration_recovery`.
4. Generate exact `repo/recovery_plan.json` rows for each visible `case_id`.
5. Record verification and live executor risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

Repository inspection, code execution, transaction-state reasoning, exact
JSON, verification, and database-action restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** resume at a statement, rollback after COMMIT BUSY, rerun after unknown commit, or trust one of ledger/user_version alone.
- **Difficulty rationale:** safe recovery depends jointly on failure phase, active transaction state, durable identity, and atomic action ordering.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `busy_phase_and_transaction_scope` | 0.35 | core | BUSY recovery respects transaction phase and retry scope |
| `idempotency_unknown_commit_and_divergence` | 0.25 | core | Ledger identity and unknown commit outcomes fail closed |
| `visible_recovery_plan` | 0.05 | core | Visible migration incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Transaction recovery and executor risks are handed off |
| `evidence_and_database_action_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/migration_recovery.py`, `repo/recovery_plan.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and references are excluded. Candidate planner code is
pure-audited with ordinary computation-only imports available; SQLite,
filesystem, process, network, private-attribute, and dynamic execution remain
unavailable to that code. The visible suite applies a clean plan with a real
`BEGIN IMMEDIATE`/commit cycle against a disposable local SQLite fixture.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma + OpenClaw run with cohort-level review.

- **Expected Gemma/OpenClaw failure modes:** wrong transaction-active rule, missing rollback, unsafe commit replay, or ledger/version mismatch acceptance.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `busy_phase_and_transaction_scope`.
- `validation_and_replay`: `idempotency_unknown_commit_and_divergence`, `visible_recovery_plan`, `evidence_and_database_action_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
