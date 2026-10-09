def _scope(value):
    return (isinstance(value, list) and value and value == sorted(value)
            and len(value) == len(set(value))
            and all(isinstance(item, str) and item for item in value))


def _copy_session(session):
    return {"generation": session["generation"], "access_token": session["access_token"],
            "refresh_token": session["refresh_token"], "scope": list(session["scope"]),
            "rotation_required": session["rotation_required"], "status": session["status"]}


def _result(decision, session, winner, ignored, conflicts):
    return {"decision": decision, "next_session": session,
            "winner_request_id": winner, "ignored_request_ids": ignored,
            "conflicts": conflicts}


def reconcile_refresh(session, attempts):
    if not isinstance(session, dict) or set(session.keys()) != {"generation", "access_token", "refresh_token", "scope", "rotation_required", "status"}:
        raise ValueError("session schema")
    generation = session["generation"]
    status = session["status"]
    if (not isinstance(generation, int) or isinstance(generation, bool) or generation < 0
            or not isinstance(session["rotation_required"], bool) or not _scope(session["scope"])
            or status not in ("active", "reauth_required")):
        raise ValueError("session value")
    if status == "active":
        if not isinstance(session["access_token"], str) or not session["access_token"] or not isinstance(session["refresh_token"], str) or not session["refresh_token"]:
            raise ValueError("active token")
    elif session["access_token"] is not None or session["refresh_token"] is not None:
        raise ValueError("reauth token")
    if not isinstance(attempts, list):
        raise ValueError("attempt list")
    ids = set()
    sequences = set()
    for attempt in attempts:
        if not isinstance(attempt, dict) or set(attempt.keys()) != {"request_id", "observed_generation", "used_refresh_token", "sequence", "response"}:
            raise ValueError("attempt schema")
        request_id = attempt["request_id"]
        observed = attempt["observed_generation"]
        sequence = attempt["sequence"]
        if (not isinstance(request_id, str) or not request_id or request_id in ids
                or not isinstance(observed, int) or isinstance(observed, bool) or observed < 0
                or not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0 or sequence in sequences
                or not isinstance(attempt["used_refresh_token"], str) or not attempt["used_refresh_token"]):
            raise ValueError("attempt value")
        ids.add(request_id)
        sequences.add(sequence)
        response = attempt["response"]
        if not isinstance(response, dict) or response.get("kind") not in ("success", "error"):
            raise ValueError("response schema")
        if response["kind"] == "success":
            if set(response.keys()) != {"kind", "access_token", "refresh_token", "scope"}:
                raise ValueError("success schema")
            if (not isinstance(response["access_token"], str) or not response["access_token"]
                    or (response["refresh_token"] is not None and (not isinstance(response["refresh_token"], str) or not response["refresh_token"]))
                    or not _scope(response["scope"])):
                raise ValueError("success value")
        elif set(response.keys()) != {"kind", "error"} or response["error"] not in ("invalid_grant", "server_error", "temporarily_unavailable"):
            raise ValueError("error value")
        if observed > generation:
            raise ValueError("future generation")
    ordered = [item for sequence, item in sorted([(item["sequence"], item) for item in attempts])]
    copied = _copy_session(session)
    if status == "reauth_required":
        return _result("no_action", copied, None, [], [])
    stale = [item["request_id"] for item in ordered if item["observed_generation"] < generation]
    current = [item for item in ordered if item["observed_generation"] == generation]
    conflicts = [{"request_id": item["request_id"], "reason": "token_mismatch"}
                 for item in current if item["used_refresh_token"] != session["refresh_token"]]
    contenders = [item for item in current if item["used_refresh_token"] == session["refresh_token"]]
    if conflicts:
        return _result("manual_intervention", copied, None, stale, conflicts)
    winner = None
    invalid = None
    for item in contenders:
        response = item["response"]
        if response["kind"] == "error":
            if response["error"] == "invalid_grant" and winner is None:
                invalid = item
                break
            continue
        if winner is not None:
            conflicts.append({"request_id": item["request_id"], "reason": "multiple_successes"})
            continue
        if not set(response["scope"]).issubset(set(session["scope"])):
            conflicts.append({"request_id": item["request_id"], "reason": "scope_escalation"})
            continue
        rotated = response["refresh_token"]
        if session["rotation_required"] and (rotated is None or rotated == session["refresh_token"]):
            conflicts.append({"request_id": item["request_id"], "reason": "rotation_violation"})
            continue
        winner = item
    if invalid is not None:
        next_session = _copy_session(session)
        next_session["generation"] += 1
        next_session["access_token"] = None
        next_session["refresh_token"] = None
        next_session["status"] = "reauth_required"
        ignored = stale + [item["request_id"] for item in contenders if item["request_id"] != invalid["request_id"]]
        return _result("reauth_required", next_session, None, ignored, [])
    if conflicts:
        return _result("manual_intervention", copied, None, stale, conflicts)
    if winner is not None:
        response = winner["response"]
        next_session = _copy_session(session)
        next_session["generation"] += 1
        next_session["access_token"] = response["access_token"]
        next_session["refresh_token"] = response["refresh_token"] or session["refresh_token"]
        next_session["scope"] = list(response["scope"])
        ignored = stale + [item["request_id"] for item in contenders if item["request_id"] != winner["request_id"]]
        return _result("adopt_success", next_session, winner["request_id"], ignored, [])
    if contenders:
        return _result("retry_refresh", copied, None, stale, [])
    return _result("no_action", copied, None, stale, [])
