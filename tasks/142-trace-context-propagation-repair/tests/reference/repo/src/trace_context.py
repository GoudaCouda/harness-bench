TOKEN_EXTRA = "!#$%&'*+-.^_`|~"


def _fail():
    raise ValueError()


def _token(value):
    return isinstance(value, str) and bool(value) and value == value.lower() and value.isascii() and all(char.isalnum() or char in TOKEN_EXTRA for char in value)


def _hex(value, size, nonzero=True):
    return isinstance(value, str) and len(value) == size and value == value.lower() and all(char in "0123456789abcdef" for char in value) and (not nonzero or any(char != "0" for char in value))


def _traceparent(values):
    if len(values) != 1 or not isinstance(values[0], str):
        return None
    raw = values[0]
    parts = raw.split("-")
    if len(parts) < 4 or not _hex(parts[0], 2, False) or parts[0] == "ff" or not _hex(parts[1], 32) or not _hex(parts[2], 16) or not _hex(parts[3], 2, False):
        return None
    if parts[0] == "00" and len(parts) != 4:
        return None
    if parts[0] != "00" and any(not part or not _hex(part, len(part), False) for part in parts[4:]):
        return None
    return {"raw": raw, "trace_id": parts[1], "flags": int(parts[3], 16)}


def _tracestate(values, maximum):
    if not values:
        return None, True
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        return None, False
    combined = ",".join(values)
    if len(combined) > 512:
        return None, False
    members = combined.split(",")
    if not 1 <= len(members) <= maximum:
        return None, False
    parsed = []
    seen = set()
    for member in members:
        if member.count("=") != 1 or member != member.strip():
            return None, False
        key, value = member.split("=", 1)
        if not _token(key) or key in seen or not value or any(ord(char) < 32 or ord(char) > 126 or char in ",=" for char in value):
            return None, False
        seen.add(key)
        parsed.append((key, value))
    return (combined, parsed), True


def _encoded(value):
    index = 0
    while index < len(value):
        char = value[index]
        if ord(char) < 33 or ord(char) > 126 or char in ",;":
            return False
        if char == "%":
            if index + 2 >= len(value) or any(code not in "0123456789ABCDEF" for code in value[index + 1:index + 3]):
                return False
            index += 3
        else:
            index += 1
    return True


def _baggage(values, maximum):
    if not values:
        return None, True
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        return None, False
    combined = ",".join(values)
    members = combined.split(",")
    if not 1 <= len(members) <= maximum:
        return None, False
    seen = set()
    parsed = []
    for member in members:
        if member != member.strip():
            return None, False
        pieces = member.split(";")
        if "=" not in pieces[0]:
            return None, False
        key, value = pieces[0].split("=", 1)
        if not _token(key) or key in seen or not _encoded(value):
            return None, False
        seen.add(key)
        for prop in pieces[1:]:
            if not prop:
                return None, False
            if "=" in prop:
                prop_key, prop_value = prop.split("=", 1)
                if not _token(prop_key) or not _encoded(prop_value):
                    return None, False
            elif not _token(prop):
                return None, False
        parsed.append((key, member))
    return parsed, True


def _validate(requests, policy):
    if not isinstance(policy, dict) or set(policy) != {"vendor_key", "sensitive_baggage_keys", "max_tracestate_entries", "max_baggage_entries"}:
        _fail()
    if not _token(policy["vendor_key"]):
        _fail()
    sensitive = policy["sensitive_baggage_keys"]
    if not isinstance(sensitive, list) or sensitive != sorted(set(sensitive)) or any(not _token(key) for key in sensitive):
        _fail()
    for name in ("max_tracestate_entries", "max_baggage_entries"):
        value = policy[name]
        limit = 32 if name == "max_tracestate_entries" else 180
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= limit:
            _fail()
    if not isinstance(requests, list):
        _fail()
    keys = {"request_id", "traceparent", "tracestate", "baggage", "participate", "boundary", "local_parent_id", "fallback_trace_id", "vendor_value", "sampled"}
    ids = set()
    for row in requests:
        if not isinstance(row, dict) or set(row) != keys or not isinstance(row["request_id"], str) or not row["request_id"] or row["request_id"] in ids:
            _fail()
        ids.add(row["request_id"])
        if not isinstance(row["traceparent"], list) or not isinstance(row["tracestate"], list) or not isinstance(row["baggage"], list) or any(not isinstance(value, str) for name in ("traceparent", "tracestate", "baggage") for value in row[name]):
            _fail()
        if not isinstance(row["participate"], bool) or not isinstance(row["sampled"], bool) or row["boundary"] not in ("internal", "external"):
            _fail()
        if not _hex(row["local_parent_id"], 16) or not _hex(row["fallback_trace_id"], 32) or not isinstance(row["vendor_value"], str) or not row["vendor_value"] or any(ord(char) < 32 or ord(char) > 126 or char in ",=" for char in row["vendor_value"]):
            _fail()
    return set(sensitive)


def propagate_contexts(requests, policy):
    sensitive = _validate(requests, policy)
    metrics = {"forwarded": 0, "participated": 0, "restarted": 0, "dropped_tracestate": 0, "dropped_baggage": 0, "filtered_baggage_entries": 0}
    decisions = []
    for row in requests:
        incoming = _traceparent(row["traceparent"])
        ts, ts_valid = _tracestate(row["tracestate"], policy["max_tracestate_entries"])
        baggage, baggage_valid = _baggage(row["baggage"], policy["max_baggage_entries"])
        if incoming is None:
            disposition = "restarted"
            trace_id = row["fallback_trace_id"]
            outgoing_parent = "00-" + trace_id + "-" + row["local_parent_id"] + ("-01" if row["sampled"] else "-00")
            outgoing_state = None
        elif not row["participate"]:
            disposition = "forwarded"
            outgoing_parent = incoming["raw"]
            outgoing_state = ts[0] if ts_valid and ts is not None else None
        else:
            disposition = "participated"
            outgoing_parent = "00-" + incoming["trace_id"] + "-" + row["local_parent_id"] + ("-01" if row["sampled"] else "-00")
            if ts_valid:
                remaining = [] if ts is None else [(key, value) for key, value in ts[1] if key != policy["vendor_key"]]
                remaining = remaining[:policy["max_tracestate_entries"] - 1]
                outgoing_state = ",".join([policy["vendor_key"] + "=" + row["vendor_value"]] + [key + "=" + value for key, value in remaining])
            else:
                outgoing_state = policy["vendor_key"] + "=" + row["vendor_value"]
        if row["tracestate"] and (incoming is None or not ts_valid):
            metrics["dropped_tracestate"] += 1
        if not baggage_valid:
            outgoing_baggage = None
            if row["baggage"]:
                metrics["dropped_baggage"] += 1
        else:
            kept = []
            for key, member in baggage or []:
                if row["boundary"] == "external" and key in sensitive:
                    metrics["filtered_baggage_entries"] += 1
                else:
                    kept.append(member)
            outgoing_baggage = ",".join(kept) or None
        metrics[disposition] += 1
        decisions.append({"request_id": row["request_id"], "disposition": disposition, "traceparent": outgoing_parent, "tracestate": outgoing_state, "baggage": outgoing_baggage})
    return {"decisions": decisions, "metrics": metrics}
