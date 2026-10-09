def _error():
    raise ValueError()


def _int(value, minimum=None):
    if not isinstance(value, int) or isinstance(value, bool) or (minimum is not None and value < minimum):
        _error()
    return value


def _string(value, nonempty=True):
    if not isinstance(value, str) or (nonempty and not value):
        _error()
    return value


def _host(value):
    _string(value)
    if value != value.lower() or not value.isascii() or value.startswith(".") or value.endswith(".") or ".." in value:
        _error()
    parts = value.split(".")
    if any(not part or part.startswith("-") or part.endswith("-") or not part.replace("-", "").isalnum() for part in parts):
        _error()
    return value


def _path_match(request_path, cookie_path):
    if request_path == cookie_path:
        return True
    if not request_path.startswith(cookie_path):
        return False
    return cookie_path.endswith("/") or (len(request_path) > len(cookie_path) and request_path[len(cookie_path)] == "/")


def _domain_match(host, domain):
    return host == domain or host.endswith("." + domain)


def _default_path(path):
    if not path.startswith("/") or path.count("/") <= 1:
        return "/"
    return path[:path.rfind("/")] or "/"


def _validate(jar, responses, requests, policy):
    if not isinstance(jar, list) or not isinstance(responses, list) or not isinstance(requests, list) or not isinstance(policy, dict) or set(policy) != {"public_suffixes"}:
        _error()
    suffixes = policy["public_suffixes"]
    if not isinstance(suffixes, list) or len(suffixes) != len(set(suffixes)):
        _error()
    for suffix in suffixes:
        _host(suffix)
    cookie_keys = {"name", "value", "domain", "path", "host_only", "secure", "http_only", "expires_at", "creation_index"}
    seen = set()
    indexes = set()
    prepared = []
    for row in jar:
        if not isinstance(row, dict) or set(row) != cookie_keys:
            _error()
        name = _string(row["name"])
        value = _string(row["value"], False)
        domain = _host(row["domain"])
        path = _string(row["path"])
        if not path.startswith("/") or any(not isinstance(row[key], bool) for key in ("host_only", "secure", "http_only")):
            _error()
        expiry = row["expires_at"]
        if expiry is not None:
            _int(expiry)
        index = _int(row["creation_index"], 0)
        identity = (name, domain, path)
        if identity in seen or index in indexes:
            _error()
        seen.add(identity)
        indexes.add(index)
        prepared.append(dict(row))
    response_keys = {"response_id", "scheme", "host", "path", "received_at", "set_cookie"}
    prior = None
    ids = set()
    for row in responses:
        if not isinstance(row, dict) or set(row) != response_keys:
            _error()
        rid = _string(row["response_id"])
        if rid in ids:
            _error()
        ids.add(rid)
        if row["scheme"] not in ("http", "https"):
            _error()
        _host(row["host"])
        if not isinstance(row["path"], str) or not row["path"].startswith("/"):
            _error()
        at = _int(row["received_at"], 0)
        if prior is not None and at < prior:
            _error()
        prior = at
        if not isinstance(row["set_cookie"], list) or any(not isinstance(line, str) or not line for line in row["set_cookie"]):
            _error()
    request_keys = {"request_id", "scheme", "host", "path", "at", "http_api"}
    request_ids = set()
    request_prior = prior
    for row in requests:
        if not isinstance(row, dict) or set(row) != request_keys:
            _error()
        qid = _string(row["request_id"])
        if qid in request_ids:
            _error()
        request_ids.add(qid)
        if row["scheme"] not in ("http", "https"):
            _error()
        _host(row["host"])
        if not isinstance(row["path"], str) or not row["path"].startswith("/") or not isinstance(row["http_api"], bool):
            _error()
        at = _int(row["at"], 0)
        if request_prior is not None and at < request_prior:
            _error()
        request_prior = at
    return prepared, set(suffixes)


