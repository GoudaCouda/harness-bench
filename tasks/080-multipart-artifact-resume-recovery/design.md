# Task Design: `080-multipart-artifact-resume-recovery`

## 1. Workflow identity

- **Role:** release engineer recovering an interrupted checksummed multipart artifact upload.
- **Trigger:** a runner lost state after uploading some parts or while completing the upload.
- **Objective:** reconcile every listed part and produce a safe offline resume or verification plan.
- **Boundary:** no object-storage, upload, overwrite, complete, abort, delete, or publication action.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| S3-MULTIPART | Amazon S3 multipart upload overview | https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html | 2026-08-27 |
| S3-CHECKSUMS | Amazon S3 object integrity checks | https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html | 2026-08-27 |
| S3-COMPLETE-MULTIPART | Amazon S3 CompleteMultipartUpload API | https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html | 2026-08-27 |

- **Adaptation:** documented multipart identity, ordering, checksum, and completion behavior becomes an offline CI artifact recovery planner.
- **Private user logs:** None.
- **Synthetic-data statement:** Upload IDs, object keys, part inventories, sizes, checksums, ETags, and incident observations are synthetic.

## 3. Real-workflow justification

CI systems often upload artifacts in parts and resume after worker loss. Reusing
the wrong upload ID, reading only one page, or completing from stale part
metadata can silently assemble a corrupt object; retrying completion after an
unknown response also requires verification rather than blind replay.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/multipart_contract.md` | authoritative reconciliation and action contract |
| `repo/src/multipart_resume.py` | broken planner |
| `repo/resume_cases.json` | visible upload incidents |
| `repo/tests/test_public.py` | public regressions |

## 5. Hidden ground truth

Hidden cohorts extend the concrete visible inputs
`repo/docs/multipart_contract.md`, `repo/resume_cases.json`, and
`repo/tests/test_public.py` with paginated and empty listings, matching,
missing, stale, and overwritten parts, unordered local evidence, complete and
unknown-completion states, stale upload IDs, malformed pagination, unsafe
object keys, invalid types, immutable evidence, and external-action restraint.
Required final state includes repaired `repo/src/multipart_resume.py`, exact
`repo/resume_plan.json`, and verified `repo/REPAIR_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/multipart_contract.md`, `repo/resume_cases.json`, and `repo/tests/test_public.py`.
2. Validate the upload identity, local manifest, pagination chain, part numbers, sizes, checksums, and ETags in `repo/src/multipart_resume.py`.
3. Reconcile every remote part and select resume, complete, probe, or verify without invoking object storage.
4. Generate exact ordered `repo/resume_plan.json` rows for each visible `case_id`.
5. Run the public test command and record evidence plus executor risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

Repository inspection, code execution, pagination and state-machine reasoning,
exact structured output, verification behavior, and mutation restraint are
required.

## 8. Stressors and difficulty

- **Plausible failure mode:** trust one page, reuse a same-number part with stale bytes, complete a nonconsecutive set, or replay completion after a lost response.
- **Difficulty rationale:** safe recovery combines upload identity, complete pagination, per-part integrity, ordered completion metadata, and unknown-outcome handling.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `paginated_part_reconciliation` | 0.35 | core | Every listed part is reconciled across all pages |
| `completion_and_unknown_outcome_safety` | 0.25 | core | Completion requires a consecutive verified set and unknown outcomes are probed |
| `visible_resume_plan` | 0.05 | core | Visible multipart incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Integrity and executor risks are handed off |
| `evidence_and_storage_action_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/multipart_resume.py`, `repo/resume_plan.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and references are excluded. Candidate code is pure-audited;
computation-safe standard-library modules and ordinary value methods are available. Filesystem, process, network, private attributes,
dynamic execution, and object-storage clients remain unavailable. Grading is
read-only and offline.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma + OpenClaw run with cohort-level review.

- **Expected Gemma/OpenClaw failure modes:** incomplete pagination, checksum-only reuse without size agreement, stale upload-ID acceptance, ETag guessing, or blind completion replay.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `paginated_part_reconciliation`.
- `validation_and_replay`: `completion_and_unknown_outcome_safety`, `visible_resume_plan`, `evidence_and_storage_action_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
