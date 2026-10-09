# Task Design: `206-bom-engineering-change-propagation`

## 1. Workflow identity

- **Primary domain:** manufacturing configuration management and production planning
- **Role:** configuration analyst recovering an approved engineering change
- **Trigger:** an ECN propagation stopped after one wrong work-order mutation and one partial baseline insert
- **Objective:** reconstruct the released where-used graph, apply effectivity and material boundaries, atomically recover SQLite, and stage internal review
- **Consequence:** a wrong child revision can escape into a top-level serial or a previously kitted unit can be silently reconfigured
- **Task family:** `manufacturing-ecn-configuration-recovery`
- **Variant:** `where-used-effectivity-and-interrupted-journal`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| MFG-ECN-01 | NIST product lifecycle and bill-of-materials research | https://www.nist.gov/programs-projects/smart-manufacturing-systems-design-and-analysis-program | Engineering-change, product-structure, and configuration-baseline workflow |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Atomic interrupted-state restoration and idempotent local commit |

- **Origin class:** public-workflow adaptation with handcrafted synthetic data.
- **Synthetic-data statement:** every item, revision, ECN, serial, lot, work order, person identifier, and database record is synthetic.
- **Private user logs:** not used.
- **Retained mechanism:** the old numbered task's static JSON rendering was discarded; no old answer artifact or fixture-specific action map was retained.
- **Adaptation:** product-configuration and SQLite transaction concepts were combined into a bounded offline ECN crash-recovery scenario with a multi-level where-used graph, mixed effectivity bases, issued-material boundaries, and a review-only release boundary.

## 3. Real-workflow justification

Manufacturers must preserve released and as-built configurations while approved
changes propagate into new item revisions. Effectivity is not equivalent to work
order status: serial and lot thresholds, already consumed parts, issued kits, and
approved substitutes constrain what planning metadata may change. The task makes
those facts dependent on real SQLite state and requires the interrupted write to
be restored before one atomic recovery. A narrative or standalone JSON report
cannot pass.

### Full-package task-only judgement

```yaml
task_key: harnessbench::206-bom-engineering-change-propagation
evidence_mode: full_package
capability_signature:
  domains: [manufacturing_configuration, engineering_change, production_planning, sqlite_recovery]
  tools: [python_cli, sqlite, json, jsonl, sha256]
  behaviors: [inspect, traverse_where_used, resolve_effectivity, preserve_as_built, recover_journal, verify, stage, replay]
  fault_or_initial_state: "one wrong work-order update and one partial target baseline from an interrupted ECN propagation"
  expected_final_state: "source-bound pending-review BOM revisions and exact planning dispositions in one recovered SQLite store"
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
  - "Parent revision and work-order decisions depend on released graph, approval, effectivity, issued component, and substitute observations."
  - "The independent evaluator checks exact plan meaning, SQLite rows, journal restoration, closure hashes, and semantic replay."
risks:
  - "Compact synthetic BOM records omit enterprise PLM permissions and formal electronic-signature infrastructure."
  - "Lexicographically sortable synthetic serial and lot identifiers keep effectivity deterministic."
missing_evidence:
  - "A fresh Gemma/OpenClaw rollout remains optional difficulty calibration."
```

## 4. Agent-visible inputs

| Asset | Purpose |
|---|---|
| `policy/ecn_policy.json` | Stable recovery identity, revision map, effectivity, dispositions, substitute authority, and external boundary |
| `policy/source_manifest.json` | Immutable source hashes |
| `evidence/engineering_change.json` | Approved ECN identity and component/effectivity evidence |
| `evidence/work_orders.jsonl` | Protected serial/lot, status, kit, issued-component, baseline, and version observations |
| `state/configuration.db` | Released BOM graph, work-order mirror, protected revision, interrupted run, and partial journal |
| `bomctl.py` | General inspect/query/impact/preview/apply/verify/stage/replay controller derived from visible sources |

The public controller exposes raw evidence plus candidate-first, object/field
and evidence-category preview failures. It does not print, return, or contain a
callable fixture-specific final plan constructor.

## 5. Hidden ground truth

The evaluator independently reads `policy/ecn_policy.json`,
`evidence/engineering_change.json`, `evidence/work_orders.jsonl`, and the seed
`state/configuration.db`; it neither imports nor executes `bomctl.py`.

The released closure is ACTUATOR-MODULE C→D, PUMP-100 12→13, SKID-900
5→6, and FIELD-KIT 2→3. Only the direct actuator line changes part identity;
parents change the referenced child revision. The old copper substitute is not
copied, while explicitly approved CONN-NI-4P-A is retained for the new part.

