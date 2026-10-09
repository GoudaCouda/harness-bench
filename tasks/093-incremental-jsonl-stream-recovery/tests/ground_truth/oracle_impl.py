from copy import deepcopy
import json
import math


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _json_value(value, depth=0):
    if value is None or isinstance(value, (str, bool)) or _integer(value):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return depth < 8 and all(_json_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return depth < 8 and all(
            isinstance(key, str) and _json_value(item, depth + 1)
            for key, item in value.items()
        )
    return False


def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _file_id(value):
    return isinstance(value, str) and bool(value)


def _pending_text(value):
    return isinstance(value, str) and all(32 <= ord(char) <= 126 for char in value)


def _segment_text(value):
    return isinstance(value, str) and all(
        char in "\r\n" or 32 <= ord(char) <= 126 for char in value
    )


def _preflight(checkpoint, segments, policy):
    if (
        not _exact(policy, ("max_pending_chars",))
        or not _integer(policy["max_pending_chars"])
        or policy["max_pending_chars"] <= 0
    ):
        raise ValueError("invalid policy")
    if (
        not _exact(checkpoint, ("file_id", "offset", "pending", "last_record_id"))
        or not _file_id(checkpoint["file_id"])
        or not _integer(checkpoint["offset"])
        or checkpoint["offset"] < 0
        or not _pending_text(checkpoint["pending"])
        or len(checkpoint["pending"]) > policy["max_pending_chars"]
        or len(checkpoint["pending"]) > checkpoint["offset"]
        or not _integer(checkpoint["last_record_id"])
        or checkpoint["last_record_id"] < 0
    ):
        raise ValueError("invalid checkpoint")
    if not isinstance(segments, list):
        raise ValueError("invalid segments")
    file_id = checkpoint["file_id"]
    offset = checkpoint["offset"]
    pending = checkpoint["pending"]
    for segment in segments:
        if (
            not _exact(segment, ("file_id", "start", "data", "eof"))
            or not _file_id(segment["file_id"])
            or not _integer(segment["start"])
            or segment["start"] < 0
            or not _segment_text(segment["data"])
            or not isinstance(segment["eof"], bool)
        ):
            raise ValueError("invalid segment")
        if segment["file_id"] == file_id:
            if segment["start"] != offset:
                raise ValueError("offset mismatch")
        else:
            if segment["start"] != 0:
                raise ValueError("rotation must start at zero")
            file_id, offset, pending = segment["file_id"], 0, ""
        offset += len(segment["data"])
        pending = (pending + segment["data"]).split("\n")[-1]
        if len(pending) > policy["max_pending_chars"]:
            raise ValueError("pending limit")
        if segment["eof"]:
            pending = ""


def consume_segments(checkpoint, segments, policy):
    _preflight(checkpoint, segments, policy)
    current = deepcopy(checkpoint)
    records = []
    quarantine = []
    for segment in segments:
        if segment["file_id"] != current["file_id"]:
            if current["pending"]:
                quarantine.append(
                    {
                        "file_id": current["file_id"],
                        "offset": current["offset"] - len(current["pending"]),
                        "reason": "truncated_on_rotation",
                    }
                )
            current = {
                "file_id": segment["file_id"],
                "offset": 0,
                "pending": "",
                "last_record_id": current["last_record_id"],
            }
        base = current["offset"] - len(current["pending"])
        buffer = current["pending"] + segment["data"]
        current["offset"] += len(segment["data"])
        parts = buffer.split("\n")
        line_offset = base
        for raw in parts[:-1]:
            line = raw[:-1] if raw.endswith("\r") else raw
            if not line:
                quarantine.append(
                    {
                        "file_id": current["file_id"],
                        "offset": line_offset,
                        "reason": "empty_line",
                    }
                )
            else:
                try:
                    value = json.loads(line)
                except Exception:
                    value = None
                valid = (
                    _exact(value, ("id", "payload"))
                    and _integer(value["id"])
                    and value["id"] > 0
                    and _json_value(value["payload"])
                )
                if not valid:
                    quarantine.append(
                        {
                            "file_id": current["file_id"],
                            "offset": line_offset,
                            "reason": "malformed_record",
                        }
                    )
                elif value["id"] > current["last_record_id"]:
                    records.append(deepcopy(value))
                    current["last_record_id"] = value["id"]
            line_offset += len(raw) + 1
        current["pending"] = parts[-1]
        if segment["eof"] and current["pending"]:
            quarantine.append(
                {
                    "file_id": current["file_id"],
                    "offset": current["offset"] - len(current["pending"]),
                    "reason": "truncated_at_eof",
                }
            )
            current["pending"] = ""
    return {"records": records, "quarantine": quarantine, "checkpoint": current}
