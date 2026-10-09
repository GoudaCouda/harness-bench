def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value, key=False):
    chars = "-_/." if key else "-_"
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in chars for char in value)
    )


def _hex(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char in "0123456789abcdef" for char in value)
    )


def _result_object(event):
    deleted = event["event_name"].startswith("ObjectRemoved:")
    return {
        "bucket": event["bucket"],
        "key": event["key"],
        "sequencer": event["sequencer"],
        "state": "deleted" if deleted else "present",
        "version_id": event["version_id"],
        "etag": None if deleted else event["etag"],
        "size": 0 if deleted else event["size"],
    }


def reconcile_object_events(objects, events, policy):
    if (
        not _exact(
            policy, ("allow_delete_markers", "require_version_id", "max_key_bytes")
        )
        or not isinstance(policy["allow_delete_markers"], bool)
        or not isinstance(policy["require_version_id"], bool)
        or not isinstance(policy["max_key_bytes"], int)
        or isinstance(policy["max_key_bytes"], bool)
        or policy["max_key_bytes"] <= 0
    ):
        raise ValueError("invalid policy")
    if not isinstance(objects, list) or not isinstance(events, list):
        raise ValueError("invalid inputs")
    object_keys = ("bucket", "key", "sequencer", "state", "version_id", "etag", "size")
    state = {}
    order = []
    for obj in objects:
        if (
            not _exact(obj, object_keys)
            or not _token(obj["bucket"])
            or not _token(obj["key"], True)
            or len(obj["key"].encode()) > policy["max_key_bytes"]
            or not _hex(obj["sequencer"])
            or obj["state"] not in ("present", "deleted")
            or (obj["version_id"] is not None and not _token(obj["version_id"]))
            or not isinstance(obj["size"], int)
            or isinstance(obj["size"], bool)
            or obj["size"] < 0
        ):
            raise ValueError("invalid object")
        if (obj["state"] == "deleted") != (
            obj["etag"] is None and obj["size"] == 0
        ) or (obj["etag"] is not None and not _token(obj["etag"])):
            raise ValueError("invalid object payload")
        identity = (obj["bucket"], obj["key"])
        if identity in state:
            raise ValueError("duplicate object")
        state[identity] = dict(obj)
        order.append(identity)
    if order != sorted(order):
        raise ValueError("objects must be sorted")
    event_keys = (
        "arrival_index",
        "event_id",
        "bucket",
        "key",
        "event_name",
        "sequencer",
        "version_id",
        "etag",
        "size",
        "event_time",
    )
    names = (
        "ObjectCreated:Put",
        "ObjectCreated:CompleteMultipartUpload",
        "ObjectRemoved:Delete",
        "ObjectRemoved:DeleteMarkerCreated",
    )
    seen = {}
    decisions = []
    counts = {"applied": 0, "ignored": 0, "blocked": 0}
    for index, event in enumerate(events):
        if (
            not _exact(event, event_keys)
            or event["arrival_index"] != index
            or not _token(event["event_id"])
            or not _token(event["bucket"])
            or not _token(event["key"], True)
            or len(event["key"].encode()) > policy["max_key_bytes"]
            or event["event_name"] not in names
            or not _hex(event["sequencer"])
        ):
            raise ValueError("invalid event identity")
        if event["version_id"] is not None and not _token(event["version_id"]):
            raise ValueError("invalid version")
        if (
            not isinstance(event["size"], int)
            or isinstance(event["size"], bool)
            or event["size"] < 0
            or not isinstance(event["event_time"], str)
            or not event["event_time"].endswith("z")
        ):
            raise ValueError("invalid event payload")
        deleted = event["event_name"].startswith("ObjectRemoved:")
        if deleted != (event["etag"] is None and event["size"] == 0) or (
            event["etag"] is not None and not _token(event["etag"])
        ):
            raise ValueError("invalid event object")
        fingerprint = tuple(
            (key, str(event[key])) for key in event_keys if key != "arrival_index"
        )
        prior_fingerprint = seen.get(event["event_id"])
        if prior_fingerprint is not None:
            status, action, reason = (
                ("ignored", "ignore", "duplicate")
                if prior_fingerprint == fingerprint
                else ("blocked", "quarantine", "event_id_conflict")
            )
        else:
            seen[event["event_id"]] = fingerprint
            identity = (event["bucket"], event["key"])
            current = state.get(identity)
            candidate = _result_object(event)
            if current is not None and int(event["sequencer"], 16) < int(
                current["sequencer"], 16
            ):
                status, action, reason = "ignored", "ignore", "stale"
            elif current is not None and int(event["sequencer"], 16) == int(
                current["sequencer"], 16
            ):
                status, action, reason = (
                    ("ignored", "ignore", "duplicate")
                    if candidate == current
                    else ("blocked", "quarantine", "sequencer_conflict")
                )
            elif policy["require_version_id"] and event["version_id"] is None:
                status, action, reason = "blocked", "quarantine", "version_id_required"
            elif (
                event["event_name"] == "ObjectRemoved:DeleteMarkerCreated"
                and not policy["allow_delete_markers"]
            ):
                status, action, reason = "blocked", "quarantine", "delete_marker_policy"
            else:
                status, action, reason = (
                    "applied",
                    "delete" if deleted else "upsert",
                    "newer_sequencer",
                )
                state[identity] = candidate
        decisions.append(
            {
                "arrival_index": index,
                "event_id": event["event_id"],
                "status": status,
                "action": action,
                "reason": reason,
            }
        )
        counts[status] += 1
    final_objects = [state[key] for key in sorted(state)]
    return {
        "decisions": decisions,
        "objects": final_objects,
        "summary": {
            "event_count": len(events),
            "applied": counts["applied"],
            "ignored": counts["ignored"],
            "blocked": counts["blocked"],
            "object_count": len(final_objects),
        },
    }
