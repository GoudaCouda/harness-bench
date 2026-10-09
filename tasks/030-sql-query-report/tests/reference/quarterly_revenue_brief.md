# Q1 2025 recognized net-revenue brief

The supplied snapshot produces **$16,750.00 of recognized net revenue from 19
included orders**. Atlas Laptop is the leading product at **$4,385.00**, and
North is the leading region at **$7,525.00**. There is no material tie in the
current product leaderboard.

The financial bridge is **$18,075.00 gross revenue - $1,000.00 line discounts -
$325.00 eligible completed refunds = $16,750.00 net revenue**. Product, region,
category and reconciliation views all use that same included line population.

Six orders are status-excluded and five orders are date-excluded. The query
includes only `paid` and `partially_refunded` orders dated from 2025-01-01
through 2025-03-31 inclusive. Status exclusion has precedence over date
exclusion in the audit. Only completed line-level refunds dated on or before the
2025-04-07 cutoff reduce revenue; pending, declined and later refunds do not.
Multiple eligible refunds are aggregated by order and line before joining, so
they cannot duplicate gross revenue. Regional order counts use distinct orders,
while category units retain the original included line quantities.

The accompanying `quarterly_report.sql` is idempotent and derives its results
from source rows rather than the current IDs or totals. It can therefore be run
again after a corrected extract is loaded under the same schema.
