def reconcile_resume(manifest, checkpoint, response):
    size = manifest["size"]
    offset = checkpoint.get("offset", 0) if checkpoint else 0
    status = response["status"]
    if status == 206:
        new_offset = offset + response["body_length"]
        return {"action": "append", "reason": "range_verified", "offset": new_offset}
    if status == 416 and offset == size:
        return {"action": "complete", "reason": "already_complete", "offset": size}
    if status == 200:
        return {"action": "complete", "reason": "full_verified", "offset": size}
    return {"action": "restart", "reason": "unsupported_status", "offset": 0}
