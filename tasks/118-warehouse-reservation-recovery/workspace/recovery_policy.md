# Reservation crash recovery policy

- An idempotency key may have at most one active reservation. Keep the lowest-sequence successful hold and cancel later duplicates.
- A verified shipment receipt is terminal: commit its reservation to `shipped`; never release that quantity.
- A held reservation past `expires_at` with no pick or shipment may be released.
- Inventory closes as `available + reserved + shipped = on_hand` for each SKU.
- `recovery_checkpoint.json` identifies the one recovery incident and binds it to the initial operational database state. A plan is valid only for that `recovery_id` and `source_state_sha256`.
- Recovery applies as one transaction keyed by the stable `recovery_id`. Replaying the same reservation actions with different JSON serialization, action order, or evidence order is an idempotent no-op. A later plan with conflicting reservation actions for the same recovery ID is rejected and never moves inventory again.
- This offline snapshot performs no physical pick, shipment, carrier, payment, or production WMS action.

## Stable evidence locators

- A reservation row may be cited by its stable ID as `warehouse.db#RSV-100-A`,
  or by the table-qualified equivalent `warehouse.db#reservations/RSV-100-A`.
- The general policy may be cited as `recovery_policy.md#policy`; the narrower
  `#duplicate-holds` and `#expired-holds` anchors are also accepted.
- A shipped reservation must additionally cite its receipt, for example
  `shipment_receipts.json#SHIP-200-A`.
- `preview` reports missing locator groups separately for each reservation and
  never mutates the database.
