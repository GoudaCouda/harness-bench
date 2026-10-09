def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_." for char in value)
    )


def _text(value):
    return isinstance(value, str) and bool(value) and value.isascii()


def _strings(values, token=False):
    return (
        isinstance(values, list)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and (
            all(_token(value) for value in values)
            if token
            else all(_text(value) for value in values)
        )
    )


def _load_schemas(values):
    if not isinstance(values, list):
        raise ValueError("invalid schemas")
    schema_keys = ("schema_id", "direction", "required", "properties", "discriminator")
    property_keys = ("name", "type", "enum", "nullable", "read_only", "write_only")
    discriminator_keys = ("property", "mappings")
    mapping_keys = ("value", "schema")
    result = {}
    order = []
    for schema in values:
        if (
            not _exact(schema, schema_keys)
            or not _token(schema["schema_id"])
            or schema["direction"] not in ("request", "response")
            or not _strings(schema["required"], token=True)
            or not isinstance(schema["properties"], list)
        ):
            raise ValueError("invalid schema")
        properties = {}
        property_order = []
        for prop in schema["properties"]:
            if (
                not _exact(prop, property_keys)
                or not _token(prop["name"])
                or not _text(prop["type"])
                or (
                    prop["enum"] is not None
                    and not _strings(prop["enum"], token=False)
                )
                or not isinstance(prop["nullable"], bool)
                or not isinstance(prop["read_only"], bool)
                or not isinstance(prop["write_only"], bool)
                or (prop["read_only"] and prop["write_only"])
            ):
                raise ValueError("invalid property")
            property_order.append(prop["name"])
            properties[prop["name"]] = prop
        if (
            property_order != sorted(property_order)
            or len(set(property_order)) != len(property_order)
            or any(name not in properties for name in schema["required"])
        ):
            raise ValueError("invalid property ordering")
        discriminator = schema["discriminator"]
        if discriminator is not None:
            if (
                not _exact(discriminator, discriminator_keys)
                or discriminator["property"] not in properties
                or not isinstance(discriminator["mappings"], list)
            ):
                raise ValueError("invalid discriminator")
            mapping_order = []
            for mapping in discriminator["mappings"]:
                if (
                    not _exact(mapping, mapping_keys)
                    or not _text(mapping["value"])
                    or not _token(mapping["schema"])
                ):
                    raise ValueError("invalid mapping")
                mapping_order.append(mapping["value"])
            if mapping_order != sorted(mapping_order) or len(set(mapping_order)) != len(
                mapping_order
            ):
                raise ValueError("invalid mapping order")
        order.append(schema["schema_id"])
        result[schema["schema_id"]] = schema
    if order != sorted(order) or len(set(order)) != len(order):
        raise ValueError("schemas must be sorted and unique")
    return result


def _active(prop, direction):
    return not prop["read_only"] if direction == "request" else not prop["write_only"]


def _finding(schema_id, path, direction, status, reason):
    return {
        "schema_id": schema_id,
        "path": path,
        "direction": direction,
        "status": status,
        "reason": reason,
    }


def _property_finding(schema_id, direction, name, old, new, old_required, new_required, policy):
    old_active = old is not None and _active(old, direction)
    new_active = new is not None and _active(new, direction)
    if not old_active and not new_active:
        return None
    if not old_active:
        breaking = direction == "request" and new_required
        return _finding(
            schema_id,
            name,
            direction,
            "breaking" if breaking else "compatible",
            "required_added" if breaking else "property_added",
        )
    if not new_active:
        breaking = direction == "response" or policy[
            "reject_unknown_request_properties"
        ]
        return _finding(
            schema_id,
            name,
            direction,
            "breaking" if breaking else "compatible",
            "property_removed",
        )
    if old["type"] != new["type"]:
        return _finding(schema_id, name, direction, "breaking", "type_changed")
    if old_required != new_required:
        breaking = (direction == "request" and new_required) or (
            direction == "response" and old_required
        )
        reason = "required_added" if new_required else "required_removed"
        return _finding(
            schema_id, name, direction, "breaking" if breaking else "compatible", reason
        )
    if old["enum"] != new["enum"]:
        if direction == "request":
            narrowed = new["enum"] is not None and (
                old["enum"] is None or not set(old["enum"]).issubset(set(new["enum"]))
            )
            return _finding(
                schema_id,
                name,
                direction,
                "breaking" if narrowed else "compatible",
                "enum_narrowed" if narrowed else "enum_changed",
            )
        widened = old["enum"] is not None and (
            new["enum"] is None or not set(new["enum"]).issubset(set(old["enum"]))
        )
        breaking = widened and policy["closed_response_enums"]
        return _finding(
            schema_id,
            name,
            direction,
            "breaking" if breaking else "compatible",
            "enum_widened" if breaking else "enum_changed",
        )
    if old["nullable"] != new["nullable"]:
        breaking = (direction == "request" and old["nullable"] and not new["nullable"]) or (
            direction == "response" and not old["nullable"] and new["nullable"]
        )
        reason = "nullable_widened" if new["nullable"] else "nullable_narrowed"
        return _finding(
            schema_id, name, direction, "breaking" if breaking else "compatible", reason
        )
    return None


