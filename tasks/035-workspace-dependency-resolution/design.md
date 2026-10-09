# Task Design: `035-workspace-dependency-resolution`

## 1. Workflow identity

- **Role:** release engineer repairing a monorepo lock resolver.
- **Trigger:** a refresh upgrades healthy locks and accepts an invalid peer set.
- **Objective:** produce one deterministic, platform-valid dependency graph.
- **Boundary:** no registry request, package installation, publication, or deployment.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| NPM-PACKAGE-JSON | npm package.json | https://docs.npmjs.com/cli/v11/configuring-npm/package-json | 2026-08-26 |
| NPM-PACKAGE-LOCK | npm package-lock.json | https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json | 2026-08-26 |

- **Adaptation:** npm peer, optional, OS/CPU, and lock metadata become a bounded exact/caret graph solver with an explicit minimal-change objective and synthetic registry snapshots.
- **Private user logs:** None were used; package names, versions, and locks are synthetic.

## 3. Real-workflow justification

Lock refreshes are global constraint problems. A locally reasonable highest
version can invalidate a peer, and optional native packages differ by target.
The repair combines code, registry evidence, execution, and a release handoff.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/resolution_contract.md` | authoritative graph/objective rules |
| `repo/src/resolver.py` | broken greedy resolver |
| `repo/resolution_cases.json` | visible manifests, registries, locks, targets |
| `repo/tests/test_public.py` | public minimal-lock and platform checks |

## 5. Hidden ground truth

Hidden graphs extend `repo/resolution_cases.json` with transitive dependency,
required/optional peer, deny-marker, cycle, and tie states. Final
`repo/src/resolver.py` must find a complete graph before selecting versions, and
`repo/resolution_report.json` must preserve each visible case decision exactly.

## 6. Expected workflow

1. Read `repo/docs/resolution_contract.md` and map version/peer graph keys.
2. Execute `repo/tests/test_public.py` against the current lock state.
3. Replace greedy selection in `repo/src/resolver.py` with bounded global search.
4. Generate `repo/resolution_report.json` and verify deterministic ordering.
5. Record supported ranges and production-manager risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

The harness needs multi-file grounding, code execution, graph/state reasoning,
exact structured output, verification, and restraint at registry boundaries.

## 8. Stressors and difficulty

- **Plausible failure mode:** choose highest first, make optional roots required,
  ignore negative markers, auto-accept optional peers, or rewrite valid locks.
- **Difficulty rationale:** correct output depends on a global objective after all
  transitive and peer constraints, so per-package fixes are insufficient.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `required_graph_and_peer_compatibility` | 0.40 | core | Required dependency and peer graph resolves globally |
| `platform_optional_and_lock_stability` | 0.20 | core | Platform, optional, and existing lock state reconcile safely |
| `visible_resolution_report` | 0.05 | core | Visible resolutions are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Resolution decisions and verification are handed off |
| `source_and_workspace_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/resolver.py`, `repo/resolution_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

The mini-registry is visible but hidden graph combinations and the independent
solver are not. Pure candidate execution has no import, filesystem, process,
network, or dynamic-call access. Evidence mutation and publication claims fail.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, then run one fresh
Gemma + OpenClaw trial and review both selected graph and unsuccessful branches.

- **Expected Gemma/OpenClaw failure modes:** greedy peer conflict, optional-root
  overconstraint, platform deny omission, version-string sorting, or lock churn.

## 12. Human validation status

- **Status:** `not_required`.
- Automated acceptance and model calibration remain required; no human approval is claimed.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `required_graph_and_peer_compatibility`.
- `validation_and_replay`: `platform_optional_and_lock_stability`, `visible_resolution_report`, `source_and_workspace_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
