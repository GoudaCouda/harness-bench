# Cron contract

The mill clock has 12 months of 30 days. `dow` is `(month-1)*30 + (day-1)`
modulo 7, with 0 for month 1 day 1.

`next_fire(expr, after)` takes a 5-field expression `minute hour day month dow`
and an `after` object with integer `month`, `day`, `hour`, and `minute`.
Return the first matching clock time **strictly after** that stamp.

Each field is `*`, a single integer, a `a-b` range, or a comma list of those.
When `day` and `dow` are both not `*`, a date matches if **either** field
matches. Otherwise the non-star field must match.

Raise `ValueError` for the wrong number of fields, empty fields, or when no
fire exists in 12 months of search.
