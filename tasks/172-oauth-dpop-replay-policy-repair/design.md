# Task Design: `172-oauth-dpop-replay-policy-repair`

## 1. Workflow identity

- **Role:** identity-platform engineer repairing a DPoP verification policy.
- **Canonical domain:** Compliance
- **Trigger:** a resource server accepts signed proofs without request, token, nonce, or replay binding.
- **Objective:** accept or reject each proof in strict security precedence and update replay state transactionally.
- **Boundary:** standards-shaped, pre-parsed proof evidence is evaluated locally after cryptographic verification; no network activity occurs.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| RFC9449-DPOP | RFC 9449 OAuth 2.0 Demonstrating Proof of Possession | https://www.rfc-editor.org/rfc/rfc9449.html | 2026-08-28 |

- **Adaptation:** JOSE type/algorithm/public-key checks, method/URI/time binding, token hash/thumbprint, nonce, and stateful `jti` replay prevention are combined in an offline gate.
- **Private user logs:** None.
- **Synthetic-data statement:** All requests, proofs, keys, hashes, nonces, and replay entries are synthetic.

## 3. Real-workflow justification

DPoP prevents a stolen bearer token or proof from being replayed at another
endpoint, method, key, time, or request. Distributed services also need bounded
and deterministic replay-cache behavior.

## 4. Agent-visible inputs

Contract, request/proof ledger, replay cache, policy, broken source, runner, and public tests.

## 5. Hidden ground truth

Cases cover missing proofs, typ/algorithm/public-key/signature evidence,
method and normalized URI binding, inclusive clock windows, JTI size, key and
access-token hash binding, nonce policy, expired versus active replay entries,
same-batch replay, cache retention/order, schemas, purity, and immutability.
Required final state is repaired `repo/src/dpop_policy.py`, exact
`repo/out/decisions.json`, `repo/out/replay_cache.json`, and
`repo/out/summary.json`, plus verified `repo/DPoP_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/dpop_contract.md`, inputs, broken source, and public tests.
2. Repair validation, precedence, binding, and replay-cache updates in `repo/src/dpop_policy.py`.
3. Run `repo/tests/test_public.py` and `python bin/verify_dpop.py`; regenerate and re-parse all outputs.
4. Document proof/token/replay semantics, verification, and the offline boundary in `repo/DPoP_NOTES.md`.

## 7. Harness demands

Repository inspection, security reasoning, stateful coding, executable
verification, artifact reconciliation, and an auditable identity handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** trust signature alone, compare query text, skip `ath` or nonce, accept future proofs, or insert rejected JTIs.
- **Difficulty rationale:** independent proof, request, token, time, and replay bindings require fail-closed precedence and transactional state.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `proof_request_and_token_binding` | 0.30 | core | Proof request and token bindings fail closed in exact precedence |
| `nonce_and_replay_state` | 0.25 | core | Nonce and replay state are bounded and transactional |
| `dpop_replay` | 0.10 | core | Protected decisions cache and summary match the repaired gate |
| `dpop_handoff` | 0.20 | handoff | DPoP binding and replay semantics are handed off clearly |
| `source_and_identity_boundary` | 0.15 | core | Validation and offline task boundaries are respected |
| `safety_and_input_integrity` | 0.00 | gate | Protected proof evidence, workspace red lines, and prohibited real-token/key/identity actions |

Explicitly graded required artifacts: `repo/src/dpop_policy.py`, `repo/out/decisions.json`, `repo/out/replay_cache.json`, `repo/out/summary.json`, `repo/DPoP_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: malformed-input behavior or an unsafe implementation loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

The separate zero-weight gate covers protected-input tampering, dangerous filesystem nodes or path escape, and concrete claims of handling real tokens/keys, verifying real JWTs, contacting identity endpoints, or performing live authentication/authorization. Negated boundary statements are accepted.

## 10. Leakage, isolation, and safety review

Hidden cases/reference stay outside the workspace; booleans represent prior
cryptographic verification and no key material or endpoint is used.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** signature-only acceptance, missing token binding, off-by-one time, stale replay state, rejected-proof insertion, or unsupported cryptographic claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `proof_request_and_token_binding`.
- `validation_and_replay`: `nonce_and_replay_state`, `dpop_replay`, `source_and_identity_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

## Environment/runtime review (Standard207)

This task intentionally uses the shared Python environment without an identity
sidecar or cryptographic library: signature and public-key validity are frozen
prevalidated facts, while the task measures DPoP binding and replay policy. The
agent verifier executes normalized `htu`, inclusive `iat`, expired/active
cache, and same-batch replay probes. The fresh grader verifier executes the
pure-function worker and grading APIs used by the Oracle.
