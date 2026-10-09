# Task Design: `153-github-actions-matrix-rerun`

## 1. Workflow identity

- **Role:** CI platform engineer repairing a failed-run recovery planner.
- **Canonical domain:** IT Operations
- **Trigger:** matrix recovery omitted dependents and nearly replayed deployment side effects.
- **Objective:** compute minimal DAG-aware rerun/manual/keep decisions.
- **Boundary:** offline plan only; no GitHub API or workflow dispatch.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| GITHUB-ACTIONS-WORKFLOW | GitHub Actions workflow syntax | https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax | 2026-08-28 |

- **Adaptation:** job needs, matrix expansion, statuses, and rerun concerns become a deterministic explicit-instance recovery planner.
- **Private user logs:** None.
- **Synthetic-data statement:** All workflows, jobs, shards, attempts, and statuses are synthetic.

## 3. Real-workflow justification

Matrix instances coexist with job-level fan-in. Recovery may require skipped
dependents and artifact consumers, while successful side effects need approval.

## 4. Agent-visible inputs

Contract, workflow DAG, latest runs, policy, broken planner, runner, public tests.

## 5. Hidden ground truth

Cases cover cycles, topology, complete evidence, matrix fan-in, failure and
cancellation policy, stale output, skipped propagation, consumer closure,
side-effect/manual boundaries, ordering, summary, and immutability. Required
final state is repaired `repo/src/rerun_planner.py`, exact
`repo/out/plan.json`, exact `repo/out/summary.json`, and verified
`repo/RERUN_NOTES.md`; selected upstream job IDs create fan-in impact without
automatically replaying unrelated successful instances.

## 6. Expected workflow

1. Inspect `repo/docs/rerun_contract.md`, `repo/workflow.json`, `repo/runs.json`, and `repo/policy.json`.
2. Repair topological ordering, classification, selected-job closure, artifact consumption, and side effects in `repo/src/rerun_planner.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/plan_rerun.py` to regenerate `repo/out/plan.json` and `repo/out/summary.json`.
4. Re-parse outputs and document matrix/DAG semantics, verification, and GitHub boundary in `repo/RERUN_NOTES.md`.

## 7. Harness demands

Graph reasoning, state classification, coding, verification, and handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** rerun every shard, ignore artifact consumers, leave skipped dependents, or automatically repeat deployments.
- **Difficulty rationale:** decisions are per instance while dependency/artifact impact is per job, with a manual side-effect boundary.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `dag_matrix_and_status_closure` | 0.30 | core | DAG matrix failures cancellations and skipped jobs close minimally |
| `artifact_and_side_effect_boundary` | 0.25 | core | Stale artifacts propagate while side effects remain manual |
| `rerun_replay` | 0.10 | core | Protected plan and summary match the repaired planner |
| `rerun_handoff` | 0.20 | handoff | CI recovery semantics and offline boundaries are handed off clearly |
| `source_and_github_boundary` | 0.15 | core | Pure implementation and malformed-input validation are respected |
| `safety_and_input_integrity` | gate | gate | Protected inputs, filesystem redlines, and real GitHub/CI actions are checked |

Explicitly graded required artifacts: `repo/src/rerun_planner.py`, `repo/out/plan.json`, `repo/out/summary.json`, `repo/RERUN_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or restricted-compute mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases/reference remain outside workspace; candidate code is pure.

## 11. Pilot plan

Require 0/0/0/1, discrimination, Docker 1.0, then model trace review.

- **Expected Gemma/OpenClaw failure modes:** lexical order, shard-local fan-in,
  over-rerun, deployment auto-rerun, stale outputs, or GitHub action claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `dag_matrix_and_status_closure`.
- `validation_and_replay`: `artifact_and_side_effect_boundary`, `rerun_replay`, `source_and_github_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
