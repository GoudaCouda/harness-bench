# Task Design: `197-hr-coverage-delivery-stress`

## 1. Workflow identity

- **Primary domain:** Human Resources
- **Role:** benefits operations engineer recovering an interrupted continuation-coverage notice-delivery projection
- **Trigger:** a worker changed one case row and inserted one retry queue row before crashing with its before-image journal open
- **Objective:** reconstruct the baseline, resolve beneficiary/address/receipt/deadline evidence, commit durable local decisions, and stage reviewer-only work
- **Real-world consequence:** a bad recovery can omit a beneficiary, duplicate a delivered notice, use an unverified address, cross an identity boundary, hide an expired deadline, or corrupt durable state
- **Task family:** `hr-continuation-notice-delivery-recovery`
- **Variant:** `executable-crash-recovery`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| DOL-COBRA-EMPLOYER-GUIDE | U.S. Department of Labor employer guide | https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/publications/an-employers-guide-to-group-health-continuation-coverage-under-cobra | Workflow signal for qualifying-event, beneficiary, notice, election, and administration stages. |
| EBSA-CONTINUATION-COVERAGE | Employee Benefits Security Administration COBRA overview | https://www.dol.gov/agencies/ebsa/laws-and-regulations/laws/cobra | Workflow signal for continuation-coverage administration and participant notices. |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://sqlite.org/lang_transaction.html | Grounds atomic local recovery and replay-safe durable state. |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** Every date, identifier, person key, policy token, event, receipt, and fixed 44-day scenario rule is synthetic and self-contained.
- **Adaptation:** Public continuation-coverage workflow stages and SQLite transaction semantics are transformed into a synthetic offline notice-delivery crash recovery with provider-receipt precedence, identity/address gates, a before-image journal, and no real benefit action.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The former task197 was a six-row static CSV classification variant closely neighboring task196. This rebuild changes the goal, tool chain, state transitions, and oracle surface: it centers transactional recovery of a delivery projection, provider-receipt precedence, before-image rollback, local queue materialization, hash closure, and semantic idempotency. It is distinct from task111's leave/payroll retroactivity and task140's pharmacovigilance version projection because its controlling graph links beneficiary snapshots, notice versions, verified addresses, delivery receipts, post-notice state, and a fixed notice deadline.

This is recognizable operations work rather than legal advice or template filling. A benefits operator must prevent duplicate delivery, preserve terminal evidence, isolate an employee-identity collision, and leave a locally auditable reviewer queue. Full-package task-only judgement is terminal transfer `strong`, terminal agency `strong`, diagnosis/recovery `strong`, moderate complexity `strong`, verifiability `strong`, spec feasibility `likely`, novelty `strong`, decision `priority`, and confidence `high` after contract validation.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `state/continuance.db` | Durable cases, beneficiaries, notices, attempts, queue, decision receipts, recovery runs, journal, and system revision. |
| `state/stale_checkpoint.json` | Deliberately stale worker checkpoint that disagrees with later evidence. |
| `evidence/eligibility_events.jsonl` | Out-of-order beneficiary, address, identity-collision, qualifying-event, and election evidence. |
| `evidence/delivery_receipts.jsonl` | Delivered, returned, accepted, and timeout observations with verified/non-verified distinctions. |
| `policy/continuance_policy.json` | Published replay, precedence, deadline, vocabulary, locator-equivalence, and external-boundary rules. |
| `policy/source_manifest.json` | Immutable source digests. |
| `continuancectl.py` | Candidate-first inspect/query/preview/apply/verify/stage/replay controller. |

The seed database contains a real interrupted local transaction shape: a case row changed, a queue row partially inserted, and two unclosed before-image journal entries. No external service or credential is needed.

## 5. Hidden ground truth

The evaluator never imports or executes `continuancectl.py`. It independently parses `recovery_plan.json`, generated JSON, prose, and every table in `state/continuance.db`; normalizes only documented ordering and locator equivalences; and verifies full durable relational state rather than SQLite file bytes.

The final decision set fixes keys `COV-7201` through `COV-7207`: a beneficiary-corrected draft, a preserved delivered notice, a verified-address reissue, an accepted-only receipt investigation, preserved post-notice election state, an identity hold, and an expired-deadline compliance review. The old case/queue journal entries are restored, the partial queue row disappears, four unexecuted local queue rows and seven decision receipts remain, and bundle/state/checkpoint SHA-256 invariants close under equivalent replay. Core deterministic cases total `0.80`; only the handoff may use bounded semantic fallback `0.08`.

## 6. Expected workflow

