# Task Design: `129-royalty-usage-allocation-recovery`

## 1. Workflow identity

- **Primary domain:** Media & Entertainment / music rights accounting
- **Role:** rights-accounting operations analyst
- **Trigger:** an out-of-order DDEX-like usage delivery contains duplicates,
  revisions, unresolved recordings, and adjustments while a prior SQLite
  allocation stopped after one row.
- **Objective:** derive the canonical usage population, resolve effective rights
  and ownership, quarantine uncertainty, recover the partial ledger, and stage
  one internal statement for review.
- **Real-world consequence:** using a current mapping or split for historical
  usage, applying an adjustment to another statement, or retaining the partial
  row can misallocate royalties or pay the same usage twice.
- **Task family:** `royalty-usage-allocation-recovery`
- **Variant:** `versioned-rights-and-interrupted-journal`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| DDEX-DSR | DDEX Digital Sales Reporting / Royalty Reporting Profile | https://dsr6.ddex.net/digital-sales-report-message-suite%3A-part-6-royalty-reporting-profile/1-introduction/ | Usage and royalty reporting relationships between recordings, works, usage, revenue, and licensors |
| DDEX-RIN | DDEX Recording Information Notification | https://rin.ddex.net/recording-information-notification/ | ISRC/ISWC recording and work identifier lineage |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Atomic interrupted-ledger recovery and idempotent local commit |

- **Origin class:** public-workflow adaptation with handcrafted synthetic data.
- **Synthetic-data statement:** every event, identifier, work, right, owner label,
  amount, and ledger record is synthetic.
- **Private user logs:** not used.
- **Retained mechanism:** no freight-claim answer or artifact was retained. The
  numbered slot was fully replaced because its previous static fallback report
  overlapped other claims/evidence tasks.
- **Adaptation:** DDEX's reporting and identifier relationships were transformed
  into a bounded offline recovery. The package is not represented as a conformant
  DDEX implementation; its compact JSONL is deliberately “DDEX-like.”

## 3. Real-workflow justification

Rights-accounting teams ingest revised usage, map sound recordings to musical
works, apply territory/effective-date authority, and hold unresolved money before
a statement can leave accounting. Corrections frequently arrive out of order,
and production allocators must be restart-safe. This task captures those coupled
risks with a real SQLite ledger, per-event signed conservation, a partial journal,
an internal-only stage, and semantic replay. A narrative-only answer cannot pass.

### Full-package task-only judgement

```yaml
task_key: harnessbench::129-royalty-usage-allocation-recovery
evidence_mode: full_package
capability_signature:
  domains: [music_rights, royalty_accounting, event_ingestion, sqlite_recovery]
  tools: [python_cli, sqlite, json, jsonl, sha256]
  behaviors: [inspect, deduplicate, resolve_effective_versions, allocate, quarantine, recover_journal, verify, replay]
  fault_or_initial_state: "out-of-order duplicate/revised usage plus one interrupted partial allocation"
  expected_final_state: "one source-bound royalty ledger and internal review stage with exact signed conservation"
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
  - "Later allocation choices depend on event-version, mapping, rights-window, split, adjustment-target, and journal observations."
  - "Preview rejects adjacent but dangerous mapping, split, adjustment, evidence, and conservation states before mutation."
  - "The independent evaluator checks plan meaning, exact SQLite rows, signed totals, hash-bound receipts, and replay closure."
risks:
  - "The compact JSONL is workflow-inspired rather than a full DDEX flat-file implementation."
  - "All monetary values divide cleanly by the supplied basis-point splits, so production rounding policy is out of scope."
missing_evidence:
  - "Real Gemma/OpenClaw rollout and human domain/oracle sign-off remain pending."
```

## 4. Agent-visible inputs

| Asset | Purpose |
|---|---|
| `policy/royalty_policy.json` | Stable recovery identity, period, version/split/adjustment rules, quarantine vocabulary, and external boundary |
| `sources/usage_events.jsonl` | Out-of-order physical deliveries with one exact duplicate, one superseded version, and signed adjustments |
| `sources/recording_work_mappings.json` | Effective-dated ISRC recording-to-ISWC mapping versions, including an ambiguous highest version |
| `sources/rights_catalog.json` | Territory/usage/date rights windows and effective ownership-split revisions |
| `state/royalty_ledger.db` | Real SQLite schema, protected source revision, interrupted journal, and one partial allocation |
| `royaltyctl.py` | Generic inspect/query/preview/apply/verify/stage/replay controller derived from visible sources |

The public controller contains algorithms but no fixture-specific final action
map or answer container. Raw queries expose evidence, while `preview` returns
field-level rejection feedback without printing the expected answer.

