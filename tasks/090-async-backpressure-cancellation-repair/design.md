# Task Design: `090-async-backpressure-cancellation-repair`

## 1. Workflow identity

- **Role:** Python reliability engineer repairing an ingestion worker pool.
- **Trigger:** unbounded fan-out, completion-order output, sibling failure, and timeout task leaks.
- **Objective:** provide bounded queueing, ordered results, failure isolation, and cancellation-safe cleanup.
- **Boundary:** local synthetic coroutines only; no thread, process, network, or production execution.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| PYTHON-ASYNCIO-QUEUE | Python asyncio queues documentation | https://docs.python.org/3/library/asyncio-queue.html | 2026-08-27 |
| PYTHON-ASYNCIO-TASKS | Python asyncio tasks documentation | https://docs.python.org/3/library/asyncio-task.html | 2026-08-27 |

- **Adaptation:** documented queue unfinished-task invariants and task cancellation semantics become an executable library repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All jobs, timings, values, and failures are synthetic.

## 3. Real-workflow justification

Ingestion and API clients need bounded producer/consumer pools. They must retain
request order for downstream correlation, isolate ordinary worker errors, and
fully clean up on either an internal deadline or caller cancellation.

## 4. Agent-visible inputs

The repository exposes the exact API contract, broken pool, synthetic jobs,
protected runner, and public asynchronous regressions.

## 5. Hidden ground truth

Hidden executable cohorts observe peak concurrency, stable input ordering,
heterogeneous values, isolated exceptions, tiny queue capacity, shutdown with
queued and running work, caller cancellation propagation, no surviving pool
tasks, validation before worker invocation, immutable inputs, and forbidden
source capabilities.

Required final workspace state is a repaired `repo/src/pool.py`, exact ordered
`repo/out/results.json`, reconciled `repo/out/audit.json`, and a complete
`repo/POOL_NOTES.md` verification handoff.

## 6. Expected workflow

1. Inspect `repo/docs/pool_contract.md`, `repo/jobs.json`, public async tests,
   and the unbounded `repo/src/pool.py` implementation.
2. Repair `repo/src/pool.py` preflight validation, bounded queueing, indexed
   results, ordinary exception isolation, and cancellation cleanup.
3. Run `repo/tests/test_public.py` and `repo/bin/run_batch.py` to generate the
   exact `repo/out/results.json` and `repo/out/audit.json` state.
4. Re-parse `repo/out/audit.json`, then document queue accounting,
   timeout/caller cancellation, and commands in `repo/POOL_NOTES.md`.

## 7. Harness demands

Concurrent code repair, queue invariants, cancellation state reasoning,
executable verification, exact structured output, and safety restraint are
required.

## 8. Stressors and difficulty

- **Plausible failure mode:** A solution wraps unbounded task creation in a
  semaphore, loses input order, lets one exception cancel siblings, misses
  `task_done()` on cancellation, returns before cleanup, swallows caller
  cancellation, or validates after work starts.
- **Difficulty rationale:** Correct behavior spans structural backpressure,
  concurrency observation, stable result attribution, two distinct
  cancellation authorities, exact queue accounting, leak-free asynchronous
  teardown, and pre-side-effect validation.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `bounded_ordered_failure_isolation` | 0.30 | core | Bounded workers preserve input order and isolate ordinary failures |
| `timeout_and_caller_cancellation_cleanup` | 0.25 | core | Internal shutdown and caller cancellation leave no pool task behind |
| `visible_batch_execution` | 0.10 | core | Protected visible execution is current and exactly reconciled |
| `verification_handoff` | 0.20 | handoff | The handoff explains queue and cancellation invariants with verification evidence |
| `source_input_and_execution_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/pool.py`, `repo/out/results.json`, `repo/out/audit.json`, `repo/POOL_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Candidate source is AST-audited and executed with only an allowlisted asyncio
import and constrained builtins. Filesystem, thread/process, network, private
attribute, reflection, and dynamic execution capabilities are rejected. Hidden
workers expose behavior rather than answer data.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma + OpenClaw pilot with timing-flake review.

- **Expected Gemma/OpenClaw failure modes:** semaphore-only unbounded fan-out,
  completion-order output, uncaught worker exceptions, incomplete deadline
  cleanup, swallowed caller cancellation, unbalanced `task_done()`, overly
  permissive source capabilities, or stale visible outputs.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `bounded_ordered_failure_isolation`.
- `validation_and_replay`: `timeout_and_caller_cancellation_cleanup`, `visible_batch_execution`, `source_input_and_execution_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
