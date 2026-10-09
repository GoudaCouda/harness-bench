DROP VIEW IF EXISTS order_join;

CREATE VIEW order_join AS
WITH customer_stats AS (
  SELECT
    customer_id,
    COUNT(*) AS row_count,
    SUM(CASE WHEN current = 1 THEN 1 ELSE 0 END) AS current_count,
    MAX(CASE WHEN current = 1 THEN segment END) AS current_segment
  FROM customers
  WHERE customer_id IS NOT NULL AND customer_id <> ''
  GROUP BY customer_id
),
customer_dim AS (
  SELECT
    customer_id,
    CASE WHEN current_count = 1 THEN 'usable' ELSE 'ambiguous' END AS resolution,
    current_segment AS segment
  FROM customer_stats
),
rate_stats AS (
  SELECT
    currency,
    date,
    COUNT(*) AS row_count,
    SUM(CASE WHEN current = 1 THEN 1 ELSE 0 END) AS current_count,
    MAX(CASE WHEN current = 1 THEN usd_rate END) AS current_rate
  FROM rates
  GROUP BY currency, date
),
rate_dim AS (
  SELECT
    currency,
    date,
    CASE WHEN current_count = 1 THEN 'usable' ELSE 'ambiguous' END AS resolution,
    current_rate AS usd_rate
  FROM rate_stats
),
resolved AS (
  SELECT
    o.*,
    c.customer_id AS found_customer,
    c.resolution AS customer_resolution,
    c.segment,
    r.currency AS found_rate,
    r.resolution AS rate_resolution,
    r.usd_rate
  FROM orders AS o
  LEFT JOIN customer_dim AS c ON o.customer_id = c.customer_id
  LEFT JOIN rate_dim AS r ON o.currency = r.currency AND o.date = r.date
)
SELECT
  order_id,
  CASE
    WHEN customer_id IS NULL OR customer_id = '' THEN 'rejected'
    WHEN found_customer IS NULL THEN 'rejected'
    WHEN customer_resolution <> 'usable' THEN 'rejected'
    WHEN found_rate IS NULL THEN 'rejected'
    WHEN rate_resolution <> 'usable' THEN 'rejected'
    ELSE 'matched'
  END AS join_status,
  CASE WHEN customer_resolution = 'usable' THEN segment END AS segment,
  CASE
    WHEN customer_resolution = 'usable' AND rate_resolution = 'usable'
    THEN ROUND(amount * usd_rate, 2)
  END AS usd_amount,
  CASE
    WHEN customer_id IS NULL OR customer_id = '' THEN 'null_customer_key'
    WHEN found_customer IS NULL THEN 'unmatched_customer'
    WHEN customer_resolution <> 'usable' THEN 'ambiguous_customer'
    WHEN found_rate IS NULL THEN 'unmatched_rate'
    WHEN rate_resolution <> 'usable' THEN 'ambiguous_rate'
    ELSE ''
  END AS reason
FROM resolved;
