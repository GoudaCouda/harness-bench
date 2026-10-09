import re

TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
SHA256 = re.compile(r"[0-9a-f]{64}")


def _printable(value):
    return isinstance(value, str) and value and all(32 <= ord(char) <= 126 for char in value)


def _safe_key(value):
    return _printable(value) and not value.startswith("/") and "\\" not in value and all(part not in ("", ".", "..") for part in value.split("/"))


def _verify(session):
    return {"object_key": session["object_key"], "object_size": session["object_size"], "checksum_sha256": session["full_checksum"]}


def _head(session):
    return {"op": "head_verify", **_verify(session)}


def plan_multipart_resume(session, local_parts, remote_pages):
    keys = {"upload_id", "object_key", "state", "part_count", "object_size", "minimum_part_size", "checksum_algorithm", "checksum_type", "full_checksum"}
    if not isinstance(session, dict) or set(session) != keys or not isinstance(session.get("upload_id"), str) or not TOKEN.fullmatch(session["upload_id"]) or not _safe_key(session.get("object_key")):
        raise ValueError("session")
    if session["state"] not in ("in_progress", "complete_unknown", "completed") or session["checksum_algorithm"] != "SHA256" or session["checksum_type"] != "COMPOSITE" or not isinstance(session["full_checksum"], str) or not SHA256.fullmatch(session["full_checksum"]):
        raise ValueError("policy")
    if any(type(session[name]) is not int or session[name] <= 0 for name in ("part_count", "object_size", "minimum_part_size")) or session["part_count"] > 10000 or not isinstance(local_parts, list) or len(local_parts) != session["part_count"] or not isinstance(remote_pages, list):
        raise ValueError("inventory")
    local = {}
    for part in local_parts:
        if not isinstance(part, dict) or set(part) != {"part_number", "size", "checksum_sha256"} or type(part["part_number"]) is not int or type(part["size"]) is not int or part["size"] <= 0 or not isinstance(part["checksum_sha256"], str) or not SHA256.fullmatch(part["checksum_sha256"]) or part["part_number"] in local or part["part_number"] < 1 or part["part_number"] > session["part_count"]:
            raise ValueError("local part")
        local[part["part_number"]] = part
    if set(local) != set(range(1, session["part_count"] + 1)) or sum(part["size"] for part in local.values()) != session["object_size"] or any(local[number]["size"] < session["minimum_part_size"] for number in range(1, session["part_count"])):
        raise ValueError("coverage")
    verification = _verify(session)
    if session["state"] != "in_progress":
        if remote_pages:
            raise ValueError("unexpected pages")
        return {"decision": "probe" if session["state"] == "complete_unknown" else "verify", "actions": [_head(session)], "reused_parts": [], "pending_parts": [], "verification": verification}
    if not remote_pages:
        raise ValueError("missing pages")
    remote = {}
    last = 0
    for index, page in enumerate(remote_pages, start=1):
        if not isinstance(page, dict) or set(page) != {"upload_id", "page", "is_truncated", "next_page", "parts"} or page["upload_id"] != session["upload_id"] or type(page["page"]) is not int or page["page"] != index or type(page["is_truncated"]) is not bool or not isinstance(page["parts"], list):
            raise ValueError("page")
        final = index == len(remote_pages)
        if (final and (page["is_truncated"] or page["next_page"] is not None)) or (not final and (not page["is_truncated"] or type(page["next_page"]) is not int or page["next_page"] != index + 1)):
            raise ValueError("pagination")
        for part in page["parts"]:
            if not isinstance(part, dict) or set(part) != {"part_number", "size", "checksum_sha256", "etag"} or type(part["part_number"]) is not int or type(part["size"]) is not int or part["size"] <= 0 or not isinstance(part["checksum_sha256"], str) or not SHA256.fullmatch(part["checksum_sha256"]) or not _printable(part["etag"]) or part["part_number"] <= last or part["part_number"] not in local:
                raise ValueError("remote part")
            last = part["part_number"]
            remote[last] = part
    reused, pending, actions = [], [], []
    for number in range(1, session["part_count"] + 1):
        source, listed = local[number], remote.get(number)
        if listed is not None and listed["size"] == source["size"] and listed["checksum_sha256"] == source["checksum_sha256"]:
            reused.append(number)
        else:
            pending.append(number)
            actions.append({"op": "upload_part", "upload_id": session["upload_id"], "part_number": number, "size": source["size"], "checksum_sha256": source["checksum_sha256"]})
    if pending:
        return {"decision": "resume", "actions": actions, "reused_parts": reused, "pending_parts": pending, "verification": verification}
    parts = [{"part_number": number, "etag": remote[number]["etag"]} for number in range(1, session["part_count"] + 1)]
    complete = {"op": "complete_multipart", "upload_id": session["upload_id"], "parts": parts, "checksum_sha256": session["full_checksum"], "object_size": session["object_size"]}
    return {"decision": "complete", "actions": [complete, _head(session)], "reused_parts": reused, "pending_parts": [], "verification": verification}
