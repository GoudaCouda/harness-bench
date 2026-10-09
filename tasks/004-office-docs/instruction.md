# Prepare the Q3 regional sales close package

You are supporting Revenue Operations at Northstar Supply. The finance lead
needs the Q3 regional sales close package for tomorrow's management review.
The order export and adjustment register are not themselves reporting totals:
apply the governing close policy, reconcile the events, and produce a usable
Word memo plus the upload used by the reporting dashboard.

Work only in `$WORKSPACE`. Read these source files before calculating anything:

- `orders_q3.csv`
- `returns_and_adjustments.csv`
- `sales_recognition_policy.md`
- `regional_sales_memo_template.docx`

Create these two files at the workspace root:

1. `regional_rollup.csv`, encoded as UTF-8, with these columns in this order:
   `region,recognized_order_count,gross_recognized_sales,deducted_refunds,net_recognized_sales`.
   Include one row for every region represented by an in-period recognized
   order. Monetary values must be decimal USD values with two fractional
   digits. Do not add a TOTAL row; the memo carries the company total.
2. `regional_sales_memo.docx`, using the supplied Word template as the starting
   point. Preserve the Northstar header and confidentiality footer, replace all
   template placeholders, and make it a finished memo suitable for a finance
   lead to circulate.

The memo must contain:

- a memo heading with date, audience, subject, and the policy ID actually used;
- a short methodology explaining which source records control recognition and
  how adjustments were treated;
- a genuine Word table that associates every region with its recognized order
  count, gross recognized sales, deducted refunds, and net recognized sales;
- a clearly labelled company reconciliation showing that gross less deducted
  refunds equals net recognized sales;
- an exception section identifying every material open, late, reversed,
  superseded, or otherwise unapplied adjustment. For each exception, include
  the relevant adjustment event ID or linked event IDs, order ID, amount, its
  Q3 treatment, and the policy reason for that treatment. Prose or a genuine
  Word table is acceptable; no particular heading or sentence wording is
  required;
- a concise management conclusion that identifies and quantifies the leading
  region by net recognized sales and explains the remaining close exposure
  from unapplied adjustments without treating that exposure as booked.

The CSV and memo must agree. Do not guess missing facts, modify any source file,
or claim that an open adjustment has already been posted. Keep the finished
memo self-contained: do not add macros, embedded active/binary content,
external templates or data relationships, or external hyperlinks. A valid
`.docx` is a real Office Open XML document, not renamed text or a page of
disconnected answer tokens. Labels such as `To`, `Prepared for`, `Subject`, or
`Topic` and equivalent professional wording are all acceptable; accuracy and
business meaning matter, not reproducing the template's exact phrasing.
