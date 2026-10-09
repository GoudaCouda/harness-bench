def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _lower_token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_" for char in value)
    )


def _upper_token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.upper()
        and value.isascii()
        and all(char.isalpha() or char == "_" for char in value)
    )


def _method(value):
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.count("/") != 2
        or not value.isascii()
    ):
        return False
    return all(
        part and all(char.isalnum() or char in "_." for char in part)
        for part in value.split("/")[1:]
    )


def plan_rpc_budget(calls, policy):
    policy_keys = (
        "max_attempts",
        "per_try_timeout_ms",
        "reserve_ms",
        "base_backoff_ms",
        "max_backoff_ms",
        "retryable_statuses",
    )
    if not _exact(policy, policy_keys):
        raise ValueError("invalid policy")
    integer_policy = (
        "max_attempts",
        "per_try_timeout_ms",
        "reserve_ms",
        "base_backoff_ms",
        "max_backoff_ms",
    )
    if (
        any(
            not isinstance(policy[key], int) or isinstance(policy[key], bool)
            for key in integer_policy
        )
        or policy["max_attempts"] <= 0
        or policy["per_try_timeout_ms"] <= 0
        or policy["reserve_ms"] < 0
        or policy["base_backoff_ms"] < 0
        or policy["max_backoff_ms"] < policy["base_backoff_ms"]
    ):
        raise ValueError("invalid policy limits")
    retryable = policy["retryable_statuses"]
    if (
        not isinstance(retryable, list)
        or retryable != sorted(retryable)
        or len(set(retryable)) != len(retryable)
        or not all(_upper_token(value) for value in retryable)
    ):
        raise ValueError("invalid retryable statuses")
    if not isinstance(calls, list):
        raise ValueError("invalid calls")
    call_keys = (
        "call_id",
        "method",
        "status",
        "attempt",
        "incoming_timeout_ms",
        "elapsed_ms",
        "response_headers_received",
        "caller_cancelled",
        "operation_scope",
        "idempotent",
        "active_child_rpcs",
    )
    allowed_statuses = (
        "NOT_STARTED",
        "OK",
        "CANCELLED",
        "DEADLINE_EXCEEDED",
        "UNAVAILABLE",
        "RESOURCE_EXHAUSTED",
        "ABORTED",
        "FAILED_PRECONDITION",
        "INTERNAL",
    )
    decisions = []
    identifiers = []
    counts = {"settled": 0, "ready": 0, "blocked": 0, "stopped": 0}
    retries = 0
    cancelled_children = 0
    for call in calls:
        if (
            not _exact(call, call_keys)
            or not _lower_token(call["call_id"])
            or not _method(call["method"])
            or call["status"] not in allowed_statuses
        ):
            raise ValueError("invalid call identity")
        numbers = ("attempt", "incoming_timeout_ms", "elapsed_ms", "active_child_rpcs")
        if (
            any(
                not isinstance(call[key], int)
                or isinstance(call[key], bool)
                or call[key] < 0
                for key in numbers
            )
            or call["incoming_timeout_ms"] <= 0
        ):
            raise ValueError("invalid call timing")
        if (
            (call["status"] == "NOT_STARTED") != (call["attempt"] == 0)
            or not isinstance(call["response_headers_received"], bool)
            or not isinstance(call["caller_cancelled"], bool)
            or not isinstance(call["idempotent"], bool)
            or call["operation_scope"] not in ("single_call", "parent_operation")
        ):
            raise ValueError("invalid call state")
        identifiers.append(call["call_id"])
        delay = 0
        timeout = 0
        cancel_count = 0
        remaining = call["incoming_timeout_ms"] - call["elapsed_ms"]
        if call["status"] == "OK":
            status, action, reason = "settled", "keep_result", "rpc_ok"
        elif call["caller_cancelled"]:
            status, action, reason = "stopped", "cancel_children", "caller_cancelled"
            cancel_count = call["active_child_rpcs"]
        elif remaining <= policy["reserve_ms"]:
            status, action, reason = "blocked", "do_not_retry", "deadline_budget"
        elif call["status"] == "NOT_STARTED":
            status, action, reason = "ready", "start_call", "not_started"
            timeout = min(
                policy["per_try_timeout_ms"], remaining - policy["reserve_ms"]
            )
        elif call["response_headers_received"]:
            status, action, reason = "blocked", "do_not_retry", "committed_rpc"
        elif (
            call["status"] == "ABORTED"
            and call["operation_scope"] == "parent_operation"
        ):
            status, action, reason = (
                "blocked",
                "restart_parent",
                "restart_parent_operation",
            )
        elif call["status"] not in retryable:
            status, action, reason = "blocked", "do_not_retry", "non_retryable_status"
        elif not call["idempotent"]:
            status, action, reason = "blocked", "do_not_retry", "non_idempotent"
        elif call["attempt"] >= policy["max_attempts"]:
            status, action, reason = "blocked", "do_not_retry", "retry_budget"
        else:
            delay = min(
                policy["max_backoff_ms"],
                policy["base_backoff_ms"] * 2 ** (call["attempt"] - 1),
            )
            available = remaining - policy["reserve_ms"] - delay
            if available <= 0:
                status, action, reason = "blocked", "do_not_retry", "deadline_budget"
                delay = 0
            else:
                status, action, reason = "ready", "retry_call", "retryable_failure"
                timeout = min(policy["per_try_timeout_ms"], available)
                retries += 1
        decisions.append(
            {
                "call_id": call["call_id"],
                "status": status,
                "action": action,
                "reason": reason,
                "delay_ms": delay,
                "timeout_ms": timeout,
                "cancel_child_rpcs": cancel_count,
            }
        )
        counts[status] += 1
        cancelled_children += cancel_count
    if identifiers != sorted(identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("calls must be sorted and unique")
    return {
        "decisions": decisions,
        "summary": {
            "call_count": len(calls),
            "settled": counts["settled"],
            "ready": counts["ready"],
            "blocked": counts["blocked"],
            "stopped": counts["stopped"],
            "retry_count": retries,
            "cancelled_child_rpcs": cancelled_children,
        },
    }
