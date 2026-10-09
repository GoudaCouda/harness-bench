# Task Design: `204-purchase-order-edi-recovery`

## 1. Workflow identity

- **Primary domain:** Procurement Operations / EDI purchasing and accounts payable.
- **Role:** procurement operations analyst recovering an interrupted local match batch.
- **Trigger:** unordered 850/855/856/810 deliveries arrived while a SQLite projection stopped after a partial write.
- **Objective:** resolve EDI identity and revision authority, perform line-level three-way match, restore the journal, commit one local projection, and stage hash-bound review queues.
- **Real-world consequence:** a wrong control-number winner, quantity, price, or posted boundary can create a duplicate payable, pay unreceived goods, or corrupt an already-posted invoice.
- **Task family:** `purchase-order-edi-recovery`.
- **Variant:** `850-855-856-810-interrupted-three-way-match`.

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| `X12-850` | X12 850 Purchase Order | https://x12.org/products/transaction-sets | Grounds the purchase-order identity and ordered line facts. |
| `X12-855` | X12 855 Purchase Order Acknowledgment | https://x12.org/products/transaction-sets | Grounds supplier acceptance, rejection, changed quantities/prices, and revisions. |
| `X12-856` | X12 856 Ship Notice/Manifest | https://x12.org/products/transaction-sets | Grounds shipment quantities before invoice matching. |
| `X12-810` | X12 810 Invoice | https://x12.org/products/transaction-sets | Grounds invoice identity, quantity, price, and payable review. |
| `SQLITE-TRANSACTIONS` | SQLite Atomic Commit | https://sqlite.org/atomiccommit.html | Grounds before-image restoration, atomic projection, and replay safety. |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** every buyer, supplier, purchase order, line, invoice, shipment, amount, envelope, event, identifier, and timestamp is synthetic.
- **Adaptation:** asynchronous EDI purchasing and AP matching are transformed into an offline recovery where envelope identity, revision authority, financial boundaries, and journal state are all locally inspectable and deterministically verifiable.
- **Private user logs:** not used.

## 3. Real-workflow justification

Procurement systems routinely receive an order, one or more acknowledgment
revisions, shipment notices, invoice redeliveries, and occasionally reused
control numbers through asynchronous transports. Accounts-payable staff must
separate transport replay from conflicting business content, select the current
acknowledgment, enforce receipt and price boundaries, preserve posted invoices,
and recover interrupted local workers. Here those decisions mutate a real
SQLite state machine and close through local payable/hold queues and hashes.
Later steps depend on earlier inspection and preview feedback, so this is not a
static checklist or calculation exercise.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `state/procurement.db` | Protected PO/line facts, posted state, match tables, recovery runs, and an interrupted before-image journal. |
| `policy/match_policy.json` | Transaction identity, revision, quantity/price tolerance, disposition vocabulary, and prohibited-action rules. |
| `policy/source_manifest.json` | SHA-256 bindings for immutable policy and EDI deliveries. |
| `evidence/edi_deliveries.jsonl` | Scrambled 850/855/856/810 deliveries with exact replay, control collision, stale revision, unknown PO, and posted traffic. |
| `poedictl.py` | Candidate-first inspect/preview/apply/verify/stage/replay controller; it checks submitted objects and fields without exporting a complete plan constructor. |

The starting database deliberately leaves PO-1004 ahead of its unrestored
journal before-image. Controller, policy, manifest, deliveries, PO identity, and
posting fields remain immutable; only declared generated outputs and the local
database may change.

## 5. Hidden ground truth

The hidden evaluator reads `tests/ground_truth/ground_truth.json`, which freezes
an independently reviewed semantic plan and logical database projection. It
never imports or executes agent-visible `poedictl.py` and never reads reference
outputs. Candidate `edi_recovery_plan.json` is normalized only for decision,
event, evidence-set, line, and JSON ordering that the instruction declares
equivalent. Candidate `state/procurement.db` is opened read-only and compared as
inert logical rows.

Key invariants include:

