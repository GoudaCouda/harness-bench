# Task Design: `115-cdc-scd2-recovery`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** analytics engineer recovering a customer-dimension materialization after an interrupted CDC batch
- **Trigger:** a batch contains an exact redelivery, an out-of-order but complete version chain, a stale event, a signed historical correction, policy-blocked records, and one event left in a durable prepare journal
- **Objective:** adjudicate every unique event, recover the SCD2 warehouse atomically, verify the dimension, and leave a replay-safe local stage receipt
- **Real-world consequence:** a wrong recovery can fork customer history, erase a retention hold, publish an unsupported schema, or double-apply a redelivery
- **Task family:** `data-cdc-scd2-recovery`
- **Variant:** `interrupted-prepare-with-late-correction`

## 2. Idea provenance

| Source ID | Public workflow | URL | Use in this task |
|---|---|---|---|
| DEBEZIUM-CDC | Debezium change-event and delivery semantics | https://debezium.io/documentation/reference/configuration/eos.html | at-least-once delivery, stable event identity, source ordering |
| KAFKA-EOS | Kafka idempotent and transactional processing guidance | https://kafka.apache.org/38/getting-started/upgrade/ | replay-safe batch commit and durable checkpoint |
| KIMBALL-SCD2 | Type-2 slowly changing dimension workflow | https://www.kimballgroup.com/wp-content/uploads/2013/08/2013.09-Kimball-Dimensional-Modeling-Techniques11.pdf | versioned history intervals and current-row projection |
| SQLITE-TRANSACTIONS | SQLite transaction semantics | https://www.sqlite.org/lang_transaction.html | executable offline state mutation and atomic recovery |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** all organizations, people, identifiers, data, signatures, and events are synthetic.
- **Adaptation:** `115-cdc-scd2-recovery` combines CDC at-least-once delivery, transactional replay, and SCD2 history into one executable offline warehouse-recovery family with newly synthesized records and failure state.
- **Private user logs:** not used.

## 3. Real-workflow justification

The agent works against a mutable SQLite warehouse rather than only manufacturing reports. It must distinguish event identity from row order, assemble a complete version chain that arrives out of order, apply a trusted correction to historical state and its inherited current projection, honor retention and schema boundaries, reconcile a pre-existing prepare journal, and prove that replay makes no further mutation. The controller supplies executable feedback but does not choose the plan for the agent.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `warehouse.db` | Current/history dimension, event ledger, quarantine, transaction, and recovery-journal state |
| `initial_warehouse.json` | Protected logical snapshot used to verify that recovery preserves and extends the pre-crash dimension |
| `cdc_batch.jsonl` | At-least-once CDC delivery containing one exact duplicate |
| `recovery_policy.md` | Published precedence, version-chain, correction, hold, and staging rules |
| `schema_registry.json` | Supported source schemas and field mappings |
| `retention_holds.csv` | Customer records whose deletes are prohibited |
| `signed_corrections.json` | Locally trusted historical corrections |
| `cdcctl.py` | Read-only inspection plus preview/apply/verify/stage controller |

## 5. Hidden ground truth

The hidden evaluator independently opens agent-visible `warehouse.db`, compares it with `initial_warehouse.json`, and verifies the required final `recovery_plan.json` state without importing or invoking `cdcctl.py`. It checks every `event_id` key, one final ledger disposition per unique event, exact SCD2 version intervals, the committed recovery-journal state, and receipt digest invariants. It checks semantic state and stable relationships rather than database page bytes, JSON formatting, action order, or prose wording. Hidden reference artifacts exist only as a full-credit fixture and are never copied to the agent-visible workspace.

## 6. Expected workflow

1. Inspect the database, batch, registry, holds, signed corrections, and interrupted journal.
2. Create one disposition for every unique event in `recovery_plan.json`, with local evidence references.
3. Use `preview`; repair the plan until every controller check passes.
4. Use `apply` once and again to prove idempotence, then run `verify`.
5. Write the human handoff, run `stage` twice, and confirm the receipt is byte-stable.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | inspection, adjudication, preview, mutation, verification, and staging must all close |
| `evidence_grounding` | event decisions depend on registry, hold, correction, journal, and batch evidence |
| `state_management` | the candidate mutates a real SQLite SCD2 warehouse and durable journal |
| `error_recovery` | a prepared event and redelivered batch must become one atomic commit |
| `verification_behavior` | controller receipts bind the final logical state and replay |
| `safety_boundary` | a held delete and unsupported or unconsented records must not enter the dimension |

