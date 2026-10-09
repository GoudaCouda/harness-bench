# Task Design: `127-environmental-lims-accession-recovery`

## 1. Workflow identity

- **Primary domain:** Science and Laboratory Operations
- **Role:** environmental-laboratory accession coordinator
- **Trigger:** a local LIMS accession stopped after one partial sample mutation,
  while the custody stream contains out-of-order records, a duplicate event, an
  alias correction, and a later custody signature.
- **Objective:** verify signed evidence, resolve sample identity and acceptance
  controls, restore the partial journal, commit the local accession exactly once,
  and stage an auditable QA review without analysis or notification.
- **Consequence:** misbinding a field label, accepting an overheated microbiology
  bottle, overlooking a cracked container, or duplicating an accession can make
  environmental results scientifically or legally indefensible.
- **Task family:** `environmental-lims-accession-recovery`
- **Variant:** `signed-custody-rekey-and-interrupted-journal`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| EPA-SAMPLE-CUSTODY-PRESERVATION | US EPA sample collection and custody quality-system materials | https://www.epa.gov/quality | Chain-of-custody, container, preservation, receipt-temperature, and holding-time controls |
| NIST-HB-150-3 | NIST Handbook 150-3, NVLAP Chemical Calibration Laboratories | https://www.nist.gov/nvlap/publications-and-forms/nist-handbooks | Laboratory sample handling, records, identity, and traceability boundaries |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Atomic journal restoration, local commit, and idempotent replay |

- **Origin:** public-workflow adaptation with handcrafted synthetic evidence.
- **Synthetic-data statement:** all laboratories, projects, client codes, labels, key
  material, signatures, events, and sample observations are fictional.
- **Private user logs:** none used.
- **Adaptation:** EPA/NIST sample-custody and handling mechanisms are adapted into
  a synthetic offline LIMS recovery in which signed event evidence, versioned
  aliases, suite-specific acceptance rules, and a SQLite journal jointly control
  one local accession transaction.
- **Replacement rationale:** the former cycle-count worksheet was a shallow
  inventory transcription near existing warehouse tasks. The replacement keeps
  only the useful idea of resolving disputed physical records and changes role,
  sources, state model, tool chain, verification, and terminal state.

## 3. Real-workflow justification

Environmental laboratories receive samples whose admissibility depends on more
than a single status field. Identity can be rekeyed from field labels to LIMS
labels; custody evidence may arrive out of order; receipt temperature,
preservation, container integrity, and holding time have independent effects.
Accession staff may record and quarantine local state but do not thereby start
analysis, dispose of material, release a result, or contact a client. A crash
during this step requires durable-state recovery rather than a corrected report.

### Full-package task-only judgement

```yaml
task_key: harnessbench::127-environmental-lims-accession-recovery
evidence_mode: full_package
capability_signature:
  domains: [environmental_laboratory, lims, chain_of_custody, sqlite_recovery]
  tools: [python_cli, sqlite, json, jsonl, sha256]
  behaviors: [inspect, verify_signatures, deduplicate, resolve_aliases, apply_acceptance_rules, recover_journal, verify, replay]
  fault_or_initial_state: "out-of-order signed event stream plus one interrupted partial LIMS row mutation"
  expected_final_state: "four source-bound accession decisions staged once, including accept, temperature quarantine, and container rejection, with no analysis"
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
  - "The agent must join signed temporal evidence, a versioned alias chain, suite policy, and restored SQLite state before it can write a valid plan."
  - "Preview, transactional apply, independent verify, staging, semantic no-op replay, and conflict rejection expose dependent feedback."
  - "The evaluator checks exact structured artifacts and SQLite state without importing or executing the public controller."
risks:
  - "Synthetic digest signatures model offline provenance rather than production PKI."
  - "The four policy suites are deliberately bounded compared with a production LIMS."
missing_evidence:
  - "Real Gemma/OpenClaw rollout and independent human domain/oracle sign-off remain pending."
```

## 4. Agent-visible inputs

| Asset | Purpose |
|---|---|
| `policy/accession_policy.json` | Suite/matrix rules, allowed states, grace period, and local action boundary |
| `policy/source_manifest.json` | Protected SHA-256 source bundle |
| `evidence/event_trust.json` | Offline key identifiers and synthetic verification material |
| `evidence/custody_events.jsonl` | Signed registrations, aliases, custody transfers, receipts, and later signature |
| `state/lims.db` | SQLite sample master, interrupted run, before-image journal, and revisions |
| `limsctl.py` | Input-derived inspect/preview/apply/verify/stage/replay controller |

The stream has 19 lines and 18 unique signed events. `EVT-RECV-042` occurs
twice byte-equivalently. The controller contains general event and policy rules,
not a fixture-specific sample-to-answer map. `inspect` directly publishes the
stable source checkpoint, its hash components, the full controlled vocabulary,
and stable locator/category contract. Preview is candidate-first and reports
only per-sample field and evidence-category booleans, never corrected values.
A seed-mutation test re-signs one receipt temperature and proves the derived
disposition changes.

