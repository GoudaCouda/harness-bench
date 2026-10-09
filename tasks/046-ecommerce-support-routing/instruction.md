# Triage a mixed e-commerce support queue

You are the customer support queue lead. A backlog contains routine fulfillment requests, missing verification, VIP threads, fraud holds, and contradictory carrier evidence.

Your job is to route every ticket conservatively and prepare customer-safe replies plus a focused human-escalation handoff.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs include:
- `order_history.csv`
- `policy.md`
- `tickets.json`

## Deliverables

- `escalation_notes.csv`: Use columns ticket_id, reason, policy_basis, human_team and include only human escalations.
- `reply_templates.md`: Create one clearly labelled ticket section whose reply key matches the routing record.
- `routing_decisions.json`: Write one object per ticket with ticket_id, action, policy_basis, order_id, priority, and customer_reply_key.

These files are a handoff to another practitioner, so choose clear prose and stable local identifiers. The named business fields are required where stated, but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Use order history and policy together. Missing verification requires an information request; VIP status raises its priority but never bypasses evidence or fraud controls.
2. Fraud holds, delivered-status disputes, and carrier or system evidence that conflicts with warehouse facts require human escalation.
3. Choose action from refund, reship, escalate_human, or information_request and cite the governing policy clause.
4. Replies must acknowledge the ticket-specific issue, state the next step, and avoid promising an outcome that the chosen route does not authorize.

Keep all source evidence byte-for-byte unchanged except for a path explicitly named as an in-place deliverable. Work offline. Do not execute or claim an external, production, payment, filing, deletion, message-send, booking, or account action. Before finishing, re-open the final CSV/JSON files and reconcile their keys and totals across the handoff.
