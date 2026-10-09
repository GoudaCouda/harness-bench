def _apply(cache, writes):
    result = {entity: dict(fields) for entity, fields in cache.items()}
    for write in writes:
        result.setdefault(write["id"], {}).update(write["fields"])
    return result


def reconcile_cache(base, events, policy):
    """Replay optimistic mutation events over a normalized cache snapshot.

    Independent layers and null writes work.  The starter still mishandles
    alias remapping, server commits that arrive out of order, entity deletion,
    and strict layer-count/schema validation.
    """
    committed = {entity: dict(fields) for entity, fields in base.items()}
    layers = {}
    order = []
    audit = []
    for event in events:
        mutation = event["mutation_id"]
        if event["kind"] == "optimistic" and event["mode"] == "apply":
            layers[mutation] = list(event["writes"])
            if mutation not in order:
                order.append(mutation)
            audit.append({"mutation_id": mutation, "action": "applied"})
        elif event["kind"] == "error":
            layers.pop(mutation, None)
            order = [item for item in order if item != mutation]
            audit.append({"mutation_id": mutation, "action": "rolled_back"})
        elif event["kind"] == "success":
            committed = _apply(committed, event["writes"])
            layers.pop(mutation, None)
            order = [item for item in order if item != mutation]
            audit.append({"mutation_id": mutation, "action": "committed"})
    visible = committed
    for mutation in order:
        visible = _apply(visible, layers[mutation])
    return {"base": committed, "visible": visible, "audit": audit}
