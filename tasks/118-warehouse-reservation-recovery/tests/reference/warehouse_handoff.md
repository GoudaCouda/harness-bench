# Warehouse reservation recovery handoff

The offline recovery retained `RSV-100-A` as the sole `IDEMP-O100` hold and
cancelled the later duplicate `RSV-100-B`. The duplicate release restored four
`SKU-A` units to available stock. It did not change order `O-100`, whose first
reservation remains held.

`RSV-200` had a verified shipment receipt (`SHIP-200-A`), so its three units
were committed to shipped stock and were never released back to availability.
Order `O-200` is terminally shipped. The expired, unpicked `RSV-300` was
released, returning five `SKU-B` units and marking order `O-300` released.

Final balances are `SKU-A`: on hand 12, available 5, reserved 4, shipped 3;
and `SKU-B`: on hand 8, available 8, reserved 0, shipped 0. Each SKU closes as
available plus reserved plus shipped equals on hand.

Recovery `WMS-REC-2026-08-16-01` remained bound to the published initial-state
checkpoint. `warehousectl.py verify` passed all reservation, order,
nonnegative-inventory, semantic-plan, and single-transaction checks. Replaying
the same actions with reordered JSON and evidence returned idempotent, leaving
exactly one recovery transaction and unchanged balances. A conflicting action
for the same recovery ID is rejected. This was an offline snapshot repair
only: no physical pick, shipment, carrier, customer, or external WMS action
was performed.
