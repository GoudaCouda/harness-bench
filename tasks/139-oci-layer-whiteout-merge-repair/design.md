# Task Design: `139-oci-layer-whiteout-merge-repair`

## 1. Workflow identity

- **Role:** container-platform engineer repairing an offline image inspector.
- **Canonical domain:** IT Operations
- **Trigger:** opaque and explicit whiteouts produced ghost files and lost same-layer additions.
- **Objective:** reconstruct a deterministic safe rootfs manifest from ordered OCI changesets.
- **Boundary:** real local OCI-style manifests and tar-safe path rules are exercised without mounting or mutating a live image.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| OCI-IMAGE-LAYER | Open Container Initiative image layer specification | https://specs.opencontainers.org/image-spec/layer/ | 2026-08-27 |

- **Adaptation:** OCI changeset, whiteout, and opaque-directory semantics are
  adapted into an offline layer-manifest reconstruction and safety repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All layers, paths, digests, modes, links, images, and audit records are synthetic.

## 3. Real-workflow justification

Scanners, SBOM tools, and image inspectors must understand the final filesystem
without blindly extracting untrusted archives. Whiteout order, type replacement,
and link safety are common sources of incorrect inventory and traversal risk.

## 4. Agent-visible inputs

The repository exposes `repo/docs/layer_contract.md`, `repo/layers.json`,
`repo/policy.json`, partially working incident code, a protected runner, and
public tests that also construct and read actual tar headers with `tarfile`.

## 5. Hidden ground truth

Hidden cohorts cover explicit whiteouts, opaque directories, marker order
independence, same-layer additions, nested descendants, file/directory/symlink
replacement, implicit directories, duplicate paths, unsafe names and symlink
targets, malformed layers, deterministic audit state, and immutability.

Required final workspace state is repaired `repo/src/layer_merge.py`, exact
`repo/out/rootfs.json` and `repo/out/audit.json`, and a verified
`repo/LAYER_NOTES.md`. The key invariant is that a whiteout only removes lower
layer state; entries created by its own layer remain authoritative.

## 6. Expected workflow

1. Inspect `repo/docs/layer_contract.md`, ordered layer entries, policy, and public cases.
2. Repair path validation, lower-state whiteouts, type replacement, and safe link handling in `repo/src/layer_merge.py`.
3. Run the full public unittest suite, including the local tar integration, and `repo/bin/merge_layers.py` to regenerate both `repo/out/` artifacts.
4. Re-parse `repo/out/rootfs.json` and `repo/out/audit.json`, then document boundaries in `repo/LAYER_NOTES.md`.

## 7. Harness demands

Repository inspection, hierarchical state reconstruction, code repair,
executable verification, artifact reconciliation, and safety reasoning are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** process markers in tar order, let an opaque marker
  erase same-layer files, remove only a directory node but retain descendants,
  keep children below a replaced file, or accept escaping symlink targets.
- **Difficulty rationale:** layer provenance, hierarchy, marker precedence,
  replacement, and path safety interact in one non-commutative state machine.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `whiteout_and_opaque_reconstruction` | 0.30 | core | Lower-layer state is reconstructed under OCI whiteout rules |
| `hierarchy_type_and_link_safety` | 0.25 | core | Hierarchy type replacement and links remain coherent and safe |
| `visible_layer_replay` | 0.10 | core | Protected fixture outputs match the repaired merger |
| `layer_handoff` | 0.20 | handoff | Layer reconstruction and safety boundaries are handed off clearly |
| `source_and_extraction_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/layer_merge.py`, `repo/out/rootfs.json`, `repo/out/audit.json`, `repo/LAYER_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references remain outside the workspace. Candidate code runs
as a bounded pure function without filesystem, archive, process, or network access.

## 11. Pilot plan

Require 0/0/0/1, neighboring whiteout/type/link mutations, Docker reference
1.0, then a model pilot with trace review for order-dependent implementations.

- **Expected Gemma/OpenClaw failure modes:** tar-order processing, same-layer
  deletion, incomplete descendant removal, unsafe implicit ancestors, symlink
  traversal, stale outputs, or weak verification notes.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `whiteout_and_opaque_reconstruction`.
- `validation_and_replay`: `hierarchy_type_and_link_safety`, `visible_layer_replay`, `source_and_extraction_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
