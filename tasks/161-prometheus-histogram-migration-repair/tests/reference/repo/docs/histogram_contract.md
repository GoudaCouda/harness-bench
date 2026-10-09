# Native histogram migration contract

`plan_histogram_migration(metrics, policy)` is pure and returns exactly
`{"decisions": [...], "summary": {...}}` without mutating arguments.

Metric IDs are sorted unique lowercase tokens. Metric names are lowercase
Prometheus identifiers. Each observation uses the exact sample schema.
`total_targets > 0`, `0 <= native_targets <= total_targets`, counts/windows are
non-negative integers, parity is a finite non-negative number, and query
parameters match their kind: quantile has only `0 < quantile < 1`; average has
all parameters null; fraction has finite `0 <= lower < upper` and null quantile.

Policy has exactly `max_parity_error_pct`, `max_counter_resets`,
`required_stable_windows`, `required_quiet_windows`, `min_native_schema`,
`max_native_schema`, and `rate_window`. Native schema bounds are inclusive.

Classic quantile query:
`histogram_quantile(Q, sum by (le) (rate(NAME_bucket[W])))`.
Classic average query:
`sum(rate(NAME_sum[W])) / sum(rate(NAME_count[W]))`.
Classic histograms cannot serve fraction queries, so their query is
`unavailable`. Native queries are respectively
`histogram_quantile(Q, sum(rate(NAME[W])))`,
`histogram_avg(sum(rate(NAME[W])))`, and
`histogram_fraction(L, U, sum(rate(NAME[W])))`.

The first applicable rule wins. Incompatible native schema, excess counter
resets, or a classic fraction query blocks. Partial native target coverage keeps
classic mode and plans `roll_out_native`; native mode during partial coverage
blocks as `premature_native_query`. At full coverage, parity drift and consumer
readiness block. Classic mode then plans `validate_parity` until stable windows
are met, followed by `switch_query_to_native`. Native mode observes classic
retirement until quiet windows are met, then plans `disable_classic_emission`.
When classic emission is already false, migration is settled.

Each decision has exactly `metric_id`, `status`, `action`, `reason`, and
`query`. Ready reasons are `coverage_incomplete`, `stability_window`,
`native_cutover_ready`, `retirement_observation`, or `classic_quiet`; settled is
`migration_complete`. Blocked reasons are the named safety failures. Summary
has `metric_count`, `settled`, `ready`, `blocked`, `native_queries`, and
`classic_queries`; `unavailable` counts as neither query mode.
