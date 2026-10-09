def plan_goaway_retries(requests, goaway, policy):
    # Broken: every unfinished stream is retried without protocol or side-effect checks.
    decisions = []
    for request in requests:
        status = "settled" if request["response_state"] == "complete" else "retry"
        decisions.append(
            {
                "request_id": request["request_id"],
                "status": status,
                "action": "keep_response"
                if status == "settled"
                else "retry_fresh_connection",
                "reason": "response_complete"
                if status == "settled"
                else "goaway_unprocessed",
                "target": "none" if status == "settled" else "fresh_connection",
            }
        )
    return {
        "decisions": decisions,
        "summary": {
            "request_count": len(requests),
            "settled": 0,
            "retry": len(requests),
            "blocked": 0,
            "highest_retry_stream": None,
        },
    }
