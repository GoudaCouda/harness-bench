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


def _sorted_upper(values):
    return (
        isinstance(values, list)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and all(_upper_token(value) for value in values)
    )


def plan_goaway_retries(requests, goaway, policy):
    if (
        not _exact(goaway, ("connection_id", "last_stream_id", "error_code"))
        or not _lower_token(goaway["connection_id"])
        or not isinstance(goaway["last_stream_id"], int)
        or isinstance(goaway["last_stream_id"], bool)
        or not 0 <= goaway["last_stream_id"] <= 2147483647
        or not _upper_token(goaway["error_code"])
    ):
        raise ValueError("invalid goaway")
    policy_keys = (
        "max_retries",
        "idempotent_methods",
        "require_idempotency_key_for_unsafe",
        "retryable_errors",
    )
    if (
        not _exact(policy, policy_keys)
        or not isinstance(policy["max_retries"], int)
        or isinstance(policy["max_retries"], bool)
        or policy["max_retries"] <= 0
        or not _sorted_upper(policy["idempotent_methods"])
        or not _sorted_upper(policy["retryable_errors"])
        or not isinstance(policy["require_idempotency_key_for_unsafe"], bool)
    ):
        raise ValueError("invalid policy")
    if not isinstance(requests, list):
        raise ValueError("invalid requests")
    request_keys = (
        "request_id",
        "method",
        "stream_id",
        "response_state",
        "reset_code",
        "body_replayable",
        "idempotency_key",
        "attempt",
    )
    decisions = []
    request_ids = []
    stream_ids = []
    counts = {"settled": 0, "retry": 0, "blocked": 0}
    retry_streams = []
    for request in requests:
        if (
            not _exact(request, request_keys)
            or not _lower_token(request["request_id"])
            or not _upper_token(request["method"])
        ):
            raise ValueError("invalid request identity")
        if (
            not isinstance(request["stream_id"], int)
            or isinstance(request["stream_id"], bool)
            or request["stream_id"] <= 0
            or request["stream_id"] > 2147483647
            or request["stream_id"] % 2 != 1
        ):
            raise ValueError("invalid client stream")
        if (
            request["response_state"] not in ("none", "headers", "reset", "complete")
            or not isinstance(request["body_replayable"], bool)
            or not isinstance(request["attempt"], int)
            or isinstance(request["attempt"], bool)
            or request["attempt"] < 0
        ):
            raise ValueError("invalid request state")
        if request["idempotency_key"] is not None and not _lower_token(
            request["idempotency_key"]
        ):
            raise ValueError("invalid idempotency key")
        if (request["response_state"] == "reset") != (
            request["reset_code"] is not None
        ) or (
            request["reset_code"] is not None
            and not _upper_token(request["reset_code"])
        ):
            raise ValueError("invalid reset evidence")
        if (
            request["response_state"] == "complete"
            and request["stream_id"] > goaway["last_stream_id"]
        ):
            raise ValueError("completion contradicts goaway boundary")
        request_ids.append(request["request_id"])
        stream_ids.append(request["stream_id"])
        if request["response_state"] == "complete":
            status, action, reason, target = (
                "settled",
                "keep_response",
                "response_complete",
                "none",
            )
        elif goaway["error_code"] not in policy["retryable_errors"]:
            status, action, reason, target = (
                "blocked",
                "do_not_retry",
                "goaway_error",
                "none",
            )
        elif request["attempt"] >= policy["max_retries"]:
            status, action, reason, target = (
                "blocked",
                "do_not_retry",
                "retry_budget",
                "none",
            )
        elif not request["body_replayable"]:
            status, action, reason, target = (
                "blocked",
                "do_not_retry",
                "body_not_replayable",
                "none",
            )
        elif request["stream_id"] > goaway["last_stream_id"]:
            status, action, reason, target = (
                "retry",
                "retry_fresh_connection",
                "goaway_unprocessed",
                "fresh_connection",
            )
        elif request["reset_code"] == "REFUSED_STREAM":
            status, action, reason, target = (
                "retry",
                "retry_fresh_connection",
                "refused_stream",
                "fresh_connection",
            )
        elif request["method"] in policy["idempotent_methods"]:
            status, action, reason, target = (
                "retry",
                "retry_fresh_connection",
                "idempotent_ambiguous",
                "fresh_connection",
            )
        elif request["idempotency_key"] is not None:
            status, action, reason, target = (
                "retry",
                "retry_with_idempotency_key",
                "keyed_ambiguous",
                "fresh_connection",
            )
        elif not policy["require_idempotency_key_for_unsafe"]:
            status, action, reason, target = (
                "retry",
                "retry_fresh_connection",
                "unsafe_policy_allowed",
                "fresh_connection",
            )
        else:
            status, action, reason, target = (
                "blocked",
                "do_not_retry",
                "ambiguous_non_idempotent",
                "none",
            )
        decisions.append(
            {
                "request_id": request["request_id"],
                "status": status,
                "action": action,
                "reason": reason,
                "target": target,
            }
        )
        counts[status] += 1
        if status == "retry":
            retry_streams.append(request["stream_id"])
    if (
        request_ids != sorted(request_ids)
        or len(set(request_ids)) != len(request_ids)
        or len(set(stream_ids)) != len(stream_ids)
    ):
        raise ValueError("request ledger must be sorted and unique")
    return {
        "decisions": decisions,
        "summary": {
            "request_count": len(requests),
            "settled": counts["settled"],
            "retry": counts["retry"],
            "blocked": counts["blocked"],
            "highest_retry_stream": max(retry_streams) if retry_streams else None,
        },
    }
