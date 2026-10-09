# Recover an interrupted purchase-order EDI match batch

Recover a synthetic offline procurement batch whose worker stopped after one
PO projection but before journal commit. The SQLite store contains protected
order/line facts, one posted invoice, and the before-image. The out-of-order EDI
stream contains representative 850s plus 855, 856, and 810 messages, including
a redelivery, control-number collision, stale revision, unknown PO, and posted
invoice traffic.

Start with `python3 poedictl.py inspect`. Read both policy files, every EDI row,
and the relevant `state/procurement.db` tables. Do not trust delivery order.
Transaction identity is sender + receiver + message type + control number:
ignore an identical redelivery, quarantine changed content under the same
identity, and use the highest accepted revision per PO/message type. If one
identity has repeated identical content and one changed singleton, retain the
repeated body and quarantine the singleton.

Match 850/855/856/810 facts line by line. An 855 rejection blocks the PO; its
quantity may decrease but not increase, and its price must stay within policy
tolerance. An 810 quantity cannot exceed acknowledged or shipped quantity and
its price must equal the authoritative 855. Keep missing acknowledgement,
supplier rejection, quantity variance, and price mismatch as distinct holds.
Preserve the posted invoice, posting identity/time, and protected PO identity.

Create `edi_recovery_plan.json` with exactly:

```text
schema_version, recovery_id, source_checkpoint, po_decisions,
event_dispositions, totals, external_actions_executed
```

Use schema version 1, recovery ID `EDI-RCV-20260819-01`, and `false` for
external actions. Each PO decision has exactly:

```text
po_id, supplier_id, disposition, final_state, ordered_amount_cents,
invoice_amount_cents, matched_amount_cents, held_amount_cents, ack_revision,
next_local_action, line_matches, evidence_refs
```

Each line match has exactly:

```text
line_id, ordered_qty, acknowledged_qty, shipped_qty, invoiced_qty,
ordered_unit_price_cents, acknowledged_unit_price_cents,
invoiced_unit_price_cents, match_status
```

Each event disposition has exactly:

```text
delivery_id, message_type, transaction_control, po_id, revision, disposition
```

Order line matches by line ID. Treat evidence references as sets and use stable
local `file#record` locators. Totals contain exactly
`active_ordered_amount_cents`, `ready_payable_amount_cents`,
`held_invoice_amount_cents`, and `preserved_posted_amount_cents`. Use published
vocabulary verbatim.

Run the guarded workflow; do not hand-edit SQLite or closure artifacts:

```bash
python3 poedictl.py preview edi_recovery_plan.json
python3 poedictl.py apply edi_recovery_plan.json
python3 poedictl.py verify edi_recovery_plan.json
python3 poedictl.py stage edi_recovery_plan.json
python3 poedictl.py replay edi_recovery_plan.json
```

Apply restores the interrupted before-image before committing one local
projection. Stage creates only a payable batch, hold queue, manifest, and
receipt. Recovery ID + source checkpoint + normalized plan define replay
identity; row/set ordering and JSON formatting are equivalent, while conflicting
content must fail before mutation.

Write `procurement_handoff.md` explaining message authority, stale/duplicate/
collision handling, matches and distinct holds, journal restoration, posted
boundary, hashes, and semantic replay. State that no EDI was sent, invoice
posted or paid, supplier contacted, or external action executed. Keep the
controller, policy, manifest, EDI source, and protected database fields
unchanged; do not use the network.
