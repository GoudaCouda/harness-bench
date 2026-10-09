def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _etag(value):
    return isinstance(value, str) and len(value) >= 2 and value[0] == '"' and value[-1] == '"' and not value.startswith("W/")


def _restart(reason):
    return {"action": "restart", "reason": reason, "offset": 0}


def _range(value):
    if not isinstance(value, str) or not value.startswith("bytes ") or "/" not in value or "-" not in value:
        return None
    span, total = value[6:].split("/", 1)
    start, end = span.split("-", 1)
    if not (start.isdigit() and end.isdigit() and total.isdigit()):
        return None
    return int(start), int(end), int(total)


def reconcile_resume(manifest, checkpoint, response):
    if not isinstance(manifest, dict) or not isinstance(response, dict):
        raise ValueError("malformed envelope")
    size, etag, digest = manifest.get("size"), manifest.get("etag"), manifest.get("sha256")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0 or not _etag(etag) or not _hex(digest):
        raise ValueError("malformed manifest")
    if checkpoint is not None and not isinstance(checkpoint, dict):
        raise ValueError("malformed checkpoint")
    status, length = response.get("status"), response.get("body_length")
    if status not in (200, 206, 416) or not isinstance(length, int) or isinstance(length, bool) or length < 0:
        if isinstance(status, int) and isinstance(length, int) and not isinstance(length, bool) and length >= 0:
            return _restart("unsupported_status")
        raise ValueError("malformed response")
    if not _hex(response.get("body_sha256")) or not _etag(response.get("etag")):
        raise ValueError("malformed response")
    trusted, offset, prefix = False, 0, None
    if checkpoint is not None:
        offset, prefix = checkpoint.get("offset"), checkpoint.get("prefix_sha256")
        if not (isinstance(checkpoint.get("temp_exists"), bool) and isinstance(offset, int) and not isinstance(offset, bool) and _etag(checkpoint.get("etag")) and _hex(prefix)):
            raise ValueError("malformed checkpoint")
        trusted = checkpoint["temp_exists"] and 0 <= offset <= size and checkpoint["etag"] == etag
    if response["etag"] != etag:
        return _restart("validator_mismatch")
    if status == 200:
        return {"action": "complete", "reason": "full_verified", "offset": size} if length == size and response["body_sha256"] == digest else _restart("full_response_invalid")
    if not trusted:
        return _restart("checkpoint_untrusted")
    if status == 416:
        return {"action": "complete", "reason": "already_complete", "offset": size} if offset == size and prefix == digest and response.get("content_range") == "bytes */" + str(size) else _restart("range_not_satisfiable")
    parsed = _range(response.get("content_range"))
    if parsed is None:
        return _restart("content_range_invalid")
    start, end, total = parsed
    if offset >= size or start != offset or end < start or end - start + 1 != length or total != size or end >= size:
        return _restart("content_range_invalid")
    new_offset = end + 1
    if new_offset == size:
        return {"action": "complete", "reason": "range_complete", "offset": size} if response.get("assembled_sha256") == digest else _restart("final_digest_mismatch")
    return {"action": "append", "reason": "range_verified", "offset": new_offset}
