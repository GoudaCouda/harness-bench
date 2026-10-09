Compare old and new metric definitions and report migration differences using only local files.

Inputs:
- $WORKSPACE/old_metric_definitions.md
- $WORKSPACE/new_metric_definitions.md
- $WORKSPACE/dashboard_before.csv
- $WORKSPACE/dashboard_after.csv
- $WORKSPACE/query_exports/old_results.csv
- $WORKSPACE/query_exports/new_results.csv
- $WORKSPACE/migration_policy.md

Create:
- $WORKSPACE/metric_migration_diff.csv
- $WORKSPACE/regression_ledger.csv
- $WORKSPACE/migration_summary.json
- $WORKSPACE/caveats.md

Rules:
1. Do not modify fixtures.
2. Compare every metric in old_results.csv or new_results.csv.
3. metric_migration_diff.csv exact header:
   metric_name,old_value,new_value,absolute_diff,relative_diff,expected_direction,classification
4. Format values and diffs with exactly four decimals where numeric. Use blank for missing numeric values.
   `absolute_diff = abs(new_value - old_value)` and is therefore non-negative. `relative_diff = (new_value - old_value) / abs(old_value)` and retains its sign. Leave both blank if either value is missing (or if the old value is zero).
5. classification must be one of: expected_definition_change, unexpected_regression, no_material_change, requires_review.
   `expected_direction` describes the expectation supported by the definition
   and migration policy, not merely the observed numeric sign. Derive it from
   the supplied sources and use only `increase`, `decrease`, `stable`, or
   `unknown` (case-insensitive prose variants such as `decrease/flat` are
   acceptable). Use `unknown` when the package provides no supported direction.
6. regression_ledger.csv exact header:
   metric_name,bad_field,policy_clause,severity
7. migration_summary.json must contain: total_metrics, expected_definition_change_count, unexpected_regression_count, no_material_change_count, requires_review_count, largest_relative_diff_metric.
   Choose `largest_relative_diff_metric` by greatest absolute magnitude of a non-blank relative_diff; break a tie lexicographically by metric_name.
8. `caveats.md` must explain which definition changes make before/after trends
   non-comparable, distinguish a true implementation regression from an
   expected definition effect, and call out any missing after-migration metric.

Do not use network access or external APIs.