## 5. Hidden ground truth

Hidden derivation begins from the agent-visible
`sources/usage_events.jsonl` and `state/royalty_ledger.db`; successful recovery
must materialize `royalty_allocation_plan.json` and the committed final
`state/royalty_ledger.db` state.

Identical deliveries of one event/version collapse; the highest event version
controls. A mapping is valid only if uniquely highest among mappings effective on
the usage date. Rights require work, territory, usage type, and date coverage.
The uniquely effective ownership revision allocates signed units and cents.

The May and June events for one work deliberately straddle a 60/40 to 50/50
revision. The negative same-statement adjustment occurs in June but targets the
May event, so it reverses at 60/40. Another negative adjustment targets an event
outside the statement and is quarantined. Unknown, ambiguous, and expired-right
events exercise three other non-payable states.

The canonical population contains eight events: allocated signed totals are
1530 units and 185000 cents, quarantined signed totals are 950 units and 95000
cents, and source totals are 2480 units and 280000 cents. The initial partial
allocation must be deleted in the same transaction that writes exact final rows.

Stable identity is `statement_id + recovery_id + source_checkpoint`. Plan
identity canonicalizes action order, allocation order, and evidence-ref sets.
Equivalent replay performs no SQLite or receipt write. A same-identity semantic
conflict is rejected before mutation.

## 6. Expected workflow

### Nearest-neighbor differences

### Versus `122-pcard-month-close-reconciliation`

1. Music usage/rights allocation replaces employee purchase-card compliance.
2. Authority is effective ISRC-to-ISWC mapping and territory rights, not
   issuer/receipt/manager/ERP evidence.
3. Input faults are duplicate revisions and unresolved catalog identity, not
   missing receipts, split purchases, or tax exceptions.
4. Negative adjustments inherit a target event's historical split instead of
   linking a refund to a prior card transaction.
5. Final SQLite state is per-rightsholder allocation plus quarantine, not a card
   transaction disposition ledger.
6. The stage is a royalty statement review, not pending ERP posting.
7. Units and money both conserve across effective ownership versions.

### Versus `118-warehouse-reservation-recovery`

1. Role and consequence concern intellectual-property revenue allocation rather
   than physical stock reservation.
2. Evidence uses identifier mappings and rights windows rather than shipment
   receipts and warehouse movements.
3. Deduplication is version-aware usage ingestion, not shipment replay.
4. Ownership split effective dates create a historical allocation graph absent
   from inventory reservation.
5. Signed adjustments must inherit target authority; inventory uses non-negative
   on-hand/reserved arithmetic.
6. Quarantines preserve unresolved royalty money instead of backordering units.
7. Final output is an internal royalty close with no payment/delivery/contact.

### Versus `084-indicator-vintage-reconcile`

1. The task commits a mutable SQLite business ledger rather than reconciling
   macroeconomic vintages into an analysis artifact.
2. Mapping is recording-to-work plus territory rights, not series/vintage keys.
3. Ownership shares allocate signed units and money to multiple entities.
4. The initial state contains a partial durable mutation requiring recovery.
5. Unknown/ambiguous/right-window states are operational quarantines.
6. Stable business identity and semantic replay are first-class acceptance cases.
7. External payment and statement-delivery redlines replace publication caveats.

Across these neighbors, role, authority, fault, rule graph, state mutation,
verifier behavior, and final state are substantively different.

### Feedback-dependent execution

1. Inspect event lineages, statement identity, journal, and partial allocation.
2. Query raw events, mappings, rights, splits, and ledger tables.
3. Build one source-checkpoint-bound canonical action per event.
4. Run `preview`; repair event-version, mapping, window, split, adjustment,
   evidence, schema, or conservation failures.
5. Run `apply`; recover and atomically replace the interrupted partial state.
6. Run `verify`; close exact event, statement, journal, and logical-ledger checks.
7. Stage only the internal receipt and write the reviewer handoff.
8. Run `replay` to prove semantic equivalence and byte stability.

## 7. Harness demands

| Demand | Concrete requirement |
|---|---|
| `evidence_grounding` | Cite event version, mapping, right, and split records rather than infer from names |
| `tool_selection` | Use raw controller queries and SQLite state at the relevant decision stages |
| `multi_step_execution` | Inspect, derive, preview, recover/apply, verify, stage, and replay in dependency order |
| `state_management` | Remove one interrupted partial row and commit exactly one statement run |
| `error_recovery` | Consume preview errors for adjacent versions/splits and recover the journal atomically |
| `verification_behavior` | Close source, semantic plan, logical ledger, receipt, and replay hashes |
| `safety_boundary` | Quarantine uncertainty and perform no payment, statement delivery, or rightsholder contact |

