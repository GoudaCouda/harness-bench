def reconcile_leases(state, requests, now_ms):
    if type(state) is not dict or type(requests) is not list or type(now_ms) is not int:
        raise ValueError("invalid root")
    capacity, next_fence, leases = state.get("capacity"), state.get("next_fence"), state.get("leases")
    if type(capacity) is not int or capacity <= 0 or type(next_fence) is not int or next_fence <= 0 or type(leases) is not list:
        raise ValueError("invalid state")
    active, ids, fences = [], set(), set()
    for raw in leases:
        if type(raw) is not dict or set(raw) != {"request_id","owner","units","acquired_ms","expires_ms","fence"}:
            raise ValueError("invalid lease")
        item = dict(raw)
        if type(item["request_id"]) is not str or not item["request_id"] or type(item["owner"]) is not str or not item["owner"] or any(type(item[k]) is not int for k in ("units","acquired_ms","expires_ms","fence")) or item["units"] <= 0 or item["fence"] <= 0 or item["expires_ms"] <= item["acquired_ms"] or item["request_id"] in ids or item["fence"] in fences:
            raise ValueError("invalid lease")
        ids.add(item["request_id"]); fences.add(item["fence"])
        if item["expires_ms"] > now_ms:
            active.append(item)
    if sum(x["units"] for x in active) > capacity or any(x["fence"] >= next_fence for x in active):
        raise ValueError("invalid accounting")
    clean, seen = [], set()
    for index, raw in enumerate(requests):
        if type(raw) is not dict or set(raw) != {"request_id","owner","units","requested_ms","ttl_ms"}:
            raise ValueError("invalid request")
        item = dict(raw)
        if type(item["request_id"]) is not str or not item["request_id"] or type(item["owner"]) is not str or not item["owner"] or any(type(item[k]) is not int for k in ("units","requested_ms","ttl_ms")) or item["units"] <= 0 or item["ttl_ms"] <= 0 or item["request_id"] in seen:
            raise ValueError("invalid request")
        seen.add(item["request_id"]); clean.append((index,item))
    decisions, pending, by_id = [None] * len(clean), [], {x["request_id"]:x for x in active}
    for index, item in clean:
        prior = by_id.get(item["request_id"])
        if prior is not None:
            same = prior["owner"] == item["owner"] and prior["units"] == item["units"]
            decisions[index] = {"request_id":item["request_id"],"status":"granted" if same else "rejected","reason":None if same else "request_id_conflict","replayed":same,"fence":prior["fence"] if same else None}
        elif item["requested_ms"] > now_ms:
            decisions[index] = {"request_id":item["request_id"],"status":"rejected","reason":"not_due","replayed":False,"fence":None}
        else:
            pending.append((item["requested_ms"],item["request_id"],index,item))
    used = sum(x["units"] for x in active)
    for _, _, index, item in sorted(pending):
        if used + item["units"] <= capacity:
            lease = {"request_id":item["request_id"],"owner":item["owner"],"units":item["units"],"acquired_ms":now_ms,"expires_ms":now_ms+item["ttl_ms"],"fence":next_fence}
            active.append(lease); used += item["units"]
            decisions[index] = {"request_id":item["request_id"],"status":"granted","reason":None,"replayed":False,"fence":next_fence}; next_fence += 1
        else:
            decisions[index] = {"request_id":item["request_id"],"status":"rejected","reason":"capacity","replayed":False,"fence":None}
    return {"leases":sorted(active,key=lambda x:x["fence"]),"decisions":decisions,"next_fence":next_fence}
