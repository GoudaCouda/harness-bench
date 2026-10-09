# Offline recall recovery policy

## Signed scope precedence

Use only a revision whose `signature_status` is `verified` and whose `key_id` is
listed in `trusted_key_ids`. A later trusted revision that names an earlier
revision in `supersedes` controls the recovery. Draft revisions never control.

## Genealogy decisions

Within the controlling manufacture window, a lot is `affected` when any of its
component batches is a targeted batch or, when enabled by the revision, a
verified descendant of a targeted batch. A mixed lot remains affected.

A lot inside the window whose component uses the targeted material but has an
`unresolved_parent` is `pending_trace`; quarantine it without guessing its
parent. Other lots are `unaffected`, including lots outside the controlling
window.

## Feed adjudication

Treat identical repeated event IDs as one delivery. For each known shipment,
`apply_current` only to the unique event with the greatest sequence greater
than the stored sequence. Other unique events for that shipment are
`ignore_stale`. Use `quarantine_unknown_shipment` for an event whose shipment
does not exist locally. Conflicting duplicates are invalid input.

## Local actions

Move all currently available on-hand units for affected lots into quarantine;
use the same local quarantine for `pending_trace` lots. Never change total
on-hand units. Affected delivered shipments require a local channel recall
draft; affected in-transit shipments require a staged stop request. Pending
trace shipments remain under a local trace hold. Unaffected lots and shipments
remain clear.

For a channel reached by an affected shipment, set `draft_ready` only when its
authority is verified; otherwise set `pending_approval`. A channel reached only
by a pending-trace shipment is `trace_hold`.

## Recovery and external-action boundary

`RC-2026-0417` stopped after preparing `EV-504`. Complete it as one local
transaction and retain one journal/transaction record. An equivalent replay
for the same recall and source checkpoint is a no-op; a conflicting replay is
rejected. Local drafts, holds, verification, and staging receipts do not mean
that a stop-sale, notice, refund, repair, or channel action was executed.
