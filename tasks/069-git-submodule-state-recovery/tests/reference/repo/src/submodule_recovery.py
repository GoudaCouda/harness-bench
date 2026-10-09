FIELDS = {"path", "depth", "recorded_sha", "checked_out_sha", "remote_sha", "initialized", "commit_present", "dirty", "untracked", "conflict"}


def _sha(value, nullable=False):
    if value is None and nullable: return
    if not isinstance(value, str) or len(value) != 40 or value != value.casefold() or any(c not in "0123456789abcdef" for c in value): raise ValueError("bad sha")


def plan_submodule_recovery(submodules, recursive):
    if not isinstance(submodules, list) or type(recursive) is not bool: raise ValueError("bad input")
    seen, output = set(), []
    for item in submodules:
        if not isinstance(item, dict) or set(item) != FIELDS: raise ValueError("bad shape")
        path, depth = item["path"], item["depth"]
        if not isinstance(path, str) or path.startswith("/") or "\\" in path or any(p in ("", ".", "..") for p in path.split("/")) or path in seen: raise ValueError("bad path")
        seen.add(path)
        if type(depth) is not int or depth < 0 or any(type(item[n]) is not bool for n in ("initialized", "commit_present", "dirty", "untracked", "conflict")): raise ValueError("bad type")
        _sha(item["recorded_sha"]); _sha(item["checked_out_sha"], True); _sha(item["remote_sha"], True)
        if item["initialized"] and item["checked_out_sha"] is None: raise ValueError("missing checkout")
        if not item["initialized"] and (item["checked_out_sha"] is not None or item["dirty"] or item["untracked"] or item["conflict"]): raise ValueError("impossible")
        if depth and not recursive: continue
        if item["conflict"]: status, action, target, reason = "blocked", "resolve_conflict", None, "merge_conflict"
        elif item["dirty"] or item["untracked"]: status, action, target, reason = "blocked", "preserve_local_changes", None, "dirty_or_untracked"
        elif not item["commit_present"]: status, action, target, reason = "blocked", "obtain_recorded_object", None, "recorded_object_missing"
        elif not item["initialized"]: status, action, target, reason = "planned", "init_checkout_recorded", item["recorded_sha"], "not_initialized"
        elif item["checked_out_sha"] != item["recorded_sha"]: status, action, target, reason = "planned", "checkout_recorded", item["recorded_sha"], "checked_out_mismatch"
        else: status, action, target, reason = "verified", "verify", None, "recorded_commit_checked_out"
        output.append({"path": path, "status": status, "action": action, "target_sha": target, "reason": reason, "_depth": depth})
    output.sort(key=lambda row: (row["_depth"], row["path"]))
    return [{k: v for k, v in row.items() if k != "_depth"} for row in output]
