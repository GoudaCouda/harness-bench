# Harborwatch Procurement policy (authoritative)

This document is authoritative. Where an incident note and this policy disagree,
this policy wins.

## 1. Gate clock

The drain is evaluated against a single frozen clock, not wall time:

- `gate_clock_epoch` = `1775777600`

`python3 poctl.py clock` prints it.

## 2. Envelope

Each item needs a non-empty `po_id` and a non-empty `vendor_id`.
An `po_id` may be used only once in the stream. The first occurrence is
eligible for later rules; a later item that repeats that `po_id` is
`malformed`.

## 3. Decision rule

Allowed decisions are `admitted`, `held`, and `malformed`.

Equal ack quantity is admitted. Partial ack is held as backorder. Over-ack is malformed, not a raise of the ordered quantity.

## 4. Authorization boundary

This drain is an offline local decision. Contacting a processor, releasing
funds, notifying a partner, filing a ticket, or deleting evidence is outside
the authorization of this task.
