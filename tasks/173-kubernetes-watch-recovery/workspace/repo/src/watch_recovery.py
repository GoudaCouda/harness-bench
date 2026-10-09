def recover_watches(watches, policy):
    """Choose recovery actions from captured Kubernetes watch outcomes.

    GONE relisting and basic checkpoints exist, but this broken version still
    orders opaque resourceVersion strings and mishandles streaming completion,
    bookmark policy, missing checkpoints, and retry exhaustion.
    """
    decisions = []
    for item in watches:
        if item["outcome"] == "GONE":
            action, reason, next_rv, complete, reset = "relist", "gone", None, False, True
        elif item["outcome"] == "EVENT" and item["event_rv"] <= item["last_applied_rv"]:
            action, reason, next_rv, complete, reset = "ignore", "duplicate_event", item["last_applied_rv"], item["initial_complete"], False
        elif item["outcome"] == "EVENT":
            action, reason, next_rv, complete, reset = "apply_event", "event", item["event_rv"], True, False
        elif item["outcome"] == "BOOKMARK":
            action, reason, next_rv, complete, reset = "checkpoint", "bookmark", item["event_rv"], True, False
        else:
            action, reason, next_rv, complete, reset = "resume_watch", "retry", item["last_applied_rv"], item["initial_complete"], False
        decisions.append({"watch_id": item["watch_id"], "action": action, "reason": reason, "next_rv": next_rv, "next_initial_complete": complete, "reset_state": reset})
    names = ("apply_initial", "apply_event", "ignore", "checkpoint", "resume_watch", "relist", "block")
    summary = {"watch_count": len(watches), **{name: sum(row["action"] == name for row in decisions) for name in names}, "state_resets": sum(row["reset_state"] for row in decisions)}
    return {"decisions": decisions, "summary": summary}
