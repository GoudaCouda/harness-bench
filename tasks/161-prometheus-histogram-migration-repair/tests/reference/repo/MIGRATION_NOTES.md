# Native histogram migration handoff

The planner keeps classic and native representations separate during a mixed
fleet rollout; it never sums both encodings and double-counts observations. A
classic quantile uses `histogram_quantile` over `_bucket` rates grouped by
`le`, while a classic average divides `_sum` and `_count` rates. A native
quantile consumes the aggregated native histogram directly, an average uses
`histogram_avg`, and a bounded fraction uses `histogram_fraction`. Fraction is
not available from the classic representation under this contract.

Target coverage must be complete before native query cutover. The configured
native schema range is checked first, and counter resets above budget block the
migration. At full coverage, parity error must be within tolerance and every
consumer must be native-ready. Classic queries remain active through the
required stable windows; only then does the plan emit the exact native query.
After cutover, classic emission remains enabled through the required quiet
windows. It can be retired only after that observation period, and migration is
settled only when classic emission is already disabled.

Verification passed with `python -m unittest discover -s tests -v` and then
`python bin/plan_migration.py`. I parsed both JSON outputs and confirmed five
metrics: one settled, three ready, one blocked; three selected queries are
native and two are classic. The visible parity failure remains blocked and the
fraction metric retires classic emission only after its quiet evidence. This
was offline with no Prometheus connection: I did not run queries, reload rules,
change scrapes, deploy instrumentation, disable live series, or claim a
production migration.
