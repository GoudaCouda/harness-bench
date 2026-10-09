# March close review memo

The AR ledger contains **USD 930.00** of recognized invoices after excluding
void/cancelled records and the JPY invoice with no dated FX rate. Customer-linked
bank-confirmed settlements reconcile to **USD 657.50 gross receipts**, less
**USD 85.00 refunds** and **USD 8.65 fees**, for **USD 563.85 customer net cash**.

The full bank statement moves **USD 578.85**. The USD 15.00 difference from
customer net cash is the USD 25.00 orphan receipt `bank_statement.csv#B009`
less the USD 10.00 orphan refund `bank_statement.csv#B010`; both remain in Cash
Suspense. P010 is not in cash because no bank line confirms it.

INV007 demonstrates the FX timing rule: the EUR 50 invoice is recognized at
the 1.20 invoice-date rate (USD 60.00), while its receipt and EUR 1 fee use the
1.15 settlement-date rate, producing USD 56.35 net cash. INV005 remains a
Treasury exception because the exact JPY rate is absent; no rate was guessed.

The proposed journal debits Cash USD 578.85, Bank Fee Expense USD 8.65,
Customer Refunds USD 85.00, and Cash Suspense USD 10.00; it credits AR Clearing
USD 527.50 and Cash Suspense USD 155.00. Debits and credits both equal USD
682.50. The controller should resolve the eight rows in `exceptions.csv` before
any later posting decision.

Every journal line is proposed only. No journal was posted, the period was not
closed, and no payment, refund, or customer contact was executed.
