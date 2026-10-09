# Task Design: `150-webauthn-counter-risk-repair`

## 1. Workflow identity

- **Role:** identity-platform engineer repairing relying-party assertion state.
- **Canonical domain:** Compliance
- **Trigger:** synced passkeys are false-positive clone detections and rejected assertions corrupt counters.
- **Objective:** replay assertion facts into deterministic credential risk and decisions.
- **Boundary:** captured, already-verified WebAuthn assertion facts are reconciled locally; cryptographic verification and browser/IdP mutation remain outside scope.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| W3C-WEBAUTHN | W3C Web Authentication Level 3 | https://www.w3.org/TR/webauthn-3/ | 2026-08-28 |

- **Adaptation:** sign counter, backup eligibility/state, RP ID, origin, and user verification become a deterministic relying-party reducer.
- **Private user logs:** None.
- **Synthetic-data statement:** All credentials, assertions, identities, counters, and origins are synthetic.

## 3. Real-workflow justification

Relying parties persist authenticator state. Counter regression can signal a
device clone, but synchronized passkeys require policy-aware handling, and an
untrusted assertion must not overwrite trusted state.

## 4. Agent-visible inputs

Contract, credentials, assertions, policy, broken code, runner, and public tests.

## 5. Hidden ground truth

Hidden cases cover trust-check precedence, revoked/unknown credentials, user and
scope mismatch, UV, immutable backup eligibility, backup-state changes, zero,
advanced and regressed counters, device/synced policy, risk escalation,
rejected-update boundaries, malformed input, and immutability. Required final
state is repaired `repo/src/assertion_risk.py`, exact
`repo/out/credentials.json`, exact `repo/out/decisions.json`, and verified
`repo/AUTH_NOTES.md`; rejected trust checks preserve every credential field.

## 6. Expected workflow

1. Inspect `repo/docs/assertion_contract.md`, `repo/credentials.json`, `repo/assertions.json`, and `repo/policy.json`.
2. Repair trust precedence, counter classification, backup state, and atomic updates in `repo/src/assertion_risk.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/assess_assertions.py` to regenerate both `repo/out/` artifacts.
4. Re-parse outputs and document semantics and the identity boundary in `repo/AUTH_NOTES.md`.

## 7. Harness demands

Inspection, security precedence reasoning, stateful coding, verification,
artifact reconciliation, and handoff are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** update before trust checks, conflate device and synced counters, allow eligibility drift, or de-escalate risk.
- **Difficulty rationale:** ordered assertions share credential state while trust precedence and counter policy create distinct update boundaries.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `trust_precedence_and_atomic_updates` | 0.25 | core | Trust failures reject without corrupting credential state |
| `counter_backup_and_risk_policy` | 0.30 | core | Counters backup signals and risk policies reconcile correctly |
| `assertion_replay` | 0.10 | core | Protected credential and decision artifacts match the repaired reducer |
| `auth_handoff` | 0.20 | handoff | Authentication state semantics and offline boundaries are handed off clearly |
| `source_and_identity_boundary` | 0.15 | core | Pure implementation and malformed-input validation are respected |
| `safety_and_input_integrity` | gate | gate | Protected inputs, filesystem redlines, and real identity/cryptography claims are checked |

Explicitly graded required artifacts: `repo/src/assertion_risk.py`, `repo/out/credentials.json`, `repo/out/decisions.json`, `repo/AUTH_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or restricted-compute mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases/reference stay outside the workspace. Candidate code is a bounded
pure function without external access.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker reference 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** trust-order inversion, rejected
  counter overwrite, synced-passkey false rejection, stale outputs, or live-auth claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `trust_precedence_and_atomic_updates`.
- `validation_and_replay`: `counter_backup_and_risk_policy`, `assertion_replay`, `source_and_identity_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
