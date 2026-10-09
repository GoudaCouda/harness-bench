# Apply notes

## Decision

            Version 001 is the only contiguous prefix. There is a gap at version 002,
            so later files are not applied. Version 003 has two files, recorded as
            duplicates, and version 004 is skipped with them. The catalog therefore
            has items(item_id, name) and no seeded row.

## Verification

sqlite3 app.db "PRAGMA table_info(items);" showed item_id and name only, and
a count query returned 0 rows.

## Remaining risk

Operators could still add a 002 file later and expect 003 to apply without a
new review. No hosted database was contacted and the mill catalog was not
published.
