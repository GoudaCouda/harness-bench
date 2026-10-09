# Task Design: `148-kubernetes-field-ownership-repair`

## 1. Workflow identity

- **Role:** platform engineer repairing a controller's Server-Side Apply preview.
- **Canonical domain:** IT Operations
- **Trigger:** rejected intents caused partial field release and forced updates crossed an ownership boundary.
- **Objective:** project atomic field values and ownership for a sequence of apply intents.
- **Boundary:** offline flattened-field planning; no API server, manifest apply, or managedFields mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| KUBERNETES-SSA | Kubernetes Server-Side Apply documentation | https://kubernetes.io/docs/reference/using-api/server-side-apply/ | 2026-08-27 |

- **Adaptation:** field conflicts, force-conflicts, shared ownership, and omitted
  field release are adapted into a deterministic controller repair workflow.
- **Private user logs:** None.
- **Synthetic-data statement:** All objects, managers, field paths, intents, and values are synthetic.

## 3. Real-workflow justification

Controllers frequently collaborate on one Kubernetes object. Incorrect field
ownership logic can overwrite autoscaler or policy-controller intent, while a
non-atomic rejection can silently delete unrelated fields.

## 4. Agent-visible inputs

The repository exposes `repo/docs/field_contract.md`, `repo/live.json`,
`repo/ownership.json`, `repo/defaults.json`, `repo/intents.json`,
`repo/policy.json`, broken code, a runner, and public tests.

## 5. Hidden ground truth

Hidden cohorts cover unowned writes, own-field changes, same-value sharing,
multi-owner conflicts, force takeover, protected conflicts, transactional
rejection, previous-owner omission, shared-owner release, default restoration,
deletion, sequential visibility, canonical paths, malformed structures,
immutability, deterministic decisions, and offline boundaries.

Required final workspace state is repaired `repo/src/field_ownership.py`, exact
`repo/out/object.json`, `repo/out/ownership.json`, `repo/out/decisions.json`, and
a verified `repo/FIELD_NOTES.md`. A rejected request must make no value or
ownership change, including omission release.

## 6. Expected workflow

1. Inspect `repo/docs/field_contract.md`, `repo/live.json`, `repo/ownership.json`, `repo/defaults.json`, `repo/intents.json`, and `repo/policy.json`.
2. Repair conflict detection, force/protection, sharing, omission, defaults, and sequential state in `repo/src/field_ownership.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/apply_intents.py` to regenerate the three `repo/out/` artifacts.
4. Re-parse all outputs and document semantics, verification, and the cluster boundary in `repo/FIELD_NOTES.md`.

## 7. Harness demands

Repository inspection, transactional state reasoning, code repair, executable
verification, artifact reconciliation, and safety handoff are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** release omitted fields before discovering a
  conflict, conflict on same values, force protected fields, retain displaced
  owners, delete shared fields, or evaluate every intent against stale state.
- **Difficulty rationale:** value state and ownership state change together,
  with transactional rejection and sequential effects across managers.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `atomic_conflict_force_and_ownership` | 0.30 | core | Apply conflicts force and ownership transitions are atomic |
| `omission_default_and_sequential_state` | 0.25 | core | Omission release defaults deletion and sequential state are exact |
| `visible_field_replay` | 0.10 | core | Protected field outputs match the repaired planner |
| `field_handoff` | 0.20 | handoff | Field-management decisions and cluster boundary are handed off clearly |
| `source_and_cluster_boundary` | 0.15 | core | Pure implementation and malformed-input validation are respected |
| `safety_and_input_integrity` | gate | gate | Protected inputs, filesystem redlines, and real Kubernetes/cluster actions are checked |

Explicitly graded required artifacts: `repo/src/field_ownership.py`, `repo/out/object.json`, `repo/out/ownership.json`, `repo/out/decisions.json`, `repo/FIELD_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or restricted-compute mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references stay outside the workspace. Candidate code runs as
a bounded pure function without network, filesystem, clock, random, process, or environment access.

## 11. Pilot plan

Require 0/0/0/1, adjacent ownership-state mutations, Docker reference 1.0, then
a model pilot with trace review for non-atomic conflict handling.

- **Expected Gemma/OpenClaw failure modes:** omitted-field mutation on rejection,
  same-value conflict, incomplete force takeover, protected overwrite, stale
  sequential state, stale artifacts, or unsupported live-apply claims.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `atomic_conflict_force_and_ownership`.
- `validation_and_replay`: `omission_default_and_sequential_state`, `visible_field_replay`, `source_and_cluster_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