- sender, receiver, message type, and transaction control form one envelope key;
- majority-identical content authorizes one delivery, exact repeats are ignored, and changed content under the key is quarantined;
- highest accepted revision per PO/message type wins and earlier revisions are stale;
- 855 quantity cannot increase 850 quantity, and its price is bounded by policy basis points;
- 810 quantity cannot exceed acknowledged or shipped quantity, and invoice price equals authoritative 855 price;
- missing 855, supplier rejection, quantity variance, and invoice price mismatch remain distinct states;
- `PO-POSTED` posting ID, timestamp, amount, identity, and state never change;
- the PO-1004 before-image is restored before one atomic projection;
- preview, verification, payable/hold queues, stage manifest, receipt, and replay share one recovery ID, source checkpoint, and semantic plan hash.

## 6. Expected workflow

1. Run `poedictl.py inspect`; inspect `state/procurement.db`, both policy files, and every JSONL delivery rather than trusting the summary.
2. Reconstruct the PO-1004 before-image, transaction keys, majority-identical redelivery winner, control collision, and highest message revision.
3. Join 850 order lines to 855 acknowledgments, 856 shipped quantities, and 810 invoice values; assign exact per-line match or hold state and totals.
4. Write `edi_recovery_plan.json`; run `preview` and repair any checkpoint, event, revision, evidence, amount, state, or total mismatch before mutation.
5. Run `apply` to restore the interrupted journal and commit one projection; run `verify` to close rows, protected fields, recovery identity, and journal state.
6. Write `procurement_handoff.md`; run `stage` to create local payable and hold queues, their hash manifest, and receipt.
7. Run `replay`; confirm equivalent decision/event/evidence ordering and JSON formatting are byte-stable and no external action occurred.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Every event disposition and match amount must agree across policy, envelope identity, JSONL payload, SQLite PO, and line facts. |
| `tool_selection` | The analyst combines shell inspection, JSONL parsing, hashing, SQLite queries, and guarded controller feedback. |
| `multi_step_execution` | Identity and revisions precede matching, which precedes journal recovery, verification, staging, and replay. |
| `state_management` | The task separates recovered baseline, partial write, committed projection, immutable posting, staged queues, and replay identity. |
| `error_recovery` | An actual wrong partial PO projection must be rolled back from its journal before applying the new batch. |
| `verification_behavior` | Plan, logical database, preview, verification, four staged artifacts, hashes, and replay must reconcile. |
| `safety_boundary` | No EDI transmission, posting, payment, or supplier contact may be executed or claimed. |

## 8. Stressors and difficulty

- **Stressors:** interrupted SQLite journal; file order differing from business order; composite envelope identity; majority-identical replay versus content collision; stale acknowledgment revision; line-level quantity and price boundaries; missing/rejected acknowledgment; immutable posted invoice; normalized replay identity.
- **Natural feedback:** `preview` reports schema, checkpoint, identity, and semantic mismatch before writes; `verify`, `stage`, and `replay` successively close database, queue, hash, and idempotency state.
- **Plausible failure mode:** trusting delivery order; treating a collision as a duplicate; applying 855 revision 1; matching five invoiced units to four shipped; treating a tolerated 855 change as an arbitrary 810 price variance; reopening a posted invoice; leaving the partial PO-1004 write in place; or staging hashes before the handoff is final.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** the agent must connect protocol identities and revisions to line-level money, then safely repair and verify a journaled state machine; downstream steps depend on all earlier resolutions rather than independent checklist fields.
- **Representation tolerance:** declared list/set order and JSON formatting are normalized, while identifiers, quantities, prices, revisions, states, local evidence, and closure hashes remain exact.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `edi_identity_revision_and_transport_resolution` | 0.15 | core | All 850/855/856/810 deliveries have exact duplicate, collision, stale, applied, unknown, or posted disposition. |
| `ready_payable_line_matches` | 0.15 | core | Locally ready decisions have exact authority, quantity, price, evidence, amount, and action. |
| `held_orders_posted_and_totals` | 0.17 | core | Distinct held outcomes, the posted decision, and portfolio totals reconcile. |
| `receipt_match_journal_and_recovery_projection` | 0.17 | core | Receipt/match rows, interrupted journal restoration, and the recovery run agree. |
| `plan_identity_order_projection_and_posted_boundary` | 0.16 | core | Plan identity, PO/line/system projection, protected identity, and posted state are exact. |
| `staged_hash_and_replay_closure` | 0.12 | deterministic enhancement | Preview, verification, queues, manifest, receipt, and byte-stable replay bind the same plan. |
| `procurement_handoff` | 0.08 | bounded semantic fallback | The handoff accurately communicates EDI resolution, matching, recovery, boundary, hashes, replay, and safety. |
| `safety_and_source_integrity` | 0.00 | redline gate | Any immutable source/protected field mutation, undeclared output, irregular path, affirmative external flag, or affirmative external-action claim forces zero. |

