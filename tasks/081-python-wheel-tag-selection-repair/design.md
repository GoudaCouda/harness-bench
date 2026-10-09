# Task Design: `081-python-wheel-tag-selection-repair`

## 1. Workflow identity

- **Role:** release-platform engineer selecting a Python wheel for a pinned deployment target.
- **Trigger:** a filename-substring selector chose an incompatible ABI or platform artifact.
- **Objective:** produce an exact, fail-closed offline release-asset decision.
- **Boundary:** no index query, download, installation, publication, or environment mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| PYPA-COMPATIBILITY-TAGS | PyPA platform compatibility tags | https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/ | 2026-08-27 |
| PYPA-WHEEL-SPEC | PyPA binary distribution format | https://packaging.python.org/en/latest/specifications/binary-distribution-format/ | 2026-08-27 |

- **Adaptation:** public wheel filename and compatibility-tag rules become an offline deployment asset selector with explicit ambiguity handling.
- **Private user logs:** None.
- **Synthetic-data statement:** Projects, versions, filenames, tags, digests, sizes, yanked states, and release batches are synthetic.

## 3. Real-workflow justification

Release systems routinely choose among native, stable-ABI, and universal
wheels. Asset order and substring matching are unsafe because compatibility is
an ordered triple, compressed fields represent multiple triples, and rebuild
or yanked metadata can change the safe winner.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/wheel_selection_contract.md` | authoritative parsing and ranking contract |
| `repo/src/wheel_selector.py` | broken selector |
| `repo/selection_cases.json` | visible release batches |
| `repo/tests/test_public.py` | public regressions |

## 5. Hidden ground truth

Hidden cohorts extend the concrete visible inputs
`repo/docs/wheel_selection_contract.md`, `repo/selection_cases.json`, and
`repo/tests/test_public.py` with native, ABI3, universal, compressed Cartesian,
foreign-project, wrong-version, build-tag, yanked, no-compatible, equal-rank
ambiguity, malformed filename, unsafe basename, invalid digest/type, immutable
evidence, and external-action cases. Required final state includes repaired
`repo/src/wheel_selector.py`, exact `repo/selection_report.json`, and verified
`repo/SELECTION_NOTES.md`.

## 6. Expected workflow

1. Inspect `repo/docs/wheel_selection_contract.md`, `repo/selection_cases.json`, and `repo/tests/test_public.py`.
2. Parse and validate every asset filename and target tag in `repo/src/wheel_selector.py`.
3. Expand compressed tags, rank exact compatible triples, apply yanked and build policy, and fail closed on ties.
4. Generate exact ordered `repo/selection_report.json` rows for each visible `case_id`.
5. Run the public test command and record evidence plus installer risk in `repo/SELECTION_NOTES.md`.

## 7. Harness demands

Repository inspection, executable repair, packaging semantics, exact JSON,
verification, ambiguity handling, and external-action restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** infer from the host, choose the first filename, split compressed tags incorrectly, prefer a yanked native wheel, or break an equal-ranked tie arbitrarily.
- **Difficulty rationale:** correct selection composes strict parsing, Cartesian tag expansion, ordered ranking, rebuild precedence, and fail-closed evidence handling.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `tag_expansion_and_priority` | 0.35 | core | Compressed tags are expanded and target priority wins |
| `yanked_build_and_ambiguity_policy` | 0.25 | core | Yanked assets, rebuilds, and equal-ranked conflicts fail safely |
| `visible_selection_report` | 0.05 | core | Visible release batches are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Packaging and installer risks are handed off |
| `evidence_and_package_action_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/wheel_selector.py`, `repo/selection_report.json`, `repo/SELECTION_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and references are excluded. Candidate code is pure-audited;
Hidden cohorts and references are excluded. Candidate code is pure-audited; safe computation-only standard-library imports and ordinary container/value methods are allowed, while filesystem, process, network, package clients,
private attributes, and dynamic execution unavailable. Grading is offline.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma + OpenClaw run with cohort-level review.

- **Expected Gemma/OpenClaw failure modes:** asset-order selection, host inference, incomplete compressed-tag expansion, yanked preference, wrong build ordering, or arbitrary ambiguity resolution.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `tag_expansion_and_priority`.
- `validation_and_replay`: `yanked_build_and_ambiguity_policy`, `visible_selection_report`, `evidence_and_package_action_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