SN-0500 and LOT-2026-09 are inclusive. The six decisions cover an immutable
assembled serial, an old-component issued kit, an unissued serial, a
pre-effectivity lot, an approved-new-substitute kit, and an unissued lot. Four
work-order rows change planning metadata; none changes physical kit evidence.

The interrupted recovery has two journal entries. Both are restored before four
target baselines, complete target BOM rows, and four planning mutations commit.
Stable identity is `ECN + recovery_id + source_checkpoint`. Plan identity
canonicalizes both record sequences and all set-valued fields. Equivalent replay
performs no SQLite or receipt write; a stale checkpoint or semantic conflict is
rejected before mutation.

## 6. Expected workflow

### Nearest-neighbor differences

### Versus `205-serialized-equipment-maintenance-recovery`

1. Configuration baselines and where-used revisions replace technician dispatch and field execution.
2. Authority is approved ECN plus released BOM graph, not telemetry, service skills, location, or appointment windows.
3. Serial and lot effectivity determine configuration applicability rather than incident severity or route priority.
4. Issued inventory is treated only as an immutable boundary; no technician or material movement is scheduled.
5. Parent item revisions propagate through a multi-level graph absent from dispatch state.
6. Final state is a local configuration-review stage, not a service work-order assignment.

### Versus `125-product-recall-scope-plan`

1. Prospective engineering configuration replaces retrospective recall genealogy and containment.
2. Where-used revision lineage replaces lot/serial trace-forward distribution lineage.
3. Effectivity selectively adopts a new baseline; recall scope normally identifies already affected material.
4. Approved substitute authority is evaluated at the component line rather than shipment disposition.
5. Released/as-built histories remain available instead of marking lots contained or notified.
6. No customer, regulator, or logistics action exists in this task.

### Versus `118-warehouse-reservation-recovery`

1. Revision graph mutation replaces stock reservation arithmetic.
2. Work-order kits constrain configuration propagation but do not create inventory movements.
3. Serial/lot effectivity is an engineering boundary, not allocation priority.
4. Approved substitutes affect BOM authority rather than available-to-promise quantity.
5. Historical released revisions and as-built units are primary invariants.
6. The SQLite journal records ECN baseline/work-order mutations, not receipts or reservations.

### Feedback-dependent execution

1. Inspect protected revision, released baselines, interrupted run, and source checkpoint.
2. Query approval, work-order, BOM, effectivity, substitute, and journal evidence.
3. Use impact discovery to reconstruct the multi-level where-used closure.
4. Build a source-bound plan and consume preview diagnostics for graph/effectivity errors.
5. Apply once to restore both partial effects and atomically commit exact target state.
6. Verify source, semantic plan, journal, BOM, work orders, and logical database.
7. Stage only an internal pending-review receipt and write the reviewer handoff.
8. Replay an equivalent representation to prove database and receipt byte stability.

## 7. Harness demands

| Demand | Concrete requirement |
|---|---|
| `evidence_grounding` | Bind every baseline and work-order decision to local policy, evidence, and SQLite locators |
| `tool_selection` | Use controller queries and SQLite-backed status at the relevant decision stage |
| `multi_step_execution` | Inspect, impact, plan, preview, restore/apply, verify, stage, and replay in dependency order |
| `state_management` | Preserve released/as-built rows while creating four review baselines and four exact planning updates |
| `error_recovery` | Restore both partial mutations and repair adjacent effectivity/substitute mistakes from preview feedback |
| `verification_behavior` | Close source checkpoint, semantic plan, journal, logical SQLite, receipt, and replay hashes |
| `safety_boundary` | Perform no engineering release, physical kit action, inventory movement, shop-floor instruction, or supplier order |

## 8. Stressors and difficulty

- **Stressors:** two-level and one-level where-used branches, child-revision propagation, inclusive serial/lot thresholds, issued old component, approved new substitute, pre-effectivity kit, immutable as-built state, two-kind interrupted journal, and semantic replay.
- **Plausible nearest correct solution:** treat WO-904 like the old-component kit and request re-kit; this fails because its issued component is explicitly approved for the new base part.
- **Plausible failure mode:** update only ACTUATOR-MODULE and SKID-900 while omitting PUMP-100's referenced child revision; the visible end-item appears revised but the configuration graph is internally inconsistent.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** later transactional actions depend on coupled graph and production-state observations, and exact independent verification catches superficially plausible partial propagation. Difficulty does not rely on network access, data volume, or hidden spelling.

## 9. Oracle design

