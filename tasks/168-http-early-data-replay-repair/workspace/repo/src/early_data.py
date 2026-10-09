def plan_early_data(requests, session, policy):
    # Broken: a resumable session is treated as application replay permission.
    decisions = []
    for request in requests:
        decisions.append(
            {
                "request_id": request["request_id"],
                "action": "send_0rtt",
                "reason": "eligible",
                "propagate_early_data": request["via_intermediary"],
                "next_attempt": None,
                "reset_application_state": False,
            }
        )
    return {
        "decisions": decisions,
        "summary": {
            "request_count": len(requests),
            "send_0rtt": len(requests),
            "send_after_handshake": 0,
            "retry_after_handshake": 0,
            "await_handshake": 0,
            "complete": 0,
            "reject_425": 0,
            "block": 0,
        },
    }
