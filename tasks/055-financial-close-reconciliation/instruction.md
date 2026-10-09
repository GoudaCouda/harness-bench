# Prepare the March close review package

You are the revenue accountant preparing a controller-ready March close package
for Northstar Services. Reconcile the AR ledger, processor settlements, bank
statement, refunds, and dated FX table under `close_policy.md`. The evidence
contains void and cancelled invoices, missing FX, unbanked processor activity,
bank activity without a known processor item, refunds, and cash whose invoice
cannot be found.

Create a `close/` directory with four deliverables:

- `reconciliation.csv`: one row for every invoice plus any **processor
  settlement that has a matching bank receipt but names an invoice absent from
  the AR ledger**. A bank-only receipt whose source ID has no processor row is
  an `orphan_bank` exception and suspense-journal item, not an additional
  reconciliation row. Use columns `record_id`, `customer_id`,
  `recognized_invoice_usd`, `gross_receipt_usd`, `refund_usd`, `fee_usd`,
  `net_cash_usd`, `close_status`.
- `exceptions.csv`: one actionable row per unresolved close exception, with
  columns `exception_id`, `category`, `amount_usd`, `owner`, `next_action`,
  `evidence`. `amount_usd` is the positive magnitude under investigation: use
  the recognized invoice amount for an outstanding receivable, and the expected
  or observed **net bank movement after processor fees** for settlement, bank,
  or refund exceptions. Leave it blank when policy requires a missing FX rate
  to remain unresolved; do not invent one. In `evidence`, separate locators
  with semicolons. Use `basename.csv#record_id` for a decisive source row (the
  record ID is the value in that source's first column), or `basename.csv` when
  the conclusion depends on checking the complete source, such as proving that
  no matching row or dated rate exists. Every locator must resolve to one of
  the supplied CSV files. Include the evidence needed for that exception; do
  not attach unrelated records merely to make the field look complete.
- `proposed_journal.csv`: a balanced, review-only journal proposal using the
  header in `journal_import_template.csv`. It must tie all in-scope bank movement
  to AR, fees, refunds, and suspense without including unbanked processor
  activity. Every line must remain `proposed`. Its `evidence` column uses the
  same semicolon-separated locator syntax. For an aggregate journal line, a
  file-level locator is appropriate when the whole source was reconciled;
  otherwise cite the source rows that determine that line. Extra evidence is
  acceptable only when it is real and relevant to the same journal role.
- `close_memo.md`: explain the tie-out, recognized-invoice and net-cash totals,
  material exceptions, FX timing effects, journal logic, and controller next
  steps with local evidence references.

Apply source precedence and Decimal rounding exactly as described by policy.
Independently reparse and reconcile your files before finishing. Keep all input
files unchanged. This task does not authorize posting a journal, closing a
period, initiating a payment/refund, contacting a customer, or using the
network; do not create or claim any such action.
