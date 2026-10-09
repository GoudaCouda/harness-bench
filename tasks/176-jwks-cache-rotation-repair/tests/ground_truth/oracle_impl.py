def plan_jwks_cache_rotation(records, policy):
    if not isinstance(records, list) or not isinstance(policy, dict): raise ValueError("records and policy")
    keys, fetched_at, max_stale = policy.get("keys"), policy.get("fetched_at"), policy.get("max_stale")
    if not isinstance(keys, list) or not isinstance(fetched_at, int) or not isinstance(max_stale, int) or max_stale < 0: raise ValueError("policy")
    keymap = {}
    for key in keys:
        if not isinstance(key, dict) or not all(isinstance(key.get(name), typ) for name, typ in (("kid", str), ("issuer", str), ("alg", str), ("not_before", int), ("not_after", int))) or key["not_before"] >= key["not_after"] or not isinstance(key.get("revoked", False), bool): raise ValueError("key")
        ident = (key["issuer"], key["kid"])
        if ident in keymap: raise ValueError("duplicate key")
        keymap[ident] = key
    seen, decisions = set(), []
    for row in records:
        if not isinstance(row, dict) or not all(isinstance(row.get(name), typ) for name, typ in (("id", str), ("issuer", str), ("kid", str), ("alg", str), ("now", int))): raise ValueError("record")
        if row["id"] in seen: raise ValueError("duplicate id")
        seen.add(row["id"]); key = keymap.get((row["issuer"], row["kid"])); age = row["now"] - fetched_at
        if age < 0: action, reason = "reject", "clock_before_fetch"
        elif key and key["revoked"]: action, reason = "reject", "revoked_key"
        elif key and key["alg"] != row["alg"]: action, reason = "reject", "algorithm_mismatch"
        elif key and key["not_before"] <= row["now"] < key["not_after"]: action, reason = "verify", "active_key"
        elif key and row["now"] >= key["not_after"] and 0 <= age <= max_stale and row.get("refresh_failed") is True: action, reason = "verify_stale", "bounded_stale_fallback"
        elif row.get("refresh_failed") is True: action, reason = "reject", "refresh_failed_no_safe_key"
        else: action, reason = "refresh", "key_missing_or_inactive"
        decisions.append({"id": row["id"], "action": action, "reason": reason, "kid": row["kid"], "cache_age": age})
    decisions.sort(key=lambda row: row["id"])
    return {"decisions": decisions, "summary": {name: sum(row["action"] == name for row in decisions) for name in ("verify", "verify_stale", "refresh", "reject")}}
