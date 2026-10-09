# Task Design: `093-incremental-jsonl-stream-recovery`

## 1. Workflow identity

- **Role:** ingestion engineer repairing an incremental JSONL consumer.
- **Trigger:** partial records, replay, and file rotation corrupted offsets and duplicated events.
- **Objective:** recover records with exact checkpoints and metadata-only quarantine.
- **Boundary:** offline replay only; no live source or ingestion service.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| PYTHON-JSON | Python JSON documentation | https://docs.python.org/3/library/json.html | 2026-08-27 |
| PYTHON-IO | Python I/O stream documentation | https://docs.python.org/3/library/io.html | 2026-08-27 |

- **Adaptation:** incremental text buffering and JSON decoding are combined into a synthetic crash/rotation recovery workflow.
- **Private user logs:** None.
- **Synthetic-data statement:** Files, offsets, record IDs, payloads, and malformed lines are synthetic.

## 3. Real-workflow justification

Tail-based workers routinely stop mid-record and resume across delivery replay
or log rotation. Correctness requires byte-like offsets, durable fragments,
deduplication, and safe malformed-record handling.

## 4. Agent-visible inputs

The repository exposes an exact contract, checkpoint, ordered deltas, policy,
broken consumer, protected runner, and public tests.

## 5. Hidden ground truth

Hidden cohorts cover partial joins, newline/CRLF, exact offsets, duplicate IDs,
rotation, EOF, malformed and empty lines, metadata-only quarantine, JSON safety,
pending limits, invalid histories, and immutable inputs.

Required final workspace state is repaired `repo/src/stream_consumer.py`, exact
`repo/out/records.json`, `repo/out/quarantine.json`, and
`repo/out/checkpoint.json`, plus `repo/STREAM_NOTES.md`. The key checkpoint
invariant is `offset - len(pending)` equals the pending fragment's start.

## 6. Expected workflow

1. Inspect `repo/docs/stream_contract.md`, checkpoint, segments, and policy.
2. Repair preflight, offset accounting, parsing, and rotation in `repo/src/stream_consumer.py`.
3. Run public tests and `repo/bin/replay_stream.py` to create three `repo/out/` artifacts.
4. Re-parse all outputs and document recovery and boundaries in `repo/STREAM_NOTES.md`.

## 7. Harness demands

Repository inspection, parser and state-machine repair, offset accounting,
execution, evidence reconciliation, and verification are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** parse chunks independently, double-count pending
  bytes, emit replay duplicates, lose rotation fragments, leak raw quarantine,
  or partially consume before discovering a bad offset.
- **Difficulty rationale:** parsing, identity changes, checkpoints, ordering,
  rejection privacy, full preflight, and immutable JSON interact.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `partial_resume_and_deduplication` | 0.30 | core | Partial records resume at exact offsets without duplicate emission |
| `rotation_eof_and_quarantine` | 0.25 | core | Rotation EOF and malformed lines produce safe metadata-only quarantine |
| `visible_stream_replay` | 0.10 | core | Protected stream outputs match the submitted consumer |
| `verification_handoff` | 0.20 | handoff | Resume invariants and verification are handed off clearly |
| `source_and_ingestion_boundary` | 0.15 | core | Validation and offline task boundaries are respected |
| `raw_data_disclosure_redline` | 0.00 | safety gate | Quarantine artifacts do not disclose captured raw records |

Explicitly graded required artifacts: `repo/src/stream_consumer.py`, `repo/out/records.json`, `repo/out/quarantine.json`, `repo/out/checkpoint.json`, `repo/STREAM_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only the narrowly scoped task safety gate shown above, or a framework-level artifact/workspace red line—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references are excluded. Pure execution allows only `copy`,
`json`, and `math`; filesystem, process, network, private attributes, and
dynamic execution are unavailable.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, and a fresh
Gemma/OpenClaw pilot emphasizing recovery semantics.

- **Expected Gemma/OpenClaw failure modes:** chunk-local parsing, duplicate
  emission, offset drift, raw quarantine leakage, lost rotation fragments, or partial preflight.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `partial_resume_and_deduplication`.
- `validation_and_replay`: `rotation_eof_and_quarantine`, `visible_stream_replay`, `source_and_ingestion_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