## 8. Stressors and difficulty

- **Stressors:** duplicate physical delivery, out-of-order superseding event,
  mapping ambiguity, mapping effective date, rights expiry, ownership revision,
  target-inherited negative adjustment, cross-statement hold, interrupted journal,
  dual signed conservation, and semantic replay.
- **Plausible nearest correct solution:** use the June 50/50 split for `USE-106`
  instead of its May target's 60/40 split; this fails the adjustment core.
- **Plausible failure mode:** keep the partial 60000-cent row and append a complete
  allocation, producing superficially correct plan totals but a double allocation
  caught by the ledger core.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** several later actions depend on evidence discovered in
  earlier steps and must survive real transactional feedback. Difficulty is not
  created by network state, hidden spelling, data volume, or command counting.

## 9. Oracle design

| Case | Weight | Tier | Independently observed outcome |
|---|---:|---|---|
| `canonical_usage_and_rights_resolution` | 0.27 | core | Exact canonical event versions, effective mappings/windows/splits, usage allocations, quarantines, and evidence |
| `adjustments_quarantine_and_conservation` | 0.27 | core | Same-statement target inheritance, cross-statement hold, exact quarantine rows, and signed event/statement conservation |
| `interrupted_journal_and_atomic_ledger` | 0.26 | core | Exact disposition/allocation rows, no partial double count, one journal/run, protected revision, and exact totals |
| `verification_stage_and_replay` | 0.12 | enhancement | Source/plan/ledger-bound verification, internal receipt, tokens, and byte-stable semantic replay |
| `royalty_handoff` | 0.08 | enhancement | Complete professional rights-accounting explanation and safety boundary |
| `source_and_external_safety` | 0.00 | redline | Immutable sources/controller, false action flags, no execution claims, and no hazardous workspace entry; ordinary extra regular files are diagnostic |

Core weight is exactly `0.80`; a non-core omission cannot compensate for a core
failure. Only the zero-weight redline forces zero. The evaluator parses bounded
JSON, text, and SQLite without importing or executing `royaltyctl.py`. The only
semantic fallback is `royalty_handoff`, capped at `0.08`.

Artifact coverage is explicit: `royalty_allocation_plan.json` is divided across
the first two cores; `state/royalty_ledger.db` is checked by adjustment and ledger
cores; `.royalty_preview.json`, `state/royalty_verification.json`,
`state/internal_statement_receipt.json`, and `state/replay_report.json` are bound
by closure; `royalty_handoff.md` owns prose and external-action checks.

### Adversarial and regression plan

- reference `1.0`; empty/pristine/malformed `0.0`;
- policy, mapping, usage, rights, or controller mutation gates to zero;
- split-effective-date adjacent error loses the appropriate core;
- duplicate, superseded event, unknown mapping, expired right, and both adjustment
  paths are directly covered;
- altered allocation or quarantine row breaks exact ledger/conservation checks;
- stale checkpoint is rejected before mutation;
- equivalent order/format replay is byte-stable; conflict is rejected unchanged;
- a valid seed mutation causes public derivation to change rather than expose a
  fixture answer;
- evaluator source contains no controller import/subprocess execution;
- case weights, semantic mapping, and real semantic input builder are contracted.

## 10. Leakage, isolation, and safety review

- Network is unnecessary and prohibited by instruction.
- Candidate code and the public controller are never executed by the evaluator.
- Public queries expose raw inputs, not a final action map.
- The controller derives outcomes from visible source records and survives a
  seed-mutation test.
- All identifiers and accounting facts are synthetic.
- Only the local SQLite ledger and declared output artifacts may change.
- Human domain/task/oracle sign-off and real Gemma/OpenClaw pilot remain pending.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** count duplicate deliveries, choose
  event version 1, apply mapping version 1 after its end date, use split version
  2 for the adjustment, allocate unknown/ambiguous/expired events, keep the
  partial row, omit signed conservation, or confuse internal staging with payment.
- Freeze package/controller/evaluator/model-service identities before rollout.
- Require deterministic reference `1.0`, negative `0.0`, contract pass, Ruff,
  design, public-leakage, and task-only oracle checks before launch.
- Inspect whether the trajectory queries raw lineage and journal state, consumes
  preview feedback, recovers atomically, and verifies/replays independently.
- Treat model score as pilot evidence, never as a task-only selection feature.
- Any semantic repair receives a fresh run identity; preserve prior diagnostics.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
