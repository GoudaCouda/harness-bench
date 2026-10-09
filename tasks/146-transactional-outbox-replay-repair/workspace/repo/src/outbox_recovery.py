def _action(kind, event):
    return {"type": kind, "event_id": event["event_id"], "attempt": event["attempts"], "idempotency_key": event["event_id"], "payload_hash": event["payload_hash"]}


def recover_outbox(events, receipts, policy):
    """Reconcile a captured outbox snapshot without contacting the broker.

    The common acknowledgement and unknown-delivery paths are implemented.  A
    known recovery bug remains around conflicting receipts, exhausted retries,
    and validation, so this is plausible incident code rather than a solution.
    """
    state = [dict(event) for event in events]
    latest = {(receipt["event_id"], receipt["attempt"]): receipt for receipt in receipts}
    actions = []
    for event in state:
        acknowledged = any(receipt["event_id"] == event["event_id"] and receipt["outcome"] == "acked" for receipt in receipts)
        if acknowledged:
            event.update(status="sent", lease_owner=None, lease_until=None, last_error=None)
            continue
        receipt = latest.get((event["event_id"], event["attempts"]))
        if receipt and receipt["outcome"] == "unknown":
            continue
        if event["status"] == "leased" and event["lease_until"] <= policy["now"]:
            event.update(status="pending", lease_owner=None, lease_until=None)

    by_aggregate = {}
    for event in state:
        by_aggregate.setdefault(event["aggregate_id"], []).append(event)
    for aggregate_id in sorted(by_aggregate):
        pending = [event for event in sorted(by_aggregate[aggregate_id], key=lambda row: row["sequence"]) if event["status"] not in ("sent", "dead")]
        if not pending:
            continue
        head = pending[0]
        receipt = latest.get((head["event_id"], head["attempts"]))
        if receipt and receipt["outcome"] == "unknown":
            actions.append(_action("probe", head))
        elif head["status"] == "pending":
            head["attempts"] += 1
            head.update(status="leased", lease_owner=policy["worker"], lease_until=policy["now"] + policy["lease_seconds"], last_error=None)
            actions.append(_action("publish", head))
    return {"state": state, "actions": actions}
