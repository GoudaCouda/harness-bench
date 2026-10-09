# Task Design: `082-http-request-retry-safety-repair`

## 1. Workflow identity

- **Role:** API-client reliability engineer repairing automatic retry policy.
- **Trigger:** a lost POST response was treated like a harmless connection failure and replayed.
- **Objective:** derive a bounded, evidence-grounded retry, probe, defer, stop, or success decision.
- **Boundary:** no HTTP request, replay, job creation, charge, or service mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| HTTP-SEMANTICS-RFC9110 | RFC 9110 HTTP Semantics | https://www.rfc-editor.org/rfc/rfc9110.html | 2026-08-27 |
| HTTP-STATUS-RFC6585 | RFC 6585 additional HTTP status codes | https://www.rfc-editor.org/rfc/rfc6585.html | 2026-08-27 |

- **Adaptation:** HTTP idempotency and Retry-After semantics become an offline client recovery state machine with an explicit application idempotency contract.
- **Private user logs:** None.
- **Synthetic-data statement:** Operation IDs, keys, digests, attempts, status observations, byte counts, and delays are synthetic.

## 3. Real-workflow justification

Client libraries see materially different evidence when connection setup fails,
a request write is partial, or a response disappears. Blindly treating all
timeouts and server errors alike can duplicate non-idempotent work; ignoring a
server delay can also worsen an incident.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/retry_contract.md` | authoritative retry state machine |
| `repo/src/retry_planner.py` | broken planner |
| `repo/retry_cases.json` | visible API incidents |
| `repo/tests/test_public.py` | public regressions |

## 5. Hidden ground truth

Hidden cohorts extend the concrete visible inputs `repo/docs/retry_contract.md`,
`repo/retry_cases.json`, and `repo/tests/test_public.py` with unsent and partial
writes, lost responses, idempotent and non-idempotent methods, decorative and
enforced keys, successful, retryable, non-retryable, applied and unknown HTTP
states, Retry-After deferral, backoff caps, exhaustion, malformed evidence,
immutable inputs, and external-action restraint. Required final state includes
repaired `repo/src/retry_planner.py`, exact `repo/retry_report.json`, and
verified `repo/RETRY_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/retry_contract.md`, `repo/retry_cases.json`, and `repo/tests/test_public.py`.
2. Validate request policy, attempt number, send-phase evidence, and HTTP observation in `repo/src/retry_planner.py`.
3. Establish replay authority from not-sent/not-applied evidence, method semantics, or an enforced idempotency key.
4. Compose status, application state, attempt limits, exponential delay, and Retry-After into the exact decision.
5. Generate `repo/retry_report.json`, run public tests, and record verification plus live-client risk in `repo/RETRY_NOTES.md`.

## 7. Harness demands

Repository inspection, executable state-machine repair, protocol reasoning,
exact structured output, verification behavior, and mutation restraint are
required.

## 8. Stressors and difficulty

- **Plausible failure mode:** retry every timeout, trust a decorative key, retry an applied operation, ignore exhaustion, or cap Retry-After below the server request.
- **Difficulty rationale:** safe replay depends jointly on transport evidence, method semantics, application guarantees, response state, and bounded scheduling.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `transport_and_idempotency_safety` | 0.35 | core | Transport ambiguity is separated from known-not-sent evidence |
| `response_backoff_and_exhaustion` | 0.25 | core | HTTP state, Retry-After, backoff, and attempt limits compose safely |
| `visible_retry_report` | 0.05 | core | Visible API incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Replay and live-client risks are handed off |
| `evidence_and_http_action_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/retry_planner.py`, `repo/retry_report.json`, `repo/RETRY_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and references are excluded. Candidate code is pure-audited;
Hidden cohorts and references are excluded. Candidate code is pure-audited; safe computation-only standard-library imports and ordinary container/value methods are allowed, while network, filesystem, process, private attributes,
and dynamic execution unavailable. Grading is read-only and offline.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma + OpenClaw run with cohort-level review.

- **Expected Gemma/OpenClaw failure modes:** conflating connection and response loss, trusting key presence without enforcement, retrying unsafe POST, mishandling applied 5xx, or violating Retry-After.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `transport_and_idempotency_safety`.
- `validation_and_replay`: `response_backoff_and_exhaustion`, `visible_retry_report`, `evidence_and_http_action_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
