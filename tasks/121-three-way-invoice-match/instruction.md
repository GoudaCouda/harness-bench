# Stage the July accounts-payable three-way match review

You are the AP analyst preparing the July review batch for a controller. The
workspace contains purchase orders, receiving events, supplier invoice lines,
the prior-payment register, the current policy, and the CSV import template
used by the review queue. Work entirely from those local records.

Use `apctl.py` as the local review-queue interface. Run
`python3 apctl.py --help` and `python3 apctl.py status` before drafting. The
`inspect --invoice-line ID` command returns the invoice, PO, receipt, and prior
register records for one line; it does not decide the correct disposition.
The supplied `.ap_review_state.json` is a draft checkpoint, not an answer.

Reconcile every invoice line against the related PO line and accepted receipt
quantity. Apply the policy in its stated precedence order, including prior paid
or scheduled invoice identities, receipt status, quantity limits, and the price
variance boundary. Do not approve or pay anything: this is a review-stage
package only.

Create exactly these two files at the workspace root; do not add notes, payment
files, or other deliverables:

1. `invoice_match.csv`, using the header in `ap_review_template.csv`. Include
   every `invoice_line_id` exactly once. Monetary values must be non-negative
   decimal amounts in USD, rendered with exactly two decimal places. Leading
   zeros are permitted and have no effect on numeric equality.
   `approved_amount + held_amount` must equal that line's invoice amount. Use
   the policy's disposition, exception code, and review owner on every row,
   including clean matches. `evidence` is a semicolon-separated set of
   `filename#record_id` locators and must make every line reviewable: cite its
   invoice, the PO and every receipt event considered when receipt/price checks
   apply, and the relevant register event when duplicate state is considered.
   This includes rejected receipts and reversed register entries that affect a
   decision. Cite only evidence used for that line; do not stuff unrelated
   locators.
2. `payables_control.json`, the batch control record. It must be one JSON object
   with exactly these keys and types, and no additional fields:

   | key | type | required value or derivation |
   |---|---|---|
   | `batch_id` | string | `2026-07-ap-review` |
   | `policy_id` | string | `AP-POL-7.2` |
   | `cutoff_date` | string | `2026-07-31` |
   | `currency` | string | `USD` |
   | `execution_state` | string | `review_only`; labels this artifact as a review proposal, not as proof of external non-execution |
   | `invoice_line_count` | integer | number of unique invoice lines in the final CSV |
   | `exception_line_count` | integer | number of final CSV rows with a non-zero held amount |
   | `invoice_total` | string | sum of invoice line amounts, with exactly two decimal places |
   | `approved_total` | string | sum of final approved amounts, with exactly two decimal places |
   | `held_total` | string | sum of final held amounts, with exactly two decimal places |

   Derive all counts and monetary totals independently from your final
   `invoice_match.csv` and ensure that they reconcile. The only permitted
   execution state is `review_only`; this artifact must not represent approval
   or payment.

Keep all provided files byte-for-byte unchanged. Do not create a payment file,
call an external service, or use the network. Before finishing, parse both
deliverables and independently verify unique line IDs, exact-cent arithmetic,
exception count, and batch totals. Keep the CSV at exactly seven cells per row.
Use standards-compliant JSON with unique keys (no `NaN` or infinity). Output
cells and JSON strings must not contain Unicode control or format characters,
including a BOM; CSV cells must not be spreadsheet-formula text beginning with
`=`, `+`, `-`, or `@` after whitespace.

After both business artifacts reconcile, run `python3 apctl.py validate`, fix
every reported interface or arithmetic error, and run `python3 apctl.py stage`.
Staging updates `.ap_review_state.json` and creates the local
`ap_review_receipt.json`; neither represents approval, posting, or payment.
Finally run `python3 apctl.py replay` twice. Both replays must pass and leave
the state and receipt byte-for-byte stable. Do not hand-edit either controller
artifact or modify `apctl.py`.
