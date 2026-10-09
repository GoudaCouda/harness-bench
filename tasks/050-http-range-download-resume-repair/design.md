# Task Design: `050-http-range-download-resume-repair`

## 1. Workflow identity

- **Role:** release engineer repairing an artifact fetcher.
- **Trigger:** retries append incompatible HTTP responses to staged bytes.
- **Objective:** reconcile checkpoint, validator, range, and digest evidence.
- **Boundary:** no network request, publication, or deployment is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| HTTP-SEMANTICS-RFC9110 | RFC 9110 HTTP Semantics | https://www.rfc-editor.org/rfc/rfc9110.html | 2026-08-27 |

- **Adaptation:** HTTP Range, Content-Range, If-Range, validator, and status semantics become a deterministic offline recovery decision over captured response evidence.
- **Private user logs:** None; manifests, validators, hashes, and incidents are synthetic.

## 3. Real-workflow justification

Download managers and build systems routinely resume large artifacts. Treating a
full response as a range, trusting a stale temp file, or accepting 416 by offset
alone can silently publish corrupted binaries despite green happy-path tests.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/resume_contract.md` | authoritative response/checkpoint contract |
| `repo/src/range_resume.py` | broken decision implementation |
| `repo/resume_cases.json` | visible captured incidents |
| `repo/tests/test_public.py` | public regressions |

## 5. Hidden ground truth

Independent hidden cohorts cover 200 replacement, valid and invalid 206 ranges,
changed validators, unsafe checkpoints, exact 416 completion, final digest
mismatch, unsupported status, malformed strong ETags, and immutable inputs.
They evaluate the agent-visible `repo/src/range_resume.py` against independent
cases. Required final state includes the repaired source plus exact
`repo/resume_report.json` and grounded `repo/REPAIR_NOTES.md`.

## 6. Expected workflow

1. Read `repo/docs/resume_contract.md` and inspect manifest, checkpoint, and response state.
2. Run `repo/tests/test_public.py` against `repo/src/range_resume.py` and reproduce unsafe decisions.
3. Repair `repo/src/range_resume.py` across the 200, 206, and 416 branches.
4. Generate `repo/resume_report.json` from `repo/resume_cases.json` in case order.
5. Record exact verification and atomic-persistence risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

Repository inspection, code execution, exact JSON generation, multi-branch state
reasoning, verification, and external-action restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** append 200, trust weak/stale ETag, mishandle inclusive
  range length, accept 416 by size alone, or skip the assembled digest.
- **Difficulty rationale:** correctness depends on relationships across three
  records and status-specific rules rather than any single field.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `response_branch_and_validator` | 0.35 | core | HTTP response branches and strong validators are reconciled |
| `checkpoint_range_and_digest` | 0.25 | core | Checkpoint, Content-Range, and digest evidence agree |
| `visible_resume_report` | 0.05 | core | Visible transfer incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Resume repair and residual risk are handed off |
| `source_and_workspace_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/range_resume.py`, `repo/resume_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and reference files are excluded. Candidate code is pure-audited;
only task-whitelisted `re` is importable, while filesystem, network, process,
private-attribute, and dynamic-call capabilities remain unavailable. The grader
workspace is read-only and network-disabled.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks and a Docker
reference pass, then run Gemma + OpenClaw and inspect branch-level failures.

- **Expected Gemma/OpenClaw failure modes:** incomplete 416 proof, weak validator acceptance,
  incorrect range arithmetic, report drift, or thin handoff notes.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `response_branch_and_validator`.
- `validation_and_replay`: `checkpoint_range_and_digest`, `visible_resume_report`, `source_and_workspace_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
