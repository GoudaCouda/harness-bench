# Prepare a station-quality coverage handoff

You are the climate-data analyst preparing a seven-day station comparison for
an operations briefing. The raw feed mixes Celsius encodings, contains late
final records alongside preliminary records, and includes QC failures,
sentinels, and missing values. Coverage must be calculated only after those
record-level decisions are closed.

Use only these local inputs in `$WORKSPACE`:

- `policy.md`
- `stations.csv`
- `observations.csv`

Create these deliverables in `$WORKSPACE`:

- `qc_records.csv`, with columns `station,date,value_c,status,reason` in that
  order and one canonical row for every station/date present in the feed;
- `coverage.json`, containing `window_days`, station-keyed `valid_days` and
  `coverage`, `qualified_stations`, `excluded_stations`, and station-keyed
  `mean_c` for qualified stations;
- `qc_note.md`, a short operational handoff explaining the duplicate decision,
  exclusion rules, unit conversion, threshold result, and verification.

Apply the precedence and no-fallback rules in `policy.md` before converting or
aggregating values. An excluded observation may retain its source-derived
value for auditability or leave it blank, but it must not contribute to valid
days or means. Missing calendar days remain in the seven-day denominator; do
not invent rows or measurements for them. Use explicit status and reason text
so another analyst can distinguish usable data from quarantine.

Derive all aggregates from the final QC ledger, parse the CSV and JSON again,
and reconcile keys, counts, coverage, and means before finishing. Do not modify
the supplied evidence, use the network, or claim an external/production update.
