def reconcile_event_windows(events, prior_windows, watermark_ms, allowed_lateness_ms, window_ms):
    grouped = {}
    pending = []
    for event in events:
        start = (event["ingest_ms"] // window_ms) * window_ms
        if start + window_ms > watermark_ms:
            pending.append(event["event_id"])
            continue
        item = grouped.setdefault((start, event["key"]), {"sum": 0, "event_ids": []})
        item["sum"] += event["value"]
        item["event_ids"].append(event["event_id"])
    windows = []
    for (start, key), item in grouped.items():
        windows.append({"key": key, "start_ms": start, "end_ms": start + window_ms, "sum": item["sum"], "event_ids": sorted(item["event_ids"]), "revision": 1, "final": True})
    return {"windows": windows, "pending": sorted(pending), "dropped_late": []}
