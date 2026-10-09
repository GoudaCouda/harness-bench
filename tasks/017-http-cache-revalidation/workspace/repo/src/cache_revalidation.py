def evaluate_cache_request(request, stored):
    """Return whether one stored response can answer a conditional request."""
    request_tag = request["headers"].get("if-none-match")
    stored_tag = stored["response_headers"].get("etag")
    if request_tag == stored_tag:
        return {"action": "not_modified", "status": 304, "reason": "etag_match"}
    return {"action": "forward", "status": None, "reason": "no_match"}
