# Subscription entitlement recovery handoff

The signed `psnap_20260818_0900` snapshot supplied only the missing
`evt_O102` invoice-finalization and `evt_C302` retry-schedule records. All
other events came from the local spool, were replayed by provider sequence,
and the duplicate `evt_C303` delivery was counted once. `evt_X901` names no
known subscription and was quarantined without creating a customer record.

Orchid is active on seven Pro seats. Its 2,500-cent partial refund changes the
invoice to partially refunded but does not reduce entitlement. Cobalt's later
verified 9,000-cent payment supersedes the failed attempt and restores four
Team seats. Amber's full 20,000-cent lost chargeback is beyond the published
grace deadline, so the local entitlement is suspended pending manual billing
review. Dahlia remains active on two Basic seats until the scheduled period
end; cancellation was not applied early.

The controller restored the interrupted prior journal before atomically
committing this projection. Preview, verification, local pending-review
receipt, and replay close over the same source, plan, and semantic database
hashes; replay reported byte-stable receipt and semantic state.

No refund, provider cancellation, provider entitlement mutation, customer
notification, or customer contact was executed. The staged receipt is local
review evidence only and does not authorize an external action.
