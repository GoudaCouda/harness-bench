def plan_dns_responses(queries, policy):
    """Plan resolver responses from cache and refresh observations.

    Fresh answers, failed-refresh stale serving, and RFC 2308's basic negative
    TTL minimum are represented.  DNSSEC failure precedence, REFUSED handling,
    stale-negative policy, timeout boundaries, and strict packet metadata
    validation remain incomplete.
    """
    decisions = []
    for query in queries:
        negative_ttl = None
        if query["refresh_kind"] in ("nxdomain", "nodata") and query["refresh_authoritative"]:
            negative_ttl = min(query["soa_ttl_sec"], query["soa_minimum_sec"], policy["max_negative_ttl"])
            action, reason, kind, ttl, ede = "serve_refreshed", "authoritative_negative", query["refresh_kind"], negative_ttl, None
        elif query["cache_kind"] is not None and query["cache_age_sec"] < query["cache_ttl_sec"]:
            action, reason, kind, ttl, ede = "serve_fresh", "cache_fresh", query["cache_kind"], query["cache_ttl_sec"] - query["cache_age_sec"], None
        elif query["refresh_kind"] == "success":
            action, reason, kind, ttl, ede = "serve_refreshed", "refresh_success", query["cache_kind"], query["refresh_ttl_sec"], None
        elif query["cache_kind"] is not None and policy["serve_stale"] and query["cache_age_sec"] <= query["cache_ttl_sec"] + query["stale_retention_sec"]:
            action, reason, kind, ttl, ede = "serve_stale", "refresh_failed", query["cache_kind"], policy["stale_answer_ttl"], 3
        elif query["refresh_elapsed_ms"] < policy["client_response_ms"]:
            action, reason, kind, ttl, ede = "wait_refresh", "refresh_pending", None, None, None
        else:
            action, reason, kind, ttl, ede = "fail", "no_usable_answer", None, None, None
        decisions.append({"query_id": query["query_id"], "action": action, "reason": reason, "response_kind": kind, "ttl": ttl, "ede_code": ede, "cache_negative_ttl": negative_ttl})
    names = ("serve_fresh", "serve_refreshed", "serve_stale", "wait_refresh", "fail")
    return {"decisions": decisions, "summary": {"query_count": len(queries), **{name: sum(row["action"] == name for row in decisions) for name in names}}}
