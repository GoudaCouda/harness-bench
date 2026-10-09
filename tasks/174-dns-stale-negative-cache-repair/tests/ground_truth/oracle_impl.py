def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return isinstance(value, str) and bool(value) and value == value.lower() and value.isascii() and all(char.isalnum() or char in "-_." for char in value)


def _upper(value):
    return isinstance(value, str) and bool(value) and value == value.upper() and value.isascii()


def _integer(value, minimum):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def plan_dns_responses(queries, policy):
    policy_keys = ("serve_stale","allow_stale_negative","refused_preempts_stale","stale_answer_ttl","client_response_ms","max_negative_ttl")
    if (
        not _exact(policy, policy_keys)
        or not all(isinstance(policy[name], bool) for name in ("serve_stale","allow_stale_negative","refused_preempts_stale"))
        or not all(_integer(policy[name], 1) for name in ("stale_answer_ttl","client_response_ms","max_negative_ttl"))
        or not isinstance(queries, list)
    ):
        raise ValueError("invalid policy")
    keys = ("query_id","qname","qtype","recursion_desired","cache_kind","cache_age_sec","cache_ttl_sec","stale_retention_sec","cache_dnssec","refresh_kind","refresh_authoritative","refresh_elapsed_ms","refresh_ttl_sec","soa_ttl_sec","soa_minimum_sec","refresh_rcode")
    decisions = []
    query_ids = []
    counts = {"serve_fresh":0,"serve_refreshed":0,"serve_stale":0,"wait_refresh":0,"fail":0}
    for query in queries:
        if (
            not _exact(query, keys)
            or not _token(query["query_id"])
            or not isinstance(query["qname"], str)
            or not query["qname"].isascii()
            or query["qname"] != query["qname"].lower()
            or not query["qname"].endswith(".")
            or not _upper(query["qtype"])
            or not isinstance(query["recursion_desired"], bool)
            or query["cache_kind"] not in (None,"positive","nxdomain","nodata")
            or query["cache_dnssec"] not in (None,"secure","insecure","bogus")
            or query["refresh_kind"] not in ("positive","nxdomain","nodata","failure","pending")
            or not isinstance(query["refresh_authoritative"], bool)
            or not _integer(query["refresh_elapsed_ms"], 0)
            or query["refresh_rcode"] not in ("NOERROR","NXDOMAIN","SERVFAIL","TIMEOUT","REFUSED")
        ):
            raise ValueError("invalid query")
        cached = query["cache_kind"] is not None
        cache_values = (query["cache_age_sec"],query["cache_ttl_sec"],query["stale_retention_sec"])
        if cached:
            if not _integer(cache_values[0],0) or not _integer(cache_values[1],1) or not _integer(cache_values[2],0) or query["cache_dnssec"] is None:
                raise ValueError("invalid cache")
        elif any(value is not None for value in cache_values) or query["cache_dnssec"] is not None:
            raise ValueError("unexpected cache")
        refresh = query["refresh_kind"]
        if refresh == "positive":
            valid_refresh = query["refresh_authoritative"] and query["refresh_rcode"] == "NOERROR" and _integer(query["refresh_ttl_sec"],1) and query["soa_ttl_sec"] is None and query["soa_minimum_sec"] is None
        elif refresh in ("nxdomain","nodata"):
            expected_rcode = "NXDOMAIN" if refresh == "nxdomain" else "NOERROR"
            valid_refresh = query["refresh_authoritative"] and query["refresh_rcode"] == expected_rcode and query["refresh_ttl_sec"] is None and _integer(query["soa_ttl_sec"],1) and _integer(query["soa_minimum_sec"],1)
        else:
            valid_refresh = query["refresh_ttl_sec"] is None and query["soa_ttl_sec"] is None and query["soa_minimum_sec"] is None
        if not valid_refresh:
            raise ValueError("invalid refresh")
        query_ids.append(query["query_id"])
        action = None
        reason = None
        response_kind = None
        ttl = 0
        ede = None
        negative_ttl = None
        if cached and query["cache_age_sec"] < query["cache_ttl_sec"]:
            action, reason, response_kind = "serve_fresh", "fresh", query["cache_kind"]
            ttl = query["cache_ttl_sec"] - query["cache_age_sec"]
        elif refresh in ("positive","nxdomain","nodata") and query["refresh_elapsed_ms"] <= policy["client_response_ms"]:
            action, reason, response_kind = "serve_refreshed", "authoritative", refresh
            if refresh == "positive":
                ttl = query["refresh_ttl_sec"]
            else:
                ttl = min(query["soa_ttl_sec"], query["soa_minimum_sec"], policy["max_negative_ttl"])
                negative_ttl = ttl
        else:
            pending_early = refresh == "pending" and query["refresh_elapsed_ms"] < policy["client_response_ms"]
            stale_candidate = cached and query["cache_age_sec"] >= query["cache_ttl_sec"]
            stale_ok = (
                stale_candidate
                and policy["serve_stale"]
                and query["recursion_desired"]
                and query["cache_age_sec"] <= query["cache_ttl_sec"] + query["stale_retention_sec"]
                and query["cache_dnssec"] != "bogus"
                and (query["cache_kind"] == "positive" or policy["allow_stale_negative"])
                and not (query["refresh_rcode"] == "REFUSED" and policy["refused_preempts_stale"])
                and (refresh == "failure" or (refresh == "pending" and not pending_early))
            )
            if stale_ok:
                action, reason, response_kind = "serve_stale", "refresh_failed", query["cache_kind"]
                ttl, ede = policy["stale_answer_ttl"], 3
            elif pending_early:
                action, reason = "wait_refresh", "client_timer"
            else:
                action = "fail"
                if not cached:
                    reason = "no_cache"
                elif not query["recursion_desired"]:
                    reason = "recursion_not_desired"
                elif not policy["serve_stale"]:
                    reason = "stale_disabled"
                elif query["cache_age_sec"] > query["cache_ttl_sec"] + query["stale_retention_sec"]:
                    reason = "stale_expired"
                elif query["cache_dnssec"] == "bogus":
                    reason = "dnssec_bogus"
                elif query["cache_kind"] != "positive" and not policy["allow_stale_negative"]:
                    reason = "negative_stale_disabled"
                elif query["refresh_rcode"] == "REFUSED" and policy["refused_preempts_stale"]:
                    reason = "refused"
                else:
                    reason = "refresh_failed"
        counts[action] += 1
        decisions.append({"query_id":query["query_id"],"action":action,"reason":reason,"response_kind":response_kind,"ttl":ttl,"ede_code":ede,"cache_negative_ttl":negative_ttl})
    if query_ids != sorted(query_ids) or len(set(query_ids)) != len(query_ids):
        raise ValueError("queries must be sorted and unique")
    summary = {"query_count":len(queries)}
    summary.update(counts)
    return {"decisions":decisions,"summary":summary}
