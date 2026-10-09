# Task Design: `119-selective-restore-manifest-repair`

## 1. Workflow identity

- **Role:** backup operator preparing a selective restore review.
- **Trigger:** an incremental chain and existing target contain ambiguous overwrite state.
- **Objective:** reconstruct the selected snapshot and produce a dry-run action plan.
- **Boundary:** no restore, delete, mount, or repository mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| RESTIC-RESTORE | Restic restoring, selection, overwrite, delete, and dry-run guidance | https://restic.readthedocs.io/en/stable/050_restore.html | 2026-08-27 |

- **Adaptation:** selective restore and dry-run mechanics are adapted into an
  offline incremental-snapshot ancestry, tombstone, and destination-conflict planner.
- **Private user logs:** None.
- **Synthetic-data statement:** All repositories, snapshots, paths, hashes, requests, and target inventories are synthetic.

## 3. Real-workflow justification

A safe restore depends on exact snapshot identity, ancestry, tombstones, scope,
and destination type/content state. A plausible file list is not sufficient.

## 4. Agent-visible inputs

The workspace exposes snapshot manifests, target inventory, an explicit request,
contract, broken planner, runner, and public tests.

## 5. Hidden ground truth

Hidden cases cover branch selection, missing/incomplete ancestry, ordered
tombstone replay, path boundaries, include/exclude segment scope, unsupported
types, identical files, overwrite modes, file/directory collisions, target-root
mapping, strict shapes, and source immutability.

Required final workspace state is repaired `repo/src/restore_planner.py`, exact
`repo/out/plan.json` and `repo/out/summary.json`, and a verified
`repo/RESTORE_NOTES.md`. The key invariant is that selected snapshot ancestry
fully determines restored state before include/exclude and target-state planning.

## 6. Expected workflow

1. Inspect `repo/docs/restore_contract.md`, snapshot catalog, request, and target inventory state.
2. Repair ancestry validation, manifest replay, filtering, and action planning in `repo/src/restore_planner.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/plan_restore.py` to regenerate both `repo/out/` artifacts.
4. Re-parse `repo/out/plan.json` and `repo/out/summary.json`, then document dry-run boundaries in `repo/RESTORE_NOTES.md`.

## 7. Harness demands

Graph/state reconstruction, path reasoning, code repair, structured diffing,
executable validation, and safety verification are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** select `latest`, replay a sibling branch, retain
deleted descendants, substring path matching, overwriting equal files, treating
a directory as a file, or plan deletes outside scope.
- **Difficulty rationale:** Coupled ancestry reconstruction, tombstones, path
  segments, destination types, and overwrite safety make this harder than archive extraction.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `selected_ancestry_replay_and_scope` | 0.30 | core | Selected snapshot ancestry tombstones and scope are exact |
| `destination_action_safety` | 0.25 | core | Destination comparisons produce safe dry-run actions |
| `visible_restore_plan` | 0.10 | core | Protected plan and summary match the repaired planner |
| `restore_handoff` | 0.20 | handoff | Restore invariants and verification are handed off clearly |
| `source_path_and_execution_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/restore_planner.py`, `repo/out/plan.json`, `repo/out/summary.json`, `repo/RESTORE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden references remain under tests. Candidate code executes as a bounded pure
function with no imports or filesystem access.

## 11. Pilot plan

Require 0/0/0/1, branch/tombstone/scope/type mutations, Docker reference 1.0,
then a fresh model pilot with trace review for unauthorized execution.

- **Expected Gemma/OpenClaw failure modes:** selecting latest instead of the
  requested snapshot, branch leakage, incomplete tombstones, substring scope,
  unsafe type replacement, accidental execution, stale artifacts, or weak handoff evidence.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic recovery and calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `selected_ancestry_replay_and_scope`.
- `validation_and_replay`: `destination_action_safety`, `visible_restore_plan`, `source_path_and_execution_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
