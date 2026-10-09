# Task Design: `137-calibration-certificate-control-recovery`

## 1. Workflow identity

- **Primary domain:** Science and Laboratory Operations / metrology quality.
- **Role:** quality systems specialist recovering a calibration-certificate control batch.
- **Trigger:** a signed reference-standard recall and corrected result arrived around an interrupted local register update.
- **Objective:** resolve traceability and inclusive guard-band decisions, recover SQLite atomically, scope downstream recall review, and stage a hash-bound offline packet.
- **Real-world consequence:** a false release can leave an untraceable or out-of-tolerance instrument in use; overbroad recall can unnecessarily stop unaffected work.
- **Task family:** `calibration-certificate-control`.
- **Variant:** `signed-standard-recall-and-interrupted-register`.

The retained directory name is a historical numeric identity. The former job
application packet was a static document-selection exercise and was fully
replaced.

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| `ISO-IEC-17025-CALIBRATION` | ISO/IEC 17025 testing and calibration laboratory competence | https://www.iso.org/ISO-IEC-17025-testing-and-calibration-laboratories.html | Grounds controlled calibration records, traceability, result validity, and laboratory review. |
| `NIST-CALIBRATION` | NIST policy on metrological traceability | https://www.nist.gov/calibrations/traceability | Grounds the complete, time-valid chain from an instrument result through reference standards. |
| `ILAC-G8` | ILAC G8:09/2019 Guidelines on Decision Rules and Statements of Conformity | https://ilac.org/publications-and-resources/ilac-guidance-series/ | Grounds explicit decision rules that combine error, uncertainty, and specification limits. |
| `SQLITE-TRANSACTIONS` | SQLite Atomic Commit | https://sqlite.org/atomiccommit.html | Grounds before-image restoration, atomic projection, and durable replay checks. |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** Every laboratory, job, asset, certificate, standard, result, work order, identifier, value, event, and timestamp is synthetic.
- **Adaptation:** The sources are transformed into a bounded offline quality-control recovery; no live LIMS, certificate portal, customer system, physical asset, or credential is needed.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Calibration laboratories must reassess issued certificates when reference
standards are recalled, corrected results arrive, or evidence integrity fails.
This task starts with a genuinely inconsistent SQLite state: a prior recovery
changed JOB-501's certificate and asset but stopped before downstream scope and
commit. The operator must inspect signed out-of-order events, detect one exact
redelivery, validate attachment bytes, evaluate every standard at the original
calibration timestamp with retroactive recall precedence, apply a decimal
guard-band rule, and distinguish downstream work before versus after the
calibration. Preview feedback, transaction recovery, independent verification,
hash staging, and replay form dependent terminal actions.

The workflow is distinct from task 127's environmental LIMS accession recovery
and task 134's Python namespace import repair. It controls issued calibration
certificates through uncertainty-based conformity, reference-chain recall
propagation, and downstream metrology impact rather than sample custody or
software package discovery.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `state/calibration.db` | Six calibration jobs, seven downstream uses, an interrupted before-image journal, recovery identities, and revision state. |
| `policy/metrology_policy.json` | Exact event, traceability, evidence, guard-band, vocabulary, schema, and offline staging rules. |
| `policy/source_manifest.json` | Byte hashes of every protected policy/evidence source. |
| `evidence/event_trust.json` | Local synthetic verification material for signed records. |
| `evidence/metrology_events.jsonl` | Out-of-order measurements, a corrected result, an exact duplicate delivery, and two signed standard recalls. |
| `evidence/reference_standards.json` | Parent chains and validity intervals, including a standard that expires only after its calibration use. |
| `evidence/results/RES-501.json` through `evidence/results/RES-506.json` and the two JOB-505 versions | Measurement payloads whose bytes must match signed attachment hashes; one is intentionally mismatched. |
| `metrologyctl.py` | Generic inspect/query/preview/apply/verify/stage/replay controller using candidate-first validation against current inputs. |

## 5. Hidden ground truth

The independent evaluator never imports or executes candidate-authored code. It
parses bounded artifacts as data, opens SQLite read-only, normalizes set and row
order, compares the exact business projection with a hidden reference, checks
protected identities and source bytes, and recomputes receipt relationships.
Candidate JSON formatting and decision/set ordering do not matter.

