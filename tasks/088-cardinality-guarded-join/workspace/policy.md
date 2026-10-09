# Revenue join contract

`orders -> customers` is many-to-one on `customer_id`; `orders -> rates` is
many-to-one on `(currency,date)`. Null keys never match.

- A dimension key with one row is usable when that row is current.
- For duplicate rows, use the record only when exactly one row has
  `current=true`. If multiple rows are current, or duplicates have no current
  row, the key is ambiguous and dependent orders are rejected.
- A missing dimension key is unmatched, not ambiguous.
- `usd_amount = amount * usd_rate`. Negative amounts are valid refunds and
  reduce matched revenue when both dimension joins succeed.
- Do not deduplicate or aggregate the fact table: every unique input order ID
  must appear once in the final ledger.
