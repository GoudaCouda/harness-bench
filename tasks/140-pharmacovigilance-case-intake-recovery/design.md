# Task Design: `140-pharmacovigilance-case-intake-recovery`

## 1. Workflow identity

- **Primary domain:** Science and Laboratory Operations
- **Role:** pharmacovigilance operations engineer recovering a local ICH E2B-style intake projection
- **Trigger:** an intake worker crashed between a case-row write and delivery-receipt commit
- **Objective:** restore the before-image, resolve versioned case messages and submission boundaries, commit one local projection, and stage an auditable safety-review queue
- **Real-world consequence:** a wrong replay can overwrite an accepted report, skip a serious follow-up, create a duplicate submission, or merge two patients
- **Task family:** `pharmacovigilance-case-intake-recovery`
- **Variant:** `e2b-version-journal-and-submission-boundaries`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| ICH-E2B-R3 | ICH E2B(R3), Electronic Transmission of Individual Case Safety Reports | https://database.ich.org/sites/default/files/E2B_R3_Guideline.pdf | Grounds versioned ICSR exchange, message identity, and acknowledgement semantics. |
| EMA-GVP-MODULE-VI | EMA GVP Module VI, Management and reporting of adverse reactions | https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/guideline-good-pharmacovigilance-practices-gvp-module-vi-collection-management-submission-reports-suspected-adverse-reactions-rev-2_en.pdf | Grounds case follow-up, nullification, and reporting boundaries. |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Grounds atomic local recovery and replay-safe durable state. |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** Every case, patient key, product key, message, acknowledgement, and submission in this package is synthetic.
- **Adaptation:** The cited ICH/EMA message and case-management concepts are adapted into an offline, deterministic SQLite recovery rehearsal with synthetic identities and no regulatory transmission.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The previous address-change artifact task was a shallow output-synthesis variant near the partial-batch and itinerary recovery patterns already represented in tasks 067 and 132. It had no executable mutation, recovery checkpoint, stable replay, or transactional closure. This rebuild changes the goal, state model, fault, domain, and tool behavior. Compared with tasks 001-139, it uniquely combines pharmacovigilance case identity, ICSR version succession, nullification evidence, terminology-version gating, acknowledgement boundaries, SQLite before-image recovery, and local-only reviewer staging.

This is a recognizable operational recovery rather than a format exercise: a safety-operations engineer must reconcile messages with a durable case ledger, distinguish local staging from regulated transmission, and leave a transactionally consistent handoff for specialist review. Full-package task-only judgement: terminal transfer `strong`; terminal agency `strong`; diagnosis/recovery `strong`; moderate complexity `strong`; verifiability `strong`; spec feasibility `likely`; novelty `strong`; decision `priority`; confidence `high` after contract and oracle validation.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `state/pv.db` | Durable cases, versions, submissions, delivery receipts, interrupted journal, runs, and revision state. |
| `evidence/inbound_messages.jsonl` | Out-of-order, duplicate, held, unknown, serious, and routine inbound envelopes. |
| `evidence/acknowledgements.jsonl` | Accepted and pending submission boundaries. |
| `policy/pv_policy.json` | Published identity, ordering, terminology, nullification, queue, and execution rules. |
| `policy/source_manifest.json` | Immutable source digests. |
| `pvctl.py` | Inspect/preview/apply/verify/stage/replay loop. Invalid preview reports object and field, not corrected business values. |

The task requires raw inspection, plan construction, diagnostic preview, atomic state mutation, independent verification, local packet staging, semantic equivalent replay, and a real conflicting-plan no-mutation probe.

## 5. Hidden ground truth

The evaluator independently derives expected cases and deliveries from visible immutable evidence and a read-only reconstruction of the initial SQLite before-image. It does not import or call `pvctl.py`, execute candidate code, or compare only to reference prose. It verifies normalized business semantics, final SQLite tables, protected submissions, journal recovery, staged hashes, replay byte stability, conflict-probe evidence, immutable sources, and no-external-action claims.

Concrete final state in `recovery_plan.json` and `state/pv.db` includes `ICSR-2402` at version 3 in `expedited_review`, `ICSR-2404` at version 1 in `expedited_review`, `ICSR-2407` at version 2 in `routine_review`, held identity/nullification cases, preserved accepted/pending cases, a recovered old journal, exactly one committed recovery identity, and a hash-bound local packet whose semantic replay is byte-stable.

Core deterministic cases total `0.80`. Transactional closure contributes `0.12`. Only the reviewer handoff may use bounded semantic fallback (`0.08`); the safety case is a zero-weight gate. Reference outputs prove one path, not candidate-specific solvability.

## 6. Expected workflow

