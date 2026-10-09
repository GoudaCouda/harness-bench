"""Typed configuration resolution for Edge Relay."""


def resolve_config(defaults, file_values, environment, cli_values, schema):
    """Return resolved values and winning source labels."""

    inputs = (defaults, file_values, environment, cli_values, schema)
    if not all(isinstance(value, dict) for value in inputs):
        raise ValueError("configuration inputs must be objects")
    names = set(schema.keys())
    if set(defaults.keys()) - names or set(file_values.keys()) - names:
        raise ValueError("unknown configuration key")
    if set(cli_values.keys()) - names:
        raise ValueError("unknown CLI key")

    env_to_name = {}
    base_keys = {"type", "nullable", "sensitive", "env"}
    for name in sorted(names):
        record = schema[name]
        if not isinstance(name, str) or not isinstance(record, dict):
            raise ValueError("invalid schema record")
        kind = record.get("type")
        expected = set(base_keys)
        if kind == "int":
            expected = expected | {"min", "max"}
        elif kind == "enum":
            expected = expected | {"choices"}
        elif kind == "string":
            expected = expected | {"allow_empty"}
        elif kind != "bool":
            raise ValueError("unsupported schema type")
        if set(record.keys()) != expected:
            raise ValueError("invalid schema shape")
        if not isinstance(record["nullable"], bool):
            raise ValueError("invalid nullable flag")
        if not isinstance(record["sensitive"], bool):
            raise ValueError("invalid sensitive flag")
        env_name = record["env"]
        if not isinstance(env_name, str) or not env_name.startswith("EDGE_"):
            raise ValueError("invalid environment name")
        if env_name in env_to_name:
            raise ValueError("duplicate environment name")
        env_to_name[env_name] = name
        if kind == "int":
            lower = record["min"]
            upper = record["max"]
            if not isinstance(lower, int) or isinstance(lower, bool):
                raise ValueError("invalid integer bounds")
            if not isinstance(upper, int) or isinstance(upper, bool) or lower > upper:
                raise ValueError("invalid integer bounds")
        if kind == "enum":
            choices = record["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError("invalid enum choices")
            if not all(isinstance(choice, str) for choice in choices):
                raise ValueError("invalid enum choices")
            if len(set(choices)) != len(choices):
                raise ValueError("duplicate enum choice")
        if kind == "string" and not isinstance(record["allow_empty"], bool):
            raise ValueError("invalid empty-string policy")

    for env_name, raw in environment.items():
        if not isinstance(env_name, str) or not isinstance(raw, str):
            raise ValueError("environment values must be strings")
        if env_name.startswith("EDGE_") and env_name not in env_to_name:
            raise ValueError("unknown service environment key")

    values = {}
    sources = {}
    for name in sorted(names):
        env_name = schema[name]["env"]
        if name in cli_values:
            raw = cli_values[name]
            source = "cli"
        elif env_name in environment:
            raw = environment[env_name]
            source = "environment"
        elif name in file_values:
            raw = file_values[name]
            source = "file"
        elif name in defaults:
            raw = defaults[name]
            source = "default"
        else:
            raise ValueError("required value is missing")

        record = schema[name]
        if source == "environment" and raw.casefold() == "null":
            raw = None
        if raw is None:
            if not record["nullable"]:
                raise ValueError("null is not allowed")
            parsed = None
        elif record["type"] == "int":
            if source == "environment":
                if not raw.isdigit():
                    raise ValueError("invalid environment integer")
                parsed = int(raw)
            else:
                if not isinstance(raw, int) or isinstance(raw, bool):
                    raise ValueError("invalid integer")
                parsed = raw
            if not record["min"] <= parsed <= record["max"]:
                raise ValueError("integer outside bounds")
        elif record["type"] == "bool":
            if source == "environment":
                lowered = raw.casefold()
                if lowered not in {"true", "false"}:
                    raise ValueError("invalid environment boolean")
                parsed = lowered == "true"
            else:
                if not isinstance(raw, bool):
                    raise ValueError("invalid boolean")
                parsed = raw
        elif record["type"] == "enum":
            if not isinstance(raw, str) or raw not in record["choices"]:
                raise ValueError("invalid enum")
            parsed = raw
        else:
            if not isinstance(raw, str):
                raise ValueError("invalid string")
            if not raw and not record["allow_empty"]:
                raise ValueError("empty string is not allowed")
            parsed = raw
        values[name] = parsed
        sources[name] = source
    return {"values": values, "sources": sources}
