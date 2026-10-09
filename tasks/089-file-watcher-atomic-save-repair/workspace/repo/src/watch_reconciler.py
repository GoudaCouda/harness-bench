def reconcile_batch(checkpoint, batch, policy):
    """Broken handler: translates each event directly and ignores snapshots."""
    watched = dict(checkpoint.get("watched", {}))
    actions = []
    for event in batch.get("events", []):
        path = event.get("path")
        if path is None:
            continue
        action = "delete" if event.get("kind") == "rename" else "reload"
        actions.append({"path": path, "action": action, "reason": "removed" if action == "delete" else "content_changed"})
    return {"actions": actions, "checkpoint": {"seq": batch.get("seq"), "watched": watched}}
