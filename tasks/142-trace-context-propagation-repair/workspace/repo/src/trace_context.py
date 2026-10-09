def _single(values):
    return values[0] if isinstance(values, list) and len(values) == 1 else None


def _valid_traceparent(value):
    if not isinstance(value, str):
        return False
    parts = value.split("-")
    return len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16 and len(parts[3]) == 2 and all(all(char in "0123456789abcdef" for char in part) for part in parts)


def _valid_tracestate(value):
    if value is None:
        return None
    members = [item.strip() for item in value.split(",")]
    if any(item.count("=") != 1 or not item.split("=", 1)[0] for item in members):
        return None
    return ",".join(members)


def _filter_baggage(value, sensitive):
    if value is None:
        return None
    kept = []
    for member in value.split(","):
        if "=" not in member:
            return None
        key, raw = member.strip().split("=", 1)
        if key not in sensitive:
            kept.append(key + "=" + raw)
    return ",".join(kept) or None


def propagate_contexts(requests, policy):
    """Prepare outbound W3C trace headers for a captured request batch.

    This starter preserves ordinary incoming traces and strips sensitive
    baggage at an external boundary.  It still mishandles vendor ordering,
    sampled flags, restart metrics, and several malformed-header cases.
    """
    decisions = []
    metrics = {"forwarded": 0, "restarted": 0, "new": 0, "invalid_traceparent": 0, "invalid_tracestate": 0, "invalid_baggage": 0, "filtered_baggage": 0}
    for request in requests:
        incoming = _single(request["traceparent"])
        parent_ok = _valid_traceparent(incoming)
        if parent_ok:
            disposition = "forwarded"
            outgoing_parent = incoming
        else:
            disposition = "new"
            flags = "01" if request["sampled"] else "00"
            outgoing_parent = "00-" + request["fallback_trace_id"] + "-" + request["local_parent_id"] + "-" + flags
            metrics["invalid_traceparent"] += bool(request["traceparent"])
        state_raw = _single(request["tracestate"])
        state = _valid_tracestate(state_raw)
        if state_raw is not None and state is None:
            metrics["invalid_tracestate"] += 1
        baggage_raw = _single(request["baggage"])
        baggage = _filter_baggage(baggage_raw, set(policy["sensitive_baggage_keys"]) if request["boundary"] == "external" else set())
        metrics[disposition] += 1
        decisions.append({"request_id": request["request_id"], "disposition": disposition, "traceparent": outgoing_parent, "tracestate": state, "baggage": baggage})
    return {"decisions": decisions, "metrics": metrics}
