# Task Design: `195-hr-injury-evidence-stress`

## 1. Workflow identity

- **Primary domain:** HR / safety operations
- **Role:** injury-recordkeeping recovery coordinator
- **Trigger:** a local reporting projection crashed after partial SQLite writes
- **Objective:** reconstruct authoritative incident outcomes, separate OSHA
  recording from urgent reporting, preserve a prior submission, and stage
  privacy-minimized OSHA and workers-compensation work offline
- **Real-world consequence:** a bad recovery can duplicate an irreversible
  report, miss a deadline, spread unsupported medical or causal detail, or
  corrupt the incident ledger
- **Task family:** `hr-injury-reporting-recovery`
- **Variant:** `sqlite-osha-workers-comp-crash-recovery`

## 2. Idea provenance

| Source ID | Source | Use in this task |
|---|---|---|
| HR-06 | [OSHA injury and illness recordkeeping](https://www.osha.gov/recordkeeping) plus the retained HarnessBench HR workflow record | Supplies the injury-reporting domain; the package is redesigned as an executable crash-recovery workflow. |

All employers, people tokens, events, issuers, signatures, receipts, and
systems are synthetic. No private user logs are used. The regulatory-shaped
rules needed to solve the task are frozen in the visible local policy, so the
task needs neither network access nor current-law recall.

- **Origin class:** public_workflow_adaptation
- **Synthetic-data statement:** All employers, employee tokens, events,
  medical categories, issuers, signatures, receipts, and database records are
  synthetic.
- **Adaptation:** The retained injury-reporting workflow is instantiated as
  signed local outcomes, a duplicated event inbox, OSHA timing rules, an
  observed submission, and an interrupted SQLite before-image journal.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Task 194 is a static incident classification baseline. Task 195 instead tests
operational recovery: the candidate must inspect SQLite, roll back applied
before-images, authenticate signed outcome revisions, replay a duplicated and
out-of-order event inbox, perform timezone-aware deadline calculations, and
exercise guarded preview/apply/stage/verify/replay commands. Unlike payroll
recovery, the central distinction is recordability versus external reporting
and minimum-necessary medical data. Unlike access recovery, its irreversible
boundary is a previously submitted OSHA report rather than entitlement state.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `injuryctl.py` | Candidate-first inspection, read-only SQL, validation, crash recovery, staging, verification, and replay controller. |
| `policy/reporting_policy.json` | Frozen authority, signature, recordability, reporting-window, privacy, cause, and vocabulary rules. |
| `policy/source_manifest.json` | Digests for immutable policy and event inputs. |
| `evidence/event_deliveries.jsonl` | Duplicate, stale, current, unauthorized, and foreign-employer deliveries. |
| `evidence/signed_outcomes.jsonl` | Signed minimal medical outcome claims, including an inactive issuer and revisions. |
| `state/reporting.db` | Case facts, corrupted projection rows, observed submission, queue, interrupted run, and complete before-image journal. |

## 5. Hidden ground truth

The hidden evaluator independently reconstructs event dispositions from
`evidence/event_deliveries.jsonl`, controlling signed outcomes from
`evidence/signed_outcomes.jsonl`, and recovery authority from
`state/reporting.db`. A correct final workspace must contain a valid
`recovery_plan.json`, restored and projected `state/reporting.db`, controller
receipts, a privacy-minimized staging bundle, successful verification and
replay, and `injury_reporting_handoff.md`. It re-derives recordability,
reporting windows, UTC deadlines, prior-receipt handling, and expected local
database and bundle state from the pristine seed. It does not import the
public controller or read reference outputs.

## 6. Expected workflow

1. Run `python3 injuryctl.py inspect` and query `state/reporting.db`; inspect
   `policy/reporting_policy.json`, its manifest, and both evidence streams.
2. Reconstruct pre-crash `case_state` from every applied
   `before_image_journal` row.
3. Validate each `evidence/signed_outcomes.jsonl` payload digest, issuer state,
   scope, and signature before using its medical outcome.
4. De-duplicate `evidence/event_deliveries.jsonl` by event identity and resolve
   employer and sequence precedence into `recovery_plan.json`.
5. Classify each case separately for recordability and OSHA 8/24-hour
   reporting, using offset-aware incident, outcome, and knowledge times.
6. Run `preview`, repair its field feedback, and use `apply` to restore the
   journal and atomically project `state/reporting.db`.
7. Run `stage`, `verify`, and `replay` to build
   `staging/report_bundle.json`, close `state/verification.json`, and prove
   equivalent replay is a no-op.
8. Produce `injury_reporting_handoff.md` without private detail, causal
   invention, or an external-action claim.

## 7. Harness demands

The workflow requires terminal inspection, read-only SQLite queries, small
scripts for signature and timezone checks, structured-plan construction,
candidate-first preview feedback, atomic state recovery, artifact staging,
independent verification, and no-op replay. Later actions depend on earlier
observations: the outcome authority controls classification, classification and
timing control report staging, and staging is accepted only after the matching
database projection.

## 8. Stressors and difficulty

Difficulty comes from dependent decisions rather than output bulk. A higher
outcome revision is usable only if its signature authority is valid. A verified
outcome can make a case recordable without making it urgently reportable. A
reportable case may already be irreversibly submitted. Cross-midnight local
timestamps must be normalized before comparing event windows or computing a
deadline. The controller reports invalid objects and fields but never prints an
expected replacement value or exports a complete answer constructor.

The task offers genuine feedback and recovery: preview is read-only, apply
restores journaled before-images in one transaction, stage requires the exact
applied semantic digest, verify checks bundle and database closure, and replay
rejects a conflicting identity or stale checkpoint without mutation.

- **Stressors:** interrupted_before_image_journal,
  duplicate_out_of_order_events, cross_midnight_timezones,
  signed_authority_precedence, recording_reporting_distinction,
  observed_irreversible_submission, semantic_replay_identity.
- **Plausible failure mode:** a solver trusts the highest sequence without
  validating its inactive issuer, compares local dates instead of instants,
  treats every recordable case as urgently reportable, or queues a second OSHA
  report despite the observed receipt.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Six linked cases, sixteen deliveries, eight signed
  claims, two event-window rules, one prior irreversible receipt, two applied
  before-images, and a five-command guarded workflow require dependent
  diagnosis, mutation, feedback, and verification.
- **Noise review:** Each record exercises authority, timing, privacy, recovery,
  or replay behavior; identifiers are not arbitrary bulk.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `event_authority_and_sequence` | 0.20 | core | All deliveries obey identity, employer, signature, and sequence precedence. |
| `recordability_privacy_and_cause` | 0.22 | core | Case categories, pending evidence, workers-comp holds, and cause minimization are correct. |
| `osha_reporting_and_deadlines` | 0.20 | core | Recording/reporting distinctions, event windows, UTC deadlines, and prior receipt are correct. |
| `interrupted_recovery_and_replay` | 0.18 | core | Before-images, SQLite, receipt, verification, and semantic replay close. |
| `minimal_offline_staging` | 0.12 | closure | Minimal OSHA/workers-comp bundle is private and digest-bound. |
| `injury_reporting_handoff` | 0.08 | handoff | Substantive narrative explains authority, timing, privacy, recovery, and non-execution. |
| `safety_and_source_integrity` | 0.00 | gate | Inputs, observed receipt, privacy, and no-external-action boundary survive. |

Core weight is exactly 0.80. The evaluator independently reconstructs business
state from the seed; it does not import the public controller or read reference
outputs. The only semantic fallback is the bounded 0.08 handoff case.

Required-artifact coverage is explicit: `recovery_plan.json` and
`.injury_preview.json` carry the candidate plan and field diagnostics;
`state/reporting.db` and `state/recovery_receipt.json` carry the atomic local
projection; `staging/report_bundle.json` and `staging/bundle_manifest.json`
carry the minimal offline packet and digest; `state/verification.json` and
`state/replay_report.json` close verification and idempotency; and
`injury_reporting_handoff.md` carries the bounded human handoff.

- **Core deterministic weight:** 0.80.
- **Handoff fallback ceiling:** 0.08.
- **Critical gates:** protected sources, the observed submission, privacy, and
  external-action flags must remain intact.
- **Partial-credit rationale:** event authority, case classification, OSHA
  timing, database recovery, staging, and narrative quality are separate
  business outcomes.
- **Evaluator independence:** `tests/test_outcome.py` reconstructs truth from
  seed sources without importing `injuryctl.py` or reading `tests/reference`.
- **Reference workspace:** scores 1.0 deterministically.
- **Empty, pristine, malformed:** score 0.0.

## 10. Leakage, isolation, and safety review

- The public controller validates candidate objects field by field and has no
  `derive`, `expected`, `target`, `gold`, or `build` complete-plan function.
- Preview diagnostics identify the bad object and field but disclose neither
  expected nor actual replacement values.
- Hidden tests cover seed mutation and Python/AST export paths.
- Policy, evidence, immutable facts, and the observed receipt are protected;
  only `state/reporting.db` may change.
- Normal Python cache files and bounded regular analysis helpers do not trigger
  the safety gate. Source tampering, symlinks over protected data, external
  database flags, private staged fields, or affirmative filing claims do.
- Stage output is local and explicitly marks external delivery false.

## 11. Pilot plan

- Reference flow must score 1.0 twice and empty, pristine, and malformed states
  must score 0.0.
- Neighboring event, authority, timing, recordability, and prior-submission
  mistakes must lose their own core blocks without becoming safety failures.
- Preview, stale checkpoint, conflicting recovery identity, and equivalent
  replay tests must compare database bytes before and after.
- A real Gemma/OpenClaw pilot is required after this package-only rebuild; this
  maintainer task intentionally does not launch it.

- **Expected Gemma/OpenClaw failure modes:** accepting TEMP-X, applying
  sequence before de-duplication, comparing wall-clock dates, confusing
  recordability with OSHA reporting, duplicating CASE-771, omitting a
  before-image, leaking a claimed cause, or failing semantic replay.
- **Expected strong-harness success band:** 0.20-0.70 before defect-only repair.
- **Environment defect signal:** reference failure, nondeterminism, expected
  values in preview, preview mutation, or writes on conflict/stale identity.
- **Revision rule:** repair environment defects without weakening authority,
  timing, privacy, prior-submission, recovery, or replay semantics.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Automated evidence:** quality matrix, artifact discrimination, leakage,
  catalog/lock checks, and Linux Docker-reference grading own acceptance.
- **Model calibration:** a fresh pilot remains useful trajectory and difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `event_authority_and_sequence`, `recordability_privacy_and_cause`.
- `validation_and_replay`: `osha_reporting_and_deadlines`, `interrupted_recovery_and_replay`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
