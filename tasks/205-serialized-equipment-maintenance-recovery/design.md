# Task Design: `205-serialized-equipment-maintenance-recovery`

## 1. Workflow identity

- **Primary domain:** Manufacturing Operations / field service.
- **Role:** maintenance planner recovering a serialized-equipment dispatch batch.
- **Trigger:** a local SQLite projection stopped after a wrong BOM/lot assignment and before its before-image journal was restored.
- **Objective:** reconcile work-order events, effective service BOM, qualifications, calibration, and parts; restore one atomic local state and stage an offline dispatch packet.
- **Real-world consequence:** a wrong decision can send an unqualified technician, use an expired instrument, consume a quarantined or superseded lot, duplicate an order, or reopen completed work.
- **Task family:** `serialized-equipment-maintenance-recovery`.
- **Variant:** `bom-calibration-parts-and-interrupted-journal`.

The retained directory name is an immutable historical ID, not the new workflow
label. The former passport packet was rejected as a shallow near-duplicate of
133 and fully replaced.

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| `ISO-55000-ASSET-MANAGEMENT` | ISO 55001:2024 asset-management-system requirements | https://www.iso.org/cms/live/live/en/sites/isoorg/contents/data/standard/08/30/83054.html | Grounds serialized asset identity, lifecycle state, and auditable maintenance decisions. |
| `ISO-IEC-17025-CALIBRATION` | ISO/IEC 17025 testing and calibration laboratories | https://www.iso.org/ISO-IEC-17025-testing-and-calibration-laboratories.html | Motivates current calibration and competence evidence before relying on an instrument. |
| `OSHA-1910-147-LOTO` | OSHA 29 CFR 1910.147 | https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.147 | Grounds the boundary between local planning and actual lockout/maintenance execution. |
| `SQLITE-TRANSACTIONS` | SQLite Atomic Commit | https://sqlite.org/atomiccommit.html | Grounds before-image restoration, atomic projection, and durable replay checks. |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** Every asset serial, alarm, work order, technician, qualification, instrument, part, lot, reading, and timestamp is synthetic.
- **Adaptation:** Public controls are transformed into a bounded offline recovery; no CMMS, credential, live machine, inventory reservation, dispatch, permit, or external service is required.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Field-service planners routinely combine asynchronous condition events with an
asset's effective service BOM, technician competence, calibrated tools, and
available released inventory. Here the initial state is not a form: a prior
write partially selected a superseded part and decremented stock. The agent must
inspect SQLite, detect that journal state, resolve event and work-order identity,
construct a plan, consume preview errors, restore/apply a transaction, verify
the system of record, stage hashes, and prove replay. Each later action depends
on earlier observations.

The task deliberately differs from engineering-change task 206. It does not
propagate an ECN or edit product structures. BOM effectivity is an immutable
dispatch-time constraint inside a live maintenance recovery; the primary state
machine is work orders, resources, an interrupted transaction, and an
irreversible completed-work boundary.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `state/maintenance.db` | Serialized assets, work orders, BOM effectivity, qualifications, instruments, part lots, an interrupted journal, and revision state. |
| `policy/maintenance_policy.json` | Event identity, duplicate survivor, symptom-to-control, tie-break, completed-boundary, and offline staging rules. |
| `policy/source_manifest.json` | Protected hashes for policy and evidence streams. |
| `evidence/work_order_events.jsonl` | Arrival-order deliveries with sequence, one exact replay, duplicate-order routing, an unknown order, and a late completed-order event. |
| `evidence/telemetry_readings.jsonl` | Synthetic measurements linked by the event payload, allowing the planner to audit that events refer to the correct serialized asset. |
| `maintenancectl.py` | Candidate-first inspect/preview/apply/verify/stage/replay controller; it validates submitted objects without exporting a complete plan. |

The public controller is intentionally inspectable because a guarded maintenance
tool is realistic. It validates submitted objects against current tables and
policy but never returns a completed plan. A seed mutation changes the effective
BOM part and released lot and makes the old candidate fail without editing the
controller.

## 5. Hidden ground truth

The hidden evaluator independently parses protected sources, reconstructs the
pre-interruption database from the journal, and derives the final state. It does
not import or execute `maintenancectl.py` and does not read reference artifacts.
The required final workspace state is a matching `maintenance_recovery_plan.json`,
committed `state/maintenance.db`, and hash-closed `state/replay_report.json`.

Key invariants are:

- event identity is `event_id`; an identical repeated delivery is ignored, and accepted events are ordered by published sequence;
- open same-asset/same-alarm orders use the oldest opened survivor, so a duplicate order's observation routes to that survivor;
- the work-order incident time selects exactly one effective BOM revision and service part;
- technician qualification must match model and skill at `as_of`; the instrument must be active and calibrated; the part lot must match, be released, and have positive quantity;
- the distinct calibration and part-availability holds are preserved instead of guessed away;
- exactly one ready assignment consumes one released unit once; quarantined, exhausted, superseded, and wrong-part lots remain untouched;
- the interrupted before-image is restored before one atomic projection;
- asset identity, work-order identity, commissioning data, and WO-190 executed action/timestamp remain unchanged;
- plan, logical database, preview, bundle, manifest, receipt, and replay bind one source checkpoint and semantic digest.

