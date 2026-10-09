# Task Design: `120-http-cookie-jar-policy-repair`

## 1. Workflow identity

- **Role:** client-platform engineer repairing an offline HTTP cookie store.
- **Trigger:** response replay widened cookie scope and broke expiry/replacement behavior.
- **Objective:** reconcile stored cookies and construct request headers under exact scope rules.
- **Boundary:** pure local planning; no HTTP request, browser profile, or live cookie mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| RFC-6265 | HTTP State Management Mechanism | https://www.rfc-editor.org/rfc/rfc6265.html | 2026-08-27 |

- **Adaptation:** RFC cookie storage, domain/path matching, expiry, and ordering
  algorithms are adapted into an offline response-replay and request-header repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All hosts, paths, cookies, values, timestamps, responses, and requests are synthetic.

## 3. Real-workflow justification

Cookie jars are persistent security-sensitive state machines. Correctness needs
response-origin validation, tuple replacement, expiry, scope matching, and
deterministic serialization rather than a simple header parser.

## 4. Agent-visible inputs

The repository exposes `repo/docs/cookie_contract.md`, `repo/jar.json`,
`repo/responses.json`, `repo/requests.json`, `repo/policy.json`, broken code,
runner, and public tests.

## 5. Hidden ground truth

Hidden cohorts cover host-only versus Domain cookies, leading dots, public
suffix rejection, default paths, segment path-match, Max-Age precedence and
zero deletion, replacement creation order, expiry boundaries, Secure setting
and sending, HttpOnly API scope, request ordering, strict shapes, and immutability.

Required final workspace state is repaired `repo/src/cookie_jar.py`, exact
`repo/out/store.json` and `repo/out/requests.json`, and a verified
`repo/COOKIE_NOTES.md`. The key invariant is that `(name, domain, path)` state
changes only after the response origin and attributes pass scope validation.

## 6. Expected workflow

1. Inspect `repo/docs/cookie_contract.md`, seed jar state, responses, policy, and request probes.
2. Repair parsing, scope validation, expiry, tuple replacement, and request matching in `repo/src/cookie_jar.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/reconcile_cookies.py` to regenerate both `repo/out/` artifacts.
4. Re-parse `repo/out/store.json` and `repo/out/requests.json`, then document boundaries in `repo/COOKIE_NOTES.md`.

## 7. Harness demands

Repository inspection, HTTP state reasoning, code repair, protected execution,
cross-artifact reconciliation, and verification are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** treat Domain as host-only, use substring path
  matching, let Expires override Max-Age, reset creation order on replacement,
  retain expired tuples, or send Secure/HttpOnly cookies in an invalid context.
- **Difficulty rationale:** parsing, origin authority, temporal state, tuple
  identity, and request ordering interact across two phases of one state machine.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `storage_scope_and_expiry` | 0.30 | core | Response cookies reconcile under exact scope and lifetime rules |
| `request_matching_and_order` | 0.25 | core | Request headers contain only eligible cookies in deterministic order |
| `visible_cookie_replay` | 0.10 | core | Protected fixture outputs match the repaired cookie jar |
| `cookie_handoff` | 0.20 | handoff | Cookie state and security boundaries are handed off clearly |
| `source_and_network_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/cookie_jar.py`, `repo/out/store.json`, `repo/out/requests.json`, `repo/COOKIE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references stay outside the workspace. Candidate code executes
as a bounded pure function with `copy` only and no filesystem or network access.

## 11. Pilot plan

Require 0/0/0/1, scope/expiry/order mutations, Docker reference 1.0, then a
fresh model pilot with trace review for fixture-specific cookie logic.

- **Expected Gemma/OpenClaw failure modes:** permissive Domain matching, wrong
  default path, Max-Age/Expires inversion, replacement-order drift, unsafe
  context sending, stale output artifacts, or incomplete handoff evidence.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `storage_scope_and_expiry`.
- `validation_and_replay`: `request_matching_and_order`, `visible_cookie_replay`, `source_and_network_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
