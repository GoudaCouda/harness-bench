def replay_cache(state, operations, policy):
    """Broken implementation: evicts eagerly and ignores TTL/access semantics."""
    entries = state["entries"]
    events = []
    for operation in operations:
        if operation["op"] == "put":
            while sum(item["size"] for item in entries.values()) + operation["size"] > policy["capacity"]:
                entries.pop(next(iter(entries)))
            entries[operation["key"]] = {"value": operation["value"], "size": operation["size"], "expires_at": state["clock"] + operation["ttl"], "last_access": 0, "pinned": operation["pinned"]}
            events.append({"op": "put", "key": operation["key"], "status": "stored", "expired": [], "evicted": []})
    return {"state": state, "events": events}