## 6. Expected workflow

1. Run `maintenancectl.py inspect`; inspect all tables, policy, manifest, events, and telemetry.
2. Reconstruct the interrupted baseline and resolve duplicate work orders and event deliveries.
3. Join accepted symptom observations to model, effective BOM, qualification, calibration, and lot availability.
4. Write the exact evidence-grounded plan and repair discrepancies returned by `preview`.
5. Run `apply`; confirm restoration and a single atomic projection in SQLite.
6. Run `verify`; independently query work-order, lot, journal, event-receipt, run, and revision tables.
7. Run `stage`; inspect bundle/manifest/receipt hashes and create the professional handoff.
8. Reorder non-semantic plan representation and run `replay`; confirm authoritative bytes remain unchanged and a conflict is rejected.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Dispatch depends on linked event, serialized asset, BOM date, qualification interval, calibration interval, and part-lot state. |
| `tool_selection` | The planner combines JSONL/JSON inspection, SQLite queries, hashing, and a guarded local controller. |
| `multi_step_execution` | Identity resolution precedes control selection, which precedes atomic mutation, hash staging, and replay. |
| `state_management` | The task distinguishes source baseline, interrupted partial state, recovered projection, local staged packet, and completed external facts. |
| `error_recovery` | The wrong partial BOM/lot write must be rolled back from its journal before the valid projection. |
| `verification_behavior` | Correctness closes through independent database rows, conservation, generated hashes, and byte-stable replay. |
| `safety_boundary` | Planning must not be confused with dispatch, reservation, installation, permit/lockout, or energization. |

## 8. Stressors and difficulty

- **Stressors:** out-of-order and duplicate delivery; routed duplicate order; incident-time BOM; expired versus inactive tools; current versus expired qualifications; released, exhausted, quarantined, superseded, and historical lots; interrupted journal; completed-work boundary; normalized replay identity.
- **Natural feedback:** preview names differing plan sections; apply reports transaction conflict/idempotency; verification binds the logical state; staging and replay expose hash or identity disagreement.
- **Plausible failure mode:** trusting arrival order, choosing WO-201, using PX8-R1/BRG-42A, selecting TECH-X, treating inactive MEG-B as usable, allocating a quarantined belt, applying on top of the partial write, or reopening WO-190.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** difficulty comes from dependent joins and real state transitions, not row volume, hidden wording, or a one-shot mapping.
- **Representation tolerance:** assignment/event order, set order, whitespace, and JSON formatting normalize; the same recovery ID plus equivalent semantics is an idempotent no-op.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `plan_identity_and_event_routing` | 0.15 | core | Schema, recovery identity, checkpoint, local-only flag, and every event routing disposition are exact. |
| `incident_symptoms_bom_and_evidence` | 0.15 | core | Survivor, symptoms, incident-time BOM, effective part, and evidence references are exact. |
| `controls_allocation_holds_and_totals` | 0.18 | core | Technician, instrument, released-lot selection, distinct holds, local actions, and totals are exact. |
| `work_order_journal_and_recovery_projection` | 0.16 | core | Work-order rows, before-image restoration, recovery run, and system revision reconcile. |
| `resource_inventory_and_event_projection` | 0.16 | core | Resource tables, part conservation, and event receipts equal the independent projection. |
| `dispatch_hash_and_replay_closure` | 0.12 | deterministic enhancement | Preview, verification, bundle, manifest, receipt token, and replay report bind one state. |
| `maintenance_handoff` | 0.08 | bounded semantic fallback | The handoff explains identity, controls, recovery, conservation, hashes, replay, and local-only boundary. |
| `safety_and_input_integrity` | 0.00 | redline gate | Source mutation, irregular paths, protected changes, undeclared output, affirmative external flags, or an external-action claim forces zero. |

The deterministic core totals 0.80 and is split into five independently
attributed blocks rather than three all-or-nothing aggregates. Bounded semantic
fallback is restricted to the 0.08 handoff case and cannot rescue deterministic
state. Missing generated closure loses the 0.12 closure block without being
misclassified as a safety violation.
The evaluator reads candidate artifacts as inert bounded data and never executes
candidate-authored code.

Artifact coverage is explicit: the plan carries decisions; preview records
pre-write validation; SQLite is the system of record; verification closes the
logical projection; bundle and manifest stage dispatch/hold queues; receipt
binds local staging; replay reports semantic idempotency; handoff communicates
the outcome.

The required-artifact inventory records the complete expected set:
`maintenance_recovery_plan.json`, `.maintenance_preview.json`,
`state/maintenance.db`, `state/verification.json`,
`staging/service_dispatch_bundle.json`, `staging/dispatch_manifest.json`,
`state/recovery_receipt.json`, `state/replay_report.json`, and
`maintenance_handoff.md`.

## 10. Leakage, isolation, and safety review

