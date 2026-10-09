# Task Design: `251-jsonl-wal-replay`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** storage engineer replaying a local JSONL WAL
- **Trigger:** a mill cache crash left a torn last line and a duplicated op_id in wal.jsonl
- **Objective:** rebuild the key-value store with first-op-wins idempotency and a dropped torn tail
- **Irreversible boundary:** no remote store, cache publish, or production failover is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| HB-S200-EVENT-STATE | event-sourced state and checkpoint recovery | https://www.sqlite.org/wal.html | 2026-09-11 | Grounds replaying a write-ahead log onto durable state |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://sqlite.org/lang_transaction.html | 2026-09-11 | Motivates dropping a torn tail rather than guessing partial records |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file, commit, SQL statement, and JSON record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** JSON Lines plus explicit op_id idempotency make WAL replay executable without SQLite's native WAL file.

## 3. Real-workflow justification

Crash recovery must ignore a truncated last record and must not apply a duplicated operation as last-write-wins. The task leaves a rebuilt store and an explicit replay report.

## 4. Agent-visible inputs

`docs/replay_contract.md` is the highest authority. `wal.jsonl` is the protected log. Keys and op_ids come from those records.

## 5. Hidden ground truth

The evaluator replays the protected log with an independent kernel. Expected store has alpha=one and gamma=three; beta is deleted; the torn delta line is dropped. Duplicate op-10 is first-wins. The evaluator does not import a candidate replayer.

The required final workspace state is `store.json`.
The durable record keeps a stable key for each decision in `store.json`.

## 6. Expected workflow

1. Read the contract and wal.jsonl.
2. Drop a last line that is not valid JSON.
3. Apply put/delete with first op_id wins.
4. Write store.json, replay_report.json, and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `001-meeting-summary` | recovery wording | 001 is not a WAL; 251 replays JSONL operations |
| `019-wheel-install-transaction-recovery` | transaction recovery | 019 repairs a package install transaction; 251 is a generic JSONL WAL |
| `007-database-point-in-time-recovery-drill` | WAL wording | 007 is PostgreSQL PITR; 251 is in-process JSONL replay |

1. Read the protected inputs and record their state before editing `store.json`.
2. Apply the published rule to the key fields that determine `store.json`.
3. Write `store.json` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires parsing a possibly torn log, applying idempotent ops, writing two JSON artifacts, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** torn last line, duplicate op_id, delete after put
- **Difficulty:** hard; last-write-wins on op-10 or including the torn line yields the wrong store
- **Plausible failure mode:** JSON-decode the file as an array, apply the second op-10, or keep beta

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`store_state` (0.50 core) checks store.json. `replay_report` (0.30 core) checks applied/skipped/torn fields. `verification_handoff` (0.20 optional) checks notes. The gate protects wal.jsonl.

### Adjacent examples

- **Nearest valid:** keep the first op-10, delete beta, drop the torn last line.
- **Nearest wrong 1:** last-write-wins sets alpha to nine.
- **Nearest wrong 2:** skip the duplicate but include a guessed delta key from the torn line.

`store.json` is a required final artifact checked by the hidden evaluator.
`replay_report.json` is a required final artifact checked by the hidden evaluator.
`REPLAY_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the rebuilt map. The evaluator recomputes from wal.jsonl.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect last-write-wins or json.loads on the whole file.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
