# Repair notes

The planner validates the migration ledger and `user_version` before any retry. `BEGIN IMMEDIATE` moves writer contention to transaction start. `SQLITE_BUSY` during a statement requires rollback and a whole-transaction retry; BUSY from COMMIT leaves the transaction active, so only COMMIT is retried after backoff. An unknown commit result is never replayed blindly: reopen and probe the ledger/checksum plus `user_version` first. Ledger insertion, schema statements, and version advancement remain one atomic transaction.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all tests pass. Residual risk belongs to the executor: bounded backoff, connection ownership, WAL/journal health, foreign-key checks, backup policy, and post-commit schema verification still require live controls. No database was opened, no SQL or migration ran, no journal or WAL was deleted, and no deployment was performed.