The required final workspace state is the coherent set
`certificate_control_plan.json`, `.metrology_preview.json`,
`state/calibration.db`, `state/verification.json`, `state/review_packet.json`,
`state/replay_report.json`, and `calibration_control_handoff.md`. The hidden
reference proves one feasible path but is never present in the agent workspace.

Key invariants are:

- event signatures are checked locally; identical event IDs are applied once and sequence conflicts fail closed;
- the latest valid correction is authoritative and its attachment digest must match actual bytes;
- every reference in a chain is valid at calibration time, with signed `affected_from_utc` recall precedence;
- `abs(error) + expanded_uncertainty <= tolerance` is inclusive and calculated with decimal arithmetic;
- bad result evidence is held rather than guessed; later standard expiry does not retroactively invalidate prior work;
- downstream scope contains only recorded uses at or after calibration for locally revoked certificates;
- the interrupted before-image is restored before one atomic six-job projection;
- protected job/use identities, source revision, sources, and physical/external action boundaries remain unchanged;
- normalized replay is a database- and packet-byte-stable no-op, while stale or conflicting identities fail before mutation.

## 6. Expected workflow

1. Inspect policy, manifest, signed events, standard chains, result attachments, and all relevant SQLite tables.
2. Reconstruct the pre-interruption baseline and establish the protected checkpoint.
3. Resolve event identity/order, corrections, attachment integrity, recall effectivity, traceability, and decimal decision limits.
4. Write one decision per job and use `preview` diagnostics to repair mismatches without changing SQLite.
5. Run `apply` to restore the journal and commit certificate, asset, assessment, and downstream-review state atomically.
6. Run `verify`, write a professional handoff, stage the hash-bound offline packet, and inspect all outputs.
7. Reorder semantically set-valued content and run `replay`; verify database and packet bytes remain stable.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Each decision joins signed events, attachment bytes, a complete reference chain, calibration time, tolerance, and recorded downstream uses. |
| `tool_selection` | The operator combines JSON/JSONL inspection, hashing, SQLite queries, decimal reasoning, and a guarded local controller. |
| `multi_step_execution` | Authority resolution precedes the plan; the plan precedes recovery, verification, staging, and replay. |
| `state_management` | Pristine baseline, interrupted partial state, committed register, staged review, and external reality remain distinct. |
| `error_recovery` | JOB-501's premature partial write is rolled back before the complete projection is committed. |
| `verification_behavior` | Independent table equality, protected fields, revision, hashes, and byte-stable replay close the result. |
| `safety_boundary` | Local statuses and review scope must not be represented as physical quarantine, certificate transmission, or customer/regulator contact. |

## 8. Stressors and difficulty

- **Stressors:** out-of-order signed events; exact duplicate delivery; corrected-result precedence; one attachment hash failure; a retroactive reference recall; a standard expiring after valid use; inclusive zero-margin acceptance; a small negative-margin rejection; downstream time scoping; interrupted journal; normalized replay identity.
- **Natural feedback:** `preview` reports object-specific differing fields, `apply` distinguishes stale/conflicting/idempotent identities, `verify` checks the committed projection, and stage/replay expose hash instability.
- **Plausible failure mode:** trusting recorded standard status without the recall, using current date instead of calibration time, rejecting the inclusive boundary, using the original instead of corrected result, accepting the mismatched attachment, including pre-calibration USE-506-OLD, or applying atop the partial write.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** difficulty comes from dependent evidence authority, temporal traceability, decimal conformity, downstream impact, and recoverable state—not row count or fixed prose.
- **Representation tolerance:** decision order, set order, whitespace, JSON formatting, and professionally equivalent handoff prose are tolerated.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `signed_event_and_traceability_authority` | 0.27 | core | Signatures, deduplication, correction, attachments, reference chains, recall timing, job identities, and evidence locators are exact. |
| `guard_band_and_control_decisions` | 0.28 | core | Decimal margins, inclusive boundary, evidence hold, certificate/asset actions, mutations, and downstream scope are exact. |
| `interrupted_register_and_atomic_state` | 0.25 | core | Before-image recovery and all job/use/assessment/recall/run/journal/revision rows match one atomic state. |
| `verification_packet_and_replay` | 0.12 | enhancement | Preview, verification, packet hashes, and semantic replay bind one stable recovery. |
| `calibration_control_handoff` | 0.08 | semantic fallback ceiling | The bounded prose handoff accurately conveys all material control decisions and boundaries. |
| `safety_and_source_integrity` | 0.00 | redline | Source/protected-identity mutation or an executed external/physical action claim scores zero. |

