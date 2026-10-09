DROP VIEW IF EXISTS order_join;

-- Draft from the failed close workbook. It joins raw dimensions directly and
-- therefore multiplies orders when a customer or rate key has duplicates.
CREATE VIEW order_join AS
SELECT
  o.order_id,
  'matched' AS join_status,
  c.segment,
  ROUND(o.amount * r.usd_rate, 2) AS usd_amount,
  '' AS reason
FROM orders AS o
LEFT JOIN customers AS c
  ON o.customer_id = c.customer_id
LEFT JOIN rates AS r
  ON o.currency = r.currency AND o.date = r.date;
