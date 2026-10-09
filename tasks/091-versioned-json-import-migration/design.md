# Task Design: `091-versioned-json-import-migration`

## 1. Workflow identity

- **Role:** application engineer repairing a settings-import migration before an upgrade.
- **Trigger:** legacy imports collapsed missing and null state, mutated caller data, and accepted malformed documents.
- **Objective:** migrate three schema versions into validated canonical v3 records with an isolated reject ledger.
- **Boundary:** no live configuration application or external service access.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| JSON-SCHEMA-2020-12 | JSON Schema validation specification | https://json-schema.org/draft/2020-12/json-schema-validation | 2026-08-27 |
| RFC-8259 | The JavaScript Object Notation data interchange format | https://www.rfc-editor.org/rfc/rfc8259 | 2026-08-27 |

- **Adaptation:** version dispatch, strict shapes, JSON value constraints, and extension preservation are adapted into an offline settings-import repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All services, endpoints, regions, tickets, versions, and settings are synthetic.

## 3. Real-workflow justification

Long-lived applications import configuration produced by old clients. A safe
upgrade must preserve explicit null, reject unknown shapes without losing valid
siblings, and make current-version imports idempotent.

## 4. Agent-visible inputs

The repository exposes an exact migration contract, defaults, mixed-version
fixture, broken implementation, protected runner, and public tests.

## 5. Hidden ground truth

Hidden cohorts cover v1 missing/null distinctions, v2 nested shapes and feature
flags, v3 canonical idempotency, extension deep-copying, finite JSON values,
unknown fields and versions, value-free rejects, duplicate IDs, invalid batch
envelopes, and input immutability. The evaluator independently executes the
submitted function and rebuilds visible outputs.

Required final workspace state is repaired `repo/src/import_migrator.py`, exact
`repo/out/migrated.json` and `repo/out/rejected.json`, and a verified
`repo/MIGRATION_NOTES.md`. The key invariant is that missing and explicit null
remain distinct while canonical v3 replay is idempotent.

## 6. Expected workflow

1. Inspect `repo/docs/import_contract.md`, `repo/defaults.json`, and `repo/imports.json`.
2. Repair preflight, version dispatch, canonicalization, and copying in `repo/src/import_migrator.py`.
3. Run public tests and `repo/bin/run_import.py` to create both `repo/out/` artifacts.
4. Re-parse both JSON outputs and record checks and boundaries in `repo/MIGRATION_NOTES.md`.

## 7. Harness demands

Repository inspection, executable code repair, nested schema reasoning,
missing/null state handling, immutable transformation, output reconciliation,
and verification are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** treat null as missing, accept booleans as ints,
  mutate nested extensions, partially accept unknown keys, abort valid siblings,
  or fail v3 idempotency.
- **Difficulty rationale:** success couples strict envelope validation with
  three schema state machines, recursive JSON safety, deterministic canonical
  output, and a separate error policy.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `versioned_migration_semantics` | 0.30 | core | All known versions migrate without collapsing explicit state |
| `rejection_and_idempotency` | 0.25 | core | Malformed and future documents are isolated with deterministic output |
| `visible_import_execution` | 0.10 | core | Protected fixture outputs exactly match the repaired importer |
| `verification_handoff` | 0.20 | handoff | The migration handoff explains boundaries and verified behavior |
| `source_and_application_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/import_migrator.py`, `repo/out/migrated.json`, `repo/out/rejected.json`, `repo/MIGRATION_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references are excluded. Candidate code executes as a pure
function with only `copy` and `math`; filesystem, process, network, private
attributes, and dynamic execution remain unavailable.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then a fresh
Gemma/OpenClaw pilot. Review semantic migration rather than formatting trivia.

- **Expected Gemma/OpenClaw failure modes:** shallow shape checks, null/default collapse,
  unknown-field acceptance, aliased extensions, weak batch preflight, stale
  generated outputs, or incomplete handoff evidence.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `versioned_migration_semantics`.
- `validation_and_replay`: `rejection_and_idempotency`, `visible_import_execution`, `source_and_application_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