def _parse(line):
    pieces = [piece.strip() for piece in line.split(";")]
    if not pieces or "=" not in pieces[0]:
        return None, "malformed_pair"
    name, value = pieces[0].split("=", 1)
    token = "!#$%&'*+-.^_`|~"
    if not name or not name.isascii() or any(not (char.isalnum() or char in token) for char in name):
        return None, "malformed_name"
    if not value.isascii() or any(ord(char) < 33 or ord(char) > 126 or char == ";" for char in value):
        return None, "malformed_value"
    attrs = {}
    flags = set()
    for piece in pieces[1:]:
        if not piece:
            continue
        if "=" in piece:
            key, attr_value = piece.split("=", 1)
            key = key.strip().lower()
            attr_value = attr_value.strip()
            if not key:
                return None, "malformed_attribute"
            attrs[key] = attr_value
            flags.discard(key)
        else:
            key = piece.strip().lower()
            if not key:
                continue
            flags.add(key)
            attrs.pop(key, None)
    for key in ("domain", "path", "max-age", "expires"):
        if key in flags:
            return None, "malformed_" + key.replace("-", "_")
    if "max-age" in attrs:
        raw = attrs["max-age"]
        if not raw or not raw.lstrip("-").isdigit():
            return None, "malformed_max_age"
    if "expires" in attrs:
        raw = attrs["expires"]
        if not raw or not raw.lstrip("-").isdigit():
            return None, "malformed_expires"
    return {"name": name, "value": value, "attrs": attrs, "secure": "secure" in flags or "secure" in attrs, "http_only": "httponly" in flags or "httponly" in attrs}, None


def reconcile_cookie_jar(jar, responses, requests, policy):
    store, public_suffixes = _validate(jar, responses, requests, policy)
    next_index = max([row["creation_index"] for row in store], default=-1) + 1
    events = []

    def expire(at):
        store[:] = [row for row in store if row["expires_at"] is None or row["expires_at"] > at]

    for response in responses:
        at = response["received_at"]
        expire(at)
        for line_index, line in enumerate(response["set_cookie"]):
            parsed, reason = _parse(line)
            base = {"response_id": response["response_id"], "line_index": line_index}
            if parsed is None:
                events.append({**base, "action": "rejected", "reason": reason})
                continue
            attrs = parsed["attrs"]
            if "domain" in attrs:
                domain = attrs["domain"].lower()
                if domain.startswith("."):
                    domain = domain[1:]
                try:
                    _host(domain)
                except ValueError:
                    events.append({**base, "action": "rejected", "reason": "invalid_domain"})
                    continue
                if domain in public_suffixes:
                    events.append({**base, "action": "rejected", "reason": "public_suffix"})
                    continue
                if not _domain_match(response["host"], domain):
                    events.append({**base, "action": "rejected", "reason": "domain_scope"})
                    continue
                host_only = False
            else:
                domain = response["host"]
                host_only = True
            raw_path = attrs.get("path")
            path = raw_path if raw_path and raw_path.startswith("/") else _default_path(response["path"])
            if parsed["secure"] and response["scheme"] != "https":
                events.append({**base, "action": "rejected", "reason": "insecure_secure"})
                continue
            identity = (parsed["name"], domain, path)
            existing = next((row for row in store if (row["name"], row["domain"], row["path"]) == identity), None)
            expiry = None
            delete_reason = None
            if "max-age" in attrs:
                delta = int(attrs["max-age"])
                if delta <= 0:
                    delete_reason = "max_age"
                else:
                    expiry = at + delta
            elif "expires" in attrs:
                expiry = int(attrs["expires"])
                if expiry <= at:
                    delete_reason = "expired"
            if delete_reason:
                store[:] = [row for row in store if (row["name"], row["domain"], row["path"]) != identity]
                events.append({**base, "action": "deleted", "reason": delete_reason})
                continue
            creation_index = existing["creation_index"] if existing else next_index
            if existing is None:
                next_index += 1
            store[:] = [row for row in store if (row["name"], row["domain"], row["path"]) != identity]
            store.append({"name": parsed["name"], "value": parsed["value"], "domain": domain, "path": path, "host_only": host_only, "secure": parsed["secure"], "http_only": parsed["http_only"], "expires_at": expiry, "creation_index": creation_index})
            events.append({**base, "action": "stored", "reason": "replaced" if existing else "new"})

    request_rows = []
    for request in requests:
        expire(request["at"])
        chosen = []
        for row in store:
            domain_ok = request["host"] == row["domain"] if row["host_only"] else _domain_match(request["host"], row["domain"])
            if not domain_ok or not _path_match(request["path"], row["path"]):
                continue
            if row["secure"] and request["scheme"] != "https":
                continue
            if row["http_only"] and not request["http_api"]:
                continue
            chosen.append(row)
        chosen.sort(key=lambda row: (-len(row["path"]), row["creation_index"]))
        request_rows.append({"request_id": request["request_id"], "cookie_names": [row["name"] for row in chosen], "cookie_header": "; ".join(row["name"] + "=" + row["value"] for row in chosen)})
    store.sort(key=lambda row: (row["domain"], row["path"], row["name"]))
    return {"store": store, "requests": request_rows, "events": events}
