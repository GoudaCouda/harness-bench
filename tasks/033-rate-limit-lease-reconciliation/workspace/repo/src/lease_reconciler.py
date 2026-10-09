def reconcile_leases(state, requests, now_ms):
    """Broken incident version: repair according to docs/lease_contract.md."""
    leases = list(state.get("leases", []))
    available = state.get("capacity", 0) - sum(item.get("units", 0) for item in leases)
    decisions = []
    next_fence = state.get("next_fence", 1)
    for request in requests:
        if request.get("units", 0) <= available:
            lease = {
                "request_id": request["request_id"], "owner": request["owner"],
                "units": request["units"], "acquired_ms": now_ms,
                "expires_ms": now_ms + request["ttl_ms"], "fence": next_fence,
            }
            leases.append(lease)
            available -= request["units"]
            next_fence += 1
            decisions.append({"request_id": request["request_id"], "status": "granted", "reason": None, "replayed": False, "fence": lease["fence"]})
        else:
            decisions.append({"request_id": request["request_id"], "status": "rejected", "reason": "capacity", "replayed": False, "fence": None})
    return {"leases": leases, "decisions": decisions, "next_fence": next_fence}
