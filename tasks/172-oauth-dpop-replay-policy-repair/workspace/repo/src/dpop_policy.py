def verify_dpop(requests, proofs, replay_cache, policy):
    # Broken: prior signature evidence is treated as the complete policy.
    decisions = [
        {"request_id": item["request_id"], "status": "accepted", "reason": "bound", "cache_expires_at": item["now"] + policy["max_age_sec"]}
        for item in requests
    ]
    return {"decisions": decisions, "replay_cache": replay_cache, "summary": {"request_count": len(requests), "accepted": len(requests), "rejected": 0, "replay_rejected": 0, "cache_entries": len(replay_cache)}}
