def build_lifecycle_plan(resources, prior_state, observed, policy):
    """Build a review-only lifecycle plan from desired, state, and refresh data.

    Moved state and ignored drift are handled because they caused the original
    outage.  Replacement triggers, dependency ordering, sensitive redaction,
    and fail-closed validation are still incomplete.
    """
    prior = {row["address"]: dict(row) for row in prior_state}
    sightings = {row["address"]: row for row in observed}
    moves = {}
    for resource in resources:
        old = resource["lifecycle"]["moved_from"]
        if old is not None and old in prior:
            prior[resource["address"]] = {**prior.pop(old), "address": resource["address"]}
            sightings[resource["address"]] = {**sightings.pop(old), "address": resource["address"]}
            moves[old] = resource["address"]

    entries = []
    steps = []
    for resource in resources:
        address = resource["address"]
        old = prior.get(address)
        sighting = sightings.get(address)
        if old is None or sighting is not None and not sighting["exists"]:
            action, before, after, reasons = "create", None, dict(resource["attributes"]), ["missing_state"]
        else:
            before = dict(sighting["attributes"])
            after = dict(resource["attributes"])
            changed = []
            for key in set(before) | set(after):
                if key in resource["lifecycle"]["ignore_changes"]:
                    if key in before:
                        after[key] = before[key]
                elif before.get(key) != after.get(key):
                    changed.append(key)
            action = "update" if changed else "no-op"
            reasons = ["drift:" + key for key in sorted(changed)]
            if any(key in resource["immutable"] for key in changed):
                action = "replace"
        if resource["lifecycle"]["moved_from"] is not None:
            reasons.append("moved_from:" + resource["lifecycle"]["moved_from"])
        entries.append({"address": address, "action": action, "reasons": sorted(reasons), "before": before, "after": after, "create_before_destroy": action == "replace" and resource["lifecycle"]["create_before_destroy"]})
        if action in ("create", "update"):
            steps.append({"address": address, "operation": action})
    summary = {name: sum(entry["action"] == name for entry in entries) for name in ("create", "update", "replace", "delete", "no-op", "blocked")}
    summary.update(step_count=len(steps), moved_count=len(moves))
    return {"plan": {"resources": sorted(entries, key=lambda row: row["address"]), "steps": steps}, "summary": summary}
