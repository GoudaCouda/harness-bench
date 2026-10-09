"""Cross-platform archive extraction preflight."""


def plan_extraction(entries, policy):
    """Return safe normalized entries or reject the complete manifest."""

    if not isinstance(entries, list) or not isinstance(policy, dict):
        raise ValueError("invalid preflight input")
    case_sensitive = policy.get("case_sensitive")
    if not isinstance(case_sensitive, bool):
        raise ValueError("invalid case policy")
    allowed_types = policy.get("allowed_types")
    if not isinstance(allowed_types, list) or set(allowed_types) != {"file", "dir"}:
        raise ValueError("invalid type policy")

    limits = []
    for key in ("max_files", "max_file_bytes", "max_total_bytes"):
        value = policy.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("invalid resource policy")
        limits.append(value)
    max_files, max_file_bytes, max_total_bytes = limits

    planned = []
    seen = set()
    path_types = {}
    file_count = 0
    total_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry.keys()) != {"path", "type", "size"}:
            raise ValueError("invalid archive member")
        path = entry.get("path")
        kind = entry.get("type")
        size = entry.get("size")
        if not isinstance(path, str) or not path:
            raise ValueError("invalid member path")
        if "\\" in path or path.startswith("/"):
            raise ValueError("non-portable member path")
        if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
            raise ValueError("absolute drive path")
        for character in path:
            if ord(character) < 32 or ord(character) == 127:
                raise ValueError("control character in path")
        components = path.split("/")
        if any(component in {"", ".", ".."} for component in components):
            raise ValueError("unsafe path component")
        if kind not in allowed_types:
            raise ValueError("unsafe member type")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("invalid member size")
        if kind == "dir" and size != 0:
            raise ValueError("directory has content size")
        if kind == "file" and size > max_file_bytes:
            raise ValueError("file exceeds size budget")

        identity = path if case_sensitive else path.casefold()
        if identity in seen:
            raise ValueError("member path collision")
        seen.add(identity)
        path_types[identity] = kind
        if kind == "file":
            file_count += 1
            total_bytes += size
        planned.append({"path": path, "type": kind, "size": size})

    identities = sorted(path_types.keys())
    for identity in identities:
        if path_types[identity] != "file":
            continue
        prefix = identity + "/"
        for other in identities:
            if other.startswith(prefix):
                raise ValueError("file is parent of another member")
    if file_count > max_files or total_bytes > max_total_bytes:
        raise ValueError("archive exceeds resource budget")
    return planned