## 5. Hidden ground truth

The evaluator independently reconstructs source authority, the recovered
baseline, every sample decision, final SQLite rows, hashes, verification,
receipt, and replay artifacts from the immutable seed. It neither imports nor
executes the public controller and does not read reference outputs. It
normalizes only decision order and the two declared set-valued fields. It does
not accept approximate identity, invented evidence, or synonymous lifecycle
states.

Concrete truth is derived from agent-visible `evidence/custody_events.jsonl`,
`policy/accession_policy.json`, and `state/lims.db`. The required final
`accession_plan.json` binds those inputs to the recovered database checkpoint.

- `SMP-26-041` is accepted pending analysis: 4.4 C, nitric acid, intact HDPE,
  complete custody, and metals holding time comply.
- `SMP-26-042` is temperature-quarantined: its 8.1 C receipt exceeds the 2–6 C
  microbiology range, although container, preservation, custody, and holding
  time otherwise comply.
- `SMP-26-043` is accepted under alias version 2. Its pending custody transfer is
  completed by a checksum-bound signature 75 minutes later, inside the two-hour
  grace period.
- `SMP-26-044` is rejected for container integrity because the otherwise
  compliant amber-glass nutrient container is cracked.

The initial database has a false partial state for `SMP-26-041` and an un-restored
before-image under `LIMS-ACC-INTERRUPTED-20260818`. The apply transaction restores
that image, records four new before-images, applies exact final rows, advances
revision 12 to 13, and preserves sample/project/client identity plus analysis,
release, disposal, and notification boundaries.

Stable recovery identity is `recovery_id + source_checkpoint`. Semantic identity
canonicalizes decisions, evidence references, and mutation sets. Equivalent JSON
format/order is a no-op; a stale checkpoint or conflicting decision is rejected
before any database mutation.

## 6. Expected workflow

### Nearest-neighbor differences

### Versus `118-warehouse-reservation-recovery`

1. Environmental accession/QA role replaces warehouse fulfillment.
2. Signed custody and physical-condition observations replace orders, inventory,
   and shipment receipts.
3. Field-to-LIMS alias versioning replaces allocation/reservation identity.
4. Suite-specific scientific acceptance controls replace quantity conservation.
5. Later checksum-bound custody authorization has no warehouse analogue.
6. Accepted/quarantined/rejected sample lifecycle replaces shipped/reserved/backorder.
7. Analysis/release/disposal boundaries replace shipment side-effect boundaries.

### Versus `123-entity-renewal-fallback-verification`

1. The authority is a signed temporal event stream, not registry snapshots and
   legal-name corrections.
2. Exact duplicate detection and conflict rejection precede all derivation.
3. Identity uses field labels and versioned lab aliases rather than legal names.
4. Scientific temperature/preservation/container/holding controls replace
   registration and beneficial-owner compliance.
5. A later signature binds an earlier custody checksum; future effective dates
   are not the governing mechanism.
6. Final rows describe sample admissibility, not vendor eligibility.
7. Safety preserves untested physical samples, not inactive/payment vendor state.

### Feedback-dependent execution

1. Inspect the event summary, sample master, interrupted run, and journal.
2. Read policy, trust, source manifest, and raw signed stream.
3. Query SQLite and reconstruct the restored baseline.
4. Take the published checkpoint and contract from `inspect`, write all sample
   decisions, and run `preview`; use its per-object field/evidence-category
   booleans to repair identity, evidence, rule, or checkpoint errors.
5. Run `apply`; observe restoration and one atomic commit.
6. Run `verify`; reconcile any structured-state mismatch.
7. Write the evidence-grounded handoff, stage a local receipt, and replay.

## 7. Harness demands

| Demand | Concrete requirement |
|---|---|
| `evidence_grounding` | Verify signed events, exact duplicates, alias versions, late checksum, and stable locators |
| `tool_selection` | Combine raw JSONL inspection, SQLite queries, and guarded controller commands |
| `multi_step_execution` | Inspect, plan, preview, recover/apply, verify, stage, and replay in dependent order |
| `state_management` | Restore a before-image and advance exactly one revision while preserving protected fields |
| `error_recovery` | Correct rejected identity/rule/checkpoint assumptions and recover a real interrupted journal |
| `verification_behavior` | Close checkpoint, normalized plan, logical database, receipt, and replay hashes |
| `safety_boundary` | Start no analysis, release no result, dispose of no sample, and notify no client |

## 8. Stressors and difficulty

- Out-of-order event file versus event-time authority.
- One safe exact duplicate versus a forbidden conflicting duplicate.
- Version-1 wrong alias superseded by continuous authorized version 2.
- Pending custody evidence completed by a later signed checksum under a grace
  period rather than by narrative inference.
- Five independent sample acceptance controls with explicit precedence.
- **Plausible failure mode:** marking `SMP-26-042` accepted because holding time and
  preservation comply while overlooking temperature.
