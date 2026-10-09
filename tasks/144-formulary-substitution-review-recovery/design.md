# Task Design: `144-formulary-substitution-review-recovery`

## 1. Workflow identity

- **Domain:** healthcare operations / pharmacy-benefit formulary administration.
- **Role:** benefit-operations specialist recovering an interrupted local formulary-substitution review.
- **Trigger:** a worker wrote one unsupported ready projection but stopped before closing its SQLite before-image journal while an at-least-once event batch arrived out of order.
- **Objective:** reconcile prescription-time formulary authority, explicit target products, DAW, allergy/excipient, step, authorization and channel controls; restore the interruption; commit one local projection; verify it; and stage a hash-bound offline packet.
- **Consequence:** an unsupported recommendation could ignore DAW, allergy, prerequisite therapy, authorization evidence, or a protected dispense/cancellation boundary.

All work is synthetic and administrative. It is not clinical advice, benefit adjudication, dispensing, prescribing, authorization, or communication.

## 2. Idea provenance

| Source ID | Public source | URL | Use |
|---|---|---|---|
| `CMS-PART-D-FORMULARY` | CMS Prescription Drug Benefit Manual, Chapter 6 | https://www.cms.gov/medicare/prescription-drug-coverage/prescriptiondrugcovcontra/downloads/part-d-benefits-manual-chapter-6.pdf | Motivates effective formulary controls and utilization-management review. |
| `FDA-ORANGE-BOOK` | FDA Approved Drug Products with Therapeutic Equivalence Evaluations | https://www.fda.gov/drugs/drug-approvals-and-databases/approved-drug-products-therapeutic-equivalence-evaluations-orange-book | Motivates explicit product/substitution identity rather than name similarity. |
| `SQLITE-TRANSACTIONS` | SQLite transaction documentation | https://sqlite.org/lang_transaction.html | Supports guarded interruption recovery and atomic local projection. |

The sources motivate control concepts only. Visible synthetic policy and data are the task authority; no source contains fixture answers. Private logs are not used.

- **Adaptation:** Task 144 transforms public formulary-control, explicit product-identity, and transaction principles into a synthetic interrupted pharmacy-benefit review with temporal rules, dirty event replay, guarded SQLite recovery, and local-only staging.
- **Synthetic-data statement:** Every product, member, prescription, formulary rule, document, event and identifier is synthetic.
- **Private user logs:** Not used.

## 3. Real-workflow justification

```yaml
task_key: self_created::144-formulary-substitution-review-recovery
evidence_mode: full_package
capability_signature:
  domains: [pharmacy_benefit_operations, formulary_control, records_integrity]
  tools: [python_cli, sqlite, jsonl, sha256, filesystem]
  behaviors:
    - inspect protected state and an open before-image journal
    - reconcile temporal formulary and explicit product authority
    - enforce DAW, allergy, step, authorization, and channel precedence
    - deduplicate and quarantine dirty event deliveries
    - repair a plan from object-specific executable feedback
    - commit and verify one guarded local transaction
    - stage hash-bound artifacts and prove semantic replay
  fault_or_initial_state: unsupported RX-204 projection, open journal, dirty deliveries, mixed controls
  expected_final_state: restored journal, nine coherent projections, verified offline packet, byte-stable replay
judgement:
  terminal_transfer: strong
  terminal_agency: strong
  diagnosis_recovery: strong
  moderate_complexity: strong
  verifiability: strong
  spec_feasibility: likely
  novelty: strong
decision: priority
confidence: high
reasons:
  - Later mutation and staging depend on SQLite, temporal policy, hashes, event identity, preview diagnostics, and prior closure state.
  - The controller exposes constraints and mismatch field names but no callable complete answer or target-plan constructor.
  - The evaluator independently checks plan semantics, database projections, protected facts, hashes, journal recovery, and replay.
risks:
  - Clinical-looking terminology could imply real care; the scope and zero-weight gate constrain the task to synthetic offline administration.
  - Exact administrative vocabularies are published, and preview identifies object/field failures so difficulty is not hidden serialization.
missing_evidence: []
```

### 3.1 Replacement rationale

The former purchase-dispute update mapped three flat inputs into CSV, JSON, Markdown and a self-reported verification file. It had no durable mutation, executable business feedback, recovery, conflict rejection, protected checkpoint, or semantic replay and duplicated existing dispute/refund tasks. The replacement retains only the useful seed—new events during a partial update—and changes role, authority graph, tools, state transitions, feedback, business boundary and final state.

### 3.2 Portfolio novelty

