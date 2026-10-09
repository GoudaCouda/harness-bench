def _timestamp(value):
    if not isinstance(value, str) or len(value) != 20:
        raise ValueError("timestamp shape")
    if value[4] != "-" or value[7] != "-" or value[10] != "T" or value[13] != ":" or value[16] != ":" or value[19] != "Z":
        raise ValueError("timestamp separators")
    digits = value[0:4] + value[5:7] + value[8:10] + value[11:13] + value[14:16] + value[17:19]
    if not digits.isdigit():
        raise ValueError("timestamp digits")
    year = int(value[0:4])
    month = int(value[5:7])
    day = int(value[8:10])
    hour = int(value[11:13])
    minute = int(value[14:16])
    second = int(value[17:19])
    if year < 1 or month < 1 or month > 12 or hour > 23 or minute > 59 or second > 59:
        raise ValueError("timestamp range")
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        month_days[1] = 29
    if day < 1 or day > month_days[month - 1]:
        raise ValueError("calendar day")
    return value


def select_checkout_engine(event, policy):
    event_keys = {"event_id", "event_time", "received_at", "account_id", "flag_snapshot"}
    policy_keys = {"retired_at", "retired_engine", "historical_flag"}
    if not isinstance(event, dict) or set(event.keys()) != event_keys:
        raise ValueError("event schema")
    if not isinstance(policy, dict) or set(policy.keys()) != policy_keys:
        raise ValueError("policy schema")
    for key in ("event_id", "event_time", "received_at", "account_id"):
        if not isinstance(event[key], str) or not event[key]:
            raise ValueError("event string")
    if policy["retired_engine"] != "v2" or policy["historical_flag"] != "checkout_v2":
        raise ValueError("policy values")
    event_time = _timestamp(event["event_time"])
    _timestamp(event["received_at"])
    retired_at = _timestamp(policy["retired_at"])
    snapshot = event["flag_snapshot"]
    if snapshot is not None and not isinstance(snapshot, dict):
        raise ValueError("snapshot type")
    if isinstance(snapshot, dict) and not all(isinstance(key, str) for key in snapshot):
        raise ValueError("snapshot keys")
    if event_time < retired_at:
        flag = policy["historical_flag"]
        if not isinstance(snapshot, dict) or flag not in snapshot or not isinstance(snapshot[flag], bool):
            raise ValueError("historical snapshot")
        return {
            "event_id": event["event_id"],
            "engine": "v2" if snapshot[flag] else "v1",
            "decision_source": "historical_snapshot",
        }
    return {
        "event_id": event["event_id"],
        "engine": policy["retired_engine"],
        "decision_source": "retired_default",
    }
