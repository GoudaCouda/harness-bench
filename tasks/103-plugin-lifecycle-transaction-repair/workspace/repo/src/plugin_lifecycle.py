def reconcile_plugins(state, catalog, request, faults):
    """Broken: toggles requested names directly and never repairs hooks."""
    active = list(state["active"])
    for name in request["disable"]:
        if name in active:
            active.remove(name)
    for name in request["enable"]:
        if name not in active:
            active.append(name)
    return {"state": {"generation": state["generation"] + 1, "active": active, "registrations": state["registrations"]}, "journal": {"status":"committed","reason":"ok","activation_order":request["enable"],"deactivation_order":request["disable"],"failed_plugin":None,"rollback_order":[]}}
