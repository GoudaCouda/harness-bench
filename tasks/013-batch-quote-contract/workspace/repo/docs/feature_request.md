# Batch quote feature request

Add a pure service-layer function with this exact signature:

```python
build_batch_quotes(requests, catalog, coupons, quote_date)
```

The function returns a list with one result per input item, in input order.
Inputs and outputs are ordinary Python dictionaries and lists.

## Batch and identity rules

- `requests` must be a list containing 1–50 items. Otherwise raise `ValueError`.
- Every item must be a dictionary. A non-dictionary item is returned as
  `{"request_id": null, "status": "rejected", "code": "invalid_item"}`.
- `request_id` must be a non-empty string.
- If a non-empty `request_id` occurs more than once, every occurrence is
  rejected with `duplicate_request_id`; unrelated items are still evaluated.

## Item validation

Validate in this order and return the first applicable code:

1. `invalid_request_id`
2. `duplicate_request_id`
3. `unknown_plan`
4. `invalid_seats`
5. `invalid_term`
6. `unknown_coupon`
7. `coupon_wrong_plan`
8. `coupon_expired`

`seats` must be an integer but not a boolean and must be between the selected
plan's inclusive `min_seats` and `max_seats`. `term_months` must be the integer
`1` or `12`, excluding booleans. Missing or null `coupon` means no coupon.

Coupon `expires_on` is inclusive: a coupon is valid on that date and expired
after it. Dates use the fixed-width ISO `YYYY-MM-DD` form supplied by the task.

## Price calculation

For a valid item:

1. `subtotal_cents = monthly_cents * seats * term_months`
2. For a 12-month term, calculate
   `term_discount_cents = subtotal_cents * annual_discount_bps // 10000`;
   otherwise it is zero.
3. Subtract the term discount.
4. Calculate the coupon discount on that remainder with integer floor division.
5. Subtract the coupon discount to obtain `total_cents`.

Return exactly these success fields:

```json
{
  "request_id": "Q-1",
  "status": "quoted",
  "subtotal_cents": 120000,
  "term_discount_cents": 12000,
  "coupon_discount_cents": 5400,
  "total_cents": 102600
}
```

Rejected outcomes contain exactly `request_id`, `status`, and `code`.

## API contract

Keep `/quotes/single` unchanged. Add an inline `POST /quotes/batch` operation to
`api/openapi.json`. Its required JSON body has `quote_date` and `requests`;
`requests` is an array with `minItems: 1`, `maxItems: 50`, and item-required
fields `request_id`, `plan`, `seats`, and `term_months`. Document JSON `200` and
`400` responses. The 200 response must describe an array of per-item outcomes.
