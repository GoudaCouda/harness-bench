def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char == "-" for char in value)
    )


def _typename(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value[0].isascii()
        and value[0].isupper()
        and all(char.isascii() and (char.isalnum() or char == "_") for char in value)
    )


def _cache_id(value, allowed):
    if not isinstance(value, str) or value.count(":") != 1:
        return False
    typename, key = value.split(":")
    return typename in allowed and _typename(typename) and _token(key)


def _field(value):
    return _token(value)


def _clone_value(value):
    if isinstance(value, dict):
        return {"$ref": value["$ref"]}
    if isinstance(value, list):
        return [{"$ref": item["$ref"]} for item in value]
    return value


def _valid_value(value, allowed):
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if _exact(value, ("$ref",)):
        return _cache_id(value["$ref"], allowed)
    if isinstance(value, list):
        return all(
            _exact(item, ("$ref",)) and _cache_id(item["$ref"], allowed)
            for item in value
        )
    return False


def _records(cache, allowed):
    if not isinstance(cache, dict):
        raise ValueError("cache must be an object")
    result = {}
    for cache_id, fields in cache.items():
        if not _cache_id(cache_id, allowed) or not isinstance(fields, dict):
            raise ValueError("invalid cache record")
        record = {}
        for field, value in fields.items():
            if not _field(field) or not _valid_value(value, allowed):
                raise ValueError("invalid field")
            record[field] = _clone_value(value)
        result[cache_id] = record
    return result


def _writes(value, allowed):
    if not isinstance(value, list):
        raise ValueError("writes must be a list")
    result = {}
    ids = []
    for item in value:
        if not _exact(item, ("id", "fields")) or not _cache_id(item["id"], allowed):
            raise ValueError("invalid write")
        if item["id"] in result or not isinstance(item["fields"], dict):
            raise ValueError("duplicate or invalid write")
        record = {}
        for field, field_value in item["fields"].items():
            if not _field(field) or not _valid_value(field_value, allowed):
                raise ValueError("invalid write field")
            record[field] = _clone_value(field_value)
        result[item["id"]] = record
        ids.append(item["id"])
    if ids != sorted(ids):
        raise ValueError("writes must be sorted")
    return result


def _patch(cache, writes):
    for cache_id, fields in writes.items():
        if cache_id not in cache:
            cache[cache_id] = {}
        cache[cache_id].update(
            {field: _clone_value(value) for field, value in fields.items()}
        )


def _project(base, active):
    result = _records(
        base, tuple(cache_id.split(":")[0] for cache_id in base) or ("Unused",)
    )
    # _records cannot validate against only base typenames when a layer introduces a new type.
    # Replace the validation clone above with a direct already-validated clone.
    result = {
        cache_id: {field: _clone_value(value) for field, value in fields.items()}
        for cache_id, fields in base.items()
    }
    for layer in active:
        if not layer["ignored"]:
            _patch(result, layer["records"])
    return result


def _references(value):
    if isinstance(value, dict):
        return [value["$ref"]]
    if isinstance(value, list):
        return [item["$ref"] for item in value]
    return []


def _closed(cache):
    return all(
        ref in cache
        for fields in cache.values()
        for value in fields.values()
        for ref in _references(value)
    )


def _rewrite_value(value, aliases):
    if isinstance(value, dict):
        return {"$ref": aliases.get(value["$ref"], value["$ref"])}
    if isinstance(value, list):
        return [{"$ref": aliases.get(item["$ref"], item["$ref"])} for item in value]
    return value


def _alias_cache(cache, aliases):
    for source, target in aliases.items():
        if source in cache:
            moved = cache[source]
            if target in cache:
                moved = {**moved, **cache[target]}
            cache[target] = moved
            del cache[source]
    for fields in cache.values():
        for field, value in list(fields.items()):
            fields[field] = _rewrite_value(value, aliases)


