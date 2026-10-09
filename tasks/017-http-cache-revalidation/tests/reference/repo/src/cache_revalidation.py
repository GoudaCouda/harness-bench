def _header_name(value):
    if not isinstance(value, str) or not value or value != value.casefold():
        return False
    return all(character.isalnum() or character == "-" for character in value)


def _headers(value):
    if not isinstance(value, dict):
        raise ValueError("header map")
    if not all(_header_name(key) and isinstance(item, str) for key, item in value.items()):
        raise ValueError("header entry")


def _one_tag(value):
    value = value.strip()
    if value.startswith("W/"):
        value = value[2:]
    if len(value) < 2 or value[0] != '"' or value[-1] != '"' or '"' in value[1:-1]:
        return None
    if not all(33 <= ord(character) <= 126 and character != '"' for character in value[1:-1]):
        return None
    return value[1:-1]


def _tag_list(value):
    value = value.strip()
    if value == "*":
        return ["*"]
    parts = []
    current = ""
    quoted = False
    for character in value:
        if character == '"':
            quoted = not quoted
        if character == "," and not quoted:
            parts.append(current)
            current = ""
        else:
            current += character
    parts.append(current)
    tags = [_one_tag(part) for part in parts]
    if quoted or not tags or any(tag is None for tag in tags):
        return None
    return tags


def _http_date(value):
    if not isinstance(value, str) or len(value) != 29:
        return None
    if value[3:5] != ", " or value[7] != " " or value[11] != " " or value[16] != " " or value[19] != ":" or value[22] != ":" or value[25:] != " GMT":
        return None
    if value[0:3] not in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
        return None
    months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    if value[8:11] not in months:
        return None
    digits = value[5:7] + value[12:16] + value[17:19] + value[20:22] + value[23:25]
    if not digits.isdigit():
        return None
    day = int(value[5:7])
    year = int(value[12:16])
    hour = int(value[17:19])
    minute = int(value[20:22])
    second = int(value[23:25])
    month = months[value[8:11]]
    days = [31,28,31,30,31,30,31,31,30,31,30,31]
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days[1] = 29
    if year < 1 or day < 1 or day > days[month - 1] or hour > 23 or minute > 59 or second > 59:
        return None
    return (year, month, day, hour, minute, second)


def evaluate_cache_request(request, stored):
    if not isinstance(request, dict) or set(request.keys()) != {"method", "uri", "headers"}:
        raise ValueError("request schema")
    if not isinstance(stored, dict) or set(stored.keys()) != {"uri", "request_headers", "response_headers"}:
        raise ValueError("stored schema")
    if not isinstance(request["method"], str) or not request["method"] or not isinstance(request["uri"], str) or not request["uri"] or not isinstance(stored["uri"], str) or not stored["uri"]:
        raise ValueError("request identity")
    _headers(request["headers"])
    _headers(stored["request_headers"])
    response = stored["response_headers"]
    if not isinstance(response, dict) or set(response.keys()) != {"etag", "last-modified", "vary"}:
        raise ValueError("response schema")
    if not all(value is None or isinstance(value, str) for value in response.values()):
        raise ValueError("response header")
    forward = {"action":"forward", "status":None, "reason":""}
    if request["method"] not in ("GET", "HEAD"):
        forward["reason"] = "method_not_cacheable"
        return forward
    if request["uri"] != stored["uri"]:
        forward["reason"] = "uri_miss"
        return forward
    vary = response["vary"]
    if vary:
        names = [name.strip().casefold() for name in vary.split(",")]
        if names == ["*"]:
            forward["reason"] = "vary_star"
            return forward
        if not names or any(not _header_name(name) for name in names):
            forward["reason"] = "invalid_vary"
            return forward
        for name in names:
            if request["headers"].get(name, "").strip() != stored["request_headers"].get(name, "").strip():
                forward["reason"] = "vary_miss"
                return forward
    if "if-none-match" in request["headers"]:
        candidates = _tag_list(request["headers"]["if-none-match"])
        current = _one_tag(response["etag"]) if response["etag"] is not None else None
        if candidates is None:
            forward["reason"] = "invalid_etag"
            return forward
        if candidates == ["*"]:
            return {"action":"not_modified", "status":304, "reason":"etag_match"}
        if current is None:
            forward["reason"] = "invalid_etag"
            return forward
        if current in candidates:
            return {"action":"not_modified", "status":304, "reason":"etag_match"}
        forward["reason"] = "etag_miss"
        return forward
    if "if-modified-since" in request["headers"]:
        requested = _http_date(request["headers"]["if-modified-since"])
        modified = _http_date(response["last-modified"])
        if requested is None or modified is None:
            forward["reason"] = "invalid_date"
            return forward
        if modified <= requested:
            return {"action":"not_modified", "status":304, "reason":"not_modified_since"}
        forward["reason"] = "date_miss"
        return forward
    forward["reason"] = "no_precondition"
    return forward
