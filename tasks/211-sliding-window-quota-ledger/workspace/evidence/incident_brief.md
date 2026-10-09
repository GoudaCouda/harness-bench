# Incident WB-2026-0317-03: partner quota batch parked

A partner batch arrived at the burst boundary. Finance asked whether refund
`e1` (a debit from more than a day ago) can restore daily quota so a large
west-side capture can proceed. It cannot: that original debit has left the
daily window.

Evaluate the pending batch against the ledger in `state/quota_events.json`.
Do not contact the partner.
