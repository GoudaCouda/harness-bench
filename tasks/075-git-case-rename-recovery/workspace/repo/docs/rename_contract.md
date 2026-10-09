# Case rename contract

`entries` is the captured stage-0 index: records have exactly `path`, `oid`,
and `stage`. Paths are safe relative slash paths, unique under the active
filesystem comparison, OIDs are 40 lowercase hexadecimal characters, and
stage must be integer zero. `requests` contains exact `from` and `to` paths.

Every source must exist exactly once. Sources and destinations must be unique
under exact comparison, and under casefold comparison when `ignore_case` is
true. A destination occupied by a non-source blocks the entire batch. Never
force an overwrite or return a partial plan.

Return executable-order `git_mv` operations and final path-sorted entries.
Case-only renames on an ignore-case checkout and rename cycles require a
collision-free temporary path in the source directory named
`.BASENAME.hb-rename-tmp-N`, choosing the first available positive N. Preserve
each source OID and stage exactly. This planner reports commands; it does not
run Git or touch the filesystem.
