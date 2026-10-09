# Repair the close pipeline without multiplying orders

You are the revenue analytics engineer taking over a failed monthly close. The
draft SQL joins raw customer and exchange-rate dimensions directly, multiplying
some orders and admitting dimension rows that are not safely resolvable.

Work only in `$WORKSPACE`. Read `policy.md` and the three CSV inputs, inspect
`pipeline/revenue_join.sql`, then run the failing baseline:

```bash
python3 bin/run_close.py
```

Repair `pipeline/revenue_join.sql` as a general many-to-one pipeline. It must
resolve each dimension key before joining facts, reject unresolved keys with
the policy's distinct reason, preserve every input order exactly once, and
include valid negative refunds in revenue only when both joins match. Do not
hard-code order IDs or final amounts.

Run `python3 bin/run_close.py` until it exits zero. The runner must generate:

- `close/order_join.csv`, with exactly the view columns
  `order_id,join_status,segment,usd_amount,reason`;
- `close/join_audit.json`, containing the observed row counts, rejection counts,
  matched revenue, cardinality declarations, errors, and pass/fail status.

Create `close_handoff.md` explaining the failed cardinality path, the SQL
resolution strategy, null/unmatched/ambiguous handling, the refund and revenue
tie-out, the validation command, and how the query remains safe for new keys.

Before finishing, rerun the close command and re-parse the final CSV and JSON.
Do not edit the inputs, policy, or runner; do not use the network or claim an
external financial-system update.
