def _sequencer(value):
    return int(value, 16)


def reconcile_object_events(objects, events, policy):
    """Reconcile an at-least-once S3 notification capture by sequencer.

    Normal stale/new ordering works independently of arrival order.  Duplicate
    event identity, URL-encoded key handling, delete markers, version policy,
    and strict malformed-event rejection are still incomplete.
    """
    state = [dict(row) for row in objects]
    by_key = {(row["bucket"], row["key"]): row for row in state}
    decisions = []
    for event in events:
        key = (event["bucket"], event["key"])
        current = by_key.get(key)
        if current is not None and _sequencer(event["sequencer"]) <= _sequencer(current["sequencer"]):
            status, reason = "ignored", "duplicate" if event["sequencer"] == current["sequencer"] else "stale"
        elif event["event_name"].startswith("ObjectRemoved") and not policy["allow_delete_markers"]:
            status, reason = "blocked", "delete_marker_policy"
        else:
            status, reason = "applied", "newer_sequencer"
            if event["event_name"].startswith("ObjectRemoved"):
                replacement = {"bucket": event["bucket"], "key": event["key"], "sequencer": event["sequencer"], "state": "deleted", "version_id": event["version_id"], "etag": None, "size": None}
            else:
                replacement = {"bucket": event["bucket"], "key": event["key"], "sequencer": event["sequencer"], "state": "present", "version_id": event["version_id"], "etag": event["etag"], "size": event["size"]}
            if current is None:
                state.append(replacement)
                by_key[key] = replacement
            else:
                current.update(replacement)
        decisions.append({"event_id": event["event_id"], "status": status, "reason": reason})
    counts = {name: sum(row["status"] == name for row in decisions) for name in ("applied", "ignored", "blocked")}
    return {"decisions": decisions, "objects": sorted(state, key=lambda row: (row["bucket"], row["key"])), "summary": {"event_count": len(events), **counts, "object_count": len(state)}}
