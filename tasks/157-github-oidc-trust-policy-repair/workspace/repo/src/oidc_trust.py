def authorize_tokens(roles, tokens, policy):
    """Evaluate captured GitHub OIDC claims against workload-role policy.

    Immutable owner/repository identifiers and basic subject/ref matching are
    enforced.  Audience arrays, workflow identity, environment subjects,
    pull-request policy, and strict claim-shape validation remain incomplete.
    """
    by_id = {role["role_id"]: role for role in roles}
    decisions = []
    for token in tokens:
        role = by_id.get(token["role_id"])
        if role is None:
            status, reason = "denied", "role"
        elif token["iss"] != role["issuer"]:
            status, reason = "denied", "issuer"
        elif token["aud"] not in role["audiences"]:
            status, reason = "denied", "audience"
        elif token["owner_id"] != role["owner_id"]:
            status, reason = "denied", "owner_id"
        elif token["repository_id"] not in role["repository_ids"]:
            status, reason = "denied", "repository_id"
        elif token["id_token_permission"] != "write":
            status, reason = "denied", "permission"
        elif role["allowed_refs"] and token["ref"] not in role["allowed_refs"]:
            status, reason = "denied", "ref"
        elif role["subject_mode"] == "immutable" and ("@" + token["owner_id"] + "/" not in token["sub"] or "@" + token["repository_id"] + ":" not in token["sub"]):
            status, reason = "denied", "subject"
        else:
            status, reason = "authorized", "matched"
        decisions.append({"request_id": token["request_id"], "role_id": token["role_id"], "status": status, "reason": reason})
    return {"decisions": decisions, "summary": {"request_count": len(tokens), "authorized": sum(row["status"] == "authorized" for row in decisions), "denied": sum(row["status"] == "denied" for row in decisions)}}
