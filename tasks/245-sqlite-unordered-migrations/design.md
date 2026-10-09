# Task Design: `245-sqlite-unordered-migrations`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** catalog engineer applying local SQLite migrations
- **Trigger:** two operators dropped overlapping versioned SQL files into an empty mill catalog
- **Objective:** apply the longest contiguous prefix from version 001 and report gaps and duplicates
- **Irreversible boundary:** no hosted database, catalog publish, or production migration is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://sqlite.org/lang_transaction.html | 2026-09-11 | Grounds applying schema changes as local atomic SQL |
| SQLITE-STEP | SQLite statement evaluation guidance | https://sqlite.org/c3ref/step.html | 2026-09-11 | Motivates executing one statement stream per versioned file |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file, commit, SQL statement, and JSON record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A tiny items catalog with a missing version and a duplicated version makes fail-closed migration executable without Flyway.

## 3. Real-workflow justification

Schema migration tools fail closed on missing or duplicate version numbers rather than applying later files out of order. The task leaves a durable SQLite file plus an explicit report.

## 4. Agent-visible inputs

`docs/migration_contract.md` is the highest authority. `migrations/*.sql` are protected versioned files. The workspace starts without `app.db`.

## 5. Hidden ground truth

The evaluator does not import a candidate migration script. It replans from filenames and independently inspects `app.db` schema and row counts. Duplicate version 003 and missing version 002 are both required in the report even though only 001 is applied.

## 6. Expected workflow

1. Read the contract and list migration filenames.
2. Detect missing versions and duplicate version numbers.
3. Apply only the contiguous prefix starting at 001 onto an empty SQLite file.
4. Write migration_report.json and APPLY_NOTES.md.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `007-database-point-in-time-recovery-drill` | database recovery | 007 is PostgreSQL PITR across timelines; 245 is SQLite versioned schema application |
| `008-db-doc-consistency` | database plus documents | 008 reconciles docs against a live schema; 245 builds the schema from unordered files |

1. Read the protected inputs and record their state before editing `app.db`.
2. Apply the published rule to the key fields that determine `app.db`.
3. Write `app.db` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires reading SQL files, applying a fail-closed version machine, writing SQLite state, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** missing version 002, duplicate version 003, later file 004
- **Difficulty:** hard; applying every unique version or the lexicographically first duplicate yields the wrong schema
- **Plausible failure mode:** ignore the gap and ALTER TABLE, or apply both 003 files

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`catalog_schema` (0.50 core) checks table/column names and that seeded rows are absent. `migration_report` (0.30 core) checks applied/duplicate/missing/skipped lists. `verification_handoff` (0.20 optional) checks notes. The gate protects the SQL inputs.

### Adjacent examples

- **Nearest valid:** apply only 001_init.sql; report missing 002 and both 003 files as duplicates.
- **Nearest wrong 1:** apply 001 and the lexicographically first 003 file.
- **Nearest wrong 2:** apply 001, skip 003, but omit duplicate_files from the report.

`app.db` is a required final artifact checked by the hidden evaluator.
`migration_report.json` is a required final artifact checked by the hidden evaluator.
`APPLY_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

Hidden expected schema is not printed in the prompt. SQL files do not contain the final report. The evaluator rebuilds the plan from filenames.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect sqlite3 CLI that applies every file in directory order.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
