# AP-POL-7.2 — review-stage three-way match

Apply controls in this order:

1. If the same `invoice_no` has status `paid` or `scheduled` in the register,
   hold the full invoice line as `duplicate_control`; a `reversed` entry is not
   an active duplicate.
2. Otherwise compare the invoice unit price with the PO unit price. Absolute
   variance above 2% is a full `price_variance` hold. Exactly 2% is permitted.
3. For a permitted price, sum only `accepted` receipt quantities. Approve the
   lesser of invoiced quantity, ordered quantity, and accepted quantity at the
   invoice unit price. Hold the remaining invoice quantity as
   `receipt_shortfall`. A fully received line uses `none` as its exception code.

Allowed dispositions are `matched`, `partial_hold`, and `full_hold`. Route
receipt shortages to `receiving`, price variance to `buyer`, duplicate control
to `ap_control`, and clean matches to `ap_review`. Evidence must identify the
source record IDs used. This procedure only stages an internal review; it never
authorizes approval or payment execution.
