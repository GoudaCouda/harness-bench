def plan_migration_recovery(migration, db_state, observation):
    """Broken implementation: resumes blindly after every failure."""
    actions = [f"statement:{index}" for index, _ in enumerate(migration["statements"])]
    if observation["phase"] != "clean":
        actions.insert(0, "wait_backoff")
    actions.append("commit")
    return {"decision": "retry", "retry_scope": "remaining_statements", "actions": actions, "verification": {"migration_id": migration["id"], "checksum": migration["checksum"], "user_version": migration["to_version"]}}
