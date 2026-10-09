# Task Design: `103-plugin-lifecycle-transaction-repair`

## 1. Workflow identity

- **Role:** application-platform engineer repairing an extension host.
- **Trigger:** failed activation left stale hooks and wrong dependency order.
- **Objective:** reconcile requested lifecycle state transactionally and deterministically.
- **Boundary:** model local registry state only; never import or install plugins.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| PLUGGY-DOCS | Pluggy plugin registration and hook calling | https://pluggy.readthedocs.io/en/stable/ | 2026-08-27 |
| PYTHON-IMPORTLIB-METADATA | Python entry-point metadata | https://docs.python.org/3/library/importlib.metadata.html | 2026-08-27 |

- **Adaptation:** plugin registration, discovery metadata, and hook ownership
  are adapted into a transactional offline lifecycle and stale-hook recovery state machine.
- **Private user logs:** None.
- **Synthetic-data statement:** All plugins, hooks, requests, faults, and registry states are synthetic.

## 3. Real-workflow justification

Extension hosts must order dependencies, clean registrations owned by disabled
plugins, and recover failed hooks without leaving half-activated state. These
are durable operational invariants rather than answer formatting.

## 4. Agent-visible inputs

The workspace exposes the lifecycle contract, catalog, stale state, desired
request, deterministic fault injection, runner, broken code, and public tests.

## 5. Hidden ground truth

Hidden cases exercise dependency enable closure, reverse-dependent disable
closure, lexical topological ties, stale and duplicate registration cleanup,
unknown/conflicting requests, activation/deactivation failures, exact rollback,
no-op generation, malformed graphs, and argument immutability.

Required final workspace state is repaired `repo/src/plugin_lifecycle.py`, exact
`repo/out/state.json` and `repo/out/journal.json`, and a verified
`repo/LIFECYCLE_NOTES.md`. The state invariant is all-or-nothing lifecycle
transition: any injected failure restores the exact prior generation and registry.

## 6. Expected workflow

1. Inspect `repo/docs/lifecycle_contract.md`, `repo/catalog.json`, current state, request, and fault plan.
2. Repair graph validation, closure ordering, registry cleanup, and rollback in `repo/src/plugin_lifecycle.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/reconcile_plugins.py` to regenerate `repo/out/state.json` and `repo/out/journal.json`.
4. Reconcile output state and journal, then document transaction boundaries in `repo/LIFECYCLE_NOTES.md`.

## 7. Harness demands

Graph reasoning, code repair, transactional state management, failure handling,
artifact generation, and executable verification are all required.

## 8. Stressors and difficulty

- **Plausible failure mode:** enable before dependencies, disable dependencies
before dependents, silently ignoring unknown plugins, preserving stale hooks,
or roll back only the last operation.
- **Difficulty rationale:** Coupled graph closure, deterministic ordering, stale
  ownership cleanup, and inverse rollback make this materially harder than a topological-sort exercise.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `dependency_closure_and_order` | 0.30 | core | Dependency closures and lifecycle order are deterministic |
| `transactional_rollback_and_rejection` | 0.25 | core | Faults and request conflicts preserve exact registry state |
| `visible_lifecycle_replay` | 0.10 | core | Protected fixture state and journal match the repaired engine |
| `lifecycle_handoff` | 0.20 | handoff | Lifecycle invariants and verification are handed off clearly |
| `source_and_loading_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/plugin_lifecycle.py`, `repo/out/state.json`, `repo/out/journal.json`, `repo/LIFECYCLE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden references stay under tests. Candidate code executes as a bounded pure
function with `copy` only; no dynamic loading or external capability is exposed.

## 11. Pilot plan

Require 0/0/0/1, adjacent lifecycle-fault discrimination, Docker reference 1.0,
and a fresh model pilot; investigate shared failure patterns for ambiguity.

- **Expected Gemma/OpenClaw failure modes:** incomplete dependency closure,
  reversed deactivation order, stale-hook retention, partial rollback,
  generation drift on no-op, stale output artifacts, or weak handoff evidence.

## 12. Human validation status

- **Status:** `not_required`.
- Automated semantic and calibration gates are authoritative for this release.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `dependency_closure_and_order`.
- `validation_and_replay`: `transactional_rollback_and_rejection`, `visible_lifecycle_replay`, `source_and_loading_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
