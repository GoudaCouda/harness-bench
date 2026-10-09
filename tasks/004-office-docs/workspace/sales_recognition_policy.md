# Northstar Supply revenue close policy

**Policy ID:** REV-CLOSE-2026-Q3
**Reporting period:** 2026-07-01 through 2026-09-30, inclusive
**Adjustment close cutoff:** 2026-10-05 23:59:59 UTC
**Reporting currency:** USD

## Recognition rules

1. Recognize an order only when `status` is `fulfilled`, its `booked_at` date
   falls inside the reporting period, and its currency is USD. Pending,
   cancelled, and out-of-period orders do not contribute to recognized order
   counts or gross recognized sales.
2. Start each region with the gross amount of its recognized orders.
3. Deduct a refund only when all of the following hold: its order is recognized
   under rule 1; the event type is `refund`; the event state is `settled`; and
   `event_at` is no later than the adjustment close cutoff.
4. If an event names `supersedes_event_id`, the superseded event is historical
   evidence and must not also be counted. A later `reversed` event therefore
   removes the superseded refund from deductions; a later replacement
   `settled` event is counted once.
5. Approved but unsettled refunds, refunds settled after cutoff, and refunds
   attached to unrecognized orders are not deducted. They must be described in
   the exception section with their order, amount, and reason.
6. For each region and for the company, net recognized sales equal gross
   recognized sales less deducted refunds. Preserve cents throughout; do not
   round intermediate values.

The close package must be internally consistent and must not state that an
unapplied adjustment has posted to the ledger.
