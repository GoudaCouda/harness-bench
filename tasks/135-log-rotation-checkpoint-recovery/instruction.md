# Recover a file tailer across log rotation

Work only in `/workspace/repo`. A local tailer crashed after its processed-record ledger advanced beyond its byte checkpoint, then the active log rotated. Inspect both log files, actual file identities, state, policy, and `tools/tailer_recovery.py --help`.

Recover only records not already in the durable ledger, advance the checkpoint to the current log EOF, and leave `out/recovered.jsonl` plus updated state. Prove a second recovery is a no-op. Write `TAILER_HANDOFF.md` with the crash boundary, inode/offset reasoning, duplicate suppression, commands, and evidence.

Do not edit logs, policy, or the utility. Do not contact external systems.
