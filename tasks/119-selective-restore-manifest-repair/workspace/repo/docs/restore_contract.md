# Selective restore planning contract

Implement `plan_restore(snapshots, destination, request)` as a pure function.
Validate the entire input before planning; malformed data raises `ValueError`.

Snapshots are unique exact `{snapshot_id,parent_id,complete,entries}` objects.
Parent is null or a non-empty string; unknown parents are allowed as incomplete
local evidence. Complete is boolean. Entries are unique per snapshot and have
exactly `path`, `operation`, `kind`, `checksum`, and `size`. Paths are canonical
absolute POSIX paths: no root path, empty segment, `.`, `..`, backslash, or
trailing slash. Operation is `upsert` or `delete`. Delete rows have null kind,
checksum, and size. Upserts have kind `file`, `directory`, or `symlink`;
directories have null checksum and size zero, while files/symlinks have a
64-lowercase-hex checksum and non-negative integer size.

The known-parent graph must be acyclic. `destination` is a unique list of exact
`{path,kind,checksum}` canonical absolute target paths; kind is file or directory,
with a valid checksum only for files and null for directories.

Request has exactly `snapshot_id`, `target_root`, `include`, `exclude`,
`overwrite`, `dry_run`, and `delete_extraneous`. Target root is canonical.
Include/exclude are unique canonical source prefixes. Prefix matching is by path
segment (`/app` matches `/app/x`, not `/apple`). Include empty means all; an
exclude always wins. Overwrite is `never` or `if_changed`. Safety requires
`dry_run=true` and `delete_extraneous=false`; otherwise raise `ValueError`.

Follow the requested snapshot only, never newest. Its ancestry must reach a
complete parent-null full snapshot and every member must be complete. A missing
parent or incomplete member returns blocked status with no actions. Replay
oldest to selected: an upsert replaces its path; a delete removes that path and
all descendants.

Only final file/directory entries in scope are planned. Symlinks are conflicts.
Map source `/x` under target root `/restore` as `/restore/x`. Missing targets are
`restore`. Same-kind directories and same-checksum files are `unchanged`.
Different kinds are `conflict/type_collision`. A changed file is
`conflict/overwrite_disabled` under `never`, otherwise `restore/content_changed`.
Rows have exactly `source_path,target_path,kind,checksum,action,reason` and sort
by source path. Never plan destination deletion.

Return exactly `{"plan": {"status","reason","snapshot_id","chain","actions"},
"summary": {"restore","unchanged","conflict","selected","dry_run"}}`.
Successful reason is `ready`; blocked reasons are `unknown_snapshot`,
`missing_parent`, or `incomplete_chain`. Chain is oldest-to-selected when known.
