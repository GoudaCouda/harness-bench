def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_" for char in value)
    )


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _versions(value):
    return (
        isinstance(value, list)
        and value == sorted(value)
        and len(set(value)) == len(value)
        and all(_token(item) for item in value)
    )


def plan_online_migration(snapshots, policy):
    policy_keys = (
        "contract_allowed",
        "max_lock_waiters",
        "max_replica_lag_ms",
        "required_stable_windows",
    )
    if not _exact(policy, policy_keys) or not isinstance(policy["contract_allowed"], bool):
        raise ValueError("invalid policy")
    for key in ("max_lock_waiters", "max_replica_lag_ms", "required_stable_windows"):
        if not _integer(policy[key]):
            raise ValueError("invalid policy limit")
    if policy["required_stable_windows"] == 0 or not isinstance(snapshots, list) or not snapshots:
        raise ValueError("invalid policy or snapshots")

    keys = (
        "snapshot_id", "deployed_versions", "dual_write_versions",
        "read_target_versions", "old_write_versions", "target_exists",
        "target_nullable", "backfill_cursor", "total_rows", "target_rows",
        "mismatch_rows", "constraint_state", "old_column_exists",
        "old_read_qps", "stable_windows", "replica_lag_ms", "lock_waiters",
    )
    seen = set()
    previous = None
    decisions = []
    counts = {"ready": 0, "blocked": 0, "complete": 0}
    rank = {"absent": 0, "not_valid": 1, "valid": 2}
    database_actions = {
        "expand_target_nullable", "repair_mismatches", "backfill_batch",
        "add_constraint_not_valid", "validate_constraint", "set_not_null",
        "drop_old_column",
    }
    for snapshot in snapshots:
        if not _exact(snapshot, keys) or not _token(snapshot["snapshot_id"]) or snapshot["snapshot_id"] in seen:
            raise ValueError("invalid snapshot")
        seen.add(snapshot["snapshot_id"])
        version_fields = ("deployed_versions", "dual_write_versions", "read_target_versions", "old_write_versions")
        if not all(_versions(snapshot[field]) for field in version_fields) or not snapshot["deployed_versions"]:
            raise ValueError("invalid versions")
        deployed = set(snapshot["deployed_versions"])
        if any(not set(snapshot[field]).issubset(deployed) for field in version_fields[1:]):
            raise ValueError("version outside deployment")
        if not all(isinstance(snapshot[field], bool) for field in ("target_exists", "target_nullable", "old_column_exists")):
            raise ValueError("invalid flags")
        number_fields = ("backfill_cursor", "total_rows", "target_rows", "mismatch_rows", "old_read_qps", "stable_windows", "replica_lag_ms", "lock_waiters")
        if not all(_integer(snapshot[field]) for field in number_fields) or snapshot["total_rows"] == 0:
            raise ValueError("invalid telemetry")
        if snapshot["backfill_cursor"] > snapshot["total_rows"] or snapshot["target_rows"] > snapshot["total_rows"] or snapshot["mismatch_rows"] > snapshot["target_rows"]:
            raise ValueError("impossible counts")
        if snapshot["constraint_state"] not in rank:
            raise ValueError("invalid constraint")
        if not snapshot["target_exists"]:
            if any((snapshot["dual_write_versions"], snapshot["read_target_versions"], snapshot["backfill_cursor"], snapshot["target_rows"], snapshot["mismatch_rows"], snapshot["constraint_state"] != "absent")):
                raise ValueError("target state without target")
        if snapshot["constraint_state"] == "valid" and (snapshot["backfill_cursor"] != snapshot["total_rows"] or snapshot["target_rows"] != snapshot["total_rows"] or snapshot["mismatch_rows"]):
            raise ValueError("valid constraint without proof")
        if not snapshot["old_column_exists"] and (snapshot["constraint_state"] != "valid" or snapshot["target_nullable"] or set(snapshot["read_target_versions"]) != deployed or snapshot["old_write_versions"] or snapshot["old_read_qps"] or snapshot["stable_windows"] < policy["required_stable_windows"]):
            raise ValueError("unsafe contracted state")
        if previous is not None:
            if any(snapshot[field] < previous[field] for field in ("total_rows", "backfill_cursor", "target_rows")):
                raise ValueError("regressing counts")
            if previous["target_exists"] and not snapshot["target_exists"]:
                raise ValueError("target removed")
            if not previous["target_nullable"] and snapshot["target_nullable"]:
                raise ValueError("nullability regressed")
            if rank[snapshot["constraint_state"]] < rank[previous["constraint_state"]]:
                raise ValueError("constraint regressed")
            if not previous["old_column_exists"] and snapshot["old_column_exists"]:
                raise ValueError("old column returned")
        previous = snapshot

        if not snapshot["target_exists"]:
            action = "expand_target_nullable"
        elif set(snapshot["dual_write_versions"]) != deployed:
            action = "deploy_dual_write"
        elif snapshot["mismatch_rows"]:
            action = "repair_mismatches"
        elif snapshot["backfill_cursor"] != snapshot["total_rows"] or snapshot["target_rows"] != snapshot["total_rows"]:
            action = "backfill_batch"
        elif snapshot["constraint_state"] == "absent":
            action = "add_constraint_not_valid"
        elif snapshot["constraint_state"] == "not_valid":
            action = "validate_constraint"
        elif set(snapshot["read_target_versions"]) != deployed:
            action = "deploy_read_cutover"
        elif snapshot["old_write_versions"]:
            action = "disable_old_writes"
        elif snapshot["target_nullable"]:
            action = "set_not_null"
        elif snapshot["old_column_exists"]:
            action = "drop_old_column"
        else:
            action = "migration_complete"

        overloaded = snapshot["replica_lag_ms"] > policy["max_replica_lag_ms"] or snapshot["lock_waiters"] > policy["max_lock_waiters"]
        if action == "migration_complete":
            status, reason = "complete", "complete"
        elif action == "drop_old_column" and not policy["contract_allowed"]:
            status, action, reason = "blocked", "wait", "contract_disabled"
        elif action == "drop_old_column" and (snapshot["old_read_qps"] > 0 or snapshot["stable_windows"] < policy["required_stable_windows"]):
            status, action, reason = "blocked", "wait", "observation_incomplete"
        elif action in database_actions and overloaded:
            status, action, reason = "blocked", "wait", "database_load"
        else:
            status, reason = "ready", "next_safe_phase"
        counts[status] += 1
        decisions.append({"snapshot_id": snapshot["snapshot_id"], "status": status, "action": action, "reason": reason})
    return {"decisions": decisions, "summary": {"snapshot_count": len(snapshots), "ready": counts["ready"], "blocked": counts["blocked"], "complete": counts["complete"], "final_action": decisions[-1]["action"]}}
