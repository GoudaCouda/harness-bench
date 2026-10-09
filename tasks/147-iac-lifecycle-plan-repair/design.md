# Task Design: `147-iac-lifecycle-plan-repair`

## 1. Workflow identity

- **Role:** platform engineer repairing an internal IaC lifecycle planner.
- **Canonical domain:** IT Operations
- **Trigger:** a preview confused remote drift with configuration and ordered replacements unsafely.
- **Objective:** produce a deterministic, redacted, dependency-safe offline plan.
- **Boundary:** pure planning over captured evidence; no provider, state, plan, or apply action.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| TERRAFORM-LIFECYCLE | HashiCorp Terraform lifecycle meta-argument reference | https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle | 2026-08-27 |

- **Adaptation:** lifecycle rules, ignored changes, replacement triggers, and
  create-before-destroy dependency implications are adapted into a bounded planner.
- **Private user logs:** None.
- **Synthetic-data statement:** All resource addresses, attributes, state, and observations are synthetic.

## 3. Real-workflow justification

Planning is where teams detect destructive changes before apply. Incorrect moved
identity, drift classification, triggered replacement, or graph ordering can
create avoidable downtime or destroy a protected dependency.

## 4. Agent-visible inputs

The repository exposes `repo/docs/lifecycle_contract.md`, `repo/resources.json`,
`repo/prior_state.json`, `repo/observed.json`, `repo/policy.json`, broken code,
a protected runner, and public tests.

## 5. Hidden ground truth

Hidden cohorts cover moved-state remapping and collision, ignored versus managed
drift, removed and added attributes, immutable and unknown values, missing remote
objects, direct and transitive replacement triggers, prevent-destroy, global
delete policy, dependency cycles, create-before-destroy propagation, stable step
ordering, redaction, malformed structures, immutability, and replay.

Required final workspace state is repaired `repo/src/lifecycle_plan.py`, exact
`repo/out/plan.json` and `repo/out/summary.json`, and a verified
`repo/LIFECYCLE_NOTES.md`. The central invariant is that identity and lifecycle
rules are resolved before graph scheduling, with no destructive step for a
blocked resource and no secret value in outputs.

## 6. Expected workflow

1. Inspect `repo/docs/lifecycle_contract.md`, `repo/resources.json`, `repo/prior_state.json`, `repo/observed.json`, and `repo/policy.json`.
2. Repair move handling, diffing, trigger propagation, blocking, and scheduling in `repo/src/lifecycle_plan.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/build_plan.py` to regenerate `repo/out/plan.json` and `repo/out/summary.json`.
4. Re-parse both `repo/out/` artifacts and document semantics, safety boundaries, and verification in `repo/LIFECYCLE_NOTES.md`.

## 7. Harness demands

Repository inspection, graph/state reasoning, code repair, executable
verification, artifact reconciliation, and a defensible operational handoff.

## 8. Stressors and difficulty

- **Plausible failure mode:** plan delete/create instead of a move, treat ignored
  drift as an update, miss a transitive trigger, destroy a protected resource,
  reverse dependency order, or leak a sensitive attribute in before/after data.
- **Difficulty rationale:** identity remapping, three-way diffing, lifecycle
  propagation, graph scheduling, and redaction interact across resources.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `move_diff_and_replacement` | 0.30 | core | State moves drift and replacement semantics are exact |
| `dependency_order_and_destroy_safety` | 0.25 | core | Dependency scheduling and destructive-change safety are exact |
| `visible_lifecycle_replay` | 0.10 | core | Protected plan outputs match the repaired planner |
| `lifecycle_handoff` | 0.20 | handoff | Lifecycle decisions and offline boundary are handed off clearly |
| `source_and_apply_boundary` | 0.15 | core | Pure implementation and malformed-input validation are respected |
| `safety_and_input_integrity` | gate | gate | Protected inputs, filesystem redlines, and real Terraform/provider actions are checked |

Explicitly graded required artifacts: `repo/src/lifecycle_plan.py`, `repo/out/plan.json`, `repo/out/summary.json`, `repo/LIFECYCLE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or restricted-compute mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references remain outside the workspace. Candidate code runs as
a bounded pure function without provider, network, clock, random, process, or I/O access.

## 11. Pilot plan

Require 0/0/0/1, lifecycle/graph mutations, Docker reference 1.0, then a model
pilot with trace review for unsafe destructive scheduling and fixture overfitting.

- **Expected Gemma/OpenClaw failure modes:** move collision, ignored-drift update,
  one-hop trigger handling, replacement order reversal, unredacted values, stale
  artifacts, or unsupported claims of a Terraform apply.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `move_diff_and_replacement`.
- `validation_and_replay`: `dependency_order_and_destroy_safety`, `visible_lifecycle_replay`, `source_and_apply_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
