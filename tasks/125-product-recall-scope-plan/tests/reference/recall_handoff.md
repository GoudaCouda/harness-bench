# RC-2026-0417 local recall recovery handoff

The controlling signed scope is SCOPE-02: it supersedes SCOPE-01, while the later
SCOPE-03-DRAFT has no authority. LOT-A and mixed LOT-B directly contain CB-77;
LOT-E contains verified descendant CB-77-D. All three are affected and their
available inventory is quarantined. LOT-F contains CB-77 but falls outside the
controlling manufacture window, and LOT-C contains only CB-SAFE, so both remain
unaffected. LOT-D uses ADH-RED through CB-UNK with an unresolved parent and is
therefore held as pending trace rather than guessed affected or cleared.

The out-of-order feed was reduced by stable event identity and sequence. EV-501,
EV-502, EV-504, and EV-506 are the current shipment events. EV-500 and EV-503
are stale. The exact duplicate EV-502 delivery is represented only once, and
EV-505 is quarantined because SH-UNKNOWN is absent. The interrupted prepared
EV-504 journal was completed in the same RC-2026-0417 transaction.

SH-A is already delivered, so CH-RETAIL receives only a local recall draft;
SH-E is in transit and has a staged stop request. SH-B is in transit but CH-DIST
still lacks approved authority, so its channel work remains pending approval.
SH-D stays under a pending-trace hold and CH-MKT remains a trace hold. Inventory
for affected and unresolved lots is nonnegative and conserved: units were moved
from available to quarantine without changing on-hand totals.

Preview, apply, independent verification, equivalent idempotent replay, and local
stage binding completed. This package executed no external stop-sale, notice,
refund, repair, shipment change, or channel action; every draft and receipt is
an offline handoff pending human authority.
