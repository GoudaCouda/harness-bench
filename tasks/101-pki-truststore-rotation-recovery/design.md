# Task Design: `101-pki-truststore-rotation-recovery`

## 1. Workflow identity

- **Primary domain:** Cybersecurity
- **Role:** platform security engineer
- **Trigger:** a partial mTLS rotation left one service on a stale chain while overlap trust is still required.
- **Objective:** repair the scoped chain and truststore, prove handshake closure, and preserve unaffected services.
- **Real-world consequence:** a wrong removal breaks the worker; a wrong chain breaks billing authentication.
- **Task family:** `cybersecurity-pki-rotation`
- **Variant:** `partial-rotation-recovery`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| CYBER-PKI-01 | NIST SP 800-57 certificate lifecycle concepts | https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final | Trust transition and key-management workflow inspiration |

All certificates, services, identifiers, and events are synthetic. No private logs are used.

- **Private user logs:** None; no private user or production operational logs were used.
- **Synthetic-data statement:** Every certificate, service, timestamp, identifier, and state transition is synthetic.
- **Adaptation:** Certificate-lifecycle guidance becomes a synthetic interrupted
  mTLS rotation where leaf/chain roles, overlap trust, preserved services,
  append-only audit state, handshakes, and retry evidence must agree.

## 3. Real-workflow justification

The agent must inspect a live-like state, distinguish leaf, intermediate, and root roles, apply a scoped plan through a controller, observe handshake failures, preserve overlap trust, and prove an idempotent retry. This is not certificate trivia or a report-only task.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `certificates.json` | Certificate subjects, issuers, roles, and validity windows |
| `services.json` | Expected service identity and rotation scope |
| `rotation_policy.md` | Trust overlap, scope, and safety rules |
| `pki_state.json` | Mutable offline service/ truststore state |
| `pki_ctl.py` | Status, apply, and verification controller |

## 5. Hidden ground truth

The hidden grader independently verifies the final service state, untouched out-of-scope objects, candidate-bound state/report hashes, single append-only audit event, and non-production handoff. It never trusts `status: pass` alone.

The final state connects `certificates.json` to `rotation_plan.json`,
`pki_state.json`, `pki_audit.jsonl`, `handshake_report.json`, and
`rotation_handoff.md`; service keys, revision state, audit event, and report
digests are independently verified.

## 6. Expected workflow

1. Query `pki_ctl.py` status and inspect certificate relationship keys.
2. Create a minimal scoped `rotation_plan.json` before changing state.
3. Apply it and inspect `pki_state.json` plus `pki_audit.jsonl` feedback.
4. Generate `handshake_report.json`; repair any chain/trust state errors.
5. Reapply to prove idempotency and write `rotation_handoff.md`.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Correctness requires status, apply, verify, and retry stages. |
| `state_management` | The state revision and unaffected services must be preserved. |
| `error_recovery` | A bad chain or trust removal is observable through the verifier. |
| `verification_behavior` | Handshake and audit digests are independently checked. |
| `safety_boundary` | The task is offline and must not claim real issuance or rollout. |

## 8. Stressors and difficulty

Difficulty comes from a coupled partial rotation, two trust roots, a still-dependent worker, immutable unrelated state, and idempotent audit behavior. Adding the new root everywhere or removing the old root is a plausible but unsafe shortcut.

- **Plausible failure mode:** remove old trust globally or replace every chain,
  fixing billing while breaking the still-dependent worker or unrelated state.
- **Difficulty rationale:** scoped chain repair, overlap preservation, revisioned
  audit, handshake closure, and idempotent retry are dependent outcomes.

## 9. Oracle design

| Case | Weight | Observable outcome |
|---|---:|---|
| `billing_chain_and_trust_rotation` | 0.30 | Valid new leaf/intermediate/root and passing handshake report |
| `overlap_and_unrelated_service_preservation` | 0.25 | Worker overlap and reporting state unchanged |
| `digest_bound_idempotent_audit` | 0.25 | One revision, one audit event, candidate-bound digests |
| `security_handoff` | 0.20 | Accurate operational and non-production handoff |
| `safety_and_input_integrity` | gate | Protected evidence and external-action boundary |

Required artifacts are covered as complete blocks: `rotation_plan.json`;
`pki_state.json` with `pki_audit.jsonl`; `handshake_report.json`; and the bounded
`rotation_handoff.md`. Isolated field correctness does not earn independent
credit outside those business results.

## 10. Leakage, isolation, and safety review

The controller reads only visible policy and data. Hidden tests/reference are outside the workspace. No secret values or live endpoints exist. Only declared state/output files may change.

## 11. Pilot plan

Review the first valid observation, whether the controller is used, apply/verify feedback, retry behavior, unrelated-state preservation, and score attribution. A full score with the entire state loop is acceptable; a one-shot hand-authored report is not.

- **Expected Gemma/OpenClaw failure modes:** confuse root/intermediate roles,
  remove overlap trust, mutate an unrelated service, hand-author handshake
  evidence, or skip the idempotent retry.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
