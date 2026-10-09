# Migration contract

Filenames are `NNN_slug.sql` where `NNN` is a three-digit version.

1. Collect every `*.sql` file in `migrations/`.
2. A version with two or more files is a duplicate. List those filenames
   (sorted) in `duplicate_files`. Do not apply any file from a duplicate
   version.
3. `missing_versions` lists every integer in `1..max(version)` that has no
   file at all.
4. Apply versions in order starting at `001` as a contiguous prefix: a
   version applies only when it has exactly one file and every smaller
   version already applied. Stop at the first missing or duplicate version.
5. `applied` lists the filenames that ran, in version order.
6. `skipped_files` lists every other `*.sql` filename, sorted.

Start from an empty database. Do not invent table names or `item_id` values.
