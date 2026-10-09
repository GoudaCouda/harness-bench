def plan_online_migration(snapshots, policy):
    """Choose the next expand-contract action for each database snapshot.

    Load gates and the ordinary backfill path work.  The implementation still
    gets mixed-version rollout, stable-window accumulation, constraint
    validation, and final contraction ordering wrong.
    """
    decisions = []
    for snapshot in snapshots:
        if snapshot["replica_lag_ms"] > policy["max_replica_lag_ms"] or snapshot["lock_waiters"] > policy["max_lock_waiters"]:
            status, action, reason = "blocked", "wait", "database_load"
        elif not snapshot["target_exists"]:
            status, action, reason = "ready", "add_nullable_target", "expand"
        elif snapshot["target_rows"] < snapshot["total_rows"]:
            status, action, reason = "ready", "backfill_batch", "backfill_incomplete"
        elif snapshot["mismatch_rows"]:
            status, action, reason = "blocked", "repair_mismatches", "data_mismatch"
        elif snapshot["constraint_state"] == "absent":
            status, action, reason = "ready", "add_not_valid_constraint", "constraint_missing"
        elif snapshot["constraint_state"] == "not_valid":
            status, action, reason = "ready", "validate_constraint", "constraint_pending"
        elif snapshot["old_read_qps"] > 0 or snapshot["stable_windows"] < policy["required_stable_windows"]:
            status, action, reason = "blocked", "observe", "old_reads_present"
        elif policy["contract_allowed"]:
            status, action, reason = "ready", "drop_old_column", "contract_ready"
        else:
            status, action, reason = "blocked", "wait", "contract_disabled"
        decisions.append({"snapshot_id": snapshot["snapshot_id"], "status": status, "action": action, "reason": reason})
    return {"decisions": decisions, "summary": {"snapshot_count": len(snapshots), "ready": sum(row["status"] == "ready" for row in decisions), "blocked": sum(row["status"] == "blocked" for row in decisions)}}