The deterministic core totals 0.80 and is split into five independently
attributed blocks rather than three all-or-nothing aggregates. Only
`procurement_handoff` can use semantic fallback and its maximum is 0.08; prose
cannot rescue a deterministic core. Missing generated closure loses the 0.12
closure block but is not itself a safety violation.
The evaluator consumes candidate artifacts as inert data and does not import or
execute the controller.

Artifact coverage is explicit: `edi_recovery_plan.json` carries decisions;
`.edi_preview.json` records pre-write validation; `state/procurement.db` is the
local system of record; `state/verification.json` closes projection;
`staging/payable_batch.json` and `staging/hold_queue.json` separate review work;
`staging/stage_manifest.json` binds hashes; `state/recovery_receipt.json` binds
the stage token; `state/replay_report.json` records byte stability; and
`procurement_handoff.md` communicates the result. The required-artifact
inventory records expected completeness; the task-local redline gate is
reserved for actual integrity or execution-boundary violations.

## 10. Leakage, isolation, and safety review

- Hidden tests, ground truth, and reference artifacts are not copied into the starting workspace.
- The public controller validates submitted objects from policy, JSONL, and SQLite and exports neither a literal answer map nor a callable complete-plan constructor.
- A seed-mutation contract tightens price tolerance, re-hashes policy, and proves the old PO-1002 candidate is rejected with object/field feedback and no expected value.
- The hidden evaluator is contract-tested not to import or execute `poedictl.py` or read reference output.
- Candidate-authored code is never executed by grading; empty, pristine, malformed, linked, irregular, and oversized states fail closed.
- Network access and credentials are unnecessary. No real buyer, supplier, order, invoice, shipment, payment, or log appears.
- Only `state/procurement.db` may be modified and only declared local artifacts may be created.

## 11. Pilot plan

- **Static contracts:** reference 1.0 and deterministic; empty/pristine/malformed 0; exact core weights; evaluator independence; direct semantic-builder invocation.
- **Adjacent negatives:** stale/applied event, duplicate/collision, unknown PO, shipment quantity, invoice price, matched amount, journal flag, and database amount each lose their owning block.
- **Redlines:** immutable source change, posted timestamp mutation, and affirmative posting/payment/contact claim each force zero.
- **Replay negatives:** reordered semantic plan is byte-stable; conflicting content under the committed recovery ID is rejected before mutation; stale checkpoint is rejected on pristine state.
- **Seed mutation:** tightening acknowledgment price tolerance from 200 to 100 basis points changes PO-1002 from ready to `hold_ack_price_variance` and changes its checkpoint.
- **Oracle modes:** empty, pristine, malformed, and reference must yield `0/0/0/1` without infrastructure error.
- **Model calibration:** after static admission, run a fresh pinned Gemma 4 31B + OpenClaw pilot; use the trajectory only for difficulty and evaluator diagnostics.
- **Expected Gemma/OpenClaw failure modes:** the model may trust arrival order, confuse collision with replay, miss revision 2, collapse distinct holds, miscompute 43,120 cents, mutate posted state, or stop before staged hash/replay closure.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Automated evidence:** package, quality-matrix, discrimination, leakage, catalog,
  lock, and Docker-reference checks own acceptance.
- **Model calibration:** a fresh pilot remains useful difficulty evidence, but is
  not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Scoring-group revision (Standard207 long-horizon reactivation)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `edi_identity_revision_and_transport_resolution`, `ready_payable_line_matches`, `held_orders_posted_and_totals`.
- `validation_and_replay`: `receipt_match_journal_and_recovery_projection`, `plan_identity_order_projection_and_posted_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

## 13. Standard207 long-horizon refactor

This package is reactivated under identity `204` to measure sustained evidence
tracking across EDI transport identity, business revision, line-level matching,
an interrupted posting projection, and offline payable/hold staging. Its
weights remain specific to procurement reconciliation rather than adopting the
uniform repair-task template. Timeout remains in the denominator and no
historical trajectory is release evidence for Standard207.
