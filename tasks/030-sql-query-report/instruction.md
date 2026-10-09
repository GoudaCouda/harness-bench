# Q1 net-revenue reporting handoff

You are taking over a quarterly sales query that Commercial Operations can no
longer rerun after the original analyst left. Finance needs the Q1 pack today,
and the same SQL will be rerun after late corrections are loaded.

The workspace contains:

- `sales_snapshot.sql`: an offline SQLite schema and the current extracted rows;
- `reporting_policy.md`: the approved recognition, refund, exclusion and
  tie-breaking rules.

Work only with these local files. Do not use a network service, and do not edit
either input.

## Deliverables

Create both of the following in the workspace:

1. `quarterly_report.sql` — a reusable SQLite script. It must be safe to run
   twice against the same database and must create or replace the five views
   listed below without changing any source-table rows.
2. `quarterly_revenue_brief.md` — a short handoff for Finance based on the
   supplied snapshot. State the recognized net-revenue total, the leading
   product and region, the number of included orders and both exclusion counts.
   Show the gross-minus-discounts-minus-completed-refunds reconciliation and
   explain the date/status/refund-cutoff rules you applied. Mention any material
   tie in a leaderboard; if there is no tie in this snapshot, say so.

The SQL is the durable deliverable: do not hard-code the current order IDs,
product IDs, regions, categories or totals. It must continue to work when rows
are corrected or appended under the same schema.

## Downstream view interface

The reporting workbook consumes these exact view and column names:

- `report_product_revenue(revenue_rank, product_id, product_name, net_revenue)`
  contains only the top three products. Rank by net revenue descending, then by
  `product_id` ascending for equal revenue.
- `report_region_revenue(region, order_count, net_revenue)` contains one row per
  region represented by an included order line. `order_count` is the distinct
  included-order count, not the line count.
- `report_category_revenue(category, units_sold, net_revenue)` contains one row
  per represented category. `units_sold` is the sum of source line quantities;
  refunds affect revenue, not this quantity.
- `report_order_audit(order_id, disposition)` contains every source order once.
  The disposition is `included`, `excluded_status`, or `excluded_date`. Apply
  status precedence: an order with both an ineligible status and an out-of-range
  date is `excluded_status`.
- `report_reconciliation(included_order_count, gross_revenue, discount_amount,
  completed_refunds, net_revenue)` contains exactly one row for the whole
  reporting period.

Money columns must be numeric and rounded to two decimal places. Product,
region and category grouping must use their stable IDs/labels from the source,
not display-name shortcuts. You may create helper views if useful, but the five
views above are the supported interface.

Before handing off, load `sales_snapshot.sql` into a temporary SQLite database,
run your script twice, query all five views, and reconcile their totals. Python's
standard-library `sqlite3` module is available if you do not have the SQLite CLI.
