def plan_histogram_migration(metrics, policy):
    # Broken: partial coverage is treated as complete and every query is native.
    decisions = []
    for metric in metrics:
        query = f"histogram_avg(sum(rate({metric['metric_name']}[5m])))"
        decisions.append(
            {
                "metric_id": metric["metric_id"],
                "status": "ready",
                "action": "switch_query_to_native",
                "reason": "native_cutover_ready",
                "query": query,
            }
        )
    return {
        "decisions": decisions,
        "summary": {
            "metric_count": len(metrics),
            "settled": 0,
            "ready": len(metrics),
            "blocked": 0,
            "native_queries": len(metrics),
            "classic_queries": 0,
        },
    }
