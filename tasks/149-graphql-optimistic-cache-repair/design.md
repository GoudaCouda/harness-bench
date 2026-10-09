# Task Design: `149-graphql-optimistic-cache-repair`

## 1. Workflow identity

- **Role:** frontend-platform engineer repairing a normalized optimistic cache reducer.
- **Trigger:** out-of-order mutation completion erased a later edit and rollback left a dangling temporary entity.
- **Objective:** reconcile canonical base and visible layered cache deterministically.
- **Boundary:** offline normalized event replay; no GraphQL request, browser state, or application mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| APOLLO-NORMALIZED-CACHE | Apollo Client caching overview | https://www.apollographql.com/docs/react/caching/overview | 2026-08-27 |
| APOLLO-OPTIMISTIC-UI | Apollo Client optimistic mutation results | https://www.apollographql.com/docs/react/performance/optimistic-ui | 2026-08-27 |

- **Adaptation:** normalized entity merge and temporary optimistic layers are
  adapted into a deterministic reducer-repair workflow.
- **Private user logs:** None.
- **Synthetic-data statement:** All entities, fields, mutations, aliases, and values are synthetic.

## 3. Real-workflow justification

Interactive clients often have several pending mutations over one normalized
entity. Correctly removing one layer, committing a server response, and rebasing
later layers is necessary to prevent flicker, stale state, and dangling refs.

## 4. Agent-visible inputs

The repository exposes `repo/docs/cache_contract.md`, `repo/base.json`,
`repo/events.json`, `repo/policy.json`, broken code, a runner, and public tests.

## 5. Hidden ground truth

Hidden cohorts cover field merge versus replacement, explicit null versus
missing, normalized references, overlapping layers, out-of-order success,
selective error rollback, ignored optimistic updates, temporary-to-server ID
aliases, reference rewriting in base and pending layers, target merge precedence,
dangling refs, malformed event state, immutability, and deterministic audit.

Required final workspace state is repaired `repo/src/optimistic_cache.py`, exact
`repo/out/base.json`, `repo/out/visible.json`, `repo/out/audit.json`, and a
verified `repo/CACHE_NOTES.md`. Resolving one mutation must never flatten or
discard a later active optimistic layer.

## 6. Expected workflow

1. Inspect `repo/docs/cache_contract.md`, `repo/base.json`, `repo/events.json`, and `repo/policy.json`.
2. Repair layer projection, commit/rollback, alias rewriting, and validation in `repo/src/optimistic_cache.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/reconcile_cache.py` to regenerate all three `repo/out/` artifacts.
4. Re-parse the artifacts and document cache semantics, verification, and network boundary in `repo/CACHE_NOTES.md`.

## 7. Harness demands

Repository inspection, normalized graph reasoning, transactional code repair,
executable verification, artifact reconciliation, and handoff are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** replace records instead of merging fields, treat
  null as missing, commit optimistic values to base, roll back all layers, apply
  responses in start order, or rewrite only base refs during ID aliasing.
- **Difficulty rationale:** canonical and visible states diverge while several
  layers overlap and resolve in an order different from creation.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `layer_commit_rollback_and_rebase` | 0.30 | core | Optimistic layers commit rollback and rebase independently |
| `normalized_merge_alias_and_reference_safety` | 0.25 | core | Normalized field merges aliases and references remain exact |
| `visible_cache_replay` | 0.10 | core | Protected cache outputs match the repaired reducer |
| `cache_handoff` | 0.20 | handoff | Cache reconciliation and offline boundaries are handed off clearly |
| `source_and_network_boundary` | 0.15 | core | Pure implementation and malformed-input validation are respected |
| `safety_and_input_integrity` | gate | gate | Protected inputs, filesystem redlines, and real GraphQL/browser actions are checked |

Explicitly graded required artifacts: `repo/src/optimistic_cache.py`, `repo/out/base.json`, `repo/out/visible.json`, `repo/out/audit.json`, `repo/CACHE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or restricted-compute mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references stay outside the workspace. Candidate code runs as
a bounded pure function without network, filesystem, clock, random, process, or environment access.

## 11. Pilot plan

Require 0/0/0/1, adjacent layer and alias mutations, Docker reference 1.0, then
a model pilot with trace review for destructive flattening of pending layers.

- **Expected Gemma/OpenClaw failure modes:** whole-record replacement, null loss,
  global rollback, stale response overwrite, partial ref rewrite, dangling temp
  IDs, stale outputs, or unsupported claims of live mutations.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `layer_commit_rollback_and_rebase`.
- `validation_and_replay`: `normalized_merge_alias_and_reference_safety`, `visible_cache_replay`, `source_and_network_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
