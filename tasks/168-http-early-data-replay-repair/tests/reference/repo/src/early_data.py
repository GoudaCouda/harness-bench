def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_." for char in value)
    )


def _method(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.upper()
        and value.isascii()
        and all(char.isalnum() or char == "-" for char in value)
    )


def plan_early_data(requests, session, policy):
    session_keys = (
        "ticket_age_sec",
        "remembered_alpn",
        "current_alpn",
        "transport_parameters_match",
        "application_settings_match",
        "anti_replay_consistent",
    )
    if (
        not _exact(session, session_keys)
        or not isinstance(session["ticket_age_sec"], int)
        or isinstance(session["ticket_age_sec"], bool)
        or session["ticket_age_sec"] < 0
        or not _token(session["remembered_alpn"])
        or not _token(session["current_alpn"])
        or not all(
            isinstance(session[name], bool)
            for name in (
                "transport_parameters_match",
                "application_settings_match",
                "anti_replay_consistent",
            )
        )
    ):
        raise ValueError("invalid session")
    policy_keys = (
        "max_ticket_age_sec",
        "max_attempts",
        "require_anti_replay_consistency",
        "safe_methods",
    )
    if (
        not _exact(policy, policy_keys)
        or not isinstance(policy["max_ticket_age_sec"], int)
        or isinstance(policy["max_ticket_age_sec"], bool)
        or policy["max_ticket_age_sec"] <= 0
        or not isinstance(policy["max_attempts"], int)
        or isinstance(policy["max_attempts"], bool)
        or policy["max_attempts"] <= 0
        or not isinstance(policy["require_anti_replay_consistency"], bool)
        or not isinstance(policy["safe_methods"], list)
        or not policy["safe_methods"]
        or policy["safe_methods"] != sorted(policy["safe_methods"])
        or len(set(policy["safe_methods"])) != len(policy["safe_methods"])
        or not all(_method(value) for value in policy["safe_methods"])
    ):
        raise ValueError("invalid policy")
    if not isinstance(requests, list):
        raise ValueError("invalid requests")
    request_keys = (
        "request_id",
        "method",
        "app_opt_in",
        "body_replayable",
        "via_intermediary",
        "received_in_early_data",
        "early_data_header",
        "origin_supports_425",
        "explicitly_configured_safe",
        "early_data_state",
        "response_status",
        "attempt",
    )
    states = ("accepted", "not_sent", "pending", "rejected")
    decisions = []
    request_ids = []
    counts = {
        "send_0rtt": 0,
        "send_after_handshake": 0,
        "retry_after_handshake": 0,
        "await_handshake": 0,
        "complete": 0,
        "reject_425": 0,
        "block": 0,
    }
    for request in requests:
        if (
            not _exact(request, request_keys)
            or not _token(request["request_id"])
            or not _method(request["method"])
            or not all(
                isinstance(request[name], bool)
                for name in (
                    "app_opt_in",
                    "body_replayable",
                    "via_intermediary",
                    "received_in_early_data",
                    "origin_supports_425",
                    "explicitly_configured_safe",
                )
            )
            or not isinstance(request["early_data_header"], list)
            or not all(
                isinstance(value, str) and value.isascii()
                for value in request["early_data_header"]
            )
            or request["early_data_state"] not in states
            or not isinstance(request["attempt"], int)
            or isinstance(request["attempt"], bool)
            or request["attempt"] <= 0
        ):
            raise ValueError("invalid request")
        state = request["early_data_state"]
        status = request["response_status"]
        if state == "accepted":
            if (
                not isinstance(status, int)
                or isinstance(status, bool)
                or status < 100
                or status > 599
            ):
                raise ValueError("invalid response state")
        elif status is not None:
            raise ValueError("invalid response state")
        if (
            not request["via_intermediary"]
            and (request["received_in_early_data"] or request["early_data_header"])
        ):
            raise ValueError("invalid direct marker")
        request_ids.append(request["request_id"])
        action = None
        reason = None
        propagate = False
        next_attempt = None
        reset = False
        if state == "accepted" and status != 425:
            action, reason = "complete", "response"
        elif state == "accepted":
            if not request["body_replayable"]:
                action, reason = "block", "body_not_replayable"
            elif request["attempt"] >= policy["max_attempts"]:
                action, reason = "block", "attempt_budget"
            else:
                action, reason = "retry_after_handshake", "too_early"
                next_attempt = request["attempt"] + 1
                reset = True
        elif state == "rejected":
            if not request["body_replayable"]:
                action, reason = "block", "body_not_replayable"
            elif request["attempt"] >= policy["max_attempts"]:
                action, reason = "block", "attempt_budget"
            else:
                action, reason = "retry_after_handshake", "early_data_rejected"
                next_attempt = request["attempt"] + 1
                reset = True
        elif state == "pending":
            action, reason = "await_handshake", "handshake_pending"
        else:
            marker = request["received_in_early_data"] or bool(
                request["early_data_header"]
            )
            if request["via_intermediary"] and not request["origin_supports_425"]:
                if marker:
                    action, reason = "reject_425", "origin_no_425"
                else:
                    action, reason = "send_after_handshake", "origin_no_425"
            elif (
                request["via_intermediary"]
                and not marker
                and not request["explicitly_configured_safe"]
            ):
                action, reason = "send_after_handshake", "intermediary_not_authorized"
            else:
                checks = (
                    (request["method"] not in policy["safe_methods"], "method_not_safe"),
                    (not request["app_opt_in"], "application_not_opted_in"),
                    (not request["body_replayable"], "body_not_replayable"),
                    (
                        session["ticket_age_sec"] > policy["max_ticket_age_sec"],
                        "ticket_expired",
                    ),
                    (
                        session["remembered_alpn"] != session["current_alpn"],
                        "alpn_changed",
                    ),
                    (
                        not session["transport_parameters_match"],
                        "transport_parameters_changed",
                    ),
                    (
                        not session["application_settings_match"],
                        "application_settings_changed",
                    ),
                    (
                        policy["require_anti_replay_consistency"]
                        and not session["anti_replay_consistent"],
                        "anti_replay_inconsistent",
                    ),
                )
                for failed, failure_reason in checks:
                    if failed:
                        action, reason = "send_after_handshake", failure_reason
                        break
                if action is None:
                    action, reason = "send_0rtt", "eligible"
                    propagate = request["via_intermediary"]
        counts[action] += 1
        decisions.append(
            {
                "request_id": request["request_id"],
                "action": action,
                "reason": reason,
                "propagate_early_data": propagate,
                "next_attempt": next_attempt,
                "reset_application_state": reset,
            }
        )
    if request_ids != sorted(request_ids) or len(set(request_ids)) != len(request_ids):
        raise ValueError("requests must be sorted and unique")
    summary = {"request_count": len(requests)}
    summary.update(counts)
    return {"decisions": decisions, "summary": summary}
