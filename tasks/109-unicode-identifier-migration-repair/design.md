# Task Design: `109-unicode-identifier-migration-repair`

## 1. Workflow identity

- **Role:** identity-platform engineer repairing a username-key migration.
- **Trigger:** compatibility and case normalization created silent collisions.
- **Objective:** canonicalize safe unique identifiers while quarantining ambiguity and preserving references.
- **Boundary:** offline migration plan only; no account or login mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| UNICODE-UAX15 | Unicode Normalization Forms | https://www.unicode.org/reports/tr15/ | 2026-08-27 |
| UNICODE-UAX31 | Unicode Identifiers and Syntax | https://www.unicode.org/reports/tr31/ | 2026-08-27 |

- **Adaptation:** Unicode normalization and identifier-profile guidance are
  adapted into an offline account-key migration with collision quarantine and reference repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All accounts, names, references, reserved keys, and policies are synthetic.

## 3. Real-workflow justification

Canonical identifiers become durable keys. A migration must detect many-to-one
normalization, preserve user-facing spelling, and avoid retargeting references
to quarantined identities.

## 4. Agent-visible inputs

The repository contains a precise profile, synthetic records, reserved names,
broken implementation, runner, and public tests.

## 5. Hidden ground truth

Hidden cohorts cover composed/decomposed text, compatibility width, multi-code
point case folds, combining marks, reserved names, invalid syntax and controls,
length after canonicalization, unrelated-script confusables, collisions,
blocked reference propagation, strict shapes, and input immutability.

Required final workspace state is repaired `repo/src/identifier_migrator.py`,
exact `repo/out/records.json` and `repo/out/conflicts.json`, and a verified
`repo/IDENTIFIER_NOTES.md`. The key invariant is that collision state is known
before any canonical identifier or dependent reference is accepted.

## 6. Expected workflow

1. Inspect `repo/docs/identifier_contract.md`, source records, reserved-key state, and public tests.
2. Repair canonicalization, validation, two-pass collision state, and reference rewriting in `repo/src/identifier_migrator.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/migrate_identifiers.py` to regenerate both `repo/out/` artifacts.
4. Re-parse `repo/out/records.json` and `repo/out/conflicts.json`, then document boundaries in `repo/IDENTIFIER_NOTES.md`.

## 7. Harness demands

Unicode reasoning, graph-aware migration, code repair, executable validation,
artifact reconciliation, and verification are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** lowercase without normalization, assign in one pass
before collision discovery, checking length before expansion, dropping display
spelling, resolve blocked references, or merge visual confusables.
- **Difficulty rationale:** Coupled normalization, profile validation, collision
  quarantine, and graph repair make the task materially harder than text cleanup.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `unicode_profile_and_canonicalization` | 0.30 | core | Unicode normalization syntax and reserved policy are exact |
| `collision_and_reference_quarantine` | 0.25 | core | Collisions and blocked references are quarantined without retargeting |
| `visible_identifier_migration` | 0.10 | core | Protected records and conflicts match the repaired migrator |
| `identifier_handoff` | 0.20 | handoff | Unicode migration invariants and verification are handed off clearly |
| `source_and_identity_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/identifier_migrator.py`, `repo/out/records.json`, `repo/out/conflicts.json`, `repo/IDENTIFIER_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases/references stay outside the workspace. Candidate code executes as
a bounded pure function with `unicodedata` only and cannot access identity systems.

## 11. Pilot plan

Require 0/0/0/1, normalization/collision/reference discrimination, Docker
reference 1.0, then a fresh model pilot with review for over-merging.

- **Expected Gemma/OpenClaw failure modes:** lowercasing without NFKC, wrong
  normalization order, one-pass collision handling, visual-confusable merging,
  retargeted blocked references, stale artifacts, or weak migration evidence.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic semantic and calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `unicode_profile_and_canonicalization`.
- `validation_and_replay`: `collision_and_reference_quarantine`, `visible_identifier_migration`, `source_and_identity_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
