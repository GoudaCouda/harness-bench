def plan_recovery(site_state, journal, wheel_record):
    """Plan a rollback for an interrupted install (incomplete implementation)."""
    actions = []
    for entry in journal["entries"]:
        if not entry["applied"]:
            continue
        path = entry["path"]
        before = entry["before"]
        if before is None:
            actions.append({"kind": "remove", "path": path})
        else:
            actions.append({"kind": "restore", "path": path,
                            "digest": before["digest"], "owners": before["owners"]})
    return {"decision": "rollback_required", "actions": actions, "conflicts": []}
