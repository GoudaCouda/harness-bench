def redact_event(event, policy):
    """Broken sanitizer: only top-level substring matching is implemented."""
    replacement = policy.get("replacement", "[REDACTED]")
    sensitive = [name.lower() for name in policy.get("sensitive_keys", [])]
    cleaned = dict(event)
    findings = []
    for key, value in event.items():
        if any(name in key.lower() for name in sensitive):
            cleaned[key] = replacement
            findings.append({"path": "/" + key, "kind": "sensitive_key"})
        elif isinstance(value, str) and "Bearer " in value:
            cleaned[key] = value.replace("Bearer ", "Bearer " + replacement)
            findings.append({"path": "/" + key, "kind": "bearer_token"})
    return {"event": cleaned, "redactions": findings}
