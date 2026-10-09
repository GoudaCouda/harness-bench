# Archive preflight security contract

`plan_extraction(entries, policy)` is a fail-closed planning step. It performs
no filesystem operations and must not mutate its arguments.

1. `entries` is a list of objects with exactly `path`, `type`, and `size`.
   `policy` supplies boolean `case_sensitive`, positive integer `max_files`,
   `max_file_bytes`, `max_total_bytes`, and `allowed_types` equal to
   `['file', 'dir']` in either order. Booleans are not integers here.
2. Paths use portable `/` separators. Reject empty paths, NUL/control
   characters, backslashes, absolute/UNC paths, drive prefixes, empty
   components, and `.` or `..` components. Do not silently rewrite them.
3. Reject symbolic links, hard links, devices, FIFOs, and every type outside
   the policy. Directories must have size zero. File sizes must be non-negative
   integers no larger than `max_file_bytes`.
4. Reject duplicate normalized paths. When `case_sensitive` is false, also
   reject case-folded collisions. Reject a file whose path is the parent of any
   other entry, regardless of archive order.
5. Count only regular files for `max_files`; sum only regular-file sizes for
   `max_total_bytes`. Exceeding either limit rejects the complete manifest.
6. On success return new objects with keys `path`, `type`, and `size`, preserving
   archive order and values. Validation must finish before a caller writes any
   member.
