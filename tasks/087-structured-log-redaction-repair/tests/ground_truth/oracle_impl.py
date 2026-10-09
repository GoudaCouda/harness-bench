import re


BEARER = re.compile(
    r"\bBearer(?P<spaces> +)(?P<secret>[A-Za-z0-9._~+/=\-]+)", re.IGNORECASE
)
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://(?P<secret>[^\s/@:]+:[^\s/@]+)@")
WORD = "A-Za-z0-9_"


def _policy(policy):
    if not isinstance(policy, dict) or set(policy) != {
        "sensitive_keys",
        "replacement",
        "text_assignments",
    }:
        raise ValueError("invalid policy shape")
    replacement = policy["replacement"]
    if not isinstance(replacement, str) or not replacement:
        raise ValueError("invalid replacement")
    normalized = []
    for field in ("sensitive_keys", "text_assignments"):
        values = policy[field]
        if not isinstance(values, list) or not values:
            raise ValueError("invalid policy names")
        folded = []
        for value in values:
            if not isinstance(value, str) or not value:
                raise ValueError("invalid policy name")
            name = value.casefold()
            if name in folded:
                raise ValueError("duplicate policy name")
            folded.append(name)
        normalized.append(folded)
    if replacement.casefold() in normalized[0] + normalized[1]:
        raise ValueError("ambiguous replacement")
    return set(normalized[0]), policy["text_assignments"], replacement


def _pointer(parent, component):
    escaped = str(component).replace("~", "~0").replace("/", "~1")
    return parent + "/" + escaped


def _text(value, path, assignments, replacement):
    assignment = re.compile(
        r"(?<!["
        + WORD
        + r"])(?:"
        + "|".join(re.escape(name) for name in assignments)
        + r")(?!["
        + WORD
        + r"])(?: *)=(?: *)(?P<secret>[^\s,;]+)",
        re.IGNORECASE,
    )
    patterns = (
        (BEARER, "bearer_token"),
        (assignment, "assignment"),
        (URL, "url_userinfo"),
    )
    cursor = 0
    pieces = []
    findings = []
    while cursor < len(value):
        choices = []
        for priority, (pattern, kind) in enumerate(patterns):
            match = pattern.search(value, cursor)
            if match is not None:
                choices.append((match.start(), priority, match, kind))
        if not choices:
            pieces.append(value[cursor:])
            break
        _, _, match, kind = min(choices, key=lambda item: (item[0], item[1]))
        start, end = match.span("secret")
        pieces.append(value[cursor:start])
        secret = value[start:end]
        pieces.append(secret if secret == replacement else replacement)
        if secret != replacement:
            findings.append({"path": path, "kind": kind})
        cursor = end
    if cursor == len(value):
        pieces.append("")
    return "".join(pieces), findings


def _walk(value, path, depth, sensitive, assignments, replacement):
    if isinstance(value, dict):
        if depth > 12 or any(not isinstance(key, str) for key in value):
            raise ValueError("invalid object")
        result = {}
        findings = []
        for key, child in value.items():
            child_path = _pointer(path, key)
            if key.casefold() in sensitive:
                result[key] = child if child == replacement else replacement
                if child != replacement:
                    findings.append({"path": child_path, "kind": "sensitive_key"})
            else:
                clean, nested = _walk(
                    child,
                    child_path,
                    depth + 1,
                    sensitive,
                    assignments,
                    replacement,
                )
                result[key] = clean
                findings.extend(nested)
        return result, findings
    if isinstance(value, list):
        if depth > 12:
            raise ValueError("container depth exceeded")
        result = []
        findings = []
        for index, child in enumerate(value):
            clean, nested = _walk(
                child,
                _pointer(path, index),
                depth + 1,
                sensitive,
                assignments,
                replacement,
            )
            result.append(clean)
            findings.extend(nested)
        return result, findings
    if isinstance(value, str):
        return _text(value, path, assignments, replacement)
    if value is None or type(value) is bool or type(value) is int:
        return value, []
    if (
        type(value) is float
        and value == value
        and value not in (float("inf"), float("-inf"))
    ):
        return value, []
    raise ValueError("non-JSON value")


def redact_event(event, policy):
    sensitive, assignments, replacement = _policy(policy)
    if not isinstance(event, dict):
        raise ValueError("event must be an object")
    clean, findings = _walk(event, "", 1, sensitive, assignments, replacement)
    return {"event": clean, "redactions": findings}
