# Task Design: `073-cross-ecosystem-version-sync-repair`

## 1. Workflow identity

- **Role:** release engineer repairing a polyglot monorepo release planner.
- **Trigger:** one tag is rendered differently across package ecosystems.
- **Objective:** produce one validated, atomic, ecosystem-specific update plan.
- **Boundary:** no manifest, tag, lockfile, registry, or publication mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| PYPA-VERSION | PyPA version specifiers | https://packaging.python.org/en/latest/specifications/version-specifiers/ | 2026-08-27 |
| NPM-PACKAGE-VERSION | npm package.json version field | https://docs.npmjs.com/cli/v7/configuring-npm/package-json/#version | 2026-08-27 |
| CARGO-MANIFEST-VERSION | Cargo manifest version field | https://doc.rust-lang.org/cargo/reference/manifest.html#the-version-field | 2026-08-27 |

- **Adaptation:** public version syntax and uniqueness rules become a captured monorepo planning incident.
- **Private user logs:** None.
- **Synthetic-data statement:** Tags, paths, package identities, and incidents are synthetic.

## 3. Real-workflow justification

Polyglot releases often derive several manifests from one tag. Python and
SemVer prerelease spellings differ, and a partial update can publish packages
that no longer identify the same source release.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/version_contract.md` | authoritative translation and validation contract |
| `repo/src/version_sync.py` | broken planner |
| `repo/version_cases.json` | visible release incidents |
| `repo/tests/test_public.py` | public regressions |

## 5. Hidden ground truth

Hidden cohorts extend the agent-visible `repo/version_cases.json` and
`repo/docs/version_contract.md` with final/alpha/beta/rc transitions, strict
precedence, canonical Python and SemVer values, sorted no-op/update sets,
unsafe and duplicate paths, basename/ecosystem mismatches, malformed records
and Boolean fields, build metadata, leading zeros, and immutable evidence.
Required final state includes repaired `repo/src/version_sync.py`, exact
`repo/version_plan.json`, and a verified `repo/REPAIR_NOTES.md` handoff.

## 6. Expected workflow

1. Reconcile `repo/docs/version_contract.md` with `repo/version_cases.json`.
2. Repair parsing, precedence, and ecosystem rendering in `repo/src/version_sync.py`.
3. Validate the complete manifest set in `plan_version_sync` before returning rows.
4. Generate `repo/version_plan.json` from every visible `case_id`.
5. Record the verification command and publisher/lockfile risk in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

Repository inspection, code execution, exact JSON, version-precedence
reasoning, verification, and publication restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** lexical comparison, one spelling for every ecosystem, permissive leading zeros, or partial output before a late invalid record.
- **Difficulty rationale:** correctness couples syntax, precedence, atomic coverage, path safety, ordering, and ecosystem translation.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `authoritative_release_and_translation` | 0.35 | core | The authoritative tag maps to each ecosystem exactly |
| `precedence_atomicity_and_invalid_safety` | 0.25 | core | Release precedence and the complete manifest set fail closed |
| `visible_version_plan` | 0.05 | core | Visible synchronization incidents are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Version translation and publisher risk are handed off |
| `evidence_and_publish_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/version_sync.py`, `repo/version_plan.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and references are excluded. Candidate code is pure-audited;
only computation-safe standard-library modules and ordinary value methods are available, with no filesystem, network, process, private attribute,
or dynamic execution. Grading is read-only and offline.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma + OpenClaw run with cohort-level review.

- **Expected Gemma/OpenClaw failure modes:** prerelease rank errors, Python spelling drift, unsafe path acceptance, or non-atomic late failure.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `authoritative_release_and_translation`.
- `validation_and_replay`: `precedence_atomicity_and_invalid_safety`, `visible_version_plan`, `evidence_and_publish_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
