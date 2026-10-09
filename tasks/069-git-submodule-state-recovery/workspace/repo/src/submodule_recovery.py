def plan_submodule_recovery(submodules, recursive):
    """Broken planner follows remote tips and ignores local changes."""
    plans = []
    for item in submodules:
        if item["depth"] and not recursive:
            continue
        target = item.get("remote_sha") or item["recorded_sha"]
        action = "verify" if item.get("checked_out_sha") == target else "checkout_remote"
        plans.append({"path": item["path"], "status": "planned", "action": action, "target_sha": target, "reason": "sync"})
    return plans
