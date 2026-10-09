def plan_slot_recovery(slots, consumers, observations, policy):
    """Plan operator-reviewed actions from PostgreSQL slot observations.

    The ordinary retained-WAL and active-slot cases are represented, while
    failover sync, invalidation, resnapshot safety, and exact LSN validation
    remain incomplete.
    """
    consumers_by_slot = {row["slot_name"]: row for row in consumers}
    plans = []
    for slot in slots:
        consumer = consumers_by_slot.get(slot["slot_name"])
        retained = observations["primary_wal_lsn"] - slot["restart_lsn"]
        if slot["active"] and retained > policy["max_retained_bytes"]:
            action, reason = "block", "slot_active"
        elif slot["invalidation_reason"] is not None or slot["restart_lsn"] < observations["oldest_available_lsn"]:
            action, reason = "resnapshot", "wal_unavailable"
        elif retained > policy["max_retained_bytes"]:
            action, reason = "advance", "retention_cap"
        elif consumer and consumer["state"] == "stopped":
            action, reason = "resume", "consumer_stopped"
        else:
            action, reason = "monitor", "healthy"
        plans.append({"slot_name": slot["slot_name"], "consumer_id": consumer["consumer_id"] if consumer else None, "action": action, "reason": reason, "retained_bytes": retained})
    return {"plans": plans, "summary": {"slot_count": len(slots), "blocked": sum(row["action"] == "block" for row in plans), "resnapshot": sum(row["action"] == "resnapshot" for row in plans)}}
