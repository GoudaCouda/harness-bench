# Task Design: `118-warehouse-reservation-recovery`

## 1. Workflow identity

- **Primary domain:** Business Operations / supply-chain systems
- **Role:** warehouse systems operator
- **Trigger:** a reservation worker crashed between hold, pick, and shipment confirmation
- **Objective:** recover duplicate, shipped, and expired reservations exactly once without double-moving inventory
- **Real-world consequence:** an unsafe retry can release already shipped stock or make available/reserved balances negative
- **Task family:** `supply-warehouse-reservation-recovery`
- **Variant:** `crash-and-duplicate-hold`

## 2. Idea provenance

| Source ID | Public source | URL | Adaptation |
|---|---|---|---|
| SUPPLY-WMS-01 | GS1 EPCIS supply-chain visibility standard | https://www.gs1.org/standards/epcis | Adapt event visibility and durable business-step identity into an offline reservation-recovery transaction. |

- **Synthetic-data statement:** Every order, reservation, receipt, SKU,
  balance, timestamp, and recovery identity is synthetic.
- **Private user logs:** Not used.
- **Adaptation:** The public event-visibility concept is adapted into a local
  SQLite WMS incident where shipment evidence, reservation precedence,
  inventory accounting, a stable recovery ID, and replay safety must close
  together. The public source contributes workflow semantics only.

## 3. Real-workflow justification

The primary deliverable is a guarded database transition, not a report. The
operator must distinguish one later duplicate hold from its canonical hold,
honor terminal shipment evidence, release only an unpicked expired hold,
preview coupled inventory effects, apply atomically, verify, and replay safely.
Task 115 mutates an analytical CDC/SCD2 warehouse; task 118 instead recovers
operational WMS reservations and irreversible shipment accounting.

## 4. Agent-visible inputs

| Input | Purpose and authority |
|---|---|
| `warehouse.db` | Mutable operational orders, reservations, inventory, and recovery journal |
| `recovery_checkpoint.json` | Stable recovery ID, as-of time, and initial operational-state digest |
| `warehouse_seed.sql` | Protected initial-state reconstruction used by the public verifier |
| `recovery_policy.md` | Duplicate, expiry, shipment, accounting, and replay rules |
| `shipment_receipts.json` | Verified terminal shipment evidence |
| `warehousectl.py` | Offline status, query, preview, apply, and verify feedback |

## 5. Hidden ground truth

The evaluator independently reads the protected initial
`workspace/warehouse.db`, `recovery_checkpoint.json`, candidate
`recovery_plan.json`, mutated `warehouse.db`, and generated
`recovery_receipt.json`. It recomputes the initial operational digest, semantic
action-plan digest, final reservation/order/inventory state, nonnegative
accounting closure, and single recovery transaction without importing or
executing `warehousectl.py`.

The required final `warehouse.db` keeps the first `IDEMP-O100` hold, cancels
its later duplicate, commits the verified shipped reservation, releases the
expired unpicked reservation, and contains one transaction keyed by
`WMS-REC-2026-08-16-01`. `recovery_receipt.json` must bind that transaction,
checkpoint, semantic action plan, and final logical state. The handoff remains
offline and does not claim a physical warehouse action.

## 6. Expected workflow

1. Read `recovery_checkpoint.json`, `recovery_policy.md`, and
   `shipment_receipts.json`; inspect `warehouse.db` with
   `warehousectl.py status` and `query`.
2. Create `recovery_plan.json` with the checkpoint identity, initial-state
   digest, one locally evidenced action per reservation, and a false external
   action flag.
3. Run `warehousectl.py preview recovery_plan.json` and inspect every projected
   reservation, order, and per-SKU balance before mutation.
4. Run `warehousectl.py apply recovery_plan.json`, then `verify`; inspect the
   mutated `warehouse.db` and generated `recovery_receipt.json`.
5. Reorder the JSON/actions/evidence without changing reservation actions and
   replay; confirm an idempotent no-op, one transaction, and an unchanged
   receipt after the second verification.
6. Write `warehouse_handoff.md` with disposition, accounting, checkpoint,
   replay, and offline-boundary evidence.

