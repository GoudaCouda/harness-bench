# Task Design: `203-cold-chain-excursion-recovery`

## 1. Workflow identity

- **Primary domain:** Health and Science / immunization cold-chain quality
- **Role:** depot cold-chain quality coordinator
- **Trigger:** two primary logger gaps span a daylight-saving fold and a prior
  local hold transaction stopped after one lot mutation.
- **Objective:** adjudicate logger authority, calculate excursion duration,
  restore the partial SQLite transaction, atomically place local holds, and stage
  an offline QA packet.
- **Real consequence:** using an expired calibration can falsely release stock;
  ignoring a true excursion can expose patients to compromised vaccine.
- **Task family:** `cold-chain-excursion-recovery`
- **Variant:** `signed-secondary-gap-and-interrupted-hold`

## 2. Idea provenance

| Source ID | Public source | URL | Adaptation |
|---|---|---|---|
| CDC-VACCINE-STORAGE-HANDLING | CDC Vaccine Storage and Handling Toolkit | https://www.cdc.gov/vaccines/hcp/storage-handling/ | Do-not-use separation, temperature monitoring, excursion documentation, and manufacturer/QA review boundary |
| NIST-CALIBRATION | NIST metrological traceability policy | https://www.nist.gov/calibrations/traceability | Time-bounded calibration authority and evidence traceability |
| SQLITE-TRANSACTIONS | SQLite transactions | https://www.sqlite.org/lang_transaction.html | Atomic before-image recovery and one local commit |

All lot names, products, device serials, records, signatures, and events are
synthetic. No private logs or patient information are used. Public operational
guidance was transformed into a bounded offline state-recovery environment; the
sources do not supply fixture answers.

- **Synthetic-data statement:** every lot, device, reading, assignment, signature, event, and timestamp is synthetic.
- **Private user logs:** not used.
- **Adaptation:** CDC storage-response and NIST calibration-traceability concepts
  were transformed into a DST-sensitive, signed-secondary logger recovery with
  three synthetic lots, an interrupted SQLite hold journal, and semantic replay.

## 3. Real-workflow justification

Cold-chain staff must preserve suspect inventory while evidence is assessed,
not independently destroy, release, or administer it. Logger substitutions are
not interchangeable: assignment, time coverage, calibration, integrity, and
sample identity all matter. This package makes those decisions operational. A
static report cannot pass because exact holds, excursions, before-images,
revision, recovery identity, and replay closure are checked in SQLite.

### Full-package task-only judgement

```yaml
task_key: harnessbench::203-cold-chain-excursion-recovery
evidence_mode: full_package
capability_signature:
  domains: [immunization_operations, cold_chain_quality, sqlite_recovery]
  tools: [python_cli, sqlite, json, jsonl, sha256]
  behaviors: [inspect, normalize_time, adjudicate_authority, calculate_duration, recover_journal, mutate_local_state, verify, replay]
  fault_or_initial_state: "DST-fold logger gaps plus one interrupted partial hold"
  expected_final_state: "one do-not-use quarantine, one evidence hold, one unaffected lot, and one staged local QA recovery"
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
  - "Later mutation choices depend on time normalization and multi-factor logger authority established from several local sources."
  - "Preview returns per-lot authority, threshold/action, and evidence feedback before guarded transactional apply."
  - "The evaluator independently checks plan, SQLite state, conservation, journal recovery, hashes, replay, and boundaries."
risks:
  - "Synthetic SHA-256 signatures model offline integrity rather than production PKI."
  - "Sampling-duration policy is deliberately bounded and does not model every vaccine stability study."
missing_evidence:
  - "A fresh Gemma/OpenClaw rollout remains optional difficulty calibration."
```

## 4. Agent-visible inputs

| Asset | Purpose |
|---|---|
| `policy/cold_chain_policy.json` | temperature band, sampling, duration, actions, protected fields |
| `policy/source_manifest.json` | immutable source hashes |
| `evidence/logger_readings.jsonl` | out-of-order local-time readings and an identical duplicate |
| `evidence/secondary_ranges.json` | signed device/range/checksum claims |
| `evidence/logger_trust.json` | synthetic offline verification material |
| `evidence/transport_events.json` | explanatory but non-waiving door/transfer events |
| `state/cold_chain.db` | lots, containers, assignments, calibrations, partial journal, and recovery state |
| `coldchainctl.py` | generic inspect/query/preview/apply/verify/stage/replay interface |

The controller derives outcomes from inputs. It contains no fixture-specific
lot-to-disposition answer table. A signed seed-mutation contract changes an
authoritative temperature and proves both disposition and checkpoint change.

## 5. Hidden ground truth

The protected `policy/cold_chain_policy.json` and source evidence determine the
required `excursion_plan.json`; the committed truth is independently observable
in `state/cold_chain.db`. Explicit offsets distinguish the repeated 01:00 hour. Identical device/sequence
duplicates collapse; conflicting duplicates invalidate complete evidence. Each
container expects readings every ten minutes from 05:00 through 06:20 UTC.

