def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return isinstance(value, str) and bool(value) and value == value.lower() and value.isascii() and all(char.isalnum() or char in "-_." for char in value)


def _rv(value):
    return isinstance(value, str) and bool(value) and len(value) <= 128 and value.isascii()


def _integer(value, minimum):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def recover_watches(watches, policy):
    if (
        not _exact(policy, ("max_attempts", "require_initial_bookmark"))
        or not _integer(policy["max_attempts"], 1)
        or not isinstance(policy["require_initial_bookmark"], bool)
        or not isinstance(watches, list)
    ):
        raise ValueError("invalid policy")
    keys = ("watch_id","mode","requested_rv","rv_match","send_initial_events","allow_bookmarks","last_applied_rv","initial_complete","outcome","event_type","event_rv","attempt")
    decisions = []
    watch_ids = []
    counts = {"apply_initial":0,"apply_event":0,"ignore":0,"checkpoint":0,"resume_watch":0,"relist":0,"block":0}
    resets = 0
    for watch in watches:
        if (
            not _exact(watch, keys)
            or not _token(watch["watch_id"])
            or watch["mode"] not in ("watch", "streaming_list")
            or (watch["requested_rv"] is not None and not _rv(watch["requested_rv"]))
            or watch["rv_match"] not in (None, "Exact", "NotOlderThan")
            or not isinstance(watch["send_initial_events"], bool)
            or not isinstance(watch["allow_bookmarks"], bool)
            or (watch["last_applied_rv"] is not None and not _rv(watch["last_applied_rv"]))
            or not isinstance(watch["initial_complete"], bool)
            or watch["outcome"] not in ("EVENT", "BOOKMARK", "GONE", "EOF", "ERROR")
            or not _integer(watch["attempt"], 1)
        ):
            raise ValueError("invalid watch")
        streaming = watch["mode"] == "streaming_list"
        if streaming:
            if not watch["send_initial_events"] or watch["rv_match"] != "NotOlderThan" or not watch["allow_bookmarks"]:
                raise ValueError("invalid streaming list")
        elif watch["send_initial_events"] or not watch["initial_complete"]:
            raise ValueError("invalid ordinary watch")
        if watch["outcome"] == "EVENT":
            if watch["event_type"] not in ("ADDED", "MODIFIED", "DELETED") or not _rv(watch["event_rv"]):
                raise ValueError("invalid event")
        elif watch["outcome"] == "BOOKMARK":
            if watch["event_type"] is not None or not _rv(watch["event_rv"]):
                raise ValueError("invalid bookmark")
        elif watch["event_type"] is not None or watch["event_rv"] is not None:
            raise ValueError("unexpected event")
        watch_ids.append(watch["watch_id"])
        action = None
        reason = None
        next_rv = watch["last_applied_rv"]
        complete = watch["initial_complete"]
        reset = False
        if watch["outcome"] == "GONE":
            action, reason, next_rv, complete, reset = "relist", "gone", None, False, True
        elif watch["outcome"] == "EVENT":
            if next_rv is not None and watch["event_rv"] == next_rv:
                action, reason = "ignore", "duplicate_event"
            else:
                action = "apply_initial" if streaming and not complete else "apply_event"
                reason = "initial_event" if action == "apply_initial" else "event"
                next_rv = watch["event_rv"]
        elif watch["outcome"] == "BOOKMARK":
            if not watch["allow_bookmarks"]:
                action, reason = "block", "unexpected_bookmark"
            else:
                action, reason = "checkpoint", "bookmark"
                next_rv = watch["event_rv"]
                if streaming and policy["require_initial_bookmark"]:
                    complete = True
        elif watch["attempt"] >= policy["max_attempts"]:
            action, reason = "block", "attempt_budget"
        elif next_rv is not None:
            action, reason = "resume_watch", watch["outcome"].lower()
        else:
            action, reason, complete, reset = "relist", "missing_checkpoint", False, True
        counts[action] += 1
        resets += int(reset)
        decisions.append({"watch_id":watch["watch_id"],"action":action,"reason":reason,"next_rv":next_rv,"next_initial_complete":complete,"reset_state":reset})
    if watch_ids != sorted(watch_ids) or len(set(watch_ids)) != len(watch_ids):
        raise ValueError("watches must be sorted and unique")
    summary = {"watch_count":len(watches)}
    summary.update(counts)
    summary["state_resets"] = resets
    return {"decisions":decisions,"summary":summary}
