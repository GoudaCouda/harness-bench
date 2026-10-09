# Recover a journal projection after a stale-cursor crash

Work only in `/workspace/repo`. A local account projection crashed while its SQLite idempotency ledger and its journal cursor were being committed. The immutable JSONL segments, seed evidence, current database, and a repository-local recovery utility are available offline.

Inspect the journal, the database tables, and `tools/journal_recovery.py --help`. Establish which durable record is authoritative, recover every unique event exactly once, advance the checkpoint to the physical end of the journal, and retain a machine-readable receipt at `out/recovery_receipt.json`. Prove that a second recovery attempt is a no-op. Write `RECOVERY_HANDOFF.md` explaining the crash boundary, duplicate-delivery handling, before/after state, commands, and verification evidence.

Do not edit the journal segments, seed SQL, policy, or recovery utility. Do not contact external systems or claim a production deployment.
