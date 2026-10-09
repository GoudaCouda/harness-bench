from copy import deepcopy
import math


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _exact(value, required, optional=()):
    return (
        isinstance(value, dict)
        and set(value) == set(required) | (set(value) & set(optional))
        and set(required) <= set(value)
        and set(value) <= set(required) | set(optional)
    )


def _json_value(value, depth=0):
    if value is None or isinstance(value, (str, bool)) or _integer(value):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return depth < 8 and all(_json_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return depth < 8 and all(
            isinstance(key, str) and _json_value(item, depth + 1)
            for key, item in value.items()
        )
    return False


def _extensions(value):
    return isinstance(value, dict) and all(
        isinstance(key, str)
        and key.startswith("x-")
        and len(key) > 2
        and _json_value(item)
        for key, item in value.items()
    )


def _name(value):
    return isinstance(value, str) and bool(value)


def _endpoint(value):
    return (
        isinstance(value, str)
        and value.startswith("https://")
        and len(value) > 8
        and not any(char.isspace() for char in value)
    )


def _retry(value):
    return _integer(value) and 0 <= value <= 10


def _region(value):
    return value is None or _name(value)


def _canonical(name, endpoint, retry_limit, region, features, extensions):
    return {
        "schema_version": 3,
        "identity": {"name": name},
        "connection": {
            "endpoint": endpoint,
            "retry_limit": retry_limit,
            "region": region,
        },
        "enabled_features": sorted(features),
        "extensions": deepcopy(extensions),
    }


def _migrate(document, defaults):
    version = document.get("schema_version")
    if not _integer(version):
        raise ValueError("invalid version")
    if version == 1:
        if not _exact(
            document,
            ("schema_version", "name", "endpoint"),
            ("retries", "region", "extensions"),
        ):
            raise ValueError("invalid v1 shape")
        retries = (
            defaults["retry_limit"]
            if "retries" not in document
            else (0 if document["retries"] is None else document["retries"])
        )
        region = defaults["region"] if "region" not in document else document["region"]
        extensions = document.get("extensions", {})
        if not (
            _name(document["name"])
            and _endpoint(document["endpoint"])
            and _retry(retries)
            and _region(region)
            and _extensions(extensions)
        ):
            raise ValueError("invalid v1 value")
        return _canonical(
            document["name"], document["endpoint"], retries, region, [], extensions
        )
    if version == 2:
        if not _exact(
            document,
            ("schema_version", "identity", "connection", "features"),
            ("extensions",),
        ):
            raise ValueError("invalid v2 shape")
        identity = document["identity"]
        connection = document["connection"]
        features = document["features"]
        extensions = document.get("extensions", {})
        if (
            not _exact(identity, ("name",))
            or not _exact(connection, ("endpoint", "retry_limit"), ("region",))
            or not isinstance(features, dict)
        ):
            raise ValueError("invalid v2 nested shape")
        region = connection.get("region", defaults["region"])
        if not (
            _name(identity["name"])
            and _endpoint(connection["endpoint"])
            and _retry(connection["retry_limit"])
            and _region(region)
            and _extensions(extensions)
        ):
            raise ValueError("invalid v2 value")
        if not all(
            _name(key) and isinstance(enabled, bool)
            for key, enabled in features.items()
        ):
            raise ValueError("invalid features")
        return _canonical(
            identity["name"],
            connection["endpoint"],
            connection["retry_limit"],
            region,
            [key for key, enabled in features.items() if enabled],
            extensions,
        )
    if version == 3:
        if not _exact(
            document,
            (
                "schema_version",
                "identity",
                "connection",
                "enabled_features",
                "extensions",
            ),
        ):
            raise ValueError("invalid v3 shape")
        identity = document["identity"]
        connection = document["connection"]
        features = document["enabled_features"]
        if not _exact(identity, ("name",)) or not _exact(
            connection, ("endpoint", "retry_limit", "region")
        ):
            raise ValueError("invalid v3 nested shape")
        if (
            not isinstance(features, list)
            or not all(_name(item) for item in features)
            or len(features) != len(set(features))
        ):
            raise ValueError("invalid feature list")
        if not (
            _name(identity["name"])
            and _endpoint(connection["endpoint"])
            and _retry(connection["retry_limit"])
            and _region(connection["region"])
            and _extensions(document["extensions"])
        ):
            raise ValueError("invalid v3 value")
        return _canonical(
            identity["name"],
            connection["endpoint"],
            connection["retry_limit"],
            connection["region"],
            features,
            document["extensions"],
        )
    raise Exception("unsupported version")


def migrate_batch(records, defaults):
    if (
        not _exact(defaults, ("retry_limit", "region"))
        or not _retry(defaults["retry_limit"])
        or not _name(defaults["region"])
    ):
        raise ValueError("invalid defaults")
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    seen = set()
    for record in records:
        if (
            not _exact(record, ("source_id", "document"))
            or not _name(record["source_id"])
            or not isinstance(record["document"], dict)
            or record["source_id"] in seen
        ):
            raise ValueError("invalid batch record")
        seen.add(record["source_id"])
    migrated = []
    rejected = []
    for record in records:
        source_id = record["source_id"]
        try:
            document = _migrate(record["document"], defaults)
        except ValueError:
            rejected.append({"source_id": source_id, "reason": "invalid_document"})
        except Exception:
            rejected.append({"source_id": source_id, "reason": "unsupported_version"})
        else:
            migrated.append({"source_id": source_id, "document": document})
    return {"migrated": migrated, "rejected": rejected}
