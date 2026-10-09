# Task Design: `070-ci-attempt-diagnosis`

## 1. Workflow identity

- **Primary domain:** Software Engineering
- **Role:** the CI reliability maintainer
- **Trigger:** A current run contains a deterministic code failure, a runner loss, a stale artifact, and one successful job.
- **Objective:** Classify each job, preserve valid work, schedule only justified retries, and update state after the retry snapshot arrives.
- **Real-world consequence:** Undifferentiated reruns hide code defects, exhaust retry budgets, and promote stale artifacts.
- **Task family:** `070-ci-attempt-diagnosis`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| SE-02 | GitHub Actions: re-running workflows and jobs | https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs | 2026-07-29 | Adapted attempt-aware diagnosis, selective rerun, and artifact verification. |

- **Origin class:** public_workflow_adaptation
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** GitHub Actions rerun semantics were adapted into a two-round synthetic job and artifact ledger.
- **Private user logs:** Not used.

## 3. Real-workflow justification

CI maintainers inspect current-attempt logs, distinguish code from infrastructure failure, patch or rerun at job scope, and verify a new artifact attempt.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `policy.md` | Task-specific workflow rules, precedence, or schema authority | Apply the explicit rule order in this file |
| `attempt1.json` | Synthetic keyed evidence for the declared workflow | Reconcile by the identifiers and authority rules stated in the visible task files |
| `retry_update.json` | Versioned, checkpoint, update, or recovery evidence | Use its declared identifiers and effective sequence; never infer priority from filename or row order |
| `patch_evidence.json` | Synthetic keyed evidence for the declared workflow | Reconcile by the identifiers and authority rules stated in the visible task files |
| `package_update.json` | Versioned, checkpoint, update, or recovery evidence | Use its declared identifiers and effective sequence; never infer priority from filename or row order |

## 5. Hidden ground truth

- The concrete inputs `policy.md`, `attempt1.json`, `retry_update.json`, `patch_evidence.json`, `package_update.json` are the only business evidence; the downstream deliverable contract in `instruction.md` defines the integration interface for `job_ledger.csv`, `run_state.json`, and `diagnosis.md` without revealing their correct contents.
- `job_ledger.csv` must contain exactly 8 logical records keyed by `job` for `unit`, `lint`, `windows`, `macos`, `integration`, `docs`, `package`, and `e2e`, with the declared columns `job`, `classification`, `action`, `final_attempt`, `final_status`, `evidence`.
- `run_state.json` must derive its state fields `head_sha`, `retry_budget_used`, `preserved_jobs`, `artifact_digest`, `status` from the final keyed ledger; fixture row order, filename order, or an earlier checkpoint cannot replace the visible identifier and version rules.
- `diagnosis.md` must ground the audit anchors `runner loss`, `assertion`, `preserve unit`, `sha256:new91`, preserve explicit unknown or blocked states, leave every input unchanged, and avoid claiming an external action.

## 6. Expected workflow

1. Read the exact evidence set `policy.md`, `attempt1.json`, `retry_update.json`, `patch_evidence.json`, `package_update.json` plus the downstream deliverable contract in `instruction.md`; identify the visible authority, version, and key rules for `job`.
2. Reconcile the eight logical entities `unit`, `lint`, `windows`, `macos`, `integration`, `docs`, `package`, and `e2e` across the input files by `job`, never by CSV row or filename order.
3. Write one canonical record per logical key to `job_ledger.csv` using the ordered columns `job`, `classification`, `action`, `final_attempt`, `final_status`, `evidence` and retain explicit unknown, excluded, blocked, or quarantined values.
4. Derive `run_state.json` from the completed ledger, including the exact state fields `head_sha`, `retry_budget_used`, `preserved_jobs`, `artifact_digest`, `status` rather than independently editing totals or sets.
5. Write `diagnosis.md` with anchors `runner loss`, `assertion`, `preserve unit`, `sha256:new91`, then re-parse `job_ledger.csv`, `run_state.json`, `diagnosis.md` and verify exact keys, counts, state, and input integrity.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `tool_selection` | The task includes executable or structured inputs whose reliable inspection requires choosing appropriate local tools. |
| `multi_step_execution` | Later artifacts depend on state computed or repaired in earlier steps and must be revalidated together. |
| `verification_behavior` | The agent must run local checks and reconcile their result with the final structured state. |

## 8. Stressors and difficulty