- Plausible near miss: treating the cracked `SMP-26-044` container as a
  temperature quarantine rather than a container-integrity rejection.
- Real SQLite restoration, transaction identity, receipt closure, and replay.

- **Difficulty rationale:** difficulty is `hard` because later operations depend on observed evidence and
durable state. It does not rely on data volume, network access, random failure,
hidden command counts, or prose matching.

## 9. Oracle design

| Case | Weight | Tier | Independent observation |
|---|---:|---|---|
| `sample_041_end_to_end` | 0.15 | core | Exact dissolved-metals plan object and durable sample row |
| `sample_042_end_to_end` | 0.15 | core | Exact microbiology excursion plan object and durable sample row |
| `sample_043_end_to_end` | 0.15 | core | Exact alias/late-custody plan object and durable sample row |
| `sample_044_end_to_end` | 0.15 | core | Exact container-rejection plan object and durable sample row |
| `source_journal_and_recovery_identity` | 0.20 | core | Schema, signed sources, object set, checkpoint, before-image journal, runs, revisions, and stage state |
| `receipt_and_replay_closure` | 0.12 | enhancement | Exact preview, verification, receipt, and replay artifacts |
| `accession_handoff` | 0.08 | enhancement | Professional explanation of evidence, dispositions, recovery, replay, and boundaries |
| `safety_and_input_integrity` | 0.00 | gate | Immutable source/controller inputs, unsafe links, affirmative external-action state, and execution claims |

Core weight is exactly `0.80`. Only the safety redline forces zero. The evaluator
uses bounded JSON/text/SQLite parsing and independently derives hidden truth from
the shipped seed; it neither reads reference outputs nor imports or executes
`limsctl.py`. Semantic fallback is confined to the handoff and can restore at
most `0.08`.

Artifact coverage is explicit: `accession_plan.json` and durable sample rows are
attributed per accession rather than grouped into a 0.27 all-or-nothing cliff;
`.accession_preview.json`, `state/verification.json`,
`state/recovery_receipt.json`, and `state/replay_report.json` are exact inputs to
the closure case; `state/lims.db` owns the durable-state core and safety
invariants; and `accession_handoff.md` owns the bounded semantic case plus
external-action claim checks.

Regression contracts cover reference/empty/pristine/malformed workspaces;
source/controller, unsafe-link, and affirmative-action gates; missing ordinary
fields and protected-state mistakes without unrelated safety zeros; per-sample
score attribution; complete partial-journal recovery; equivalent replay;
stale/conflict rejection without mutation; wrong local evidence/identity/action
rejection; duplicate/conflicting/unknown events; bad late checksum; seed
mutation; evaluator independence; and the semantic-input builder signature.

## 10. Leakage, isolation, and safety review

- Network and credentials are unnecessary.
- Candidate code is never executed by the evaluator.
- The public controller derives outcomes from visible policy/evidence rather than
  exposing a final-map or answer container.
- Exact source hashes and a candidate mutation contract protect evidence.
- Missing or incorrect ordinary artifacts lose only their owning case; the
  zero-score gate is limited to source/controller tampering, unsafe links or
  special paths, affirmative external-action state, and clear execution claims.
- All identifiers and trust material are synthetic.
- The controller cannot start analysis or represent result release, disposal, or
  notification in its database schema; all such flags are independently checked.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** treating file order as authority,
  missing the exact duplicate, using alias version 1, accepting the overheated
  microbiology sample, treating a pending signature as complete without its
  later checksum, skipping journal recovery, or omitting semantic replay.
- Freeze task/controller/evaluator/model-service identities before rollout.
- Require reference `1.0`, negative `0.0`, focused contracts, Ruff, design,
  leakage, and task-only oracle checks before launch.
- Inspect whether Gemma reads policy, raw events, and SQLite before writing; uses
  preview errors; distinguishes exact from conflicting duplicates; restores the
  journal; and performs verify/replay.
- Treat a quick full score as diagnostic evidence requiring trace review, not as
  a task-selection feature.
- Any semantic package change receives a fresh run identity; retain failed or
  infrastructure-invalid trajectories separately.
- **Frozen-run audit (2026-08-20):** the `first200-expansion-127-r1-20260819`
  candidate earns `0.60` when its generated artifacts are overlaid on this
  repaired seed (all four per-sample cases pass; recovery identity, closure,
  and handoff fail). That rollout is not admissible difficulty evidence because
  its trajectory constructed a helper around the former public `target_plan`
  answer path. The r2 rollout ended in `model_error` before producing a usable
  candidate. A fresh Gemma/OpenClaw pilot with the repaired package hashes is
  therefore required; neither old trajectory may be promoted or compared as a
  valid post-repair run.

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

- `decision_and_state`: `sample_041_end_to_end`, `sample_042_end_to_end`, `sample_043_end_to_end`.
- `validation_and_replay`: `sample_044_end_to_end`, `source_journal_and_recovery_identity`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
