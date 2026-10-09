# Recover warehouse reservations after a worker crash

You are the warehouse systems operator recovering an offline WMS snapshot. A
worker crashed between reserve, pick and shipment confirmation. The database now
contains a duplicate hold for one idempotency key, a shipped order whose stock
must never be released, and an expired untouched reservation.

Work only in `$WORKSPACE`.

1. Read `recovery_policy.md` and `recovery_checkpoint.json`, then inspect `warehouse.db` with
   `python3 warehousectl.py status` and the documented `query` command.
2. Create `recovery_plan.json` with `schema_version` 1, the checkpoint's stable
   `recovery_id` and `source_state_sha256`, `external_actions_executed` set to
   false, and one action for each open reservation. Each action has
   `reservation_id`, `action` (`keep`, `cancel_duplicate`, `commit_shipped`, or
   `release_expired`), and `evidence_ids`. Evidence must use workspace-relative
   `file#record` locators and cover the reservation plus the controlling policy
   or shipment receipt.
3. Run `python3 warehousectl.py preview recovery_plan.json`. It writes no state;
   inspect every projected inventory and order transition.
4. Run `python3 warehousectl.py apply recovery_plan.json`, then
   `python3 warehousectl.py verify`. The latter writes `recovery_receipt.json`.
5. Apply the same reservation actions again with harmless JSON, action-order,
   or evidence-order variation. It must return `idempotent`, must not add a
   second recovery transaction, and must not move inventory again. A conflicting
   action for this already recovered `recovery_id` must be rejected.
6. Write `warehouse_handoff.md` explaining the duplicate hold, shipped-stock
   boundary, expired release, stable recovery/checkpoint identity, final
   balances, verification and semantic replay, and that no physical pick,
   shipment, or external WMS action occurred. Run `verify` once more and confirm
   the receipt remains stable.

Do not edit the controller, checkpoint, protected `warehouse_seed.sql`, policy,
shipment receipts, or database schema. The controller uses the protected seed
only to reconstruct the initial state for independent local verification. Do
not hand-author the receipt or directly update SQLite tables. All data is
synthetic and the controller is offline.
