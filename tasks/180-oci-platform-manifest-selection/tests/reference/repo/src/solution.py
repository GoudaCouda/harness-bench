def plan_oci_platform_manifest_selection(records, policy):
    if not isinstance(records, list) or not isinstance(policy, dict) or not isinstance(policy.get("target"), dict): raise ValueError("records and policy")
    target = policy["target"]; required = policy.get("required_annotations", {}); preferred = policy.get("preferred_features", [])
    if not isinstance(target.get("os"), str) or not isinstance(target.get("architecture"), str) or not isinstance(required, dict) or not isinstance(preferred, list): raise ValueError("policy")
    seen, candidates, rejected = set(), [], []
    for row in records:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("digest"), str) or not isinstance(row.get("platform"), dict): raise ValueError("record")
        if row["id"] in seen: raise ValueError("duplicate id")
        seen.add(row["id"]); p = row["platform"]; annotations = row.get("annotations", {})
        if not isinstance(p.get("os"), str) or not isinstance(p.get("architecture"), str) or not isinstance(p.get("os.features", []), list) or not isinstance(annotations, dict): raise ValueError("descriptor")
        reason = None
        if p["os"] != target["os"] or p["architecture"] != target["architecture"]: reason = "os_arch_mismatch"
        elif p.get("variant") != target.get("variant"): reason = "variant_mismatch"
        elif not set(target.get("required_features", [])).issubset(set(p.get("os.features", []))): reason = "missing_feature"
        elif any(annotations.get(k) != v for k, v in required.items()): reason = "annotation_mismatch"
        if reason: rejected.append({"id": row["id"], "reason": reason})
        else: candidates.append((sum(feature in p.get("os.features", []) for feature in preferred), row["digest"], row["id"]))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2])); rejected.sort(key=lambda row: row["id"])
    if not candidates: status, selected, reason = "no_match", None, "no_compatible_descriptor"
    elif len(candidates) > 1 and candidates[0][0] == candidates[1][0]: status, selected, reason = "ambiguous", None, "equal_preference_candidates"
    else: status, selected, reason = "selected", candidates[0][1], "most_preferred_compatible"
    return {"status": status, "selected_digest": selected, "reason": reason, "compatible": [item[1] for item in candidates], "rejected": rejected}
