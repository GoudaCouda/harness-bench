def assess_assertions(credentials, assertions, policy):
    """Reconcile verified assertion metadata with stored credential counters.

    This seed protects device counters and flags the common synced-passkey
    equality case.  It still applies checks in the wrong precedence for some
    identity failures and does not fully validate duplicate assertions or
    backup-state transitions.
    """
    state = [dict(row) for row in credentials]
    by_id = {row["credential_id"]: row for row in state}
    decisions = []
    for assertion in assertions:
        credential = by_id.get(assertion["credential_id"])
        reason = None
        if credential is None or credential["status"] != "active":
            reason = "credential"
        elif not assertion["signature_valid"]:
            reason = "signature"
        elif assertion["origin"] not in policy["allowed_origins"]:
            reason = "origin"
        elif assertion["rp_id"] != policy["rp_id"]:
            reason = "rp_id"
        elif policy["require_user_verification"] and not assertion["user_verified"]:
            reason = "user_verification"
        elif assertion["user_id"] != credential["user_id"]:
            reason = "user"
        if reason is not None:
            decisions.append({"assertion_id": assertion["assertion_id"], "decision": "rejected", "reason": reason})
            continue
        synced = credential["backup_eligible"] or assertion["backup_eligible"]
        if not synced and assertion["sign_count"] <= credential["sign_count"] and assertion["sign_count"] != 0:
            decisions.append({"assertion_id": assertion["assertion_id"], "decision": "rejected", "reason": "counter_regression"})
            continue
        if synced and assertion["sign_count"] <= credential["sign_count"]:
            credential["risk"] = "elevated"
        credential["sign_count"] = max(credential["sign_count"], assertion["sign_count"])
        credential["last_assertion"] = assertion["assertion_id"]
        decisions.append({"assertion_id": assertion["assertion_id"], "decision": "accepted", "reason": "counter_flagged" if credential["risk"] == "elevated" else "ok"})
    return {"credentials": state, "decisions": decisions}
