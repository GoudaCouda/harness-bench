import json


def consume_segments(checkpoint, segments, policy):
    """Broken implementation: parses each chunk independently and trusts offsets."""
    records = []
    for segment in segments:
        for line in segment["data"].splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        checkpoint["file_id"] = segment["file_id"]
        checkpoint["offset"] += len(segment["data"])
    return {"records": records, "quarantine": [], "checkpoint": checkpoint}
