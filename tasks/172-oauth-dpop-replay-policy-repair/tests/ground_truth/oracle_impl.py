def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return isinstance(value, str) and bool(value) and value == value.lower() and value.isascii() and all(char.isalnum() or char in "-_." for char in value)


def _text(value):
    return isinstance(value, str) and bool(value) and value.isascii()


def _upper(value):
    return _text(value) and value == value.upper()


def _integer(value, minimum):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def verify_dpop(requests, proofs, replay_cache, policy):
    policy_keys = ("allowed_algs", "max_age_sec", "future_skew_sec", "max_jti_chars", "require_nonce")
    if (
        not _exact(policy, policy_keys)
        or not isinstance(policy["allowed_algs"], list)
        or not policy["allowed_algs"]
        or policy["allowed_algs"] != sorted(policy["allowed_algs"])
        or len(set(policy["allowed_algs"])) != len(policy["allowed_algs"])
        or not all(_upper(value) for value in policy["allowed_algs"])
        or not _integer(policy["max_age_sec"], 1)
        or not _integer(policy["future_skew_sec"], 0)
        or not _integer(policy["max_jti_chars"], 1)
        or not isinstance(policy["require_nonce"], bool)
    ):
        raise ValueError("invalid policy")
    if not isinstance(requests, list) or not isinstance(proofs, list) or not isinstance(replay_cache, list):
        raise ValueError("invalid inputs")
    request_keys = ("request_id", "method", "htu", "now", "token_jkt", "access_token_hash", "required_nonce")
    request_map = {}
    request_ids = []
    for request in requests:
        nonce = request.get("required_nonce") if isinstance(request, dict) else None
        if (
            not _exact(request, request_keys)
            or not _token(request["request_id"])
            or not _upper(request["method"])
            or not _text(request["htu"])
            or not _integer(request["now"], 0)
            or not _token(request["token_jkt"])
            or not _text(request["access_token_hash"])
            or (nonce is not None and not _text(nonce))
            or (policy["require_nonce"] and nonce is None)
            or (not policy["require_nonce"] and nonce is not None)
        ):
            raise ValueError("invalid request")
        request_ids.append(request["request_id"])
        request_map[request["request_id"]] = request
    if request_ids != sorted(request_ids) or len(set(request_ids)) != len(request_ids):
        raise ValueError("requests must be sorted and unique")
    proof_keys = ("request_id", "typ", "alg", "public_jwk", "signature_verified", "htm", "htu", "iat", "jti", "jkt", "ath", "nonce")
    proof_map = {}
    proof_ids = []
    for proof in proofs:
        nonce = proof.get("nonce") if isinstance(proof, dict) else None
        if (
            not _exact(proof, proof_keys)
            or proof["request_id"] not in request_map
            or not _text(proof["typ"])
            or not _upper(proof["alg"])
            or not isinstance(proof["public_jwk"], bool)
            or not isinstance(proof["signature_verified"], bool)
            or not _upper(proof["htm"])
            or not _text(proof["htu"])
            or not _integer(proof["iat"], 0)
            or not _text(proof["jti"])
            or not _token(proof["jkt"])
            or not _text(proof["ath"])
            or (nonce is not None and not _text(nonce))
        ):
            raise ValueError("invalid proof")
        proof_ids.append(proof["request_id"])
        proof_map[proof["request_id"]] = proof
    if proof_ids != sorted(proof_ids) or len(set(proof_ids)) != len(proof_ids):
        raise ValueError("proofs must be sorted and unique")
    cache_keys = ("jkt", "jti", "expires_at")
    cache = {}
    cache_order = []
    for entry in replay_cache:
        if not _exact(entry, cache_keys) or not _token(entry["jkt"]) or not _text(entry["jti"]) or not _integer(entry["expires_at"], 0):
            raise ValueError("invalid replay entry")
        pair = (entry["jkt"], entry["jti"])
        cache_order.append(pair)
        cache[pair] = entry["expires_at"]
    if cache_order != sorted(cache_order) or len(set(cache_order)) != len(cache_order):
        raise ValueError("replay cache must be sorted and unique")
    if requests:
        cutoff = min(item["now"] for item in requests)
        cache = {pair: expiry for pair, expiry in cache.items() if expiry > cutoff}
    decisions = []
    accepted = 0
    replay_rejected = 0
    for request in requests:
        proof = proof_map.get(request["request_id"])
        reason = None
        if proof is None:
            reason = "missing_proof"
        elif proof["typ"].lower() != "dpop+jwt":
            reason = "typ"
        elif proof["alg"] not in policy["allowed_algs"] or proof["alg"] == "NONE" or proof["alg"].startswith("HS"):
            reason = "algorithm"
        elif not proof["public_jwk"]:
            reason = "public_jwk"
        elif not proof["signature_verified"]:
            reason = "signature"
        elif proof["htm"] != request["method"]:
            reason = "method"
        elif proof["htu"] != request["htu"]:
            reason = "uri"
        elif proof["iat"] > request["now"] + policy["future_skew_sec"]:
            reason = "iat_future"
        elif proof["iat"] < request["now"] - policy["max_age_sec"]:
            reason = "iat_expired"
        elif len(proof["jti"]) > policy["max_jti_chars"]:
            reason = "jti_size"
        elif proof["jkt"] != request["token_jkt"]:
            reason = "key_binding"
        elif proof["ath"] != request["access_token_hash"]:
            reason = "token_hash"
        elif policy["require_nonce"] and proof["nonce"] != request["required_nonce"]:
            reason = "nonce"
        elif (proof["jkt"], proof["jti"]) in cache:
            reason = "replay"
        expiry = None
        if reason is None:
            reason = "bound"
            expiry = request["now"] + policy["max_age_sec"]
            cache[(proof["jkt"], proof["jti"])] = expiry
            accepted += 1
        elif reason == "replay":
            replay_rejected += 1
        decisions.append({"request_id": request["request_id"], "status": "accepted" if reason == "bound" else "rejected", "reason": reason, "cache_expires_at": expiry})
    final_cache = [{"jkt": pair[0], "jti": pair[1], "expires_at": cache[pair]} for pair in sorted(cache)]
    return {"decisions": decisions, "replay_cache": final_cache, "summary": {"request_count": len(requests), "accepted": accepted, "rejected": len(requests) - accepted, "replay_rejected": replay_rejected, "cache_entries": len(final_cache)}}
