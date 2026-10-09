# Task Design: `067-reproducible-archive-manifest-repair`

## 1. Workflow identity

- **Role:** release engineer repairing nondeterministic package metadata.
- **Trigger:** identical sources yield different archive manifests across workers.
- **Objective:** canonicalize paths, order, timestamp, mode, and member identity.
- **Boundary:** no external artifact build, publication, or deployment is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| REPRO-SOURCE-DATE-EPOCH | SOURCE_DATE_EPOCH specification | https://reproducible-builds.org/specs/source-date-epoch/ | 2026-08-27 |
| REPRO-TIMESTAMPS | Reproducible Builds timestamp guidance | https://reproducible-builds.org/docs/timestamps/ | 2026-08-27 |
| PYTHON-ZIPFILE | Python ZIP file format interface | https://docs.python.org/3/library/zipfile.html | 2026-08-27 |

- **Adaptation:** reproducible timestamp and archive metadata guidance becomes an offline canonical member planner over captured build inventory.
- **Private user logs:** None; worker roots, hashes, and files are synthetic.
- **Synthetic-data statement:** All fixtures, hashes, paths, and expected outcomes are synthetic.

## 3. Real-workflow justification

Release archives commonly inherit current time, checkout paths, source modes,
and iteration order. These differences defeat byte-for-byte verification and can
hide duplicate or unsafe members even when source content is unchanged.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/archive_contract.md` | authoritative canonicalization contract |
| `repo/src/archive_manifest.py` | broken member planner |
| `repo/build_cases.json` | visible cross-worker incidents |
| `repo/tests/test_public.py` | public regressions |

## 5. Hidden ground truth

Hidden cohorts execute `repo/src/archive_manifest.py` with extensions of
`repo/build_cases.json` and `repo/docs/archive_contract.md`: different roots and
orders, ZIP lower/upper bounds, odd epochs, file/directory modes, SHA casing,
dot segments, backslashes, duplicate file/directory identities, malformed
types, and immutable inputs. Final state includes `repo/archive_report.json`
and `repo/REPAIR_NOTES.md` as well as the repaired source.

## 6. Expected workflow

1. Read `repo/docs/archive_contract.md`, `repo/build_cases.json`, and `repo/tests/test_public.py`.
2. Repair `repo/src/archive_manifest.py` to validate and strip `build_root`.
3. Normalize timestamp and mode and sort members in `repo/src/archive_manifest.py`.
4. Generate `repo/archive_report.json` from all visible cases.
5. Record verification and downstream writer risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

Repository inspection, code execution, exact JSON generation, path and metadata
reasoning, verification, and release-boundary restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** sort before stripping roots, retain mtimes, round
  odd ZIP times up, preserve unsafe modes, or miss file-versus-directory duplicates.
- **Difficulty rationale:** reproducibility requires several independent fields
  to be canonical simultaneously while malformed inventories fail closed.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `canonical_members_and_metadata` | 0.35 | core | Members, modes, digests, and ordering are canonical |
| `root_timestamp_and_duplicate_safety` | 0.25 | core | Build paths, timestamps, and invalid members fail closed |
| `visible_archive_report` | 0.05 | core | Visible build incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Reproducibility behavior and writer risk are handed off |
| `source_and_publish_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/archive_manifest.py`, `repo/archive_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and reference files are excluded. Candidate code is pure-audited;
only `re` may be imported, while filesystem, network, process, private attribute,
and dynamic execution remain unavailable. Grading is read-only and offline.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, and Docker reference 1.0,
then run Gemma + OpenClaw and inspect cohort-level failures.

- **Expected Gemma/OpenClaw failure modes:** root-prefix mistakes, timestamp
  off-by-one, duplicate aliasing, permissive digest handling, or report drift.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `canonical_members_and_metadata`.
- `validation_and_replay`: `root_timestamp_and_duplicate_safety`, `visible_archive_report`, `source_and_publish_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