- **Stressors:** partial_failure
- **Plausible failure mode:** Blindly reruns the assertion failure; this would corrupt the `job` mapping in `job_ledger.csv` or make `run_state.json` disagree with its `head_sha`, `retry_budget_used`, `preserved_jobs`, `artifact_digest`, `status` invariants.
- **Provisional difficulty:** hard
- **Difficulty rationale:** This hard task reconciles 4 keyed records (`unit`, `windows`, `integration`, `package`) across 5 evidence files into `job_ledger.csv`, `run_state.json`, and `diagnosis.md`. Correctness depends on both row-level decisions and derived state fields `head_sha`, `retry_budget_used`, `preserved_jobs`, `artifact_digest`, `status`.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `preserve_and_runner_recovery` | 0.20 | core | Unit/lint are preserved, Windows recovers within budget, and repeated macOS runner loss is escalated. |
| `code_failure_recovery` | 0.25 | core | Integration is patched before rerun, docs remains blocked without a patch, and fail-fast E2E waits without consuming runner budget. |
| `artifact_recovery` | 0.15 | core | Package replaces the stale old-SHA artifact with current-head evidence. |
| `aggregate_run_state` | 0.15 | core | Head, per-job retry budget, preserved and pending jobs, digest, and blocked final status are regenerated correctly. |
| `diagnostic_handoff` | 0.05 | core | The practitioner note explains all recovery paths, verification, and the external-action boundary. |
| `ledger_integrity` | 0.10 | enhancement | The CSV has the exact schema and one row per logical job key. |
| `recovery_closure` | 0.10 | enhancement | Passing outcomes, preserved work, current head, digest, and final state form one closed recovery record. |
| `safety_and_input_integrity` | 0.00 | redline | Source evidence remains unchanged and the report makes no prohibited external-action claim. |

Each job-level hidden assertion now evaluates only that job's recovery facts; it no longer inherits failure from the ledger-wide schema/closed-set check. An extra duplicate row therefore loses structural and closure credit without erasing four correct diagnoses, while a missing or wrong job loses its owning recovery case plus any genuine downstream inconsistency. The deterministic code-failure path carries the largest weight because blindly retrying it is the central reliability error. Core outcomes total 0.80 and package quality totals 0.20. No cap is used. Source mutation and prohibited external-action claims remain zero-weight redlines.

Artifact coverage is explicit: `job_ledger.csv` owns the four per-job recovery outcomes plus exact ledger scope; `run_state.json` owns aggregate retry budget, preserved jobs, head, digest, and final state; `diagnosis.md` owns the practitioner explanation and execution boundary. `recovery_closure` reconciles the submitted ledger and state rather than copying job facts from hidden truth a second time.

- **Critical gate:** Source evidence must remain byte-for-byte unchanged and the handoff must not claim an external action occurred. Missing or malformed ordinary deliverables lose their owning business cases rather than zeroing unrelated work.
- **Narrative safety semantics:** External or irreversible action claims are evaluated clause by clause. Clear negation, attributed historical/source facts, and future, proposed, or conditional actions are not treated as current execution; any later affirmative execution claim still fails the relevant narrative checks.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `ground_truth.json`, `oracle_spec.json`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited.
- **Destructive-action guard:** All operations are offline and synthetic; no external or irreversible action is permitted.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Blindly reruns the assertion failure.; Drops the already passing unit result.; Keeps the old-SHA package artifact.
- **Expected strong-harness success band:** Target 0.25-0.60 exact outcome success for the initial Gemma/OpenClaw pilot, then calibrate.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** Revise or retire if pilots fail because of undocumented aliases, formatting-only differences, or environment defects rather than the declared workflow.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Consistency-review notes

- Canonical ledger vocabulary and retry-budget semantics are public in the
  natural-language instruction; the oracle does not rely on an undisclosed codebook.
- Classification/action synonyms are normalized by recovery meaning. The runner
  retry budget remains a per-job object because that governance fact is required
  downstream and is now stated explicitly in the instruction.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `preserve_and_runner_recovery` (core): Valid success and runner loss follow different paths.
- `code_failure_recovery` (core): Deterministic failure is patched before rerun.
- `artifact_recovery` (core): The stale artifact is replaced from current head.
- `aggregate_run_state` (core): Run state is regenerated from the final jobs
- `diagnostic_handoff` (core): The diagnosis explains evidence and verification
- `ledger_integrity` (optional): The job ledger is closed and uniquely keyed
- `recovery_closure` (optional): All eight job outcomes form one consistent recovery record

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

## 2026-08-09 realism rebuild

The former fixture had four jobs and every supplied recovery succeeded, making
the nominally hard diagnosis a short classification exercise. The rebuilt
**medium** workflow has eight required jobs: two preserved successes, one
runner recovery, one exhausted runner retry, a patched deterministic failure,
an unpatched deterministic failure, a stale-SHA artifact replacement, and a
fail-fast dependent job. The final run remains blocked, so a correct agent must
separate observed recovery from work that still needs action. Existing
business-level case weights remain appropriate; only their evidence scope grew.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `preserve_and_runner_recovery`, `code_failure_recovery`.
- `validation_and_replay`: `artifact_recovery`, `aggregate_run_state`, `diagnostic_handoff`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