def _aliases(value, allowed):
    if not isinstance(value, dict):
        raise ValueError("aliases must be an object")
    result = {}
    for source, target in value.items():
        if (
            not _cache_id(source, allowed)
            or not _cache_id(target, allowed)
            or source == target
        ):
            raise ValueError("invalid alias")
        result[source] = target
    if len(set(result.values())) != len(result) or set(result) & set(result.values()):
        raise ValueError("alias collision or chain")
    return result


def _sorted_cache(cache):
    return {
        cache_id: {field: _clone_value(fields[field]) for field in sorted(fields)}
        for cache_id, fields in sorted(cache.items())
    }


def reconcile_cache(base, events, policy):
    if not _exact(policy, ("allowed_typenames", "max_active_layers")):
        raise ValueError("invalid policy")
    allowed = policy["allowed_typenames"]
    limit = policy["max_active_layers"]
    if (
        not isinstance(allowed, list)
        or allowed != sorted(allowed)
        or len(set(allowed)) != len(allowed)
        or not allowed
        or not all(_typename(item) for item in allowed)
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 20
    ):
        raise ValueError("invalid policy")
    canonical = _records(base, allowed)
    if not _closed(canonical) or not isinstance(events, list):
        raise ValueError("invalid base or events")
    active = []
    seen = set()
    audit = []
    for event in events:
        if not _exact(event, ("kind", "mutation_id", "mode", "writes", "aliases")):
            raise ValueError("invalid event")
        kind = event["kind"]
        mutation_id = event["mutation_id"]
        if not _token(mutation_id) or kind not in ("optimistic", "success", "error"):
            raise ValueError("invalid event identity")
        writes = _writes(event["writes"], allowed)
        aliases = _aliases(event["aliases"], allowed)
        status = ""
        if kind == "optimistic":
            if (
                event["mode"] not in ("apply", "ignore")
                or mutation_id in seen
                or aliases
            ):
                raise ValueError("invalid optimistic start")
            if event["mode"] == "ignore" and writes:
                raise ValueError("ignored layer cannot write")
            if len(active) >= limit:
                raise ValueError("too many active layers")
            seen.add(mutation_id)
            active.append(
                {
                    "mutation_id": mutation_id,
                    "ignored": event["mode"] == "ignore",
                    "records": writes,
                }
            )
            status = "ignored" if event["mode"] == "ignore" else "layer_started"
            if not _closed(_project(canonical, active)):
                raise ValueError("dangling optimistic reference")
        else:
            if event["mode"] != "resolve":
                raise ValueError("invalid resolution mode")
            matches = [
                index
                for index, layer in enumerate(active)
                if layer["mutation_id"] == mutation_id
            ]
            if len(matches) != 1:
                raise ValueError("unknown resolution")
            layer = active.pop(matches[0])
            if kind == "error":
                if writes or aliases:
                    raise ValueError("error resolution cannot write")
                status = "rolled_back"
            else:
                existing = set(canonical)
                for pending in active:
                    existing.update(pending["records"])
                existing.update(layer["records"])
                if any(source not in existing for source in aliases):
                    raise ValueError("unknown alias source")
                _alias_cache(canonical, aliases)
                for pending in active:
                    _alias_cache(pending["records"], aliases)
                _patch(canonical, writes)
                projected = _project(canonical, active)
                if any(target not in projected for target in aliases.values()):
                    raise ValueError("alias target missing")
                status = "committed"
            if not _closed(_project(canonical, active)):
                raise ValueError("dangling resolved reference")
        audit.append(
            {
                "mutation_id": mutation_id,
                "kind": kind,
                "status": status,
                "active_layers": [layer["mutation_id"] for layer in active],
            }
        )
    visible = _project(canonical, active)
    if not _closed(visible):
        raise ValueError("dangling final reference")
    return {
        "base": _sorted_cache(canonical),
        "visible": _sorted_cache(visible),
        "audit": audit,
    }
