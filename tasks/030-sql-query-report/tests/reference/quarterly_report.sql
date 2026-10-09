DROP VIEW IF EXISTS report_reconciliation;
DROP VIEW IF EXISTS report_order_audit;
DROP VIEW IF EXISTS report_category_revenue;
DROP VIEW IF EXISTS report_region_revenue;
DROP VIEW IF EXISTS report_product_revenue;
DROP VIEW IF EXISTS _report_line_facts;
DROP VIEW IF EXISTS _report_completed_refunds;

CREATE VIEW _report_completed_refunds AS
SELECT
  order_id,
  line_id,
  ROUND(SUM(amount), 2) AS completed_refunds
FROM refunds
WHERE status = 'completed'
  AND refund_date <= '2025-04-07'
GROUP BY order_id, line_id;

CREATE VIEW _report_line_facts AS
SELECT
  o.order_id,
  c.region,
  p.product_id,
  p.product_name,
  p.category,
  oi.quantity,
  ROUND(oi.quantity * oi.unit_price, 2) AS gross_revenue,
  ROUND(oi.discount_amount, 2) AS discount_amount,
  ROUND(COALESCE(r.completed_refunds, 0), 2) AS completed_refunds,
  ROUND(
    oi.quantity * oi.unit_price
      - oi.discount_amount
      - COALESCE(r.completed_refunds, 0),
    2
  ) AS net_revenue
FROM orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
JOIN order_items AS oi ON oi.order_id = o.order_id
JOIN products AS p ON p.product_id = oi.product_id
LEFT JOIN _report_completed_refunds AS r
  ON r.order_id = oi.order_id AND r.line_id = oi.line_id
WHERE o.status IN ('paid', 'partially_refunded')
  AND o.order_date BETWEEN '2025-01-01' AND '2025-03-31';

CREATE VIEW report_product_revenue AS
WITH product_totals AS (
  SELECT
    product_id,
    product_name,
    ROUND(SUM(net_revenue), 2) AS net_revenue
  FROM _report_line_facts
  GROUP BY product_id, product_name
), ranked AS (
  SELECT
    ROW_NUMBER() OVER (
      ORDER BY net_revenue DESC, product_id ASC
    ) AS revenue_rank,
    product_id,
    product_name,
    net_revenue
  FROM product_totals
)
SELECT revenue_rank, product_id, product_name, net_revenue
FROM ranked
WHERE revenue_rank <= 3
ORDER BY revenue_rank;

CREATE VIEW report_region_revenue AS
SELECT
  region,
  COUNT(DISTINCT order_id) AS order_count,
  ROUND(SUM(net_revenue), 2) AS net_revenue
FROM _report_line_facts
GROUP BY region
ORDER BY region;

CREATE VIEW report_category_revenue AS
SELECT
  category,
  SUM(quantity) AS units_sold,
  ROUND(SUM(net_revenue), 2) AS net_revenue
FROM _report_line_facts
GROUP BY category
ORDER BY category;

CREATE VIEW report_order_audit AS
SELECT
  order_id,
  CASE
    WHEN status NOT IN ('paid', 'partially_refunded') THEN 'excluded_status'
    WHEN order_date NOT BETWEEN '2025-01-01' AND '2025-03-31' THEN 'excluded_date'
    ELSE 'included'
  END AS disposition
FROM orders
ORDER BY order_id;

CREATE VIEW report_reconciliation AS
SELECT
  COUNT(DISTINCT order_id) AS included_order_count,
  ROUND(SUM(gross_revenue), 2) AS gross_revenue,
  ROUND(SUM(discount_amount), 2) AS discount_amount,
  ROUND(SUM(completed_refunds), 2) AS completed_refunds,
  ROUND(SUM(net_revenue), 2) AS net_revenue
FROM _report_line_facts;