## 8. Stressors and difficulty

- **Stressors:** exact redelivery, out-of-order events, version gap analysis, stale rewind, signed correction propagation, retention hold, schema incompatibility, interrupted prepare, and idempotent replay.
- **Plausible failure mode:** the agent follows arrival order and defers a chain that is complete after sorting, applies a protected delete, accepts an unsupported schema, changes historical version 3 without propagating its inherited field, or mutates the prepared event twice.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** copying visible event fields cannot produce a coherent history, current projection, ledger, quarantine, journal, and receipt; the candidate must reason across records and then survive executable checks.
- **Noise review:** action and JSON key order are ignored, equivalent SQLite page layouts are accepted, and handoff wording is judged by bounded concepts rather than a reference string.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `event_adjudication_and_plan` | 0.20 | core | exact unique-event coverage, policy dispositions, evidence, and source binding |
| `scd2_history_and_current_projection` | 0.27 | core | complete C001/C002/C005 history and current state, including correction inheritance |
| `quarantine_and_safety_boundaries` | 0.18 | core | held delete and invalid records are quarantined without mutating protected customers |
| `transaction_checkpoint_and_replay` | 0.15 | core | one committed transaction, resolved prepare journal, exact ledger, idempotent replay |
| `verification_and_stage_binding` | 0.12 | enhancement | controller receipt and stage receipt bind the logical warehouse, plan, and sources |
| `recovery_handoff` | 0.08 | enhancement | reviewable gap, correction, quarantine, recovery, and offline explanation |
| `safety_and_input_integrity` | 0.00 | redline | protected evidence/controller unchanged and no external-action claim |

The four core cases total 0.80, so the principal business workflow must be correct to pass. The evaluator treats the candidate database and documents as bounded data and never executes candidate-authored code. Bounded semantic fallback is confined to the 0.08 handoff case and requires both independently mapped criteria—event/SCD2 effects and recovery closure—to pass. The no-external-action boundary remains deterministic and gate-protected rather than delegated to the Judge.

Artifact coverage is explicit: `warehouse.db` owns the materialized state and durable transaction; `recovery_plan.json` owns event adjudication and evidence; `cdc_verification.json` binds independent controller checks; `cdc_stage_receipt.json` binds the replay-safe local stage; and `recovery_handoff.md` owns the reviewable explanation.

## 10. Leakage, isolation, and safety review

- Hidden tests, ground truth, and references remain under `tests/` and are not copied to the agent workspace.
- Public policy names legal dispositions and workflow rules but does not expose the final action map, dimension rows, content digests, or receipt tokens.
- The task is fully offline and all scenario records are synthetic.
- Only `warehouse.db` may be modified; the four declared result artifacts may be created.
- Protected evidence and controller mutation is a zero-score gate, as is a claim that an external publish, notification, or deployment occurred.

## 11. Pilot plan

- Reference must score 1.0 deterministically, while pristine and malformed workspaces must not pass or crash.
- Contract tests cover source tamper, held-delete, stale rewind, alternative ordering, genuine replay, stale receipt, core-only tier, evaluator independence, and the real semantic-input builder contract.
- **Expected Gemma/OpenClaw failure modes:** following delivery order, missing correction inheritance, confusing prepared with applied, weak evidence locators, and omitting the second replay.
- A real Gemma 4 31B + OpenClaw pilot is required before admission. Model outcomes diagnose task and interface quality but are not selection labels.
- Revise or retire the task if failures are driven by undocumented representation choices rather than the published workflow.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `event_adjudication_and_plan`, `scd2_history_and_current_projection`.
- `validation_and_replay`: `quarantine_and_safety_boundaries`, `transaction_checkpoint_and_replay`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
