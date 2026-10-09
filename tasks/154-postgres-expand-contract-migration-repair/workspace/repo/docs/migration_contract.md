# Online migration planning contract

Implement `plan_online_migration(snapshots, policy)` without mutating inputs.
Malformed or regressing snapshots raise `ValueError` rather than producing a
partial plan.

Policy has exact keys `contract_allowed`, `max_lock_waiters`,
`max_replica_lag_ms`, and `required_stable_windows`; booleans and nonnegative
integer limits are strict, and required windows is positive. Snapshots are an
ordered nonempty list with exact keys shown in `snapshots.json`. Snapshot and
version IDs are lowercase ASCII tokens. All version lists are sorted unique;
dual-write, target-read, and old-write versions are subsets of deployed.

Counts and telemetry are nonnegative integers. Backfill cursor and target rows
do not exceed total rows; mismatches do not exceed target rows. Across snapshots,
total rows, cursor, and target rows never decrease. Target existence,
non-nullability, constraint rank (`absent`, `not_valid`, `valid`), and old-column
removal never regress. A missing target has no target rollout state. A valid
constraint requires complete backfill and zero mismatches. A removed old column
requires valid/non-null target state, all deployed readers cut over, no old
writers, zero old-read QPS, and enough stable windows.

Choose one next action per snapshot in this precedence: `expand_target_nullable`;
`deploy_dual_write` until every deployed version dual-writes; `repair_mismatches`;
`backfill_batch`; `add_constraint_not_valid`; `validate_constraint`;
`deploy_read_cutover`; `disable_old_writes`; `set_not_null`; and finally
`drop_old_column`. A fully contracted snapshot is `complete`/`migration_complete`.

Database actions are expansion, mismatch repair, backfill, both constraint
actions, set-not-null, and drop-column. If replica lag is above its maximum or
lock waiters exceed their maximum, return `blocked` action `wait` and reason
`database_load` instead. Drop-column is also blocked with `contract_disabled`
when policy forbids it, or `observation_incomplete` until old-read QPS is zero
and stable windows meet policy. Other planned actions are `ready`; their reason
is `next_safe_phase`.

Each decision has exact keys `snapshot_id`, `status`, `action`, and `reason`.
Summary has exact keys `snapshot_count`, `ready`, `blocked`, `complete`, and
`final_action`. No SQL, deployment, filesystem, network, clock, process, random,
or environment access is allowed.