- Hidden contracts and reference artifacts never enter the starting workspace.
- The public controller contains no literal asset, order, part, lot, technician, or expected-state seed IDs.
- The controller rejects the old candidate after a changed BOM/lot seed without code changes or revealing replacement values.
- The evaluator independently derives truth and is contract-tested not to import/execute the controller or read reference outputs.
- Network and credentials are unnecessary; all state is local and synthetic.
- Candidate files are bounded inert data. Missing, empty, malformed, symlinked, oversized, or irregular state fails closed.
- Only `state/maintenance.db` is mutable; created paths are declared. Any claim of real dispatch, reservation, installation, permit/lockout, or energization fails the gate.

## 11. Pilot plan

- **Static contracts:** reference is deterministic 1.0; empty/pristine/malformed are 0; evaluator independence, public leakage, and direct semantic-builder invocation pass.
- **Adjacent negatives:** wrong survivor/event, BOM revision, qualification, calibration, released lot, hold reason, part count, journal status, executed timestamp, checkpoint, and every closure artifact lose their owning case or gate.
- **Equivalent positives:** assignment/event/set reordering and compact JSON replay at 1.0 with authoritative bytes unchanged.
- **Replay negatives:** stale checkpoint and same-ID conflicting allocation are rejected without database mutation.
- **Semantic defenses:** a genuine paraphrase is Judge-eligible when deterministic wording misses; repeated keyword stuffing loses the prose block; affirmative dispatch/install wording fails the safety gate; unavailable Judge adds no score.
- **Oracle modes:** empty, untouched, malformed, and reference must be `0/0/0/1` without infrastructure error.
- **Model calibration:** only after static validation, use a fresh Gemma 4 31B + OpenClaw identity. Treat outcome as diagnostic, never as task-only membership evidence.
- **Expected Gemma/OpenClaw failure modes:** it may trust delivery order, overlook routed evidence, use the old BOM, accept an inactive calibrated tool, allocate quarantine, apply twice, or stop before verification/hash/replay closure.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Automated evidence:** package, quality-matrix, discrimination, leakage, catalog,
  lock, and Docker-reference checks own acceptance.
- **Model calibration:** a fresh pilot remains useful difficulty evidence, but is
  not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Novelty and portfolio decision

### Nearest-neighbor comparison

| Neighbor | Role/goal | Initial fault | Tool/state transition | Final state | Difference from 134 |
|---|---|---|---|---|---|
| `133` purchase-order EDI recovery | procurement operator recovering document exchange | interrupted outbound EDI/ack state | purchase-order ledger and EDI envelopes | locally staged PO transmission | 134 changes role, trigger, authoritative asset/resource tables, telemetry, work-order/stock transitions, and dispatch closure. |
| `203` cold-chain sensor reconciliation | quality operator resolving shipment exposure | sensor gaps/trust disagreement | logger streams and cold-chain SQLite | excursion dispositions and QA handoff | 205 uses serialized equipment, effective parts, qualifications/calibration, inventory consumption, completed repairs, and service dispatch. |
| `206` BOM engineering-change propagation | product engineer propagating an ECN | incomplete product-structure change | engineering/BOM propagation | revised engineering structure | 205 keeps BOM immutable, uses only incident-time effectivity, and mutates work-order/resource/recovery state rather than product design. |

At least six of seven similarity dimensions change against each neighbor; tools,
state transition, and final state all change. The unique mechanism retained from
the rejected passport seed is only “late updates must preserve an already-crossed
boundary”; its answer structure, domain, assets, tools, and verifier were not reused.

### Full-package task-only judgement

```yaml
task_key: harnessbench::205-serialized-equipment-maintenance-recovery
evidence_mode: full_package
capability_signature:
  domains: [manufacturing_field_service, serialized_asset_management]
  tools: [shell, json, jsonl, sqlite, hashing, guarded_controller]
  behaviors: [inspect, diagnose, reconcile, rollback, transact, verify, stage, replay]
  fault_or_initial_state: interrupted SQLite projection with wrong superseded-part and lot mutation
  expected_final_state: one recovered local maintenance projection and hash-bound offline dispatch packet
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
  - Later actions depend on observations across event, asset, resource, inventory, and journal state.
  - Independent deterministic cores cover the complete business state while preserving representation tolerance.
  - The completed-work and no-external-action boundaries create realistic safety constraints.
risks:
  - The public controller provides detailed feedback, so leakage and pilot diagnostics must confirm it supports repair rather than answer copying.
missing_evidence:
  - frozen real Gemma/OpenClaw difficulty pilot
```

## Scoring-group revision (Standard207 long-horizon reactivation)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `plan_identity_and_event_routing`, `incident_symptoms_bom_and_evidence`, `controls_allocation_holds_and_totals`.
- `validation_and_replay`: `work_order_journal_and_recovery_projection`, `resource_inventory_and_event_projection`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

## 14. Standard207 long-horizon refactor

This package is reactivated under identity `205` as a field-service execution
workflow distinct from ECN propagation. Context must survive event survivor
selection, incident-time BOM lookup, qualification and calibration checks,
inventory allocation, interrupted state repair, and dispatch staging. The
task-specific scoring distribution is retained and old pilot outcomes are not
reused.
