# Purchase-card close policy (revision 2026-06)

## Evidence and precedence

Each positive issuer charge requires a receipt whose parsed total, currency, merchant, and transaction locator agree with the issuer row, plus a recorded `accepted` department acceptance. Refunds do not require a new receipt, but must name an already-posted original transaction in the ERP ledger. Decisions use this precedence: linked refund; missing or invalid receipt; connected split-purchase review; missing acceptance; non-reimbursable sales tax; clear.

## Published dispositions

- `clear`: complete receipt and acceptance; clear the full charge.
- `hold_missing_receipt`: no valid receipt artifact; clear zero and hold the full charge.
- `hold_suspected_split`: every vertex in a same-cardholder, same-merchant, same-local-day connected component whose combined positive charges exceed 500.00 USD while each charge does not; clear zero and hold each full charge. Acceptance does not waive this review.
- `hold_missing_acceptance`: valid receipt but no `accepted` department evidence; clear zero and hold the full charge.
- `partial_nonreimbursable_tax`: otherwise complete evidence, but sales tax is not reimbursable for this tax-exempt organization; clear subtotal and hold the exact tax.
- `clear_prior_period_refund`: clear a negative amount only against its named, already-posted prior-period original. Never net it against an unrelated current exception.

Receipt hashes must match `receipt_manifest.json`. PDF, HTML, and JSON receipt bodies must be parsed rather than trusted by filename. Amounts are integer cents. The issuer and ERP databases, acceptance database, receipt artifacts, and prior postings are immutable.

## Recovery and side-effect boundary

The business identity is the `close_id` in `close_context.json`; the source checkpoint binds the immutable inputs, not JSON formatting. A semantically equivalent plan replay is a no-op. A different decision under an already committed `close_id`, or a changed source checkpoint, is a conflict and must not mutate close state. The interrupted prepared row is local recovery evidence, not proof of posting. `stage` remains pending an independent ERP posting approval. No payment, ERP posting, cardholder contact, procurement approval, or external notification is permitted.
