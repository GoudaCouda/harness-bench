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


def _command(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.upper()
        and value.isascii()
        and all(char.isalnum() or char == "_" for char in value)
    )


def _integer(value, minimum):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def plan_cluster_retries(requests, slots, policy):
    policy_keys = (
        "max_attempts",
        "base_backoff_ms",
        "max_backoff_ms",
        "reserve_ms",
    )
    if (
        not _exact(policy, policy_keys)
        or not _integer(policy["max_attempts"], 1)
        or not _integer(policy["base_backoff_ms"], 1)
        or not _integer(policy["max_backoff_ms"], 1)
        or not _integer(policy["reserve_ms"], 0)
        or policy["base_backoff_ms"] > policy["max_backoff_ms"]
    ):
        raise ValueError("invalid policy")
    if not isinstance(slots, list) or not isinstance(requests, list):
        raise ValueError("invalid inputs")
    slot_map = {}
    slot_order = []
    for item in slots:
        if (
            not _exact(item, ("slot", "node"))
            or not _integer(item["slot"], 0)
            or item["slot"] > 16383
            or not _token(item["node"])
        ):
            raise ValueError("invalid slot")
        slot_order.append(item["slot"])
        slot_map[item["slot"]] = item["node"]
    if slot_order != sorted(slot_order) or len(set(slot_order)) != len(slot_order):
        raise ValueError("slots must be sorted and unique")
    request_keys = (
        "request_id",
        "command",
        "key_slots",
        "target_node",
        "outcome",
        "redirect_slot",
        "redirect_node",
        "attempt",
        "idempotent",
        "result_received",
        "deadline_remaining_ms",
    )
    outcomes = (
        "ASK",
        "CLUSTERDOWN",
        "MOVED",
        "OK",
        "READONLY",
        "TIMEOUT",
        "TRYAGAIN",
        "UNASSIGNED",
    )
    decisions = []
    request_ids = []
    counts = {
        "complete": 0,
        "retry_redirect": 0,
        "retry_backoff": 0,
        "refresh_and_retry": 0,
        "block": 0,
    }
    topology_updates = 0
    for request in requests:
        keys = request.get("key_slots") if isinstance(request, dict) else None
        if (
            not _exact(request, request_keys)
            or not _token(request["request_id"])
            or not _command(request["command"])
            or not isinstance(keys, list)
            or not keys
            or keys != sorted(keys)
            or len(set(keys)) != len(keys)
            or not all(_integer(slot, 0) and slot <= 16383 for slot in keys)
            or not _token(request["target_node"])
            or request["outcome"] not in outcomes
            or not _integer(request["attempt"], 1)
            or not isinstance(request["idempotent"], bool)
            or not isinstance(request["result_received"], bool)
            or not _integer(request["deadline_remaining_ms"], 0)
        ):
            raise ValueError("invalid request")
        redirect = request["outcome"] in ("MOVED", "ASK")
        if redirect:
            if (
                not _integer(request["redirect_slot"], 0)
                or request["redirect_slot"] > 16383
                or not _token(request["redirect_node"])
            ):
                raise ValueError("invalid redirect")
        elif request["redirect_slot"] is not None or request["redirect_node"] is not None:
            raise ValueError("unexpected redirect")
        if (request["outcome"] == "OK") != request["result_received"]:
            raise ValueError("invalid result evidence")
        request_ids.append(request["request_id"])
        action = None
        reason = None
        target = None
        asking = False
        update = None
        next_attempt = None
        backoff = 0
        if len(keys) > 1:
            action, reason = "block", "cross_slot"
        elif request["outcome"] == "OK":
            action, reason = "complete", "response"
        elif redirect and request["redirect_slot"] != keys[0]:
            action, reason = "block", "redirect_slot_mismatch"
        else:
            if request["outcome"] == "MOVED":
                update = {
                    "slot": request["redirect_slot"],
                    "node": request["redirect_node"],
                }
                slot_map[update["slot"]] = update["node"]
                topology_updates += 1
            if request["attempt"] >= policy["max_attempts"]:
                action, reason = "block", "attempt_budget"
            elif redirect:
                if request["deadline_remaining_ms"] <= policy["reserve_ms"]:
                    action, reason = "block", "deadline_budget"
                else:
                    action = "retry_redirect"
                    reason = "moved" if request["outcome"] == "MOVED" else "ask"
                    target = request["redirect_node"]
                    asking = request["outcome"] == "ASK"
                    next_attempt = request["attempt"] + 1
            elif request["outcome"] in ("READONLY", "UNASSIGNED"):
                if request["deadline_remaining_ms"] <= policy["reserve_ms"]:
                    action, reason = "block", "deadline_budget"
                else:
                    action, reason = "refresh_and_retry", request["outcome"].lower()
                    next_attempt = request["attempt"] + 1
            else:
                if request["outcome"] in ("CLUSTERDOWN", "TIMEOUT") and not request[
                    "idempotent"
                ]:
                    action, reason = "block", "ambiguous_non_idempotent"
                else:
                    backoff = min(
                        policy["base_backoff_ms"] * 2 ** (request["attempt"] - 1),
                        policy["max_backoff_ms"],
                    )
                    if request["deadline_remaining_ms"] <= backoff + policy["reserve_ms"]:
                        action, reason = "block", "deadline_budget"
                        backoff = 0
                    else:
                        action = "retry_backoff"
                        reason = request["outcome"].lower()
                        target = request["target_node"]
                        next_attempt = request["attempt"] + 1
        counts[action] += 1
        decisions.append(
            {
                "request_id": request["request_id"],
                "action": action,
                "reason": reason,
                "target_node": target,
                "send_asking": asking,
                "update_slot": update,
                "next_attempt": next_attempt,
                "backoff_ms": backoff,
            }
        )
    if request_ids != sorted(request_ids) or len(set(request_ids)) != len(request_ids):
        raise ValueError("requests must be sorted and unique")
    summary = {"request_count": len(requests)}
    summary.update(counts)
    summary["topology_updates"] = topology_updates
    return {
        "decisions": decisions,
        "slots": [
            {"slot": slot, "node": node} for slot, node in sorted(slot_map.items())
        ],
        "summary": summary,
    }