| Case | Weight | Tier | Independently observed outcome |
|---|---:|---|---|
| `where_used_configuration_baseline` | 0.27 | core | Exact four-item paths, revisions, changed lines, child links, quantities, substitutes, and evidence |
| `effectivity_kit_and_as_built_boundaries` | 0.27 | core | Exact six serial/lot decisions, inclusive thresholds, kit/substitute rules, mutations, and no external action |
| `interrupted_journal_and_atomic_sqlite_state` | 0.26 | core | Both partial effects restored; exact target BOM/work-order rows, two run identities, eight current journal entries, and logical hash |
| `verification_stage_and_semantic_replay` | 0.12 | enhancement | Source/plan/database-bound preview, verification, internal receipt, and byte-stable replay |
| `engineering_handoff` | 0.08 | enhancement | Complete professional configuration recovery explanation and safety boundary |
| `source_and_external_safety` | 0.00 | redline | Immutable inputs/controller, false action flags, no execution claims, and no hazardous workspace entry |

Core weight is exactly `0.80`; an enhancement cannot compensate for a core
failure. Only the zero-weight redline forces zero. The evaluator parses bounded
JSON, Markdown, and SQLite independently without importing or executing the
public controller. The only semantic fallback is `engineering_handoff`, capped
at `0.08`.

Artifact ownership is explicit: `ecn_recovery_plan.json` is divided between the
first two cores; `state/configuration.db` is checked by all three cores;
`.ecn_preview.json`, `state/verification.json`,
`state/internal_change_receipt.json`, and `state/replay_report.json` are bound by
closure; `engineering_handoff.md` owns prose semantics and action claims.

### Adversarial and regression plan

- reference `1.0`; empty, untouched, and malformed `0.0`;
- policy, ECN, work-order evidence, manifest, or controller mutation gates to zero;
- adjacent serial/lot boundary, omitted intermediate parent, old-substitute carryover, and wrong issued-kit disposition lose their relevant core;
- altered BOM or work-order database row breaks exact logical state;
- stale checkpoint is rejected before mutation;
- equivalent ordering/formatting replay is database- and receipt-byte-stable;
- same recovery identity with a different semantic plan is rejected unchanged;
- a valid seed work-order mutation plus refreshed manifest changes public impact output;
- the real r1 near-plan receives object/field diagnostics instead of two aggregate booleans;
- preview writes only its bounded diagnostic artifact, not SQLite or closure state;
- bounded regular Python/SQL analysis helpers and ordinary bytecode caches do not gate;
- ordinary extra regular artifacts are diagnostic; linked/irregular artifacts and affirmative external-action flags still gate;
- AST and `python -c` import checks find no public complete-answer constructor;
- evaluator source contains no import or execution of `bomctl.py`.

## 10. Leakage, isolation, and safety review

- Hidden ground truth, evaluator, reference builder, and reference artifacts live under `tests/`, outside the agent workspace.
- Agent-visible input contains no final action map, plan digest, expected target rows, receipt token, or hidden grader output.
- `bomctl.py impact` exposes discovered paths and candidate work orders, not final dispositions.
- The immutable source manifest and mutation contract protect policy, ECN evidence, work-order evidence, and controller bytes.
- The evaluator opens candidate SQLite read-only, rejects links/unexpected table sets/oversized files, and never mutates the workspace.
- The environment is offline, non-root, and dependency-free beyond Python's standard library.
- External effects are represented only as explicit false flags and handoff boundaries.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** omit the intermediate PUMP-100
revision, compare status instead of serial/lot effectivity, treat the approved
new substitute as an old-part kit, overwrite an as-built revision, retain the
partial row, or stop before verification/staging/replay. Harness failures would
instead include controller launch, workspace-copy, SQLite-open, or evaluator
infrastructure errors and must be classified separately.

1. Validate canonical container form, task metadata, full task-suite scope 207, design claims, public leakage, Ruff, and file modes.
2. Run focused reference, empty, untouched, malformed, near-miss, source-tamper, replay-equivalence, stale, conflict, and seed-mutation contracts.
3. Require oracle-quality outcomes `0.0 / 0.0 / 0.0 / 1.0` for empty, untouched, malformed, and reference workspaces.
4. Require semantic-builder parseability and ensure fallback is offered only for the 0.08 handoff case.
5. Run real Gemma/OpenClaw only after all task-only gates pass; keep infrastructure failures separate from task defects.
6. Inspect actual preview retries, SQLite recovery, verification, staging, replay, tool failures, and external-action claims before admission.

## 12. Human validation status

- **Status:** `not_required`
- Deterministic package, quality-matrix, discrimination, leakage, lock, and
  Docker-reference checks own acceptance; a real rollout is optional difficulty
  calibration.
- This status does not claim human approval; human approval is not part of
  benchmark admission.

## 13. Standard207 long-horizon refactor

This package is reactivated under identity `206`. Its length comes from a
multi-level where-used graph, effectivity and as-built boundaries, and recovery
of an interrupted configuration transaction—not from interchangeable receipt
boilerplate. The scoring remains specific to configuration correctness,
durable propagation, and closure; timeout remains a terminal model/harness
outcome.
