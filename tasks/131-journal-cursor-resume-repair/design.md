# Task Design: 131-journal-cursor-resume-repair

## 1. Workflow identity

This IT Operations task models recovery of an account projection after a crash split two related durable commits. The SQLite projection and applied-event idempotency ledger contain e104, while the consumer cursor still points to e102. The objective is to reconcile immutable JSONL segments and durable state, apply every remaining unique event exactly once, and prove replay is idempotent.

## 2. Idea provenance

The design adapts SQLite transaction guidance at https://www.sqlite.org/lang_transaction.html and the idempotent-consumer pattern used by at-least-once event systems. The retained source ID is `SQLITE-TRANSACTIONS`.

- **Private user logs:** None were used; the incident timeline and records are authored benchmark fixtures.
- **Synthetic-data statement:** Account identifiers, event IDs, balances, timestamps, journal segments, and crash state are synthetic.

- **Adaptation:** SQLite transaction guidance and idempotent-consumer practice are transformed into an offline crash boundary where an applied-event ledger is ahead of a separate journal cursor and duplicate delivery crosses segment files.

## 3. Real-workflow justification

A consumer can commit its business projection and idempotency ledger, then crash before advancing a separate file cursor. On restart, trusting the cursor revisits committed events, while trusting only the current balances can skip unapplied tail records. Real recovery reconciles the authoritative deduplication ledger, physical journal positions, projection state, and duplicate delivery before making a transactional change.

## 4. Agent-visible inputs

Two immutable JSONL segments contain ordered account deltas, including e103 delivered in both segments. The generated SQLite database contains accounts, `applied_events`, and `consumer_cursor`. Policy identifies the ledger as authoritative and the cursor as an optimization. A local recovery utility provides inspect, verify, and guarded recovery operations and refuses a ledger-ahead recovery unless the discrepancy is acknowledged.

## 5. Hidden ground truth

The evaluator binds visible journal segments, `repo/state/projection.db`, policy, and `repo/tools/journal_recovery.py` to required final state in `repo/state/projection.db`, `repo/out/recovery_receipt.json`, and `repo/RECOVERY_HANDOFF.md`. The controlling invariant is ledger-owned exactly-once application: committed event e104 is not replayed merely because cursor state is stale, while every unique tail event advances balances, versions, provenance, and the physical checkpoint once.

## 6. Expected workflow

1. Inspect immutable journal segments, policy, and table state in `repo/state/projection.db`, including `applied_events` and `consumer_cursor`.
2. Use `repo/tools/journal_recovery.py` inspection mode to reconcile the stale cursor event with the authoritative ledger state.
3. Invoke guarded recovery with explicit ledger-ahead acknowledgement so only unapplied unique events mutate projection state.
4. Verify balances, versions, event provenance, cursor key, database integrity, and `repo/out/recovery_receipt.json`.
5. Copy the recovered repository state and perform a second replay, requiring no event or database change.
6. Write `repo/RECOVERY_HANDOFF.md` with crash boundary, duplicate handling, before/after state, commands, and evidence.

## 7. Harness demands

The task requires shell and SQLite inspection, multi-source evidence reconciliation, selection of the correct guarded operation, stateful execution, exact-once reasoning, durable receipt handling, and post-change verification. It cannot be solved by returning a value from a standalone function.

## 8. Stressors and difficulty

- **Stressors:** stale-but-valid cursor; ledger-ahead crash state; duplicate e103 across segment boundary; unapplied physical tail; transactional projection.
- **Plausible failure mode:** trusting the cursor can double-apply e103/e104, trusting balances alone can skip tail events, and editing only cursor or balance state can leave ledger provenance and replay inconsistent.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** recovery requires choosing authority among conflicting durable records, exact-once event reconciliation, an atomic SQLite transition, physical checkpoint closure, and copied-state replay proof.

## 9. Oracle design

Projection correctness weighs 0.35, ledger and physical checkpoint consistency 0.25, repeatable no-op replay plus truthful receipt 0.20, and handoff quality 0.20. The oracle explicitly grades `repo/state/projection.db`, `repo/out/recovery_receipt.json`, and `repo/RECOVERY_HANDOFF.md`. Core weight equals the 0.80 threshold; a zero-weight gate protects journal, policy, seed, utility, and filesystem boundaries.

## 10. Leakage, isolation, and safety review

The task is fully offline and uses a local SQLite database. The utility exposes diagnostics and guarded actions but not the expected final balances as an answer key. Hidden scoring recomputes state independently. Ordinary recovery mistakes lose weighted outcomes; only mutation of protected evidence or unsafe filesystem nodes reaches the gate.

## 11. Pilot plan

Acceptance requires untouched and malformed states to score zero, a reference score of one, and adversarial failures for balance-only edits, cursor-only edits, missing ledger provenance, duplicate application, forged receipts, tool tampering, and non-idempotent replay.

- **Expected Gemma/OpenClaw failure modes:** treat the stale cursor as authority, replay e104, miss the cross-segment duplicate, patch balances without event provenance, fail to advance to physical EOF, or claim idempotency without executing a copied-state second recovery.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh model/harness run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.