def _discriminator_finding(schema_id, direction, old, new, new_required, policy):
    if old is None and new is None:
        return None
    if new is None:
        return _finding(
            schema_id, "$discriminator", direction, "breaking", "discriminator_removed"
        )
    if old is None:
        breaking = direction == "response" and policy["closed_response_variants"]
        return _finding(
            schema_id,
            "$discriminator",
            direction,
            "breaking" if breaking else "compatible",
            "discriminator_added",
        )
    if old["property"] != new["property"]:
        return _finding(
            schema_id,
            "$discriminator",
            direction,
            "breaking",
            "discriminator_property_changed",
        )
    if policy["require_discriminator_property"] and new["property"] not in new_required:
        return _finding(
            schema_id,
            "$discriminator",
            direction,
            "breaking",
            "discriminator_not_required",
        )
    old_values = set(item["value"] for item in old["mappings"])
    new_values = set(item["value"] for item in new["mappings"])
    if not old_values.issubset(new_values):
        return _finding(
            schema_id,
            "$discriminator",
            direction,
            "breaking",
            "discriminator_mapping_removed",
        )
    if (
        direction == "response"
        and policy["closed_response_variants"]
        and not new_values.issubset(old_values)
    ):
        return _finding(
            schema_id,
            "$discriminator",
            direction,
            "breaking",
            "response_variant_added",
        )
    return _finding(
        schema_id,
        "$discriminator",
        direction,
        "compatible",
        "discriminator_preserved",
    )


def compare_api_schemas(old_schemas, new_schemas, policy):
    policy_keys = (
        "reject_unknown_request_properties",
        "closed_response_enums",
        "closed_response_variants",
        "require_discriminator_property",
    )
    if not _exact(policy, policy_keys) or not all(
        isinstance(policy[name], bool) for name in policy_keys
    ):
        raise ValueError("invalid policy")
    old_map = _load_schemas(old_schemas)
    new_map = _load_schemas(new_schemas)
    findings = []
    for schema_id in sorted(set(old_map) | set(new_map)):
        old = old_map.get(schema_id)
        new = new_map.get(schema_id)
        if old is None:
            findings.append(
                _finding(schema_id, "$schema", new["direction"], "compatible", "schema_added")
            )
            continue
        if new is None:
            findings.append(
                _finding(schema_id, "$schema", old["direction"], "breaking", "schema_removed")
            )
            continue
        if old["direction"] != new["direction"]:
            raise ValueError("schema direction changed")
        direction = old["direction"]
        old_props = {item["name"]: item for item in old["properties"]}
        new_props = {item["name"]: item for item in new["properties"]}
        for name in sorted(set(old_props) | set(new_props)):
            finding = _property_finding(
                schema_id,
                direction,
                name,
                old_props.get(name),
                new_props.get(name),
                name in old["required"],
                name in new["required"],
                policy,
            )
            if finding is not None:
                findings.append(finding)
        discriminator = _discriminator_finding(
            schema_id,
            direction,
            old["discriminator"],
            new["discriminator"],
            new["required"],
            policy,
        )
        if discriminator is not None:
            findings.append(discriminator)
    breaking = len([item for item in findings if item["status"] == "breaking"])
    return {
        "findings": findings,
        "summary": {
            "schema_count": len(set(old_map) | set(new_map)),
            "finding_count": len(findings),
            "breaking": breaking,
            "compatible": len(findings) - breaking,
            "release_status": "blocked" if breaking else "compatible",
        },
    }