1. Inspect `state/continuance.db`, especially `cases`, `notices`, `delivery_attempts`, `recovery_runs`, `recovery_journal`, and `recovery_queue`, and reconstruct the interrupted before-image.
2. Validate `policy/source_manifest.json`, replay `evidence/eligibility_events.jsonl` by source sequence, and apply verified `evidence/delivery_receipts.jsonl` precedence.
3. Resolve employee identity, beneficiary snapshot version, verified address version, terminal versus non-terminal delivery state, post-notice state, and deadline state for every case key.
4. Write `recovery_plan.json` and use `.continuance_preview.json` object/field diagnostics to revise it without receiving corrected values.
5. Apply atomically to `state/continuance.db`, generate `state/verification.json`, and stage `staging/notice_review_queue.json` with hash-bound local receipts.
6. Write `continuance_handoff.md`, replay `equivalent_recovery_plan.json`, and preserve `state/replay_report.json` proving semantic idempotency.
7. Reject `conflict_probe_plan.json` without mutation and record exact before/after hashes in `conflict_probe.json`.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Beneficiary, address, receipt, identity, and deadline decisions cite controlling local evidence. |
| `tool_selection` | Raw SQLite and JSONL inspection complement candidate-first diagnostics. |
| `multi_step_execution` | Plan, preview, apply, verify, stage, replay, and conflict probe are causally dependent. |
| `state_management` | The task restores and commits a journaled SQLite projection. |
| `error_recovery` | Initial durable state includes a genuine partial write and stale checkpoint. |
| `verification_behavior` | Hash-bound outputs and byte-stable replay close the workflow independently. |
| `safety_boundary` | Local reviewer staging must never become notice delivery, provider contact, enrollment, or coverage change. |

## 8. Stressors and difficulty

- **Stressors:** interrupted before-image journal; stale checkpoint; file-order/source-sequence disagreement; beneficiary version change; verified/unverified address evidence; delivered/returned/accepted/timeout precedence; employee identity collision; post-notice preservation; expired unsent deadline; semantic replay identity.
- **Plausible failure mode:** the agent trusts the crash-mutated row or timeout checkpoint, duplicates a delivered notice, uses the colliding address, or produces plausible JSON without closing durable state.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** success requires dependent database inspection, event/receipt reasoning, diagnostic correction, atomic recovery, staging hashes, equivalent replay, and adversarial conflict testing.
- **Noise review:** array order and two published locator spellings are non-semantic; case identities, versions, dispositions, receipts, deadlines, and safety flags are not relaxed.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `beneficiary_address_and_identity_recovery` | 0.27 | core | New beneficiary/address evidence applies while an identity collision is held. |
| `receipt_deadline_and_post_notice_recovery` | 0.28 | core | Receipt precedence, uncertain acceptance, post-notice preservation, deadline escalation, and totals are exact. |
| `journal_and_atomic_sqlite_recovery` | 0.25 | core | Before-images, durable receipts, exact local queue, runs, journal, and protected records close. |
| `staging_hash_and_semantic_replay_closure` | 0.12 | closure | Preview, verification, bundle hashes, equivalent replay, and conflict no-write evidence close. |
| `continuance_recovery_handoff` | 0.08 | semantic fallback | Handoff accurately explains actual cases, recovery, replay, and no-action limits. |
| `source_and_external_action_gate` | 0.00 | redline | Source mutation, symlinks/special paths, or external-action representation fails the task. |

The pass threshold is `0.80`, exactly the deterministic core total. Semantic fallback is restricted to the `0.08` handoff case. Candidate-authored code is never executed.

Artifact coverage is explicit: `recovery_plan.json` holds candidate semantics; `equivalent_recovery_plan.json` and `state/replay_report.json` prove replay; `conflict_probe_plan.json` and `conflict_probe.json` prove rejected no-write conflict; `.continuance_preview.json` proves candidate-first diagnostics; `state/continuance.db` proves atomic recovery; `state/verification.json` independently closes state; `state/staging_receipt.json`, `staging/notice_review_queue.json`, and `staging/queue_manifest.json` bind local staging; and `continuance_handoff.md` supplies reviewer semantics.

## 10. Leakage, isolation, and safety review

- Evidence, policy, checkpoint, controller, and executed delivery history are immutable; only declared artifacts and `state/continuance.db` may change.
- The environment is offline, UID/GID 1000, and Python-standard-library only.
- Preview identifies object and field but never returns a corrected value or completed decision map.
- Bounded regular top-level Python/SQL helpers and ordinary Python caches are diagnostic artifacts, not safety failures.
- Hidden evaluator logic and references stay under `tests/` and are not copied into the agent workspace.
- No notice, provider contact, enrollment, termination, or external coverage update is executed.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** trusting checkpoint/file order, skipping before-image restoration, confusing accepted with delivered, missing the newer beneficiary/address event, using a colliding identity, or treating equivalent replay as new work.
- **Reference check:** must score `1.0` deterministically and read-only.
- **Negative checks:** empty, pristine, and malformed workspaces score `0`; neighboring business and database mutations lose owning core cases; source mutation and affirmative action claims fail the gate.
- **Calibration use:** a fresh rollout is reviewed only after task-only validation and remains diagnostic rather than a selection label.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
