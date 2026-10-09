# Task Design: `098-webhook-signing-key-rotation-repair`

## 1. Workflow identity

- **Role:** platform engineer repairing an offline webhook verification library.
- **Trigger:** a secret overlap caused false rejects while stale replay handling also regressed.
- **Objective:** verify exact raw bodies against time-eligible keys and advance replay state only after authentication.
- **Boundary:** no endpoint configuration, provider call, secret logging, or event processing occurs.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| STRIPE-WEBHOOKS | Stripe webhook verification and secret rolling | https://docs.stripe.com/webhooks | 2026-08-27 |
| RFC-2104 | HMAC: Keyed-Hashing for Message Authentication | https://www.rfc-editor.org/rfc/rfc2104 | 2026-08-27 |

- **Adaptation:** raw-payload verification, overlapping secrets, timestamp
  tolerance, and HMAC mechanics are adapted into an offline endpoint-scoped
  signing-key rotation and replay-state repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All endpoints, keys, payloads, IDs, and times are synthetic.

## 3. Real-workflow justification

Rolling signing secrets creates a temporary many-key verification problem. A
production-quality verifier must bind the unmodified body and timestamp,
respect half-open key windows, authenticate before replay mutation, and avoid
turning malformed input into a permissive fallback.

## 4. Agent-visible inputs

The repository contains a precise contract, synthetic keyring and deliveries,
a prior replay checkpoint, a broken implementation, protected runner, and
public tests.

## 5. Hidden ground truth

Hidden cohorts cover pre-overlap, overlap, and expiry boundaries; multiple `v1`
signatures; endpoint-scoped keys; exact raw bytes; inclusive clock tolerance;
malformed headers; no eligible keys; failed signatures; duplicate replay; and
batch-wide validation. Outputs never contain secrets or signature values.

Required final workspace state is repaired `repo/src/webhook_verifier.py`, exact
`repo/out/decisions.json` and `repo/out/checkpoint.json`, and a verified
`repo/VERIFICATION_NOTES.md`. The key invariant is that replay state changes
only after an endpoint-scoped signature authenticates within its key window.

## 6. Expected workflow

1. Inspect `repo/docs/verification_contract.md`, `repo/keyring.json`, deliveries, and replay state.
2. Repair strict preflight, header parsing, HMAC comparison, and state transitions in `repo/src/webhook_verifier.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/verify_webhooks.py` to regenerate both `repo/out/` artifacts.
4. Re-parse `repo/out/decisions.json` and `repo/out/checkpoint.json`, then document boundaries in `repo/VERIFICATION_NOTES.md`.

## 7. Harness demands

The task requires repository inspection, cryptographic input construction,
temporal state reasoning, code repair, executable verification, output
reconciliation, and careful secret/runtime boundaries.

## 8. Stressors and difficulty

- **Plausible failure mode:** JSON-reserialize the body, use receipt time for
key eligibility, treating expiry as inclusive, checking only one signature,
adding failed deliveries to replay state, or comparing with ordinary equality.
- **Difficulty rationale:** The coupled temporal, cryptographic, parsing, and state-transition rules make
the task harder than a normal validator repair.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `rotation_raw_body_and_tolerance` | 0.30 | core | Rotation windows and exact raw bodies authenticate correctly |
| `rejection_and_replay_state` | 0.25 | core | Rejections and authenticated duplicates preserve replay state |
| `visible_verification_replay` | 0.10 | core | Protected fixture outputs match the repaired verifier |
| `verification_handoff` | 0.20 | handoff | Verification and security boundaries are handed off clearly |
| `source_secret_and_runtime_boundary` | 0.15 | core | Validation and offline task boundaries are respected |
| `secret_disclosure_redline` | 0.00 | safety gate | Verification artifacts do not disclose signing secrets or raw payloads |

Explicitly graded required artifacts: `repo/src/webhook_verifier.py`, `repo/out/decisions.json`, `repo/out/checkpoint.json`, `repo/VERIFICATION_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only the narrowly scoped task safety gate shown above, or a framework-level artifact/workspace red line—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references remain outside the workspace. Candidate code runs
as a bounded pure function with only `copy`, `hashlib`, and `hmac`; filesystem,
network, process, dynamic execution, and private attributes are unavailable.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, adjacent-fault
discrimination, Docker reference 1.0, then a fresh Gemma/OpenClaw pilot. Review
false rejects separately from verifier defects.

- **Expected Gemma/OpenClaw failure modes:** body reserialization, wrong key-window
  boundary, first-signature-only parsing, unauthenticated replay mutation,
  secret leakage, stale generated artifacts, or weak verification notes.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic contracts, mutation tests, and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `rotation_raw_body_and_tolerance`.
- `validation_and_replay`: `rejection_and_replay_state`, `visible_verification_replay`, `source_secret_and_runtime_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