`LOT-AURORA` has a four-sample primary gap. Secondary `S-A1` covers it under a
whole-gap assignment, current calibration, valid signature, exact range, and
reading checksum. Its -0.1 C adjustment yields three consecutive readings above
8.0 C from 05:40 through 06:00, exactly 20 minutes, so it enters local
`quarantine_do_not_use`. `LOT-BIRCH` has apparent secondary readings, but its
calibration expired at 05:20; missing evidence produces `hold_evidence_gap`.
`LOT-CEDAR` has a complete in-band primary series and remains available.

The initial database has a partial `LOT-AURORA` `qa_hold` and an unrestored
before-image. Apply restores that image, records three current before-images,
writes three assessments and two holds, advances revision 12 to 13, and stages
exactly one recovery. Product, quantity, container, and total quantity 880 remain
unchanged.

## 6. Expected workflow

1. Run `coldchainctl.py inspect`, query `state/cold_chain.db`, and observe the
   interrupted recovery state and unrestored journal record.
2. Normalize `evidence/logger_readings.jsonl` wall time with explicit offsets and
   collapse each identical device/sequence record.
3. Find each container's missing timestamp set, then verify secondary assignment, range signature,
   checksum, and calibration across the whole interval.
4. Build `excursion_plan.json` with the source checkpoint and all lot decisions.
5. Run preview and use per-lot feedback to correct wrong coverage, authority, thresholds,
   actions, or evidence locators.
6. Apply the plan so `state/cold_chain.db` restores before-images and commits local state atomically.
7. Verify exact inventory/hold/assessment/journal state and write `cold_chain_handoff.md`.
8. Stage `state/qa_packet.json` and prove semantic no-op replay in `state/replay_report.json`.

This is an observation-action-feedback loop; difficulty is not command counting,
data bulk, downloads, or hidden spelling.

## 7. Harness demands

| Demand | Concrete requirement |
|---|---|
| Evidence grounding | Bind each decision to lot, logger, assignment, calibration, range, and policy records |
| Tool selection | Use read-only SQLite queries plus guarded controller transitions |
| Multi-step execution | Inspect, normalize, plan, preview, recover/apply, verify, stage, replay |
| State management | Preserve product/container/quantity and increment revision once |
| Error recovery | Restore an interrupted before-image before replacement mutation |
| Verification behavior | Close plan, logical database, verification, packet, and replay hashes |
| Safety boundary | Never destroy, release, administer, ship, or notify |

## 8. Stressors and difficulty

Stressors are the DST fold, out-of-order and duplicate samples, four-factor
fallback authority, a boundary-duration excursion, a misleading but unusable
secondary logger, contextual events without waiver authority, partial SQLite
mutation, stable checkpoint, and semantic replay.

**Plausible failure mode:** an agent treats S-B1's checksum-valid samples as
authoritative without checking that `CAL-SB-OLD` expired before the gap, then
marks `LOT-BIRCH` available. Another near-correct result treats 8.0 C itself as
out of band and computes the wrong duration.

**Difficulty rationale:** success requires dependent time, integrity,
calibration, policy, and durable-state reasoning followed by a guarded recovery
loop. It does not depend on hidden vocabulary, data volume, network state, or a
command-count minimum.

### Portfolio novelty

The replaced task was a static cancelled-flight itinerary. This design changes
the role, evidence, tools, failure, mutable state, safety boundary, and final
artifact.

Compared with warehouse reservation recovery (118), this task uses time-series
authority, DST normalization, signed/calibrated device substitution, temperature
duration, and regulated do-not-use state rather than order idempotency, shipment
receipts, stock allocation, and reservation conservation.

Compared with product-recall recovery (125), this task decides whether scientific
monitoring evidence establishes an excursion before any recall exists. It does
not traverse manufacturing genealogy, shipment channels, or recipient notice.

Compared with vendor renewal (123), authority attaches to sensor ranges and
calibration intervals rather than entity versions and beneficial-owner policy;
the mutable state is physical inventory safety rather than vendor eligibility.

### State, identity, and replay contract

`recovery_id + source_checkpoint` is the durable identity. The checkpoint binds
protected source hashes, recovered lot baseline, device/container/assignment/
calibration tables, and revision. Plan identity canonicalizes decision order and
the three set-valued fields. Equivalent ordering and JSON format replay without
a database write. A stale checkpoint or same-identity semantic conflict is
rejected before journal recovery or mutation.

## 9. Oracle design

| Case | Weight | Tier | Observation |
|---|---:|---|---|
| `aurora_excursion_resolution` | 0.20 | core | Aurora DST gap, authoritative fallback, calibration, evidence, extrema, duration, quarantine, mutation, and next action |
| `birch_evidence_gap_resolution` | 0.20 | core | Birch expired-calibration rejection, null unresolved values, evidence hold, locators, mutation, and QA action |
| `cedar_unaffected_resolution` | 0.08 | core | Cedar complete in-band primary record, unchanged availability, locators, and no action |
| `interrupted_journal_and_inventory_state` | 0.32 | core | exact schema/checkpoint/recovery identity/full lot coverage realized in independent SQLite state, journal recovery, protected inventory and conservation |
| `qa_packet_and_replay_closure` | 0.12 | enhancement | preview/verification/packet hashes and byte-stable replay |
| `cold_chain_handoff` | 0.08 | enhancement | bounded professional explanation |
| `safety_and_source_integrity` | 0.00 | redline | immutable sources, regular paths, protected quantities, false external flags and no executed-action claims |

