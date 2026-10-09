TOKEN_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-_."
PATH_CHARS = TOKEN_CHARS + "=[]"


def _fail():
    raise ValueError()


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char in TOKEN_CHARS for char in value)
    )


def _path(value):
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.endswith("/")
        or "//" in value
    ):
        return False
    parts = value[1:].split("/")
    return all(
        part not in ("", ".", "..")
        and part.isascii()
        and all(char in PATH_CHARS for char in part)
        for part in parts
    )


def _scalar(value):
    return (
        value is None
        or isinstance(value, (str, bool))
        or (isinstance(value, int) and not isinstance(value, bool))
    )


def _path_map(value, allowed):
    return isinstance(value, dict) and all(
        path in allowed and _scalar(child) for path, child in value.items()
    )


def _sorted_paths(value):
    return (
        isinstance(value, list)
        and value == sorted(set(value))
        and all(_path(path) for path in value)
    )


def _validate(live, ownership, defaults, intents, policy):
    if (
        not isinstance(policy, dict)
        or set(policy) != {"allowed_paths", "protected_prefixes"}
        or not _sorted_paths(policy["allowed_paths"])
        or not _sorted_paths(policy["protected_prefixes"])
    ):
        _fail()
    allowed = set(policy["allowed_paths"])
    if (
        not _path_map(live, allowed)
        or not _path_map(defaults, allowed)
        or not isinstance(ownership, list)
        or not isinstance(intents, list)
    ):
        _fail()
    if ownership != sorted(
        ownership,
        key=lambda row: row["path"] if isinstance(row, dict) and "path" in row else "",
    ):
        _fail()
    owner_map = {}
    owner_keys = {"path", "managers"}
    for row in ownership:
        if (
            not isinstance(row, dict)
            or set(row) != owner_keys
            or row["path"] not in live
            or row["path"] in owner_map
            or not isinstance(row["managers"], list)
            or row["managers"] != sorted(set(row["managers"]))
            or not row["managers"]
            or any(not _token(manager) for manager in row["managers"])
        ):
            _fail()
        owner_map[row["path"]] = set(row["managers"])
    request_ids = set()
    intent_keys = {"request_id", "manager", "force", "fields"}
    for row in intents:
        if (
            not isinstance(row, dict)
            or set(row) != intent_keys
            or not _token(row["request_id"])
            or row["request_id"] in request_ids
            or not _token(row["manager"])
            or not isinstance(row["force"], bool)
            or not _path_map(row["fields"], allowed)
        ):
            _fail()
        request_ids.add(row["request_id"])
    return owner_map


def _protected(path, prefixes):
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def apply_intents(live, ownership, defaults, intents, policy):
    owner_map = _validate(live, ownership, defaults, intents, policy)
    current = dict(live)
    owners = {path: set(managers) for path, managers in owner_map.items()}
    decisions = []
    for intent in intents:
        manager = intent["manager"]
        fields = intent["fields"]
        conflicts = []
        for path, value in fields.items():
            others = owners.get(path, set()) - {manager}
            if path in current and current[path] != value and others:
                conflicts.append(path)
        conflicts = sorted(conflicts)
        protected = bool(
            intent["force"]
            and any(
                _protected(path, policy["protected_prefixes"]) for path in conflicts
            )
        )
        if conflicts and (not intent["force"] or protected):
            decisions.append(
                {
                    "request_id": intent["request_id"],
                    "manager": manager,
                    "status": "protected" if protected else "conflict",
                    "conflicts": conflicts,
                    "changed_paths": [],
                    "acquired_paths": [],
                    "released_paths": [],
                    "forced_paths": [],
                }
            )
            continue
        changed = set()
        acquired = set()
        released = set()
        forced = set()
        previous = {path for path, managers in owners.items() if manager in managers}
        for path in previous - set(fields):
            owners[path].remove(manager)
            released.add(path)
            if not owners[path]:
                owners.pop(path)
                if path in defaults:
                    if current.get(path) != defaults[path]:
                        changed.add(path)
                    current[path] = defaults[path]
                elif path in current:
                    current.pop(path)
                    changed.add(path)
        for path, value in fields.items():
            old_owners = owners.get(path, set())
            others = old_owners - {manager}
            if manager not in old_owners:
                acquired.add(path)
            if path not in current or current[path] != value:
                if others and intent["force"]:
                    forced.add(path)
                current[path] = value
                owners[path] = {manager}
                changed.add(path)
            else:
                owners.setdefault(path, set()).add(manager)
        decisions.append(
            {
                "request_id": intent["request_id"],
                "manager": manager,
                "status": "applied",
                "conflicts": conflicts,
                "changed_paths": sorted(changed),
                "acquired_paths": sorted(acquired),
                "released_paths": sorted(released),
                "forced_paths": sorted(forced),
            }
        )
    final_object = {path: current[path] for path in sorted(current)}
    final_ownership = [
        {"path": path, "managers": sorted(managers)}
        for path, managers in sorted(owners.items())
        if managers and path in current
    ]
    return {
        "object": final_object,
        "ownership": final_ownership,
        "decisions": decisions,
    }