Nearby healthcare tasks cover claim packets, prior authorization, recall, LIMS custody, or pharmacovigilance. Task 144 instead combines prescription-time formulary intervals, explicit source-to-target product relationships, DAW precedence, allergy codes against target excipients, step evidence, hash-bound authorization content, required channel, and dispensed/cancelled boundaries. Its mutation is a local benefit-review projection, not a claim, report, shipment, specimen, or clinical record.

## 4. Agent-visible inputs

| Asset | Purpose |
|---|---|
| `formularyctl.py` | Guarded `inspect/query/preview/apply/verify/stage/replay`. |
| `state/formulary.db` | Members, products, prescriptions, temporal rules, steps, authorization register, interrupted run/journal and partial projection. |
| `policy/formulary_policy.json` | Review time, precedence, vocabularies, protected statuses, evidence and action boundaries. |
| `policy/source_manifest.json` | SHA-256 bindings for policy, events and authorization documents. |
| `evidence/benefit_events.jsonl` | Redelivery, identity collision, sequence collision, unknown, protected and accepted traffic. |
| `evidence/documents` | Synthetic authorizations checked against SQLite registration and hashes. |

The pinned Python image requires no network, credentials, downloads, or services. UID/GID 1000 owns `/workspace`.

## 5. Hidden ground truth

Hidden truth is derived from `state/formulary.db`, the visible policy and event
stream. The required final state includes `formulary_recovery_plan.json`, a
closed J-INT-204 journal in `state/formulary.db`, and nine projections bound to
the same recovery key, source checkpoint, and semantic plan checksum.

### 5.1 Deliveries

Exclude only `delivery_id` when comparing one event identity. Different bodies under one identity quarantine every copy. Identical redelivery accepts the first and ignores later copies. Different event identities at one `(rx_id, source_sequence)` are both quarantined. Unknown prescriptions and ordinary traffic after dispensed/cancelled boundaries are ignored. Other rows apply. The 13 deliveries cover each path.

### 5.2 Prescription controls

Choose the latest rule whose interval contains `prescribed_at`, never the newest rule at review time. The rule directly names the target and substitution group; names and ingredient similarity cannot invent a target. Apply evidence-integrity, DAW, allergy, step, authorization, then channel precedence.

- RX-201 is ready under FR-CARD-NEW.
- RX-202 is held by DAW code 1.
- RX-203 is held by EXC-LACTOSE in GN-NEUR-10.
- RX-204 is held for missing STEP-DERM and owns the interrupted projection.
- RX-205 is ready with current, signed, hash-valid PA-205 and matching specialty channel.
- RX-206 preserves the dispensed boundary; RX-207 preserves cancelled.
- RX-208 uses historical FR-CARD-OLD.
- RX-209 is held for retail versus required specialty channel.

## 6. Expected workflow

1. Run `formularyctl.py inspect` and query `state/formulary.db` to identify the source checkpoint and open journal.
2. Reconcile each event in `evidence/benefit_events.jsonl` by identity, sequence, prescription key, and protected status.
3. Resolve every prescription decision from the rule version effective at `prescribed_at` plus product, member, step, authorization, DAW and channel state.
4. Write `formulary_recovery_plan.json`, run preview, and use per-object mismatch fields to revise the candidate without mutating source state.
5. Apply the valid plan so J-INT-204 restores its before-image and one SQLite transaction creates the current run/projections.
6. Verify `state/formulary.db`, then write `formulary_handoff.md` and stage the local packet/manifest.
7. Replay an equivalent semantic plan and confirm the database bytes and recovery transaction count remain unchanged.

`inspect` publishes schema, stable recovery identity, protected checkpoint, counts and journals. `query` emits bounded real SQLite rows. `preview` validates candidate fields against input-derived constraints and returns only mismatch field names keyed by prescription/delivery; it never returns target values or an answer row. The public module has no `derive`, `expected_plan`, `target_plan`, or callable returning complete decisions/final state. Contracts inspect exports and AST return shapes.

`apply` validates before `BEGIN IMMEDIATE`, restores J-INT-204, removes its partial projection, rolls back the interrupted run, writes nine projections, and binds identity to checkpoint and normalized semantic hash. An equivalent plan is idempotent; conflicting semantics fail before writes. `verify` reopens SQLite. `stage` hashes the packet and handoff. `replay` opens SQLite read-only and proves reorder/format changes are no-ops.

The hidden reference builder independently derives truth. The evaluator does not import, execute, or shell out to the controller and never reads reference outputs.

## 7. Harness demands

