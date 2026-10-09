def assess_compatibility(baseline, candidate, consumers):
    """Broken symmetric diff; repair from docs/compatibility_contract.md."""
    issues = []
    for consumer in consumers:
        for operation_id in consumer.get("operations", []):
            if operation_id not in candidate:
                issues.append({"consumer_id": consumer["consumer_id"], "operation_id": operation_id, "direction": "operation", "field": "*", "code": "operation_removed"})
                continue
            before = baseline[operation_id]["response"].get("properties", {})
            after = candidate[operation_id]["response"].get("properties", {})
            for field in sorted(set(before) ^ set(after)):
                issues.append({"consumer_id": consumer["consumer_id"], "operation_id": operation_id, "direction": "response", "field": field, "code": "schema_changed"})
    return {"compatible": not issues, "issues": issues}
