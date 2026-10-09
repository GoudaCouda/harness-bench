# Task Design: `108-dst-recurrence-schedule-repair`

## 1. Workflow identity

- **Role:** platform engineer repairing a recurring-job planner.
- **Trigger:** DST transitions and short months caused duplicate or drifting jobs.
- **Objective:** expand local-wall recurrences into deterministic UTC occurrences.
- **Boundary:** create an offline plan only; no clock, queue, or calendar mutation.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| RFC-5545 | Internet Calendaring and Scheduling Core Object Specification | https://www.rfc-editor.org/rfc/rfc5545 | 2026-08-27 |
| PEP-495 | Local Time Disambiguation (`fold`) | https://peps.python.org/pep-0495/ | 2026-08-27 |
| PYTHON-ZONEINFO | Python IANA time zone support | https://docs.python.org/3/library/zoneinfo.html | 2026-08-27 |

- **Adaptation:** recurrence and local-time disambiguation mechanics are adapted
  into an offline recurring-job planner with timezone-history and override state.
- **Private user logs:** None.
- **Synthetic-data statement:** All schedules, zones, overrides, windows, and job IDs are synthetic.

## 3. Real-workflow justification

Schedulers persist local intent but dispatch UTC instants. They must distinguish
nonexistent from ambiguous wall times, preserve identity across zone changes,
and avoid iterative month drift.

## 4. Agent-visible inputs

The workspace supplies an exact contract, multiple schedules, timezone-history
and override state, a UTC window, broken engine, runner, and public tests.

## 5. Hidden ground truth

Hidden cases cover both US DST boundaries, non-DST zones, gap skip/shift,
fold earlier/later, daily/weekly/monthly intervals, leap and short months,
timezone effective-date boundaries, override skip/reschedule, stable ordinal
IDs, UTC window endpoints, invalid zones/shapes, and immutability.

Required final workspace state is repaired `repo/src/recurrence_engine.py`, exact
`repo/out/occurrences.json` and `repo/out/skipped.json`, and a verified
`repo/SCHEDULE_NOTES.md`. The key invariant is that each stable ordinal derives
from the original local start while timezone state selects one valid UTC instant.

## 6. Expected workflow

1. Inspect `repo/docs/recurrence_contract.md`, schedules, timezone history, overrides, and UTC window state.
2. Repair nominal recurrence and wall-time resolution in `repo/src/recurrence_engine.py`.
3. Run `repo/tests/test_public.py` and `repo/bin/expand_schedules.py` to regenerate both `repo/out/` artifacts.
4. Re-parse `repo/out/occurrences.json` and `repo/out/skipped.json`, then document boundaries in `repo/SCHEDULE_NOTES.md`.

## 7. Harness demands

The agent needs repository navigation, calendar/timezone reasoning, code repair,
executable feedback, cross-artifact reconciliation, and verification.

## 8. Stressors and difficulty

- **Plausible failure mode:** add fixed UTC durations, use only `fold=0`, accept a
normalized nonexistent time, iteratively clamping monthly dates, applying the
new zone one day early, or derive IDs from shifted timestamps.
- **Difficulty rationale:** Coupled civil recurrence, IANA history, ambiguous and
  nonexistent wall times, overrides, and identity make the task substantially harder than meeting-slot conversion.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `nominal_recurrence_and_zone_history` | 0.30 | core | Recurrence dates monthly clamps and timezone history remain stable |
| `dst_resolution_and_overrides` | 0.25 | core | DST gaps folds and overrides preserve local intent and identity |
| `visible_schedule_expansion` | 0.10 | core | Protected occurrence and skip artifacts match the repaired engine |
| `schedule_handoff` | 0.20 | handoff | Temporal invariants and verification are handed off clearly |
| `source_clock_and_execution_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/recurrence_engine.py`, `repo/out/occurrences.json`, `repo/out/skipped.json`, `repo/SCHEDULE_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden references remain outside the workspace. Candidate code is executed in
a bounded pure worker with `calendar`, `datetime`, and `zoneinfo` only.

## 11. Pilot plan

Require 0/0/0/1, semantic mutations at each temporal boundary, Docker reference
1.0, then a fresh model pilot with trace review for hard-coded offsets.

- **Expected Gemma/OpenClaw failure modes:** fixed-duration recurrence, wrong fold,
  normalized DST gaps, iterative month drift, unstable occurrence IDs, window
  endpoint inclusion, stale artifacts, or incomplete temporal handoff.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic timezone and model-calibration gates replace manual review.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `nominal_recurrence_and_zone_history`.
- `validation_and_replay`: `dst_resolution_and_overrides`, `visible_schedule_expansion`, `source_clock_and_execution_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
