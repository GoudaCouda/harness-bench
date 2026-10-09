# Shipment exception recovery policy

Review time is 2026-06-04 15:00 UTC.

- An ETA after the promise is delayed; an equal/earlier ETA is on track. A
  missing ETA is an evidence gap, not a confirmed delay.
- On-track shipments are monitored. Evidence gaps go to Carrier Operations for
  trace before the stated cutoff and are not messaged as confirmed delays.
- Standard delayed shipments receive a delay notification; no automatic credit.
- VIP delayed shipments use an expedited replacement when enough inventory can
  arrive earlier than the original. Reserve with Warehouse Operations.
- Premium delayed shipments first use a carrier recovery option that improves
  the ETA when its cutoff is still open. Otherwise use an in-stock faster
  replacement. If neither is possible, notify and offer a shipping credit.
- Never promise the recovery date as guaranteed. Customer messages may name the
  current estimate and proposed recovery, but must not expose internal notes.
  This offline plan does not reserve stock, upgrade service, issue credit, or
  contact a customer.
