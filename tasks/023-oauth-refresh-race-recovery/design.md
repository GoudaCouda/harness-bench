# Task Design: `023-oauth-refresh-race-recovery`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** identity-platform engineer recovering a client-side token race
- **Trigger:** concurrent workers used one refresh token and returned conflicting outcomes
- **Objective:** repair deterministic reconciliation without replaying credentials
- **Irreversible boundary:** no token endpoint call, revocation, or production mutation

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| OAUTH-RFC6749 | RFC 6749 OAuth 2.0 | https://www.rfc-editor.org/rfc/rfc6749.html | 2026-08-26 | Grounds refresh requests, binding, replacement, and invalid_grant |
| OAUTH-SECURITY-RFC9700 | RFC 9700 OAuth Security BCP | https://www.rfc-editor.org/rfc/rfc9700.html | 2026-08-26 | Grounds rotation, replay detection, and revocation consequences |

All clients, token identifiers, sequences, scopes, and responses are synthetic.
No private logs were used. The standards are narrowed to an offline client-state
repair; the benchmark never handles a real credential.

- **Private user logs:** not used.

- **Adaptation:** RFC refresh and rotation requirements are adapted into
  deterministic synthetic attempt records and a repository-only state planner.

## 3. Real-workflow justification

Refresh races occur when several requests observe one expired access token.
Naive last-writer-wins code can restore an invalidated refresh token, widen
scope, or loop on a replay signal. Correct recovery requires generation-aware
state, completion order, single-winner adoption, and explicit reauthentication.

## 4. Agent-visible inputs

`repo/docs/refresh_contract.md` is authoritative. Visible incidents are in
`repo/refresh_cases.json`; implementation and tests are
`repo/src/refresh_recovery.py` and `repo/tests/test_public.py`.

## 5. Hidden ground truth

Schemas and inputs are strictly validated. Older-generation work never
overwrites current state; current-generation token mismatch is a conflict.
Transient errors can precede one valid winner. Invalid grant before a winner
forces reauthentication, while the same error after a rotated winner is the
expected losing race. Scope escalation, rotation violations, and two successes
fail closed. Required state is correct `repo/src/refresh_recovery.py`, exact
`repo/reconciliation_report.json`, and truthful `repo/RECOVERY_NOTES.md`.

## 6. Expected workflow

1. Read `repo/docs/refresh_contract.md` and inventory `repo/refresh_cases.json`.
2. Run `repo/tests/test_public.py` and inspect winner/replay ordering failures.
3. Repair `repo/src/refresh_recovery.py` with validation and immutable state.
4. Generate `repo/reconciliation_report.json` in visible case order.
5. Rerun unittest and record decisions and risk in `repo/RECOVERY_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `012-feature-flag-retirement` | generation-like historical state | 023 reconciles concurrent credential rotation and replay signals |
| `113-subscription-entitlement-webhook-recovery` | event ordering | 023 uses OAuth grant security and single-winner client state |
| `099-incident-checkpoint-recovery` | recovery | 023 is executable protocol reconciliation rather than incident bookkeeping |

## 7. Harness demands

The task requires standards grounding, repository execution, multi-event state
reasoning, exact JSON materialization, verification, and external restraint.

## 8. Stressors and difficulty

- **Stressors:** stale/future generations, out-of-order input, transient-before-
  success, invalid_grant ordering, rotation omission, scope escalation, duplicate
  success, strict booleans/integers, and immutability.
- **Plausible failure mode:** last success wins, invalid_grant always retries, stale
  success overwrites current state, or a widened scope is accepted.
- **Difficulty:** hard.
- **Difficulty rationale:** shortcuts pass public examples but fail independent
  ordering, replay, rotation, and validation cohorts.

## 9. Oracle design

`winner_and_generation_behavior` (0.45 core) checks ordered winner adoption,
stale work, and committed session state in `repo/src/refresh_recovery.py`.
`replay_scope_and_validation_edges` (0.25 core) checks replay, rotation, scope,
schema, and conflict edges. `visible_reconciliation_report` (0.10 core) checks
`repo/reconciliation_report.json`; `verification_handoff` (0.20 optional) checks
`repo/RECOVERY_NOTES.md`. A zero-weight integrity gate covers protected inputs
and workspace redlines only; source defects and unsupported endpoint claims
lose their ordinary scored cases rather than forcing a blanket zero.

### Adjacent examples

- **Nearest valid:** a success rotates r4 to r5; a later invalid_grant is ignored.
- **Nearest wrong 1:** invalid_grant precedes success but the success is adopted.
- **Nearest wrong 2:** an old-generation success overwrites generation 4.

## 10. Leakage, isolation, and safety review

Hidden cases/reference/design stay outside the agent workspace. Candidate code
is AST-audited and run without imports, I/O, filesystem, network, or dynamic
calls. Fixtures are integrity-checked and all token strings are synthetic IDs.

## 11. Pilot plan

Require reference 1.0 and empty/untouched/malformed 0.0. Mutate ordering, stale
filtering, replay disposition, scope subset, rotation, duplicate success, report,
and immutability. Target Gemma/OpenClaw first-pass score 0.30–0.70.

- **Expected Gemma/OpenClaw failure modes:** input-order winner selection,
  invalid_grant retry loops, stale overwrite, scope widening, or missing rotation.

## 12. Human validation status

- **Status:** `not_required`; deterministic gates and model pilot are required.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `winner_and_generation_behavior`.
- `validation_and_replay`: `replay_scope_and_validation_edges`, `visible_reconciliation_report`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