## 7. Harness demands

The task requires relational inspection, evidence-grounded adjudication,
feedback-driven plan repair, an atomic local state mutation, cross-table
accounting, protected-source validation, recovery-journal identity, semantic
replay, and independent verification. Later actions depend on observations
created by status, preview, apply, and verify.

## 8. Stressors and difficulty

- two rows share one idempotency key but only the later hold is a duplicate;
- a picked reservation is also backed by a verified terminal shipment receipt;
- an old reservation is releasable only because it is both expired and unpicked;
- inventory changes couple availability, reserved stock, shipped stock, and order state;
- plan SHA is intentionally not recovery identity, because harmless evidence or ordering changes must not replay inventory;
- a conflicting action for the already committed recovery ID must be rejected without any database write.

- **Plausible failure mode:** an agent releases shipped stock, cancels both
  duplicate holds, skips preview, changes evidence ordering and applies stock a
  second time, hand-forges the receipt, or leaves a negative reserved balance.
- **Difficulty rationale:** policy precedence, shipment evidence, four
  reservation decisions, coupled SQLite state, source-checkpoint binding,
  semantic-plan normalization, atomic recovery, and replay verification must
  agree; plausible row-wise classification alone is insufficient.

## 9. Oracle design

| Case | Weight | Independent observable |
|---|---:|---|
| `reservation_recovery` | 0.30 | `recovery_plan.json` and `warehouse.db` retain the canonical hold, cancel only its duplicate, and release only the expired unpicked reservation with matching order states |
| `shipped_stock_and_inventory_close` | 0.25 | `warehouse.db` commits verified shipped stock and every exact available/reserved/shipped balance is nonnegative and closes to on-hand |
| `recovery_identity_and_replay` | 0.25 | `warehouse.db` has one stable-ID/checkpoint/semantic-plan transaction and `recovery_receipt.json` independently binds the same logical state |
| `plan_evidence` | 0.10 | `recovery_plan.json` covers every reservation with sufficient portable local evidence and the offline flag |
| `warehouse_handoff` | 0.10 | `warehouse_handoff.md` accurately explains dispositions, balances, checkpoint, semantic replay, and offline scope |
| `safety_and_input_integrity` | gate | protected checkpoint, seed, policy, receipts, and controller are unchanged and no physical/external action is claimed |

Artifact ownership is explicit: `warehouse.db` is covered by the three core
state cases; `recovery_plan.json` is covered by reservation adjudication,
recovery identity, and plan evidence; `recovery_receipt.json` is covered by
recovery identity; and `warehouse_handoff.md` is covered by the handoff case.
The three deterministic core cases total 0.80. Only the 0.10 handoff may use a
bounded semantic fallback; prose cannot rescue state, accounting, identity,
receipt, evidence, or safety failures.

Reference=1.0, pristine<0.8, source mutation=0.0, negative inventory, stale
checkpoint, plan-conflict replay, alternate serialization/evidence ordering,
and a changed protected baseline are contract-tested.

## 10. Leakage, isolation, and safety review

All data and credential-like identifiers are synthetic. The workflow is fully
offline and needs no service, credential, network, device, or Docker daemon.
Reference outputs and hidden evaluator logic are not copied to the workspace.
The public verifier derives terminal state by executing the protected seed in
memory and applying policy/receipt-derived normalized actions; it contains no
literal final reservation/order answer map. Only `warehouse.db` and the three
declared output files may change.

## 11. Pilot plan

Expected diagnostic failures are releasing the shipped row, retaining the
later duplicate, releasing a picked row, omitting local evidence, using a plan
digest as incident identity, skipping preview, or failing semantic replay. A
fresh Gemma 4 31B + OpenClaw run is required after the final task definition;
the trace must show inspection, preview feedback, mutation, independent
verification, and replay. Candidate performance is diagnostic only and is not
a task-selection feature.

- **Expected Gemma/OpenClaw failure modes:** treating every expired-looking row
  alike, missing the verified receipt, supplying a stale checkpoint, producing
  a plausible plan without controller feedback, or reporting idempotence
  without performing and inspecting the replay.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
