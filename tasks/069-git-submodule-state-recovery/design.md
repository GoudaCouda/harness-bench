# Task Design: `069-git-submodule-state-recovery`

## 1. Workflow identity

- **Role:** release engineer recovering a submodule-based checkout.
- **Trigger:** status contains uninitialized, mismatched, dirty, conflicted, and nested children.
- **Objective:** plan restoration to recorded gitlinks without destroying local work.
- **Boundary:** no fetch, checkout, reset, clean, push, or remote-tip update is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| GIT-SUBMODULE | Git submodule command documentation | https://git-scm.com/docs/git-submodule | 2026-08-27 |
| GIT-STATUS-SUBMODULE | Git status submodule state documentation | https://git-scm.com/docs/git-status | 2026-08-27 |
| GIT-SUBMODULES | Git submodule data-model documentation | https://git-scm.com/docs/gitsubmodules | 2026-08-27 |

- **Adaptation:** recorded gitlink, checkout, dirty-worktree, missing-object, and recursive status semantics become a deterministic offline recovery plan.
- **Private user logs:** None; paths and object IDs are synthetic. All fixtures and expected outcomes are synthetic.
- **Synthetic-data statement:** All fixtures, object IDs, paths, and expected outcomes are synthetic.

## 3. Real-workflow justification

Submodules pin dependency commits in the superproject while each child has its
own worktree and object database. Blindly following a remote branch or forcing a
checkout can both violate release reproducibility and destroy uncommitted work.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/submodule_contract.md` | authoritative recovery and safety contract |
| `repo/src/submodule_recovery.py` | broken remote-tip planner |
| `repo/submodule_cases.json` | visible captured status inventories |
| `repo/tests/test_public.py` | public regressions |

## 5. Hidden ground truth

Hidden cohorts execute `repo/src/submodule_recovery.py` with extensions of
`repo/submodule_cases.json` and `repo/docs/submodule_contract.md`: exact and
mismatched gitlinks, uninitialized children, absent objects, dirty/untracked
state, merge conflicts, recursion filtering, unsafe paths, duplicate records,
malformed SHA and type state, and immutable inputs. Final state also requires
exact `repo/recovery_report.json` and grounded `repo/REPAIR_NOTES.md`.

## 6. Expected workflow

1. Read `repo/docs/submodule_contract.md`, `repo/submodule_cases.json`, and `repo/tests/test_public.py`.
2. Repair validation and gitlink authority in `repo/src/submodule_recovery.py`.
3. Add local-change, conflict, missing-object, and recursion handling in `repo/src/submodule_recovery.py`.
4. Generate `repo/recovery_report.json` in visible case order.
5. Record exact verification and executor risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

Repository inspection, code execution, exact JSON generation, Git state-model
reasoning, verification, and destructive-action restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** choose `remote_sha`, collapse dirty and mismatch,
  force an absent object, process nested records without recursion, or let
  conflict lose precedence over local-change handling.
- **Difficulty rationale:** each plan requires authority, object availability,
  worktree safety, and nested scope to agree before a target is proposed.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `gitlink_authority_and_checkout_state` | 0.35 | core | Recorded gitlinks govern initialization and checkout recovery |
| `local_change_conflict_and_recursion_safety` | 0.25 | core | Local work, conflicts, missing objects, and nesting fail closed |
| `visible_recovery_report` | 0.05 | core | Visible submodule incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Gitlink recovery and executor risk are handed off |
| `evidence_and_git_action_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/submodule_recovery.py`, `repo/recovery_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and references are excluded. Candidate code is pure-audited with
no imports; filesystem, network, process, Git execution, private attributes, and
dynamic execution are unavailable. Grading is read-only and offline.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, and Docker reference 1.0,
then run Gemma + OpenClaw and inspect state-level failures.

- **Expected Gemma/OpenClaw failure modes:** remote-tip targeting, forced dirty
  checkout, wrong conflict precedence, missing-object fetch assumptions, or report drift.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `gitlink_authority_and_checkout_state`.
- `validation_and_replay`: `local_change_conflict_and_recursion_safety`, `visible_recovery_report`, `evidence_and_git_action_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
