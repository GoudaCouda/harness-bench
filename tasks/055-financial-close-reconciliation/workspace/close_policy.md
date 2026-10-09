# FIN-CLOSE-3.1 — March review close

The close date is 2026-03-31 and all output amounts are USD rounded half-up to
two decimals per source transaction.

1. Recognize `open` invoices at the FX rate on `invoice_date`. Exclude `void`
   and `cancelled` invoices. If the exact dated FX rate is missing, do not guess
   or forward-fill it: exclude the invoice from USD totals and route it to
   Treasury as `missing_fx`.
2. Cash exists only when a processor settlement has a matching bank `receipt`
   line with the same source ID, currency, date, and net source amount
   (`gross_amount - fee_amount`). Convert gross and fee separately using the
   settlement-date rate. An unbanked processor settlement is `bank_unconfirmed`
   and contributes zero cash to this close.
3. A bank-confirmed settlement for a void/cancelled invoice or missing invoice
   remains real cash but is routed to suspense rather than revenue/AR clearing.
4. Count a refund only when its processor record has a matching bank `refund`
   line. Convert on `refund_date`. A refund whose invoice is absent is an
   `orphan_refund` suspense item, not a customer refund in reconciliation.
5. A bank line without a known processor settlement/refund is `orphan_bank`
   suspense. The proposed journal must include all bank movement, including
   orphan items, but must exclude unbanked processor activity.

The proposal may debit Cash, Bank Fee Expense, Customer Refunds, and Cash
Suspense, and credit AR Clearing and Cash Suspense. It must balance and every
line must have `batch_status=proposed`. Posting, closing the period, paying,
refunding, or contacting a customer requires separate controller approval and
is outside this task.