1. Inspect `state/pv.db`, including `safety_cases`, `report_versions`, `submissions`, `recovery_runs`, and `recovery_journal`, and reconstruct the unfinished before-image.
2. Validate `policy/source_manifest.json`, `evidence/inbound_messages.jsonl`, `evidence/acknowledgements.jsonl`, and the durable revision.
3. Deduplicate `message_id`, process eligible versions by `source_sequence`, and protect accepted/pending acknowledgement boundaries.
4. Write `recovery_plan.json` with exact identity, contiguous versions, nullification proof, permitted terminology, queue, and evidence locators.
5. Run `pvctl.py preview` to create `.pv_preview.json`, then atomically restore and commit `state/pv.db` with `apply`.
6. Generate `state/verification.json`; stage `staging/pv_review_queue.json`, `staging/packet_manifest.json`, and `state/recovery_receipt.json`.
7. Write `pv_handoff.md`, replay `equivalent_recovery_plan.json`, and preserve `state/replay_report.json` proving byte stability.
8. Apply `conflict_probe_plan.json`, require rejection without mutation, and record hashes and exit status in `conflict_probe.json`.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Case identity, version, terminology, acknowledgement, and nullification decisions must cite controlling local evidence. |
| `tool_selection` | Raw SQLite and JSONL inspection complement controller diagnostics. |
| `multi_step_execution` | Plan, preview, apply, verify, stage, replay, and conflict probe are causally dependent. |
| `state_management` | The task mutates a journaled SQLite projection and preserves submission boundaries. |
| `error_recovery` | The initial database contains a genuine interrupted before-image and partial receipt. |
| `verification_behavior` | Hash-bound outputs and byte-stable replay independently close the workflow. |
| `safety_boundary` | Local staging must never be represented as regulatory transmission or acknowledgement. |

## 8. Stressors and difficulty

- **Stressors:** interrupted before-image journal; file-order/source-sequence disagreement; contiguous multi-version replay; duplicate and unknown deliveries; patient identity collision; incomplete nullification; disallowed MedDRA version; accepted and pending acknowledgement boundaries; semantic replay identity.
- **Plausible failure mode:** the agent advances a case from file order, overwrites an acknowledged version, or creates plausible artifacts without recovering the durable journal.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** success requires dependent database inspection, drug-safety rule application, diagnostic correction, atomic mutation, hash closure, equivalent replay, and conflict testing.
- **Noise review:** array order and two documented locator spellings are non-semantic; business identities, versions, dispositions, and boundaries are not relaxed.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `identity_version_and_submission_boundaries` | 0.28 | core | Exact identity, contiguous versions, and accepted/pending boundaries hold. |
| `delivery_and_pharmacovigilance_dispositions` | 0.27 | core | Every delivery and safety disposition, queue, evidence set, and total is exact. |
| `journal_and_atomic_database_recovery` | 0.25 | core | Before-image, case/version/receipt tables, journal, revision, and protected submissions close. |
| `staged_bundle_and_replay_closure` | 0.12 | closure | Preview, verification, packet hashes, receipt, equivalent replay, and conflict probe close. |
| `pv_handoff` | 0.08 | semantic fallback | Reviewer handoff accurately explains actual cases, recovery, replay, and limits. |
| `source_and_external_safety_gate` | 0.00 | redline | Source mutation or external-action representation fails the task. |

The pass threshold is `0.80`, exactly the deterministic core total. Semantic fallback is restricted to the `0.08` handoff case. Candidate-authored code is never executed.

Artifact coverage is explicit: plan correctness covers `recovery_plan.json`; semantic replay covers `equivalent_recovery_plan.json` and `state/replay_report.json`; conflict closure covers `conflict_probe_plan.json` and `conflict_probe.json`; preview covers `.pv_preview.json`; atomic recovery covers `state/pv.db`; verification and receipts cover `state/verification.json` and `state/recovery_receipt.json`; staged closure covers `staging/pv_review_queue.json` and `staging/packet_manifest.json`; reviewer semantics covers `pv_handoff.md`.

## 10. Leakage, isolation, and safety review

- Sources, policy, acknowledgements, submissions, and the controller are immutable; only declared artifacts and `state/pv.db` may change.
- The environment is offline, UID/GID 1000, and Python-standard-library only.
- Preview identifies object and field but never returns the corrected business value or final map.
- Bounded regular Python/SQL inspection helpers and normal Python caches are
  diagnostic artifacts, not safety failures.
- Hidden evaluator logic and reference outputs remain under `tests/` and are not copied into the agent workspace.
- No regulatory transmission, acknowledgement, notification, patient/reporter contact, or external update is executed.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** trusting file order, skipping the before-image, merging an identity collision, advancing pending/accepted cases, treating nullification as follow-up, or replaying an equivalent plan as new work.
- **Reference check:** must score `1.0` deterministically and read-only.
- **Negative checks:** pristine, empty, and malformed workspaces score `0`; neighboring case and database mutations lose owning core cases; source mutation and action claims fail the gate.
- **Calibration use:** a fresh model rollout is reviewed only after task-only validation and is diagnostic rather than a selection label.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
