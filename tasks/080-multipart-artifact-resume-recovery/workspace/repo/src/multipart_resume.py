def plan_multipart_resume(session, local_parts, remote_pages):
    """Broken planner: trusts the first page and completes immediately."""
    remote = remote_pages[0]["parts"] if remote_pages else []
    return {
        "decision": "complete",
        "actions": [{"op": "complete_multipart", "upload_id": session["upload_id"], "parts": [{"part_number": item["part_number"], "etag": item["etag"]} for item in remote]}],
        "reused_parts": [item["part_number"] for item in remote],
        "pending_parts": [],
        "verification": {"object_key": session["object_key"], "object_size": session["object_size"], "checksum_sha256": session["full_checksum"]},
    }
