# Commercial Operations Q1 2025 reporting policy

## Reporting period and eligible orders

- The reporting period is 2025-01-01 through 2025-03-31, inclusive, using
  `orders.order_date` as stored in the extract.
- Only orders whose status is `paid` or `partially_refunded` are eligible.
- For the audit view, status exclusion takes precedence over date exclusion.

## Line and refund treatment

- Gross revenue is `quantity * unit_price` for every line on an eligible order.
- Subtract the line's `discount_amount` once.
- Subtract refunds only when `refunds.status = 'completed'` and
  `refund_date <= '2025-04-07'`.
- Refunds are line-level adjustments. Several refund rows can refer to one line;
  aggregate them before joining to order items so that the source line is never
  duplicated.
- Pending or declined refunds and completed refunds after the cutoff do not
  reduce Q1 revenue.
- Net line revenue is gross revenue minus the line discount minus eligible
  completed refunds. The extract is governed so that this value is non-negative.

## Reporting and reconciliation

- `units_sold` remains the source quantity on included lines; partial monetary
  refunds do not change it.
- Regional order count is a distinct order count.
- Product leaderboard ties are resolved by stable `product_id` ascending.
- All five report views must derive from source rows and agree with the same
  eligible-order and refund logic.
