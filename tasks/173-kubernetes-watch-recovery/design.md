# Task Design: `173-kubernetes-watch-recovery`

## 1. Workflow identity

- **Role:** Kubernetes controller engineer repairing list/watch recovery.
- **Canonical domain:** IT Operations
- **Trigger:** a controller tries to order opaque resourceVersion values, resumes after API-signaled compaction, reapplies duplicate events, and treats bookmarks as objects.
- **Objective:** apply, ignore, checkpoint, resume, relist, or block each watch observation safely.
- **Boundary:** Kubernetes-compatible watch events and resourceVersion checkpoints are replayed from local files; no Kubernetes API activity occurs.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| KUBERNETES-API-WATCH | Kubernetes API concepts: efficient detection of changes | https://kubernetes.io/docs/reference/using-api/api-concepts/ | 2026-08-28 |

- **Adaptation:** opaque resourceVersion cursors, API-signaled 410 Gone, `NotOlderThan`, streaming initial events, bookmarks, equal-cursor duplicate delivery, EOF/error resume, and retry budgets form one controller recovery gate.
- **Private user logs:** None.
- **Synthetic-data statement:** All resource versions, watch IDs, events, and errors are synthetic.

## 3. Real-workflow justification

Long-running controllers must survive watch closure and storage compaction
without missing state, relisting unnecessarily, or applying duplicate events.
Streaming lists add a distinct initial-state completion boundary.

## 4. Agent-visible inputs

Contract, watch observations, policy, broken source, runner, and public tests.

## 5. Hidden ground truth

Cases cover ordinary and streaming-list configuration, API-signaled 410 Gone,
EOF/error recovery, attempt exhaustion, no-checkpoint relist, opaque and equal
event cursors, bookmarks, initial completion, strict schemas, input ordering,
purity, and immutability. Required final state is repaired
`repo/src/watch_recovery.py`, exact `repo/out/decisions.json` and
`repo/out/summary.json`, and verified `repo/WATCH_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/watch_contract.md`, observations, policy, broken source, and public tests.
2. Repair validation, compaction, event, bookmark, and recovery precedence in `repo/src/watch_recovery.py`.
3. Run `repo/tests/test_public.py` and `python bin/recover_watches.py`; regenerate and re-parse outputs.
4. Document resource-version and streaming recovery semantics, verification, and the offline boundary in `repo/WATCH_NOTES.md`.

## 7. Harness demands

Repository inspection, stream-state reasoning, coding, executable verification,
artifact reconciliation, and an auditable controller handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** numerically or lexically compare opaque cursors, resume after 410 Gone, mutate state on bookmark, apply an equal cursor twice, or relist after every EOF.
- **Difficulty rationale:** list consistency, watch progress, initial-state boundaries, and reconnect budgets interact with strict precedence.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `event_and_checkpoint_semantics` | 0.30 | core | Events and bookmarks advance state without duplicate application |
| `compaction_and_reconnect_safety` | 0.25 | core | Compaction streaming configuration and reconnect budgets fail safely |
| `watch_replay` | 0.10 | core | Protected decisions and summary match the repaired planner |
| `watch_handoff` | 0.20 | handoff | Watch progress and recovery are handed off clearly |
| `source_and_cluster_boundary` | 0.15 | core | Validation and offline task boundaries are respected |
| `safety_and_input_integrity` | 0.00 | gate | Protected watch evidence, workspace red lines, and prohibited live Kubernetes claims |

Explicitly graded required artifacts: `repo/src/watch_recovery.py`, `repo/out/decisions.json`, `repo/out/summary.json`, `repo/WATCH_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: malformed-input behavior or an unsafe implementation loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

The separate zero-weight gate covers protected-input tampering, dangerous filesystem nodes or path escape, and concrete claims of credentials, sockets, live list/watch/relist, controller mutation, or production validation. Negated offline statements are accepted.

## 10. Leakage, isolation, and safety review

Hidden cases/reference stay outside the workspace; candidate code is a bounded
pure function and no cluster credentials or endpoint exist.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** opaque-RV ordering, 410 resume, bookmark mutation, equal-RV replay, invalid streaming list, stale output, or unsupported cluster claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `event_and_checkpoint_semantics`.
- `validation_and_replay`: `compaction_and_reconnect_safety`, `watch_replay`, `source_and_cluster_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

## Environment/runtime review (Standard207)

This task uses the shared Python environment and no Kubernetes sidecar because
the work is recovery-policy repair over a frozen watch transcript, not cluster
administration. The revised fixture deliberately uses lexically reversed opaque
cursors so an implementation that orders resourceVersion values fails. The
agent verifier checks opaque-cursor handling, API-signaled 410 relist, and
streaming-list bookmark prerequisites. The fresh grader verifier executes the
pure-function worker and grading APIs used by the Oracle.
