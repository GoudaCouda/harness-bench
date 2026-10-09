def migrate_batch(records, defaults):
    """Broken legacy implementation: only handles a permissive v1 subset."""
    migrated = []
    rejected = []
    for record in records:
        document = record["document"]
        if document.get("schema_version") != 1:
            rejected.append({"source_id": record["source_id"], "reason": "unsupported_version"})
            continue
        document["schema_version"] = 3
        document["identity"] = {"name": document.pop("name")}
        document["connection"] = {
            "endpoint": document.pop("endpoint"),
            "retry_limit": document.pop("retries", defaults["retry_limit"]) or defaults["retry_limit"],
            "region": document.pop("region", defaults["region"]) or defaults["region"],
        }
        document["enabled_features"] = []
        document.setdefault("extensions", {})
        migrated.append({"source_id": record["source_id"], "document": document})
    return {"migrated": migrated, "rejected": rejected}
