# Task Design: `142-trace-context-propagation-repair`

## 1. Workflow identity

- **Role:** observability-platform engineer repairing a trace propagation adapter.
- **Canonical domain:** IT Operations
- **Trigger:** malformed vendor state broke valid traces and external requests leaked baggage.
- **Objective:** derive safe deterministic outgoing context for forwarding and participating services.
- **Boundary:** actual W3C HTTP header strings are parsed and rendered locally; no request, span export, collector, or mesh mutation occurs.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| W3C-TRACE-CONTEXT | W3C Trace Context Recommendation | https://www.w3.org/TR/trace-context/ | 2026-08-27 |
| W3C-BAGGAGE | W3C Baggage Candidate Recommendation | https://www.w3.org/TR/baggage/ | 2026-08-27 |

- **Adaptation:** standard traceparent/tracestate propagation and baggage privacy
  considerations are adapted into an offline trust-boundary repair workflow.
- **Private user logs:** None.
- **Synthetic-data statement:** All trace IDs, parent IDs, vendors, baggage values, requests, and boundaries are synthetic.

## 3. Real-workflow justification

Intermediaries must preserve valid distributed traces even when optional vendor
state is bad, while participating services update parent identity and privacy
filters baggage at trust boundaries. Small parsing mistakes fragment traces or leak data.

## 4. Agent-visible inputs

The repository exposes `repo/docs/trace_contract.md`, `repo/requests.json`,
`repo/policy.json`, partially working adapter code, a protected runner, and
public tests that parse real HTTP header blocks with the Python standard library.

## 5. Hidden ground truth

Hidden cohorts cover version-00 and future traceparent parsing, zero IDs,
uppercase/length/suffix errors, duplicate headers, restart identity, sampled
flags, pass-through byte preservation, independent tracestate failure, vendor
upsert/order/limits, baggage percent escapes, duplicate keys, external privacy
filtering, malformed structures, deterministic metrics, and immutability.

Required final workspace state is repaired `repo/src/trace_context.py`, exact
`repo/out/decisions.json` and `repo/out/metrics.json`, and a verified
`repo/TRACE_NOTES.md`. The key invariant is that invalid optional tracestate
never invalidates a valid traceparent, while invalid traceparent always restarts
the trace and discards inherited vendor state.

## 6. Expected workflow

1. Inspect `repo/docs/trace_contract.md`, request headers, trust-boundary policy, and public cases.
2. Repair traceparent, tracestate, baggage, participation, restart, and sampling logic in `repo/src/trace_context.py`.
3. Run the full public unittest suite, including the HTTP-header integration, and `repo/bin/propagate_traces.py` to regenerate both `repo/out/` artifacts.
4. Re-parse `repo/out/decisions.json` and `repo/out/metrics.json`, then document boundaries in `repo/TRACE_NOTES.md`.

## 7. Harness demands

Repository inspection, protocol parsing, privacy-policy reasoning, code repair,
executable verification, and artifact reconciliation are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** let malformed tracestate restart a valid trace,
  forward an all-zero ID, alter pass-through bytes, append vendor state instead
  of moving it first, mishandle percent escapes, or leak sensitive baggage.
- **Difficulty rationale:** independent header validity, versioning, identity
  transitions, ordering, sampling, and privacy filtering interact per request.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `traceparent_restart_and_participation` | 0.30 | core | Trace identity is forwarded participated or restarted correctly |
| `tracestate_baggage_and_privacy` | 0.25 | core | Optional vendor and baggage state is propagated safely |
| `visible_trace_replay` | 0.10 | core | Protected fixture outputs match the repaired adapter |
| `trace_handoff` | 0.20 | handoff | Trace propagation and privacy boundaries are handed off clearly |
| `source_and_telemetry_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/trace_context.py`, `repo/out/decisions.json`, `repo/out/metrics.json`, `repo/TRACE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references stay outside the workspace. Candidate code runs as
a bounded pure function without network, clock, randomness, or process access.

## 11. Pilot plan

Require 0/0/0/1, adjacent protocol/privacy mutations, Docker reference 1.0,
then a model pilot with trace review for over-coupled header validity.

- **Expected Gemma/OpenClaw failure modes:** tracestate-triggered restart,
  future-version rejection, wrong sampled bit, pass-through rewriting, vendor
  order drift, baggage leakage, stale outputs, or incomplete handoff evidence.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `traceparent_restart_and_participation`.
- `validation_and_replay`: `tracestate_baggage_and_privacy`, `visible_trace_replay`, `source_and_telemetry_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
