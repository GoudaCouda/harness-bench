# Apply the mill catalog migrations

The mill catalog directory has versioned SQL files that were dropped in by
two operators. Apply them to a new SQLite database. Read
`docs/migration_contract.md` and every file in `migrations/`.

Create `app.db` with only the contiguous prefix the contract allows. Write
`migration_report.json` using the filenames and version numbers already
present in `migrations/`. Create `APPLY_NOTES.md` covering gaps, duplicate
versions, what was applied, one verification step, and one remaining risk.

Do not modify the SQL files, contact a hosted database, or claim the mill
catalog was published.
