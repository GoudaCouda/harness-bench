# Migration recovery contract

`migration` has exactly `id`, `from_version`, `to_version`, `checksum`, and
non-empty `statements`. IDs use lowercase letters, digits, `_`, and `-`;
versions are non-negative integers with `to_version > from_version`; checksum
is 64 lowercase hexadecimal characters. Statements are non-empty strings and
must not contain transaction-control commands.

`db_state` has exactly integer `user_version` and an applied `ledger`. Ledger
records have the migration identity/version/checksum fields, unique IDs, valid
forward versions, and a highest `to_version` equal to `user_version` (or both
are zero for an empty ledger). A matching ledger record at the target version
is already applied; any identity/checksum/version divergence blocks recovery.

`observation` has exactly `phase` and Boolean `transaction_active`. Supported
phases are `clean`, `busy_begin`, `busy_statement`, `busy_commit`,
`commit_unknown`, and `interrupted`. Only statement/commit BUSY observations
have an active transaction. Statement BUSY rolls back and retries the whole
transaction; commit BUSY retains the transaction and retries only COMMIT.
Unknown commit probes ledger plus `user_version` before choosing any retry.
Interrupted connections are reopened and retry the full transaction. Use
`BEGIN IMMEDIATE`; insert the ledger row and set `user_version` inside the same
transaction as all statements. Return a decision, retry scope, ordered symbolic
actions, and exact verification identity. The planner never opens SQLite.
