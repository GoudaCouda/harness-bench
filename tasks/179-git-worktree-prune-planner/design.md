# Task Design: `179-git-worktree-prune-planner`

## 1. Workflow identity

- **Role:** production engineer repairing main/locked/protected worktrees, dirty-state preservation, filesystem versus admin metadata, expiry boundary, safe prune, and registration repair.
- **Domain:** Software Engineering
- **Objective:** repair executable code, replay a local incident fixture, and leave a verifiable handoff.
- **Boundary:** local Docker workspace only; no external action.

## 2. Idea provenance

- **Source ID:** `HB-S200-THREE-WAY-MERGE`.
- **Primary source:** https://git-scm.com/docs/git-worktree (accessed 2026-08-31).
- **Adaptation:** The task narrows the public specification to main/locked/protected worktrees, dirty-state preservation, filesystem versus admin metadata, expiry boundary, safe prune, and registration repair; identifiers and incidents are synthetic, but the state transitions and boundary semantics are preserved.
- **Private user logs:** None.
- **Synthetic-data statement:** All identities, payloads, events, paths, domains, timestamps, and policies are synthetic.

## 3. Real-workflow justification

`Repair a safe Git worktree prune plan` is a production-adjacent code repair grounded in a public protocol or tool contract. It requires inspection, implementation, replay, and verification; it is not a one-step classification or an answer-shaped form.

## 4. Agent-visible inputs

The repository exposes the exact input/output schema and all normative rules in `repo/docs/contract.md`, plus a broken `plan_git_worktree_prune`, one replay fixture, a runner, and public smoke/immutability tests. The agent is not asked to guess an answer shape.

## 5. Hidden ground truth

Independent hidden cohorts vary main/locked/protected worktrees, dirty-state preservation, filesystem versus admin metadata, expiry boundary, safe prune, and registration repair, input ordering, exact inclusive/exclusive boundaries, ambiguity, duplicates, and malformed state. Reference code and expected results are absent from the agent workspace.

The required final workspace state contains repaired `repo/src/solution.py`, freshly generated and parseable `repo/out/result.json`, and substantive `repo/REPAIR_NOTES.md`; protected fixture and contract files remain unchanged.

## 6. Expected workflow

1. Inspect the contract, fixture, broken function, runner, and public tests.
2. Implement `plan_git_worktree_prune` without changing protected inputs.
3. Run public tests and `python3 bin/run_repair.py`, then re-open `out/result.json`.
4. Write `REPAIR_NOTES.md` with decisions, exact boundary handling, commands/results, and offline scope.

## 7. Harness demands

Repository inspection, code editing, multi-step terminal use, protocol reasoning, executable verification, artifact reconciliation, and a concise handoff.

## 8. Stressors and difficulty

**Plausible failure mode:** For `Repair a safe Git worktree prune plan`, a shallow repair may mishandle main/locked/protected worktrees, dirty-state preservation, filesystem versus admin metadata, expiry boundary, safe prune, and registration repair, pass the visible shape, and still produce an unsafe or stale neighboring decision.

**Difficulty rationale:** The task combines multiple interacting rules around main/locked/protected worktrees, dirty-state preservation, filesystem versus admin metadata, expiry boundary, safe prune, and registration repair, exact boundaries, ambiguity refusal, malformed input, and deterministic output. Difficulty comes from public protocol semantics and hidden neighboring-error combinations, not from secret output conventions.

## 9. Oracle design

Hidden primary and edge cohorts vary main/locked/protected worktrees, dirty-state preservation, filesystem versus admin metadata, expiry boundary, safe prune, and registration repair, input ordering, exact boundaries, and malformed/duplicate state. The independent Oracle grades behavior in repaired `repo/src/solution.py` at 0.35 + 0.25; fresh `repo/out/result.json` replay is 0.20; `repo/REPAIR_NOTES.md` is 0.20. The bounded semantic judge can recognize equivalent handoff prose only and can never rescue structured behavior. The zero-weight safety gate covers protected-source mutation, unsafe filesystem nodes, and affirmative external-action claims.

Reference, empty, untouched, and malformed candidates must score 1/0/0/0.

## 10. Leakage, isolation, and safety review

Ground truth remains outside the workspace. Candidate code runs through the bounded pure-function worker; inputs are immutable and evaluation is offline. Only genuine protected-state, unsafe-node, or false external-action red lines can zero the score.

## 11. Pilot plan

Run schema/design/leakage checks, reference-empty-untouched-malformed quality, neighboring-error discrimination, production Docker reference grading, then a fresh local-model trajectory review of implementation and score behavior.

**Expected Gemma/OpenClaw failure modes:** On `Repair a safe Git worktree prune plan`, expect stopping after public smoke tests, collapsing main/locked/protected worktrees, dirty-state preservation, filesystem versus admin metadata, expiry boundary, safe prune, and registration repair into a generic policy loop, leaving stale replay output, or asserting verification without re-opening the generated artifact.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

The four positive outcomes retain weights 0.35, 0.25, 0.20, and 0.20.
Invalid source is an ordinary scored failure; the zero-weight gate is limited
to protected-input mutation, unsafe workspace nodes, and narrowly scoped false
claims about live Git prune/repair or worktree deletion.

## Environment/runtime review (Standard207)

This task uses the shared environment and requires Git 2.39.5 in addition to
Python 3.12. Its agent verifier creates a real temporary Git repository and
linked worktrees, removes only the temporary filesystem paths, and checks
git-worktree porcelain plus prune dry-run behavior. It also confirms that a
locked missing worktree is not proposed for pruning. The task itself remains a
non-destructive planner over captured repository metadata; no user worktree is
mutated. The grader verifier checks the bounded pure worker and grading APIs
used by the Oracle.
