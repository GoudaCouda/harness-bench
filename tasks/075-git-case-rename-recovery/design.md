# Task Design: `075-git-case-rename-recovery`

## 1. Workflow identity

- **Role:** repository maintainer recovering a cross-platform rename batch.
- **Trigger:** case-only and cyclic renames collide on an ignore-case checkout.
- **Objective:** produce an ordered, identity-preserving, no-overwrite plan.
- **Boundary:** no captured checkout, remote, or production mutation is authorized;
  tests may create and mutate a disposable local Git repository under the test
  temporary directory.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| GIT-MV | Git `mv` documentation | https://git-scm.com/docs/git-mv.html | 2026-08-27 |
| GIT-CORE-IGNORECASE | Git `core.ignoreCase` documentation | https://git-scm.com/docs/git-config#Documentation/git-config.txt-coreignoreCase | 2026-08-27 |

- **Adaptation:** Git rename and casefold behavior becomes a captured-index recovery
  plan whose operations are replayed against a disposable local Git repository.
- **Private user logs:** None.
- **Synthetic-data statement:** Paths, OIDs, requests, and collisions are synthetic.

## 3. Real-workflow justification

Case-only renames frequently cross Linux, Windows, and macOS checkouts. Direct
bulk moves can overwrite a tracked path or lose which blob belonged to which
destination, especially in swaps and longer cycles.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/rename_contract.md` | authoritative planner contract |
| `repo/src/case_rename.py` | broken planner |
| `repo/rename_cases.json` | visible incidents |
| `repo/tests/test_public.py` | public regressions |
| `repo/tests/test_git_integration.py` | real local Git replay and blob-identity check |

## 5. Hidden ground truth

Hidden cohorts extend the agent-visible `repo/rename_cases.json` and
`repo/docs/rename_contract.md` with case-only moves, direct moves, two- and
three-node cycles, temporary-name collisions, OID preservation, casefold
duplicate entries, occupied non-source destinations, unsafe paths, missing
sources, unmerged stages, malformed hashes and Boolean flags, and immutable
evidence. The central invariant is that each tracked OID survives under exactly
one final path after every ordered operation. Required final state includes
repaired `repo/src/case_rename.py`, exact `repo/rename_plan.json`, and verified
`repo/REPAIR_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/rename_contract.md`, `repo/rename_cases.json`, and `repo/tests/test_public.py`.
2. Validate captured index entries and requests in `repo/src/case_rename.py`.
3. Order free destinations and deterministic temporary hops in `plan_case_renames`.
4. Generate exact `repo/rename_plan.json` rows for every visible `case_id`.
5. Explain status/OID verification and executor risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

Repository inspection, code execution, graph/state reasoning, exact JSON,
verification, and Git-action restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** direct case-only move, force overwrite, unstable temporary names, or OID/path reassociation during a cycle.
- **Difficulty rationale:** ordered operations must remain valid after every prior operation under two path-comparison regimes.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `casefold_and_cycle_planning` | 0.35 | core | Case-only and cyclic renames receive deterministic temporary hops |
| `index_identity_and_collision_safety` | 0.25 | core | Object identity is preserved while malformed or colliding batches fail closed |
| `visible_rename_plan` | 0.05 | core | Visible rename incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Filesystem and index risks are handed off |
| `evidence_and_git_action_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/case_rename.py`, `repo/rename_plan.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and references are excluded. Candidate planner code is
pure-audited with ordinary computation-only imports available; filesystem,
process, network, private-attribute, and dynamic execution remain unavailable to
that code. The visible suite replays a plan using real `git init`, `git add`,
`git commit`, and `git mv` commands only inside a disposable local fixture.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma + OpenClaw run and cohort-level review.

- **Expected Gemma/OpenClaw failure modes:** incorrect cycle order, casefold collision drift, unsafe temporary path, or identity loss.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `casefold_and_cycle_planning`.
- `validation_and_replay`: `index_identity_and_collision_safety`, `visible_rename_plan`, `evidence_and_git_action_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
