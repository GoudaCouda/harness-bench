# Submodule recovery contract

`plan_submodule_recovery(submodules, recursive)` is an offline planner. It does
not execute Git. Each input has exactly `path`, `depth`, `recorded_sha`,
`checked_out_sha`, `remote_sha`, `initialized`, `commit_present`, `dirty`,
`untracked`, and `conflict`.

- Paths are unique safe POSIX relative paths. `depth` is a non-negative integer.
  When `recursive` is false, only depth 0 records are returned.
- SHA values are lowercase 40-hex strings; checked-out and remote SHA may be
  null only when uninitialized. The recorded gitlink is authoritative;
  `remote_sha` is evidence only and is never a recovery target.
- Conflict blocks with `resolve_conflict`. Dirty or untracked state next blocks
  with `preserve_local_changes`; neither may propose a target SHA.
- If the recorded object is absent, block with `obtain_recorded_object`, whether
  initialized or not. The planner cannot authorize a fetch.
- A clean uninitialized record with the object present uses
  `init_checkout_recorded`. A clean initialized mismatch uses
  `checkout_recorded`. A clean exact match uses `verify`.
- Output sorts by `(depth, path)` and contains exactly `path`, `status`,
  `action`, `target_sha`, and `reason`. Action statuses are `blocked`, `planned`,
  or `verified`. Planned actions target `recorded_sha`; other targets are null.

Malformed or internally inconsistent states raise `ValueError`. In particular,
an initialized record needs a checked-out SHA and an uninitialized record must
not claim dirty, untracked, conflict, or a checked-out SHA.
