def _default_path(request_path):
    if request_path.count("/") <= 1:
        return "/"
    return request_path.rsplit("/", 1)[0] or "/"


def _domain_match(host, domain):
    return host == domain or host.endswith("." + domain)


def _path_match(request_path, cookie_path):
    return request_path == cookie_path or (
        request_path.startswith(cookie_path)
        and (cookie_path.endswith("/") or request_path[len(cookie_path)] == "/")
    )


def _parse_set_cookie(line):
    parts = [part.strip() for part in line.split(";")]
    if not parts or "=" not in parts[0]:
        return None
    name, value = parts[0].split("=", 1)
    attrs = {}
    flags = set()
    for part in parts[1:]:
        if "=" in part:
            key, attr_value = part.split("=", 1)
            attrs[key.strip().lower()] = attr_value.strip()
        elif part:
            flags.add(part.lower())
    return name, value, attrs, flags


def reconcile_cookie_jar(jar, responses, requests, policy):
    """Replay captured Set-Cookie headers, then prepare request headers.

    The seed handles the ordinary host/path and expiry workflow.  It still has
    an incident-era defect: Domain attributes are accepted without checking
    public-suffix or origin scope, and malformed records are not rejected
    atomically.
    """
    store = [dict(cookie) for cookie in jar]
    events = []
    next_index = max((row["creation_index"] for row in store), default=-1) + 1
    for response in responses:
        at = response["received_at"]
        store = [row for row in store if row["expires_at"] is None or row["expires_at"] > at]
        for line_index, line in enumerate(response["set_cookie"]):
            parsed = _parse_set_cookie(line)
            if parsed is None:
                events.append({"response_id": response["response_id"], "line_index": line_index, "action": "rejected", "reason": "malformed_pair"})
                continue
            name, value, attrs, flags = parsed
            domain = attrs.get("domain", response["host"]).lower().lstrip(".")
            host_only = "domain" not in attrs
            path = attrs.get("path") or _default_path(response["path"])
            identity = (name, domain, path)
            existing = next((row for row in store if (row["name"], row["domain"], row["path"]) == identity), None)
            delta = int(attrs["max-age"]) if "max-age" in attrs else None
            expires_at = at + delta if delta is not None else int(attrs["expires"]) if "expires" in attrs else None
            store = [row for row in store if (row["name"], row["domain"], row["path"]) != identity]
            if delta is not None and delta <= 0 or expires_at is not None and expires_at <= at:
                events.append({"response_id": response["response_id"], "line_index": line_index, "action": "deleted", "reason": "max_age" if delta is not None else "expired"})
                continue
            creation_index = existing["creation_index"] if existing else next_index
            next_index += existing is None
            store.append({"name": name, "value": value, "domain": domain, "path": path, "host_only": host_only, "secure": "secure" in flags, "http_only": "httponly" in flags, "expires_at": expires_at, "creation_index": creation_index})
            events.append({"response_id": response["response_id"], "line_index": line_index, "action": "stored", "reason": "replaced" if existing else "new"})

    rendered = []
    for request in requests:
        eligible = [row for row in store if (request["host"] == row["domain"] if row["host_only"] else _domain_match(request["host"], row["domain"])) and _path_match(request["path"], row["path"]) and (not row["secure"] or request["scheme"] == "https") and (not row["http_only"] or request["http_api"])]
        eligible.sort(key=lambda row: (-len(row["path"]), row["creation_index"]))
        rendered.append({"request_id": request["request_id"], "cookie_names": [row["name"] for row in eligible], "cookie_header": "; ".join(row["name"] + "=" + row["value"] for row in eligible)})
    return {"store": sorted(store, key=lambda row: (row["domain"], row["path"], row["name"])), "requests": rendered, "events": events}
