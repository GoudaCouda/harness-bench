# Task Design: 085-station-qc-coverage

## 1. Workflow identity

- Primary domain: Data Analytics
- Role: climate-data quality analyst preparing a seven-day operational comparison.
- Trigger: raw observations contain duplicates, late final records, failed QC, sentinels, blanks, missing calendar days, and three unit encodings.
- Objective: close one canonical record per observed station/day before deriving coverage and qualified-station means.
- Boundary: local synthetic evidence only; no network or production update.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| DA-03 | NOAA GHCN-Daily | https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily | 2026-07-29 |
- **Private user logs:** None.
- **Synthetic-data statement:** Station identities, dates, measurements, QC flags, and coverage records are synthetic.

Station-day identity, QC flags, unit conversion, and coverage concepts are adapted into synthetic records. No private user logs are used.

- **Adaptation:** NOAA-style station-day identity, QC flags, unit encodings, and coverage rules are transformed into an offline seven-day feed where duplicate precedence must close before aggregation.

## 3. Real-workflow justification

Operational climate analysis must resolve record-level quality before aggregation. Averaging preliminary and final duplicates, falling back from a failed final row, or treating a sentinel as a temperature can materially alter both station means and qualification. Missing calendar days must remain in the coverage denominator.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| policy.md | authoritative window, precedence, exclusion, conversion, and threshold rules |
| stations.csv | station-to-unit mapping for tenths-C, C, and Fahrenheit |
| observations.csv | 27 raw records that collapse to 24 canonical station-days |
| instruction.md | output schemas and reconciliation requirements |

The policy controls duplicate precedence and explicitly forbids preliminary fallback when a corresponding final record exists but fails QC.

## 5. Hidden ground truth

The final ledger contains 24 observed station/date keys. Valid-day counts are ST-A 6, ST-B 4, ST-C 6, and ST-D 2, all divided by seven calendar days. ST-A and ST-C qualify; ST-B and ST-D do not. Qualified means are approximately 13.583333 C and 14.166667 C.

Important cases include a late final replacing preliminary data at ST-A and ST-C, no fallback to ST-D's preliminary value after a flagged final, tenths-C and Fahrenheit conversion, sentinel exclusion, QFLAG exclusion, and a blank value. Missing dates are not invented as ledger rows.

The oracle binds visible `policy.md`, `stations.csv`, and `observations.csv` to required state in `qc_records.csv`, `coverage.json`, and `qc_note.md`. The controlling invariant is one canonical record per observed station/date key: a failed final record blocks preliminary fallback, and only usable canonical state contributes to seven-day coverage and means.

## 6. Expected workflow

1. Read `policy.md` before interpreting record state.
2. Join `observations.csv` to `stations.csv` and group by station/date key.
3. Select final over preliminary; when the final fails QC, exclude without fallback.
4. Apply QFLAG, sentinel, and blank-value exclusions.
5. Convert retained values to Celsius and write state to the 24-row `qc_records.csv`.
6. Derive valid days, seven-day coverage, qualification, exclusions, and qualified means into coverage.json.
7. Document decisions in qc_note.md and reparse/reconcile both structured outputs.

## 7. Harness demands

The task requires policy-first evidence grounding, keyed duplicate resolution, exact state management, unit conversion, structured artifact generation, and cross-artifact verification. The harness must preserve a no-fallback decision that is easy to lose when processing rows greedily.

## 8. Stressors and difficulty

- Final and preliminary duplicates arrive in mixed order.
- A failed final must block a cleaner preliminary fallback.
- Three unit encodings require distinct conversions.
- Excluded rows may retain only their source-derived value, never an invented one.
- Coverage uses seven calendar days even when no row exists.
- Means are reported only for qualifying stations.

The task is medium difficulty: 24 canonical rows and several interacting policies make it realistic without requiring a long algorithmic implementation.

- **Plausible failure mode:** a row-greedy implementation may average duplicate preliminary/final values, fall back after a failed final, count a sentinel, use observed-row count as the denominator, or include excluded stations in means.
- **Difficulty rationale:** precedence, QC exclusion, three unit conversions, fixed calendar denominator, and aggregate closure interact; each shortcut can yield numerically plausible output.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| station_qc | 0.40 | core | Every observed station/day has the correct converted value, disposition, and reason |
| coverage_state | 0.30 | core | Valid days, coverage, station sets, and qualified means reconcile |
| qc_handoff | 0.10 | core | Duplicate, no-fallback, exclusions, units, threshold, outcomes, and verification are explained |
| record_integrity | 0.10 | optional | The ledger has the exact schema and closed unique key set |
| coverage_closure | 0.10 | optional | Aggregate state is dynamically consistent with usable ledger rows |
| safety_and_input_integrity | 0.00 | gate | Inputs remain unchanged and no prohibited external action is claimed |

The pass threshold is 0.80. Equivalent usable/excluded status labels and equivalent numeric spellings are accepted. Excluded rows may be blank or retain the exact source-derived converted value. Ordinary business mistakes lose their own cases; the gate is reserved for source mutation, grader failure, or a real prohibited action.

Artifact coverage is explicit: `qc_records.csv` owns canonical station-day decisions, `coverage.json` owns valid-day/coverage/mean state derived from that ledger, and `qc_note.md` explains precedence, exclusions, units, threshold, and verification.

## 10. Leakage, isolation, and safety review

Hidden ground truth, oracle implementation, contract tests, references, and this design are excluded from the agent workspace. Network access is disabled. All records are synthetic. The agent may create only qc_records.csv, coverage.json, and qc_note.md.

## 11. Pilot plan

Required checks are:

- deterministic reference score 1.0;
- equivalent valid/quarantined status labels are accepted;
- an excluded flagged row may retain its source-derived value but not an invented value;
- equivalent coverage wording is accepted;
- replacing the station coverage map with a scalar loses state and closure only;
- including a sentinel as usable breaks QC and closure without becoming a safety failure;
- source mutation zeros the score through the integrity gate;
- shared agent and grader environments pass isolated Docker verification.

A fresh Gemma/OpenClaw run remains calibration evidence, not a manual admission requirement.

- **Expected Gemma/OpenClaw failure modes:** ignore final-over-preliminary precedence, fall back from a failed final, convert before recognizing sentinels, shrink the seven-day denominator, report means for excluded stations, or leave `coverage.json` inconsistent with `qc_records.csv`.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh Gemma/OpenClaw run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.