Core business state totals 0.80, so polished prose cannot rescue an incorrect
recovery. The semantic judge can affect only the 0.08 handoff case. Regression
tests cover an empty workspace, malformed artifacts, source mutation, executed
claims, inclusive-boundary and recall/correction neighbor errors, interrupted
state, stale checkpoint, preview no-mutation, equivalent replay, identity
conflict, signed seed mutation, and direct database tampering.

The oracle explicitly covers every required artifact:
`certificate_control_plan.json` carries the normalized business decisions;
`.metrology_preview.json` proves source-bound preflight without mutation;
`state/calibration.db` is the authoritative recovered register;
`state/verification.json` independently closes its hashes and invariants;
`state/review_packet.json` binds the verified state and handoff;
`state/replay_report.json` proves semantic idempotence; and
`calibration_control_handoff.md` supplies the bounded professional explanation.

### Full-package task-only judgement

```yaml
task_key: harnessbench::137-calibration-certificate-control-recovery
evidence_mode: full_package
capability_signature:
  domains: [metrology_quality, calibration_certificate_control]
  tools: [shell, python, jsonl, sha256, sqlite, guarded_controller]
  behaviors: [inspect, authenticate, deduplicate, temporal_reasoning, decimal_decision_rule, recover, atomically_mutate, verify, stage, replay]
  fault_or_initial_state: "signed recalls and a corrected result surround a partially applied certificate-control transaction"
  expected_final_state: "one recovered SQLite register, scoped offline recall review, hash-bound packet, and byte-stable replay"
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
  - "Later mutations depend on authenticated event, attachment, chain, time, and decimal observations."
  - "The hidden evaluator checks business state independently rather than trusting controller output or prose."
  - "Certificate recall propagation and uncertainty-aware conformity add a primary workflow absent from neighboring inventory and field-service tasks."
risks:
  - "The public controller exposes object-specific feedback, so the real model pilot must confirm difficulty is substantive rather than dominated by iterative correction."
missing_evidence:
  - "A real Gemma/OpenClaw pilot is intentionally outside this subtask and remains required before admission."
```

## 10. Leakage, isolation, and safety review

- Hidden reference outputs, tests, and semantic rubric remain under `tests/` and are not copied into the agent workspace.
- The environment is network-independent and requires no credentials or uncontrolled external state.
- The controller exports no callable complete-plan constructor. Candidate-first
  errors identify only the job, field, and evidence category, never an expected
  business value.
- The evaluator treats candidate files as bounded inert data and opens candidate SQLite read-only.
- Only `state/calibration.db` may change; all policy/evidence/controller bytes and protected identifiers are enforced.
- The offline plan cannot send certificates, contact external parties, or perform physical asset actions.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** trust recorded standard status and miss a signed recall; use the as-of date rather than calibration time; reject the inclusive zero margin; keep the superseded JOB-505 result; trust the mismatched JOB-504 attachment; over-scope USE-506-OLD; or apply on top of the interrupted row.
- **Reference check:** the hidden reference must score 1.0 deterministically on repeated evaluations.
- **Negative checks:** pristine and malformed workspaces score 0; each neighboring authority or guard-band error loses its core block; register tampering loses the atomic-state core; source mutation or a physical/external execution claim trips the zero-score gate.
- **Runtime checks:** preview and stale/conflict failures preserve database bytes;
  a reordered equivalent plan replays without changing database or packet
  bytes; a valid signed seed mutation makes the previous candidate fail on the
  affected object/field without disclosing the replacement value.
- **Calibration use:** a real Gemma/OpenClaw run is reviewed only after package correctness is frozen, and may motivate task revision only when it exposes a reproducible spec, feedback, or evaluator defect.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
