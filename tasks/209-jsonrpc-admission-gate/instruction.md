# Admit a JSON-RPC partner batch through a conflicting policy overlay

You are the on-call admission engineer at Harborline Payments. A partner batch
is parked in front of the JSON-RPC gate. The method catalog still lists
payouts, a freeze overlay still names `payouts.create`, and an incident note
claims that freeze was lifted for one tenant. Those three sources do not agree.

Compliance needs a decision an auditor can read, and a frozen method must not
be forwarded.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs
include:
- `policy.md`
- `evidence/incident_brief.md`
- `catalogs/method_catalog.json`
- `catalogs/tenant_capabilities.json`
- `overlays/freeze.json`
- `staging/inbound_batch.json`
- `gatectl.py`

## Deliverables

- `state/admission_log.json`: One decision per batch item, the decision counts,
  and the methods this gate actually forwarded.
- `state/gate_receipt.json`: The JSON-RPC response batch for requests (not
  notifications), the response count, and the same decision counts.
- `state/verification.json`: Record the controller command you ran, the result
  of each attempt, and whether re-running it left the state unchanged.
- `jsonrpc_admission_handoff.md`: Explain the conflicting sources, why each
  class of item resolved the way it did, why the freeze still held, the
  verification you performed, and the authorization boundary.

These files are a handoff to another practitioner, so choose clear prose and
stable local identifiers. The named business fields are required where stated,
but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read `policy.md` before recording decisions; it is authoritative over the
   catalogs, the overlay, and `evidence/incident_brief.md` where they disagree.
2. Apply the published decision precedence in order. A frozen method stays
   frozen even when the tenant also lacks the capability.
3. Notifications (items with no `id` member) never produce a response.
4. Use `python3 gatectl.py validate` for feedback, and run it more than once so
   your verification record reflects repeat behavior rather than a single pass.
5. Create only the four declared handoff artifacts. Do not modify catalogs,
   overlays, policy, evidence, the batch, or the controller.

Keep all source evidence byte-for-byte unchanged except for a path explicitly
named as an in-place deliverable. Work offline. Do not execute or claim an
external, production, payment, filing, deletion, message-send, booking, or
account action. Before finishing, re-open the final JSON files and reconcile
their keys and totals across the handoff.