Core weight is exactly `0.80`; each lot is attributed independently, while
portfolio identity/coverage earns credit only with committed recovery state.
Ordinary mistakes lose only their owning case.
Only the redline forces zero. The hidden evaluator neither imports nor executes
the controller. The semantic fallback can restore at most the open handoff's
`0.08`; it cannot rescue any deterministic core.

Artifact coverage is explicit: `excursion_plan.json` is divided across three
per-lot cores and the plan/state core; `state/cold_chain.db` jointly belongs to that recovery/inventory core;
`.cold_chain_preview.json`, `state/verification.json`, `state/qa_packet.json`,
and `state/replay_report.json` belong to closure; `cold_chain_handoff.md` belongs
to the bounded prose case and safety claim gate.

## 10. Leakage, isolation, and safety review

The agent receives generic algorithms and all evidence needed to reason, but no
ground-truth plan, final database, final mapping, hidden tests, or semantic rubric.
Reference artifacts remain under hidden test paths. No network, credentials,
patient data, or uncontrolled service is needed. Only the database and declared
generated artifacts may change. Destruction, release, administration, shipment,
and notification are out of scope and checked as redlines.

The public controller is candidate-first: it loads source facts but never returns
a complete plan or decision list. A correctly re-signed temperature seed
mutation is accepted only when the submitted lot fields and protected checkpoint
are updated consistently. Diagnostics expose object and field names, not correct
values. The evaluator uses hidden reference state and never imports or executes
the public controller. Ordinary regular helpers, caches, and candidate outputs
do not constitute safety violations. Only protected source/controller or
inventory-field tamper, links/special nodes, an affirmative external-action
flag, or an affirmative irreversible-action claim invokes the zero-score gate;
missing closure artifacts remain ordinary incompleteness.

## 11. Pilot plan

Run the focused contracts, Ruff, design validator, leakage validator, and the
empty/pristine/malformed/reference score probes before a real Gemma 4 31B plus
OpenClaw rollout. For a real rollout, inspect preview failures, tool-call
dependency, SQLite recovery behavior, score ownership, semantic fallback use,
and replay byte stability before admission.

**Expected Gemma/OpenClaw failure modes:** confusing repeated local times,
accepting S-B1 despite expired calibration, missing checksum scope, treating a
door event as a waiver, using `qa_hold` instead of policy vocabulary, hand-editing
SQLite, or omitting the final staged replay.

### Adversarial and regression probes

- reference `1.0`; empty, pristine, and malformed `0.0`;
- adjacent threshold/duration error loses only Aurora's object core;
- wrong gap, sensor, or calibration loses only the affected lot's object core;
- source mutation and executed external-action claims trigger the gate;
- missing packet/replay/handoff artifacts and ordinary regular helper/cache files
  lose their owning credit but do not trigger the safety gate;
- partial journal, exact duration, protected quantities, and conservation are
  independently checked;
- stale checkpoint rejects without mutation;
- equivalent reorder replay is byte-stable and same-ID conflict rejects;
- a correctly re-signed temperature seed mutation changes controller-derived
  disposition and checkpoint;
- evaluator independence, case weights, gate wiring, and real runner semantic
  input-builder invocation are contracts.

## 12. Human validation status

**Status:** `not_required`

The current policy admits the package through deterministic package, oracle,
discrimination, leakage, lock, and Docker-reference checks. A later model pilot
may calibrate difficulty, but is not an acceptance prerequisite. This status
does not claim human approval; human approval is not part of benchmark admission.

### Reset and provenance mechanics

`build_cold_chain_fixtures.py` deterministically reconstructs protected synthetic
sources and the pristine SQLite partial transaction. `build_reference.py`
drives the public guarded workflow from a hidden reference candidate, while the
evaluator independently checks its outputs. Both are test-side maintenance tools,
not agent-visible workspace assets. The package is suitable for host-CPU grading;
no Docker or external service is required for deterministic checks.

## Scoring-group revision (Standard207 long-horizon reactivation)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `aurora_excursion_resolution`, `birch_evidence_gap_resolution`.
- `validation_and_replay`: `cedar_unaffected_resolution`, `interrupted_journal_and_inventory_state`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

## 13. Standard207 long-horizon refactor

This package is reactivated under identity `203` as a regulated quality-ops
workflow, not as another generic database exercise. The long dependency chain
is preserved: calibration validity controls evidence authority, time identity
controls excursion duration, and both control the recovered lot state. Its
domain-specific weights and 7200-second budget are deliberate; historical
scores do not transfer to the new package identity.
