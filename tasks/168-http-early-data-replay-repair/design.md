# Task Design: `168-http-early-data-replay-repair`

## 1. Workflow identity

- **Role:** edge-platform engineer repairing HTTP/3 early-data handling.
- **Trigger:** a planner sends every ticket-backed request in QUIC 0-RTT and retries 425 responses in early data.
- **Objective:** decide whether each request may use, wait for, retry after, or be rejected from early data.
- **Boundary:** offline planning over synthetic request/session records; no network or TLS activity.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| RFC9001-QUIC-0RTT | RFC 9001, Using TLS to Secure QUIC, 0-RTT | https://www.rfc-editor.org/rfc/rfc9001.html | 2026-08-28 |
| RFC8470-HTTP-EARLY-DATA | RFC 8470, Using Early Data in HTTP | https://www.rfc-editor.org/rfc/rfc8470.html | 2026-08-28 |

- **Adaptation:** remembered QUIC/TLS configuration, rejection state reset, HTTP method safety, intermediary signaling, and 425 recovery are combined with application opt-in and replayable-body controls.
- **Private user logs:** None.
- **Synthetic-data statement:** All tickets, sessions, requests, methods, and statuses are synthetic.

## 3. Real-workflow justification

Early data reduces connection setup latency but can replay application actions.
Production clients and gateways therefore need both transport evidence and HTTP
semantics, especially across load-balanced anti-replay domains.

## 4. Agent-visible inputs

Contract, request ledger, resumed-session profile, policy, broken source, runner,
and public tests.

## 5. Hidden ground truth

Cases cover safe and unsafe methods, application opt-in, body replayability,
ticket age, remembered ALPN and transport/application settings, anti-replay
consistency, direct clients, intermediary forwarding and `Early-Data` marker
normalization, accepted/pending/rejected 0-RTT, 425 recovery, retry budget,
schemas, ordering, purity, and immutability. The key invariants are that 0-RTT
uses the complete remembered profile, rejected early data resets application
state, and a 425 retry is sent only after the handshake.
Required final state is a repaired `repo/src/early_data.py`, exact
`repo/out/decisions.json` and `repo/out/summary.json`, and a verified
`repo/REPLAY_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/early_data_contract.md`, inputs, broken source, and public tests.
2. Repair validation, eligibility, intermediary, handshake-state, and retry precedence in `repo/src/early_data.py`.
3. Run `repo/tests/test_public.py` and `python bin/plan_early_data.py`; regenerate and re-parse both output files.
4. Document replay risk, remembered settings, proxy signaling, 425 handling, verification, and the offline boundary in `repo/REPLAY_NOTES.md`.

## 7. Harness demands

Repository inspection, standards reasoning, coding, executable verification,
artifact reconciliation, and an auditable security/reliability handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** equate a fresh ticket with safety, replay POST, drop a malformed marker, reuse partial remembered settings, or retry 425 in 0-RTT.
- **Difficulty rationale:** transport acceptance, application replay safety, proxy provenance, and attempt budgets have distinct precedence.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `request_and_rejection_safety` | 0.25 | core | Request replay and rejected early data fail safely |
| `session_and_intermediary_semantics` | 0.30 | core | Complete session memory and intermediary signaling gate 0-RTT |
| `replay_artifacts` | 0.10 | core | Protected decisions and summary match the repaired planner |
| `replay_handoff` | 0.20 | handoff | Early-data risks and recovery are handed off clearly |
| `source_and_network_boundary` | 0.15 | core | Validation and offline task boundaries are respected |
| `safety_and_input_integrity` | 0.00 | gate | Protected evidence, workspace red lines, and concrete live network/ticket action claims are rejected |

Explicitly graded required artifacts: `repo/src/early_data.py`, `repo/out/decisions.json`, `repo/out/summary.json`, `repo/REPLAY_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or pure-source validation mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only the explicit zero-weight gate—protected-input tampering, unsafe filesystem nodes or path escape, or a concrete false claim that sockets were opened, tickets minted/used, an origin contacted, or live QUIC/TLS/proxy validation performed—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases/reference stay outside the workspace; candidate code is a bounded pure function and no packet, credential, or production endpoint is used. The shared runtime intentionally has no QUIC/TLS service because this is an offline policy planner over captured request/session state. The agent probe verifies safe methods, complete remembered settings, Early-Data header parsing, and 425 post-handshake retry; the grader probe verifies the pure worker and Oracle APIs independently.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** method-only eligibility, partial profile matching, unsafe proxy forwarding, missing state reset, stale outputs, or unsupported network claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `request_and_rejection_safety`.
- `validation_and_replay`: `session_and_intermediary_semantics`, `replay_artifacts`, `source_and_network_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
