# Account projection recovery handoff

The incident boundary was a committed projection and idempotency ledger through e104 with `consumer_cursor` still at e102. I treated `applied_events` as the durable authority and the cursor only as a resumable scan hint. This matters because e103 is also delivered again at the start of segment 00042; replay must classify it as a duplicate rather than apply its 700-cent delta twice.

Before recovery, the durable ledger ended at e104 while the stale cursor ended at e102. I ran the repository inspection command, then recovered with `python3 tools/journal_recovery.py --ack-stale-cursor`. After recovery, the transaction had added only e105 through e108 and advanced the physical checkpoint to segment 00042 line 6, event e108. Final balances are acct-a 1050, acct-b 475, and acct-c 500 cents. SQLite `PRAGMA integrity_check` returned `ok`.

A copied-state second `python3 tools/journal_recovery.py` recovery produced `newly_applied_event_ids: []` and left balances, versions, ledger rows, and cursor unchanged, proving the exact-once/no-op property. All work was offline against the supplied local journal and database; no production service or external system was contacted.
