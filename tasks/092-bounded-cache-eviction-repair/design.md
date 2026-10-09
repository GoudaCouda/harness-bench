# Task Design: `092-bounded-cache-eviction-repair`

## 1. Workflow identity

- **Role:** platform engineer repairing an in-process metadata cache.
- **Trigger:** TTL boundaries and eager eviction caused stale reads and destructive failed writes.
- **Objective:** implement validated transactional TTL/LRU replay with pinned capacity.
- **Boundary:** offline state replay only; no production cache mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| PYTHON-FUNCTOOLS-LRU | Python functools caching documentation | https://docs.python.org/3/library/functools.html#functools.lru_cache | 2026-08-27 |

- **Adaptation:** bounded recency and cache accounting are extended into a synthetic persisted TTL/pinning recovery workflow.
- **Private user logs:** None.
- **Synthetic-data statement:** Keys, values, clocks, capacities, and operations are synthetic.

## 3. Real-workflow justification

Bounded caches combine expiry, recency, overwrite accounting, and entries that
cannot be evicted during critical work. A failed insert must not corrupt useful
state while checking whether it can fit.

## 4. Agent-visible inputs

An exact contract, state, policy, operation replay, broken engine, protected
runner, and public tests form the executable repository.

## 5. Hidden ground truth

Hidden cohorts cover inclusive TTL, access counters, lexical LRU ties, pinned
capacity, successful and failed overwrites, oversize writes, deep-copied JSON,
canonical state, invalid sequences, and immutable inputs. Visible artifacts are
independently rebuilt from submitted source.

Required final workspace state is repaired `repo/src/cache_engine.py`, exact
`repo/out/state.json` and `repo/out/events.json`, and `repo/CACHE_NOTES.md`. The
key invariant is that a rejected put commits no planned victim or overwrite.

## 6. Expected workflow

1. Inspect `repo/docs/cache_contract.md`, `repo/state.json`, `repo/operations.json`, and policy.
2. Repair preflight and transactional replay in `repo/src/cache_engine.py`.
3. Run public tests and `repo/bin/replay_cache.py` to create state and event outputs.
4. Re-parse both outputs and record invariants and commands in `repo/CACHE_NOTES.md`.

## 7. Harness demands

Repository inspection, state-machine repair, capacity planning, deterministic
ordering, execution, artifact reconciliation, and verification are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** use `<` at expiry, update misses, evict pinned
  entries, miscount overwrite size, apply victims before a failed fit, or accept booleans as integers.
- **Difficulty rationale:** correctness spans time, recency, transactional
  capacity, immutable values, deterministic evidence, and preflight validation.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `ttl_lru_and_overwrite` | 0.30 | core | TTL and LRU state transitions preserve exact recency and capacity |
| `pinned_transactional_failure` | 0.25 | core | Pinned capacity and failed writes preserve durable cache state |
| `visible_cache_replay` | 0.10 | core | Protected replay artifacts match the repaired state machine |
| `verification_handoff` | 0.20 | handoff | Cache invariants and verification are handed off clearly |
| `source_and_runtime_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/cache_engine.py`, `repo/out/state.json`, `repo/out/events.json`, `repo/CACHE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references are excluded. Pure execution permits only `copy`
and `math`; filesystem, process, network, private attributes, and dynamic calls are unavailable.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, and a fresh
Gemma/OpenClaw pilot focused on state semantics rather than formatting.

- **Expected Gemma/OpenClaw failure modes:** eager victim removal, incorrect TTL
  inequality, recency updates on misses, pinned eviction, stale output, or weak validation.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `ttl_lru_and_overwrite`.
- `validation_and_replay`: `pinned_transactional_failure`, `visible_cache_replay`, `source_and_runtime_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
