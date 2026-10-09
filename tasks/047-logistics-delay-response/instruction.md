Prepare the 15:00 UTC logistics exception handoff. Reconcile shipments, carrier
updates, customer tiers, replacement inventory, and the recovery policy.

Create `delay_actions.csv` with columns
`shipment_id,status,action,owner,deadline,reason`, covering every shipment once.
Choose an operational action that follows the recovery precedence and does not
consume inventory twice. Create `customer_messages.md` with one draft section
for each confirmed delayed shipment and none for on-track or evidence-gap items.
Each draft should honestly communicate the current estimate and proposed next
step without guaranteeing a date, blaming the customer, or exposing carrier
notes.

Do not modify inputs or claim that a trace, reservation, upgrade, credit, or
message has already been executed.
