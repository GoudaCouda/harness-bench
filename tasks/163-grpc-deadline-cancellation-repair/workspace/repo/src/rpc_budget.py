def plan_rpc_budget(calls, policy):
    # Broken: each failure receives a fresh per-try timeout and cancellation is ignored.
    decisions = []
    for call in calls:
        decisions.append(
            {
                "call_id": call["call_id"],
                "status": "ready",
                "action": "retry_call",
                "reason": "retryable_failure",
                "delay_ms": 0,
                "timeout_ms": policy["per_try_timeout_ms"],
                "cancel_child_rpcs": 0,
            }
        )
    return {
        "decisions": decisions,
        "summary": {
            "call_count": len(calls),
            "settled": 0,
            "ready": len(calls),
            "blocked": 0,
            "stopped": 0,
            "retry_count": len(calls),
            "cancelled_child_rpcs": 0,
        },
    }