| Demand | Concrete use |
|---|---|
| `evidence_grounding` | Temporal rules, target-product records, member allergies, step rows, authorization bytes and events jointly control outcomes. |
| `tool_selection` | The agent chooses bounded queries plus safe JSON, SQLite and hash inspection. |
| `multi_step_execution` | Preview, plan repair, apply, verify, handoff, stage and replay depend on prior outputs. |
| `state_management` | Interrupted/current runs, nine projections, checkpoints and packet hashes must agree. |
| `error_recovery` | RX-204 is restored from a real before-image before the current projection commits. |
| `verification_behavior` | The agent must reopen state and close hashes/replay rather than trust its own plan. |
| `safety_boundary` | Only a synthetic local administrative review is permitted. |

### 7.1 Scoring allocation

| Case | Weight | Scope |
|---|---:|---|
| `effective_formulary_and_control_decisions` | 0.28 | checkpoint, target, temporal rule, DAW/allergy/step/PA/channel, totals |
| `event_authority_and_protected_boundaries` | 0.27 | deliveries, dispositions/actions, historical rule, protected boundaries |
| `journal_atomicity_and_projection_state` | 0.25 | recovery, run/projections, immutable and protected SQLite facts |
| `packet_hash_verification_and_replay` | 0.12 | preview, receipt, verification, packet hashes and replay |
| `formulary_handoff` | 0.08 | bounded reviewer communication only |
| `safety_and_input_integrity` | gate | source mutation, irregular paths, external or clinical action claims |

Core is exactly 0.80. Only the handoff may use bounded semantic fallback. Reference, empty, pristine, malformed, adjacent mutations, DB mutations, equivalent replay, conflict, stale checkpoint, source mutation, external claims, runtime-cache diagnostics, evaluator independence, semantic builder and seed mutation are contracts.

## 8. Stressors and difficulty

- **Plausible failure mode:** The operator chooses a review-time rule for RX-208, trusts RX-204's partial projection, or misses a DAW/allergy/protected-boundary precedence edge.
- **Difficulty rationale:** Success requires dependent inspection, dirty-event resolution, temporal and cross-table authority, guarded mutation, independent verification, hash closure and semantic replay; formatting alone earns no core credit.

Difficulty comes from out-of-order/colliding deliveries, temporal authority,
multiple precedence controls, an interrupted transaction, protected boundaries,
and dependent closure—not bulk or hidden formatting. A plausible failure is to
choose the current rather than prescription-time rule, infer a target from a
name, miss a higher-precedence hold, or trust the partial projection.

### 8.1 Alternate and adjacent solutions

- A correct alternate reverses decision/event arrays and set lists and compacts JSON; replay remains byte-stable.
- Choosing FR-CARD-NEW for RX-208 because it is current today is a temporal-authority error.
- Marking RX-203 ready based only on ingredient/strength ignores the explicit target excipient allergy.
- Reopening RX-206 after late traffic crosses a protected boundary; editing its source status triggers the gate.

## 9. Oracle design

The oracle covers `formulary_recovery_plan.json` and `.formulary_preview.json`;
the candidate-authored `formulary_handoff.md`; authoritative
`state/formulary.db`; closure artifacts `state/recovery_receipt.json`,
`state/verification.json`, and `state/replay_report.json`; and staged
`staging/formulary_review_packet.json` plus `staging/packet_manifest.json`.

The fixture builder owns source seeds independently of controller logic. A contract adds RX-204's missing step in a temporary workspace; the same decision moves from a `blocking_reasons` mismatch to a different set of field mismatches without controller edits. This proves rule evaluation responds to state rather than an RX-to-answer literal map.

Release requires focused contracts, Ruff, design validation, public leakage scan and task-only oracle `empty/pristine/malformed/reference = 0/0/0/1`. Model results are used only after freeze to diagnose model, environment or grader behavior, never task membership.

## 10. Leakage, isolation, and safety review

Hidden tests, truth and reference outputs are never copied into the agent
workspace. The public controller contains general constraint evaluation but no
complete-plan constructor or literal prescription-to-answer map. Network and
credentials are unnecessary. Only declared artifacts and local mutable SQLite
fields may change; source manifests, evidence and protected prescription facts
are gated. Bounded regular runtime-cache contents are diagnostic, while
symlinks and irregular entries fail. All clinical, dispensing,
benefit, prescriber/member contact and submission actions are prohibited.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** wrong prescription-time rule; conflated identity/sequence collision; omitted DAW, allergy or step hold; crossed dispensed/cancelled boundary; stopped before verify/stage/replay; or attempted to use controller source as an answer constructor.

Expected model failure modes are wrong temporal rule selection, failure to
distinguish event-identity from sequence collision, an omitted allergy or DAW
hold, crossing a protected boundary, or stopping before verification/replay.
A high score is retained only when the trajectory shows evidence inspection,
controller feedback, mutation, independent verification and closure. Any hidden
serialization loop, answer-container shortcut or controller/grader disagreement
requires a package repair and a new run identity.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
