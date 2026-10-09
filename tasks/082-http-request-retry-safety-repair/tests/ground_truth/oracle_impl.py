import re

TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
SHA256 = re.compile(r"[0-9a-f]{64}")
METHODS = {"GET", "HEAD", "PUT", "DELETE", "OPTIONS", "POST", "PATCH"}
IDEMPOTENT = {"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}
RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _validate_request(request):
    keys = {
        "method",
        "operation_id",
        "body_sha256",
        "idempotency_key",
        "key_replay_safe",
        "max_attempts",
        "base_delay_ms",
        "max_delay_ms",
    }
    if not isinstance(request, dict) or set(request) != keys:
        raise ValueError("invalid request shape")
    key = request["idempotency_key"]
    if (
        request["method"] not in METHODS
        or not isinstance(request["operation_id"], str)
        or not TOKEN.fullmatch(request["operation_id"])
        or not isinstance(request["body_sha256"], str)
        or not SHA256.fullmatch(request["body_sha256"])
        or (key is not None and (not isinstance(key, str) or not TOKEN.fullmatch(key)))
        or type(request["key_replay_safe"]) is not bool
        or (request["key_replay_safe"] and key is None)
    ):
        raise ValueError("invalid request identity")
    for name in ("max_attempts", "base_delay_ms", "max_delay_ms"):
        if type(request[name]) is not int or request[name] <= 0:
            raise ValueError("invalid retry policy")
    if (
        request["max_attempts"] > 10
        or request["base_delay_ms"] > request["max_delay_ms"]
    ):
        raise ValueError("invalid retry bounds")


def _validate_observation(observation):
    keys = {"outcome", "status", "retry_after_ms", "application_state", "bytes_sent"}
    if not isinstance(observation, dict) or set(observation) != keys:
        raise ValueError("invalid observation shape")
    outcome = observation["outcome"]
    status = observation["status"]
    retry_after = observation["retry_after_ms"]
    application = observation["application_state"]
    sent = observation["bytes_sent"]
    if type(sent) is not int or sent < 0:
        raise ValueError("invalid byte evidence")
    if outcome == "http":
        if (
            type(status) is not int
            or status < 100
            or status > 599
            or (
                retry_after is not None
                and (
                    type(retry_after) is not int
                    or retry_after < 0
                    or retry_after > 86400000
                )
            )
            or application not in ("not_applied", "unknown", "applied")
            or (200 <= status <= 299 and application != "applied")
        ):
            raise ValueError("invalid HTTP observation")
    elif outcome in ("connect_failure", "write_failure", "response_lost"):
        if status is not None or retry_after is not None or application is not None:
            raise ValueError("transport failure has response fields")
        if outcome == "connect_failure" and sent != 0:
            raise ValueError("connect failure sent bytes")
        if outcome == "response_lost" and sent == 0:
            raise ValueError("lost response requires sent bytes")
    else:
        raise ValueError("invalid outcome")


def _result(decision, next_attempt, delay_ms, safety_basis, reason):
    return {
        "decision": decision,
        "next_attempt": next_attempt,
        "delay_ms": delay_ms,
        "safety_basis": safety_basis,
        "reason": reason,
    }


def _unknown_basis(request):
    if request["method"] in IDEMPOTENT:
        return "method_idempotent"
    if request["key_replay_safe"]:
        return "idempotency_key"
    return None


def plan_http_retry(request, attempt_number, observation):
    _validate_request(request)
    _validate_observation(observation)
    if (
        type(attempt_number) is not int
        or attempt_number < 1
        or attempt_number > request["max_attempts"]
    ):
        raise ValueError("invalid attempt number")

    outcome = observation["outcome"]
    if outcome == "http":
        status = observation["status"]
        if 200 <= status <= 299:
            return _result("success", None, None, None, "http_success")
        if status not in RETRY_STATUSES:
            return _result("stop", None, None, None, "non_retryable_status")
        if observation["application_state"] == "applied":
            return _result("stop", None, None, None, "operation_applied")
        if observation["application_state"] == "not_applied":
            basis = "not_applied"
        else:
            basis = _unknown_basis(request)
    elif outcome == "connect_failure" or (
        outcome == "write_failure" and observation["bytes_sent"] == 0
    ):
        basis = "not_sent"
    else:
        basis = _unknown_basis(request)

    if basis is None:
        return _result("probe", None, None, None, "outcome_unknown")
    if attempt_number >= request["max_attempts"]:
        return _result("stop", None, None, basis, "attempts_exhausted")

    delay = request["base_delay_ms"] * (2 ** (attempt_number - 1))
    if delay > request["max_delay_ms"]:
        delay = request["max_delay_ms"]
    retry_after = observation["retry_after_ms"]
    if retry_after is not None and retry_after > request["max_delay_ms"]:
        return _result(
            "defer",
            attempt_number + 1,
            retry_after,
            basis,
            "retry_after_exceeds_budget",
        )
    if retry_after is not None and retry_after > delay:
        delay = retry_after
    return _result("retry", attempt_number + 1, delay, basis, "retry_safe")
