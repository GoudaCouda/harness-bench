# Drain an RPC failure stream through a probe-budget circuit breaker

You are the on-call admission engineer at Northharbor RPC. A partner failure
stream is parked in front of the per-service circuit breaker. Policy publishes
a consecutive-failure threshold, a cooldown, and a one-probe half-open budget.
An incident note claims that a success during cooldown should close the
breaker. Those sources do not agree.

Operations needs a decision an auditor can read, and a short-circuited call
must not be forwarded.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs
include:
- `policy.md`
- `evidence/incident_brief.md`
- `staging/rpc_events.json`
- `breakerctl.py`

## Deliverables

- `state/breaker_log.json`: One decision per event, the decision counts, and
  the event ids this breaker actually forwarded.
- `state/breaker_receipt.json`: The same counts, the forwarded ids, and the
  terminal `breaker_mode` per service.
- `state/verification.json`: Record the controller command you ran, the result
  of each attempt, and whether re-running it left the state unchanged.
- `circuit_breaker_handoff.md`: Explain the cooldown-versus-note conflict, why
  each class of event resolved the way it did, why the first success after the
  trip was not a close, the verification you performed, and the authorization
  boundary.

These files are a handoff to another practitioner, so choose clear prose and
stable local identifiers. The named business fields are required where stated,
but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read `policy.md` before recording decisions; it is authoritative over
   `evidence/incident_brief.md` where they disagree.
2. Apply the published mode machine in order. An `open` breaker stays open
   until cooldown expires, even when the next event is a success.
3. `half_open` admits at most one probe. A failed probe reopens; a successful
   probe closes.
4. Use `python3 breakerctl.py validate` for feedback, and run it more than once
   so your verification record reflects repeat behavior rather than a single
   pass.
5. Create only the four declared handoff artifacts. Do not modify policy,
   evidence, the stream, or the controller.

Keep all source evidence byte-for-byte unchanged except for a path explicitly
named as an in-place deliverable. Work offline. Do not execute or claim an
external, production, payment, filing, deletion, message-send, booking, or
account action. Before finishing, re-open the final JSON files and reconcile
their keys and totals across the handoff.
