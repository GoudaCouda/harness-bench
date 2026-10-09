def compare_api_schemas(old_schemas, new_schemas, policy):
    # Broken: direction and schema semantics are ignored.
    return {
        "findings": [],
        "summary": {
            "schema_count": len(set(item["schema_id"] for item in old_schemas + new_schemas)),
            "finding_count": 0,
            "breaking": 0,
            "compatible": 0,
            "release_status": "compatible",
        },
    }
