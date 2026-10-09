def plan_http_retry(request, attempt_number, observation):
    """Broken policy: retry every transport error and server error."""
    status = observation.get("status")
    should_retry = observation["outcome"] != "http" or status >= 500
    return {
        "decision": "retry" if should_retry else "stop",
        "next_attempt": attempt_number + 1 if should_retry else None,
        "delay_ms": request["base_delay_ms"] if should_retry else None,
        "safety_basis": None,
        "reason": "retry_safe" if should_retry else "non_retryable_status",
    }
