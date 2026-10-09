The July reimbursement batch is waiting for controller review. Reconcile the
submitted expenses against the travel authorizations, corporate-card feed,
attachments, event schedule, FX table, approval register, and reimbursement
policy in the workspace.

Treat `expense_lines.csv` as the submitted batch, but do not trust its category,
attachment, trip, or duplicate status without checking the other records. Use
the policy's treatment of lodging tax, provided meals, per diem, missing
receipts, approval gates, personal spend, duplicates, and foreign currency.

Create:

- `reimbursement_audit.csv`, with one row for every submitted `expense_id` and
  header
  `expense_id,employee,claimed_usd,allowed_usd,status,reason,recommended_action`.
  `status` must be `approved`, `adjusted`, `pending`, or `rejected`. Monetary
  fields are USD numbers with two decimals and no currency symbols.
- `missing_docs.md`, a controller handoff that identifies each item blocked by
  missing or invalid documentation/authorization, distinguishes it from a
  policy rejection, and reconciles total claimed USD, total allowed USD, and
  counts by status.

Do not modify source records, invent an approval, treat a copied receipt as a
second expense, or claim that any payment was issued. This review only stages
the batch for the controller.
