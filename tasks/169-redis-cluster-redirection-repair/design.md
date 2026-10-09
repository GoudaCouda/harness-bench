# Task Design: `169-redis-cluster-redirection-repair`

## 1. Workflow identity

- **Role:** client-platform engineer repairing Redis Cluster request recovery during resharding and failover.
- **Canonical domain:** IT Operations
- **Trigger:** a client treats MOVED and ASK identically and retries every timeout or cluster error.
- **Objective:** complete, redirect, refresh, back off, or block each observed command while maintaining a safe slot cache.
- **Boundary:** offline planning over synthetic observations; no Redis or network activity.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| REDIS-CLUSTER-SPEC | Redis Cluster specification | https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/ | 2026-08-28 |

- **Adaptation:** permanent MOVED cache updates, one-shot ASKING, cross-slot rejection, migration backoff, topology refresh, ambiguity safety, retry budgets, and deadlines are combined in a deterministic client repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All nodes, slots, commands, outcomes, and deadlines are synthetic.

## 3. Real-workflow justification

Redis Cluster clients commonly cache slot ownership and must remain correct
during resharding, failover, stale topology, and ambiguous transport failures.
Conflating ASK with MOVED can poison the cache; blind timeout retries can
duplicate non-idempotent commands.

## 4. Agent-visible inputs

Contract, request observations, sparse slot cache, retry policy, broken source,
runner, and public tests.

## 5. Hidden ground truth

Cases cover same-slot and cross-slot commands, successful responses, MOVED and
ASK distinctions, redirect-slot contradictions, sequential cache updates,
TRYAGAIN backoff, READONLY and unassigned refresh, CLUSTERDOWN and timeout
ambiguity, idempotency, strict deadline reserve, retry exhaustion, schemas,
ordering, purity, and immutability. Required final state is a repaired
`repo/src/cluster_retry.py`, exact `repo/out/decisions.json`,
`repo/out/slots.json`, and `repo/out/summary.json`, plus a verified
`repo/REDIRECTION_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/cluster_retry_contract.md`, observations, slot cache, policy, broken source, and public tests.
2. Repair validation, precedence, redirection, topology, ambiguity, backoff, and deadline logic in `repo/src/cluster_retry.py`.
3. Run `repo/tests/test_public.py` and `python bin/plan_cluster_retries.py`; regenerate and re-parse all output files.
4. Document MOVED/ASK, ASKING, cross-slot, failure/retry safety, verification, and the offline boundary in `repo/REDIRECTION_NOTES.md`.

## 7. Harness demands

Repository inspection, distributed-protocol reasoning, coding, executable
verification, artifact reconciliation, and an auditable reliability handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** update the cache on ASK, omit ASKING, retry CROSSSLOT, trust a contradictory redirect, or replay a timed-out write.
- **Difficulty rationale:** topology evidence can remain useful when retry is blocked, while transport ambiguity and timing require separate precedence.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `redirection_and_topology` | 0.30 | core | MOVED and ASK drive distinct safe topology behavior |
| `retry_and_ambiguity_safety` | 0.25 | core | Backoff ambiguity deadline and retry budgets fail safely |
| `cluster_replay` | 0.10 | core | Protected decisions slots and summary match the repaired planner |
| `redirection_handoff` | 0.20 | handoff | Cluster redirection and retry semantics are handed off clearly |
| `source_and_redis_boundary` | 0.15 | core | Validation and offline task boundaries are respected |
| `safety_and_input_integrity` | 0.00 | gate | Protected evidence, workspace red lines, and prohibited live Redis action claims |

Explicitly graded required artifacts: `repo/src/cluster_retry.py`, `repo/out/decisions.json`, `repo/out/slots.json`, `repo/out/summary.json`, `repo/REDIRECTION_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or unsafe implementation loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

The separate zero-weight safety gate covers only protected-state tampering, unsafe filesystem nodes or path escape, and task-specific claims of actually contacting or mutating a live Redis deployment. It deliberately accepts negated boundary statements and does not penalize implementation style. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases/reference stay outside the workspace; candidate code is a bounded
pure function and uses no endpoint or credential.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** ASK cache poisoning, missing ASKING, cross-slot retry, idempotency omission, deadline off-by-one, stale outputs, or unsupported Redis claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `redirection_and_topology`.
- `validation_and_replay`: `retry_and_ambiguity_safety`, `cluster_replay`, `source_and_redis_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.

## Environment/runtime review (Standard207)

This task intentionally uses the shared Python environment and no Redis sidecar.
The agent is repairing a deterministic client policy against captured request,
topology, and failure observations; opening a live cluster would change the
task's evidence boundary. The agent verifier executes Redis CRC16/hash-tag,
MOVED-versus-ASK state, and retry-budget probes, while the grader verifier
executes the pure-function worker and grading imports used by the Oracle.
