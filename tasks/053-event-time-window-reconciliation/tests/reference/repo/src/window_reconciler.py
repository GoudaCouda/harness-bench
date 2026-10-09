def reconcile_event_windows(events, prior_windows, watermark_ms, allowed_lateness_ms, window_ms):
    if not isinstance(events, list) or not isinstance(prior_windows, list):
        raise ValueError("malformed envelope")
    for value in (watermark_ms, allowed_lateness_ms, window_ms):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("malformed timing")
    if allowed_lateness_ms < 0 or window_ms <= 0:
        raise ValueError("malformed timing")

    states = {}
    owners = {}
    for item in prior_windows:
        if not isinstance(item, dict):
            raise ValueError("malformed prior window")
        key, start, end = item.get("key"), item.get("start_ms"), item.get("end_ms")
        ids, revision = item.get("event_ids"), item.get("revision")
        valid = (
            isinstance(key, str) and key
            and isinstance(start, int) and not isinstance(start, bool)
            and isinstance(end, int) and not isinstance(end, bool)
            and end == start + window_ms and end <= watermark_ms
            and isinstance(item.get("sum"), int) and not isinstance(item.get("sum"), bool)
            and isinstance(ids, list) and ids == sorted(ids) and len(ids) == len(set(ids))
            and all(isinstance(event_id, str) and event_id for event_id in ids)
            and isinstance(revision, int) and not isinstance(revision, bool) and revision > 0
            and isinstance(item.get("final"), bool)
        )
        if not valid or (key, start) in states:
            raise ValueError("malformed prior window")
        computed_final = end + allowed_lateness_ms <= watermark_ms
        if item["final"] and not computed_final:
            raise ValueError("invalid prior finality")
        state = {"key": key, "start_ms": start, "end_ms": end, "sum": item["sum"], "event_ids": list(ids), "revision": revision, "final": computed_final, "existing": True, "changed": False}
        states[(start, key)] = state
        for event_id in ids:
            if event_id in owners:
                raise ValueError("duplicate prior ownership")
            owners[event_id] = (start, key)

    unique = {}
    for event in events:
        valid = (
            isinstance(event, dict)
            and isinstance(event.get("event_id"), str) and event.get("event_id")
            and isinstance(event.get("key"), str) and event.get("key")
            and isinstance(event.get("event_ms"), int) and not isinstance(event.get("event_ms"), bool)
            and isinstance(event.get("value"), int) and not isinstance(event.get("value"), bool)
        )
        if not valid:
            raise ValueError("malformed event")
        event_id = event["event_id"]
        normalized = {"event_id": event_id, "key": event["key"], "event_ms": event["event_ms"], "value": event["value"]}
        if event_id in unique and unique[event_id] != normalized:
            raise ValueError("conflicting replay")
        unique[event_id] = normalized

    pending, dropped = [], []
    for event_id in sorted(unique):
        event = unique[event_id]
        start = (event["event_ms"] // window_ms) * window_ms
        key = (start, event["key"])
        if event_id in owners:
            if owners[event_id] != key:
                raise ValueError("event moved between windows")
            continue
        end = start + window_ms
        if end > watermark_ms:
            pending.append(event_id)
            continue
        final = end + allowed_lateness_ms <= watermark_ms
        state = states.get(key)
        if final or (state is not None and state["final"]):
            dropped.append(event_id)
            continue
        if state is None:
            state = {"key": event["key"], "start_ms": start, "end_ms": end, "sum": 0, "event_ids": [], "revision": 1, "final": False, "existing": False, "changed": False}
            states[key] = state
        state["sum"] += event["value"]
        state["event_ids"].append(event_id)
        state["changed"] = True
    windows = []
    for key in sorted(states):
        state = states[key]
        if state["existing"] and state["changed"]:
            state["revision"] += 1
        state["event_ids"].sort()
        state["final"] = state["end_ms"] + allowed_lateness_ms <= watermark_ms
        windows.append({name: state[name] for name in ("key", "start_ms", "end_ms", "sum", "event_ids", "revision", "final")})
    return {"windows": windows, "pending": sorted(pending), "dropped_late": sorted(dropped)}
