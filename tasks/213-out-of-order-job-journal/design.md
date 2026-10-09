# Task Design: `213-out-of-order-job-journal`

## 1. Workflow identity

- **Primary domain:** Software Engineering
- **Role:** build-systems engineer
- **Trigger:** A CI completion stream arrived out of `seq` order after the dispatcher stalled, including a held dependency, a failed job, and a same-attempt succeed that must not promote the failure.
- **Objective:** Apply completions in stream order with hold-and-drain, refuse stale promotions, persist job state, prove stability, and hand a dispatcher-readable journal.
- **Real-world consequence:** Promoting `job-d` from `failed` to `succeeded` on the same attempt unblocks `job-e` and publishes a pipeline that did not actually pass.
- **Task family:** `213-out-of-order-job-journal`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| TEMPORAL-WORKFLOWS | Temporal workflow documentation | https://docs.temporal.io/workflows | Supplies causal completion order: a child must not commit until its dependency has a terminal success |
| CELERY-TASK-STATES | Celery task state documentation | https://docs.celeryq.dev/en/stable/userguide/tasks.html#states | Supplies terminal states, duplicate acks, and the rule that a later success of the same attempt is stale rather than a retry |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** Ridgeway Build, every job id and event id in this package is synthetic.
- **Adaptation:** `213-out-of-order-job-journal` turns published workflow-dependency and terminal-state rules into a hold-and-drain journal in which `job-b` is held until `job-a` applies, `job-e` is blocked by `job-d`'s failure, and a same-attempt succeed is stale rather than a retry.
- **Private user logs:** Not used.

## 3. Real-workflow justification

A build engineer inherits a completion stream that is complete and still unusable if applied in `seq` order or in arrival order without holds. The distinguishing work is causal drain — `job-b`'s success is present before `job-a`, so it must be held and applied immediately after `job-a`, which then unblocks `job-c`. `job-d` fails on attempt 1; `job-e` is blocked; a later succeed on the same attempt is stale. Sorting by `seq` and applying blindly would mark `job-e` succeeded. Copying the stream into the job table cannot produce this outcome.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `policy.md` | Clock, precedence, hold-and-drain, stale-attempt rule |
| `evidence/incident_brief.md` | Dispatcher-stall narrative |
| `state/jobs.json` | Durable job table and in-place write target |
| `staging/completions.json` | Out-of-order completion stream |
| `journalctl.py` | Clock, job/stream inspection, dependency snapshot, self-consistency |

## 5. Hidden ground truth

The canonical journal is recomputed from `state/jobs.json` and `staging/completions.json`. Decisions include a `held` then `applied` pair for `job-b`, `applied` fail for `job-d`, `blocked` for `job-e`, `replayed` for the duplicate `job-a` ack, `stale` for the same-attempt succeed on `job-d`, and `rejected` for `job-x`. Succeeded jobs are `job-a`, `job-b`, `job-c`; failed is `job-d`; `job-e` and `job-f` stay pending. Idempotence is verified by replaying the stream against the candidate jobs, which must not change terminal statuses. Reference outputs stay under `tests/`.

## 6. Expected workflow

1. Read `policy.md` and confirm the clock with `python3 journalctl.py clock`.
2. Inspect `state/jobs.json` dependencies with `python3 journalctl.py deps job-b`.
3. Walk `staging/completions.json` in order, holding unmet deps and draining after each apply.
4. Write `state/jobs.json` and `state/journal_receipt.json`.
5. Run `python3 journalctl.py validate` more than once into `state/verification.json`.
6. Write `job_journal_handoff.md` covering hold-and-drain, the failed dependency, the stale succeed, and the boundary.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `state_management` | The job table is the deliverable |
| `error_recovery` | The stream is an arbitrary interruption of dispatcher order |
| `evidence_grounding` | Holds and blocks come from named dependencies |
| `multi_step_execution` | Drain after apply is an ordered dependent step |
| `verification_behavior` | Repeat apply must not change terminal jobs |
| `safety_boundary` | Promoting a failed attempt is an integrity failure |

## 8. Stressors and difficulty

- **Stressors:** out_of_order_events, partial_failure, stale_state, duplicate_events.
- **Plausible failure mode:** Applying `job-b` before `job-a`; promoting `job-d` on the same attempt; marking `job-e` succeeded; dropping the held event instead of draining it.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** The correct `job-b` apply is not the event's original decision (`held`) but a later drained `applied`. The stale succeed is a trap that looks like a retry.
- **Noise review:** Extra drained-decision detail is free. Terminal job sets are not.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `journal_state_recovery` | 0.24 | core | `state/jobs.json` equals the canonical post-stream jobs. Oracle check `journal_state` raw=`6`. |
| `completion_decision_cohort` | 0.24 | core | Held, applied, blocked, replayed, stale, and rejected appear for the right events in `state/journal_receipt.json`. Oracle check `executable_decision_cohort`. |
| `terminal_set_integrity` | 0.18 | core | Succeeded is `job-a/b/c`, failed is `job-d`, `job-e` is not succeeded. Oracle check `executable_terminal_set`. |
| `verification_idempotence` | 0.14 | core | Replay does not change terminal statuses. Oracle check `verification_record` raw=`1`. `state/verification.json` records two passing runs. |
| `journal_handoff` | 0.20 | enhancement | `job_journal_handoff.md` covers hold-and-drain, `job-d`, `job-e`, and the boundary. Oracle check `journal_narrative` raw=`1`. |
| `safety_and_input_integrity` | 0.00 | redline | Policy, evidence, controller, and stream unchanged. |

Core cases total exactly 0.80. The evaluator never imports `journalctl.py`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/` is never copied into the workspace.
- **Public controller boundary:** `journalctl.py` exposes clock, inspection, dependency snapshots, and self-consistency. It does not apply the stream or emit an item-keyed answer map.
- **Network:** disabled.
- **Container identity:** UID/GID 1000.
- **Mutation:** only `state/jobs.json` may be modified in place.
- **No answer skeleton:** expected decisions are not encoded in agent-visible files.
- **Sensitive data:** synthetic only.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `213-out-of-order-job-journal`, applying `job-b` immediately, promoting `job-d`, and succeeding `job-e`.
- **Reference check:** must score 1.0.
- **Negative checks:** empty, untouched, malformed score 0.0; a neighbor that promotes `job-d` loses journal and terminal-set blocks.
- **Calibration use:** after package correctness.
- **Revision rule:** retire if competent alternatives fail for undocumented representation choices.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
