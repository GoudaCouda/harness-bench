def plan_cluster_retries(requests, slots, policy):
    # Broken: every failure is made permanent and ASK poisons the slot cache.
    slot_map = {item["slot"]: item["node"] for item in slots}
    decisions = []
    for request in requests:
        update = None
        if request["redirect_slot"] is not None:
            update = {
                "slot": request["redirect_slot"],
                "node": request["redirect_node"],
            }
            slot_map[update["slot"]] = update["node"]
        decisions.append(
            {
                "request_id": request["request_id"],
                "action": "retry_redirect",
                "reason": "moved",
                "target_node": request["redirect_node"],
                "send_asking": False,
                "update_slot": update,
                "next_attempt": request["attempt"] + 1,
                "backoff_ms": 0,
            }
        )
    return {
        "decisions": decisions,
        "slots": [
            {"slot": slot, "node": node} for slot, node in sorted(slot_map.items())
        ],
        "summary": {
            "request_count": len(requests),
            "complete": 0,
            "retry_redirect": len(requests),
            "retry_backoff": 0,
            "refresh_and_retry": 0,
            "block": 0,
            "topology_updates": len(
                [item for item in decisions if item["update_slot"] is not None]
            ),
        },
    }
